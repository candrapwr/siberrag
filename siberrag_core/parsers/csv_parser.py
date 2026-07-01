"""Parser untuk CSV (.csv) berbasis pandas.

CSV umum di Indonesia: data kependudukan, transaksi, dataset, master data.
Berbeda dari XLSX yang membuat 1 tabel atomic, CSV dipecah per BATCH baris
(default 50 baris/chunk) agar:
- Data besar (ribuan baris) tetap efisien (tidak satu chunk raksasa)
- Retrieval bisa cari baris spesifik dengan konteks header kolom
- Setiap chunk utuh sebagai tabel markdown (header diulang tiap batch)

Strategi:
1. Baca CSV via pandas (robust: auto-detect delimiter, encoding, quote)
2. Ambil header (nama kolom) sebagai baris pertama
3. Bagi data menjadi batch berukuran ``batch_rows`` (default 50)
4. Setiap batch jadi TABLE element terpisah, dengan header diulang
5. Bila ada multiple "sheet" (tidak mungkin di CSV), tetap 1 tabel
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from siberrag_core.models.elements import Document, DocumentElement, ElementType
from siberrag_core.parsers.base import BaseParser, ParseError

try:
    import pandas as pd  # type: ignore
    _HAS_PANDAS = True
except Exception:  # pragma: no cover
    _HAS_PANDAS = False

try:
    import csv as _csv_stdlib
except Exception:  # pragma: no cover
    _csv_stdlib = None

# jumlah baris per batch (chunk). Bisa di-override via subclass/config bila perlu.
_DEFAULT_BATCH_ROWS = 50
# target token per batch (auto-adjust batch size bila baris lebar).
# Sedikit di bawah target chunk (500) untuk mengakomodasi baris outlier yang
# lebih panjang dari rata-rata (mis. deskripsi HS yang panjang di BTKI).
_TARGET_BATCH_TOKENS = 400
_MAX_BATCH_ROWS = 200  # cap maksimum baris per batch

# Mode format baris CSV:
# - "table"  : markdown table (header diulang). Visual bagus, tapi embedding
#              kurang akurat untuk data tabular besar (header dominan).
# - "narrative" (default): tiap baris jadi kalimat "Kolom: nilai, Kolom: nilai".
#              Lebih baik untuk retrieval embedding karena konten unik menonjol.
_ROW_FORMAT = "narrative"


def is_available() -> bool:
    """True bila pandas terpasang (parser utama). Fallback ke stdlib csv bila tidak."""
    return _HAS_PANDAS or _csv_stdlib is not None


class CsvParser(BaseParser):
    """Parser CSV dengan batch-batching baris."""

    extensions = ("csv", "tsv")
    name = "csv"

    def __init__(self, config: Optional[object] = None,
                 *, batch_rows: int = _DEFAULT_BATCH_ROWS) -> None:
        super().__init__(config)
        self.batch_rows = max(1, batch_rows)

    def parse(self, path: Path, *, filename: Optional[str] = None) -> Document:
        # deteksi delimiter dari ekstensi (TSV = tab)
        delimiter = "\t" if path.suffix.lower() == ".tsv" else None

        if _HAS_PANDAS:
            df = self._read_pandas(path, delimiter)
        elif _csv_stdlib is not None:
            df = self._read_stdlib(path, delimiter)
        else:
            raise ParseError("Tidak ada library CSV (pandas atau stdlib csv) tersedia.")

        if df is None or df.empty:
            # CSV kosong -> dokumen kosong
            root = DocumentElement.document(order=0)
            return self._make_document(root, path=path, filename=filename)

        root = self._build_tree(df, path)
        return self._make_document(root, path=path, filename=filename)

    # ----- readers -----
    def _read_pandas(self, path: Path, delimiter: Optional[str]):
        """Baca CSV via pandas. Coba delimiter umum (koma/titik koma/tab) & encoding."""
        last_exc = None
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        # urutan delimiter yang umum di Indonesia: koma (default), titik koma, tab
        delimiters_to_try = [delimiter] if delimiter else [",", ";", "\t", "|"]
        for delim in delimiters_to_try:
            for enc in encodings:
                try:
                    df = pd.read_csv(str(path), sep=delim, encoding=enc, dtype=str)
                    # validasi: hasil baca harus punya > 1 kolom ATAU memang 1 kolom asli.
                    # Cek dengan membandingkan header split manual vs hasil pandas.
                    if len(df.columns) > 1:
                        return df
                    # bila 1 kolom, cek apakah header asli punya delimiter (berarti salah detect)
                    with open(path, "r", encoding=enc, errors="ignore") as f:
                        first_line = f.readline()
                    if delim in first_line and delim not in (",",):
                        # header mengandung delimiter tapi tidak terpisah -> coba lanjut
                        continue
                    return df  # 1 kolom asli, kembalikan
                except Exception as exc:
                    last_exc = exc
                    continue
        # fallback terakhir dengan python engine + auto-detect
        for enc in encodings:
            try:
                return pd.read_csv(str(path), sep=None, engine="python", encoding=enc, dtype=str)
            except Exception as exc:
                last_exc = exc
        raise ParseError(f"Gagal parse CSV {path.name}: {last_exc}")

    def _read_stdlib(self, path: Path, delimiter: Optional[str]):
        """Fallback: baca CSV via stdlib csv (tanpa pandas)."""
        import csv as csv_mod
        rows: list[list[str]] = []
        encodings = ["utf-8", "latin-1", "cp1252"]
        delim = delimiter or ","
        for enc in encodings:
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    # sniff delimiter bila tidak ditentukan
                    sample = f.read(2048)
                    f.seek(0)
                    if delimiter is None:
                        try:
                            sniffer = csv_mod.Sniffer()
                            dialect = sniffer.sniff(sample, delimiters=",;\t|")
                            delim = dialect.delimiter
                        except Exception:
                            delim = ","
                    reader = csv_mod.reader(f, delimiter=delim)
                    rows = [r for r in reader]
                break
            except UnicodeDecodeError:
                continue
        if not rows:
            return None
        # konversi ke dict mirip DataFrame
        header = rows[0]
        data = [dict(zip(header, row)) for row in rows[1:] if row]
        return _StdlibFrame(header, data)

    def _estimate_batch_size(self, df, header: list[str]) -> int:
        """Estimasi jumlah baris per batch agar ~500 token/batch.

        Strategi: sampel beberapa baris, hitung rata-rata chars/baris (termasuk
        header), lalu bagi target token (~500 ≈ 2000 chars) dengan lebar baris.
        Bila data sangat lebar (21 kolom), batch mengecil otomatis (mis. 5 baris).
        """
        n = len(df)
        if n == 0:
            return 1
        # sampel hingga 50 baris untuk estimasi lebar
        sample_n = min(50, n)
        sample = df.head(sample_n)
        # hitung total chars header + data sample
        total_chars = 0
        # header (dihitung sekali per baris karena diulang tiap batch)
        header_chars = sum(len(str(c)) + 3 for c in header)  # +3 utk "| " dan " |"
        for i in range(sample_n):
            row = sample.iloc[i]
            total_chars += header_chars
            for col in header:
                val = row[col]
                if val is None or (isinstance(val, float) and val != val):
                    val_str = ""
                else:
                    val_str = str(val)
                total_chars += len(val_str) + 3
        avg_chars_per_row = total_chars / sample_n
        # target ~1600 chars/batch (≈400 token) — sedikit di bawah chunk target
        # untuk akomodasi baris outlier yang lebih panjang dari rata-rata.
        estimated = max(1, int(1600 / avg_chars_per_row))
        return min(estimated, self.batch_rows, _MAX_BATCH_ROWS)

    # ----- tree builder -----
    def _build_tree(self, df, path: Path) -> DocumentElement:
        root = DocumentElement.document(order=0)
        order = [0]
        header = list(df.columns)

        # heading = nama file (sebagai konteks dokumen)
        heading_text = path.stem
        root.add(DocumentElement.heading(heading_text, level=1, page=1, order=order[0]))
        order[0] += 1

        # auto-adjust batch size berdasarkan lebar baris rata-rata.
        # Tujuan: setiap batch ~500 token (target chunk ideal).
        batch_size = self._estimate_batch_size(df, header)

        # bagi data ke batch
        total_rows = len(df)
        batch_num = 0
        for start in range(0, total_rows, batch_size):
            batch_num += 1
            end = min(start + batch_size, total_rows)
            batch_label = f"Batch {batch_num}: baris {start + 1}-{end} dari {total_rows}"
            # sub-heading untuk konteks batch
            root.add(DocumentElement.heading(batch_label, level=2, page=1, order=order[0]))
            order[0] += 1

            if _ROW_FORMAT == "narrative":
                # Format naratif: tiap baris jadi kalimat "Kolom: nilai, Kolom: nilai".
                # Lebih baik untuk retrieval embedding karena konten unik tiap baris
                # menonjol (tidak tenggelam di header tabel markdown yang berulang).
                para_lines: list[str] = []
                for i in range(start, end):
                    row = df.iloc[i]
                    parts: list[str] = []
                    for col in header:
                        val = row[col]
                        if val is None or (isinstance(val, float) and val != val):
                            val_str = ""
                        else:
                            val_str = str(val).strip()
                        if val_str:
                            parts.append(f"{col}: {val_str}")
                    if parts:
                        para_lines.append(" | ".join(parts))
                if para_lines:
                    para = DocumentElement(
                        type=ElementType.PARAGRAPH,
                        content="\n".join(para_lines),
                        page_start=1, page_end=1, order=order[0],
                    )
                    order[0] += 1
                    root.add(para)
            else:
                # Format tabel markdown (default lama): header diulang tiap batch.
                table = DocumentElement(type=ElementType.TABLE, page_start=1, page_end=1, order=order[0])
                order[0] += 1
                # baris header (diulang tiap batch agar konteks kolom selalu ada)
                header_row = DocumentElement(type=ElementType.TABLE_ROW)
                for col in header:
                    header_row.children.append(
                        DocumentElement(type=ElementType.TABLE_CELL, content=str(col))
                    )
                table.children.append(header_row)
                # baris data
                for i in range(start, end):
                    row_el = DocumentElement(type=ElementType.TABLE_ROW)
                    row = df.iloc[i]
                    for col in header:
                        val = row[col]
                        if val is None or (isinstance(val, float) and val != val):  # NaN check
                            val_str = ""
                        else:
                            val_str = str(val).strip()
                        row_el.children.append(
                            DocumentElement(type=ElementType.TABLE_CELL, content=val_str)
                        )
                    table.children.append(row_el)
                if len(table.children) > 1:  # ada header + minimal 1 data
                    root.add(table)
        return root


class _StdlibFrame:
    """Mock DataFrame minimal dari stdlib csv agar _build_tree bisa pakai .iloc/.columns."""

    def __init__(self, header: list[str], data: list[dict]) -> None:
        self.columns = header
        self._data = data

    @property
    def empty(self) -> bool:
        return len(self._data) == 0

    def __len__(self) -> int:
        return len(self._data)

    def iloc(self, i: int) -> dict:
        return self._data[i]
