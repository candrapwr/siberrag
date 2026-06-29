"""Chunker - memecah semantic block menjadi chunk token-aware.

Algoritma (GLOBAL packing lintas-block):
1. Seluruh SemanticBlock dipecah menjadi unit-unit utuh (kalimat / list-item /
   baris tabel / heading). Unit tidak pernah dipotong.
2. Seluruh unit dari seluruh block dikumpulkan SATU aliran berurutan (sesuai
   posisi dokumen), masing-masing membawa konteks block-nya (chapter/section/page).
3. Unit digabungkan ke chunk hingga mendekati ``target_tokens``. Heading/list/
   table adalah unit ATOMIC - tidak pernah dipecah, tetapi block kecil berurutan
   DAPAT digabung menjadi satu chunk hingga mencapai target. Inilah yang mencegah
   chunk undersized pada dokumen dengan banyak pasal pendek.
4. Bila sebuah unit atomic tunggal lebih besar dari ``max_tokens`` (jarang),
   unit tetap utuh (kualitas > ukuran).
5. Overlap diterapkan saat chunk harus dipecah: unit terakhir (non-atomic) dibawa
   ke awal chunk berikutnya.
6. Chunk kecil di akhir dokumen digabung ke chunk sebelumnya bila memungkinkan.

Prioritas: KUALITAS > jumlah token. Chunk sedikit over/under target lebih baik
daripada memotong struktur.
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, ChunkingConfig
from siberrag_core.models.blocks import SemanticBlock
from siberrag_core.models.chunk import Chunk, ChunkMetadata
from siberrag_core.models.elements import ElementType
from siberrag_core.utils.logging import logger
from siberrag_core.utils.tokens import TokenCounter, get_counter
from siberrag_core.utils.text import split_sentences, count_words


class Chunker:
    """Token-aware chunker untuk semantic block (global packing)."""

    def __init__(self, config: Optional[ChunkingConfig | AppConfig] = None) -> None:
        self.cfg: ChunkingConfig = (
            config.chunking if isinstance(config, AppConfig) else (config or ChunkingConfig())
        )
        self.counter: TokenCounter = get_counter(self.cfg.encoding)

    def chunk(
        self,
        blocks: list[SemanticBlock],
        *,
        document_id: str,
        filename: str,
        language: str = "",
    ) -> list[Chunk]:
        """Pecah daftar block menjadi chunk via global packing."""
        # 1. ekstrak seluruh unit dari seluruh block (satu aliran berurutan)
        all_units: list[_Unit] = []
        for block in blocks:
            all_units.extend(self._block_to_units(block))
        if not all_units:
            logger.debug("Chunker: tidak ada unit (dokumen kosong).")
            return []

        # 2. pack global menjadi groups-of-units
        groups = self._pack_units(all_units)

        # 3. bangun Chunk dengan metadata dari konteks unit
        from siberrag_core.utils.ids import chunk_id
        total = len(groups)
        chunks: list[Chunk] = []
        for idx, group_units in enumerate(groups):
            body = self._join_units(group_units)
            ctx = self._derive_context(group_units, blocks)
            # prepend konteks chapter/section bila diaktifkan (membantu retrieval)
            context_header = self._context_header(ctx) if self.cfg.prepend_context else ""
            text = f"{context_header}{body}" if context_header else body
            meta = ChunkMetadata(
                id=chunk_id(document_id, idx),
                document_id=document_id,
                filename=filename,
                page_start=ctx["page_start"],
                page_end=ctx["page_end"],
                chapter=ctx["chapter"],
                section=ctx["section"],
                chunk_index=idx,
                total_chunk=total,
                token_count=self.counter(text),
                word_count=count_words(text),
                language=language,
                block_type=ctx["block_type"],
            )
            chunks.append(Chunk(id=meta.id, text=text, metadata=meta))

        logger.debug(f"Chunker: {len(blocks)} block -> {total} chunk "
                     f"(target {self.cfg.target_tokens} tok).")
        return chunks

    # ----- unit extraction -----
    def _block_to_units(self, block: SemanticBlock) -> list[_Unit]:
        """Pecah block menjadi unit utuh, masing-masing membawa konteks block."""
        units: list[_Unit] = []
        ctx = _BlockCtx(
            chapter=block.chapter or "",
            section=block.section or "",
            page_start=block.page_start or 1,
            page_end=block.page_end or block.page_start or 1,
            block_type=block.block_type,
        )
        # heading sebagai unit pemisah + konteks
        if block.title:
            units.append(_Unit(text=block.title, kind="heading", atomic=True,
                               ctx=ctx))
        for el in block.elements:
            units.extend(self._element_to_units(el, ctx))
        return units

    def _element_to_units(self, el, ctx: "_BlockCtx") -> list["_Unit"]:  # noqa: ANN001
        units: list[_Unit] = []
        page = el.page_start or ctx.page_start

        if el.type == ElementType.HEADING:
            if el.content.strip():
                units.append(_Unit(text=el.content.strip(), kind="heading",
                                   atomic=True, ctx=ctx))
            return units

        if el.type in (ElementType.BULLET_LIST, ElementType.NUMBERED_LIST):
            items = [c.content for c in el.children if c and c.content.strip()]
            if items:
                if el.type == ElementType.NUMBERED_LIST:
                    text = "\n".join(f"{i}. {it}" for i, it in enumerate(items, start=1))
                else:
                    text = "\n".join(f"- {it}" for it in items)
                units.append(_Unit(text=text, kind="list", atomic=True, ctx=ctx, page=page))
            return units

        if el.type == ElementType.TABLE:
            rows: list[str] = []
            for row in el.children:
                cells = [c.content.strip() for c in row.children if hasattr(c, "content")]
                if cells:
                    rows.append("| " + " | ".join(cells) + " |")
            if rows:
                units.append(_Unit(text="\n".join(rows), kind="table",
                                   atomic=True, ctx=ctx, page=page))
            return units

        if el.type in (ElementType.CAPTION, ElementType.IMAGE_CAPTION):
            if el.content.strip():
                units.append(_Unit(text=el.content.strip(), kind="caption",
                                   atomic=True, ctx=ctx, page=page))
            return units

        # paragraf: pecah jadi kalimat (unit non-atomic)
        text = el.content.strip()
        if not text:
            return units
        sentences = split_sentences(text)
        if len(sentences) <= 1:
            # paragraf tidak bisa dipecah kalimat. Bila terlalu besar (> max),
            # pecah di batas baris; bila baris tunggal masih > max (mis. teks
            # encoding rusak tanpa tanda baca), pecah paksa per-kata.
            if self.counter(text) > self.cfg.max_tokens:
                units.extend(self._force_split(text, ctx, page))
            else:
                units.append(_Unit(text=text, kind="paragraph", atomic=False,
                                   ctx=ctx, page=page))
        else:
            for s in sentences:
                if s.strip():
                    # kalimat yang masih terlalu besar -> force split per kata
                    if self.counter(s) > self.cfg.max_tokens:
                        units.extend(self._force_split(s, ctx, page))
                    else:
                        units.append(_Unit(text=s.strip(), kind="sentence",
                                           atomic=False, ctx=ctx, page=page))
        return units

    def _force_split(self, text: str, ctx: "_BlockCtx", page: Optional[int]) -> list["_Unit"]:
        """Pecah teks raksasa yang tidak punya pemisah alami.

        Urutan: baris -> kata. Setiap sub-unit dibuat kira-kira seukuran target_tokens
        agar packing mudah menggabungkannya kembali.
        """
        units: list[_Unit] = []
        target = self.cfg.target_tokens
        # pecah per baris dulu
        chunks_text: list[str] = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if self.counter(line) <= self.cfg.max_tokens:
                chunks_text.append(line)
            else:
                # baris masih > max: pecah per kata, gabung hingga ~target
                buf: list[str] = []
                buf_tokens = 0
                for word in line.split():
                    w_tokens = self.counter(word)
                    if buf and buf_tokens + w_tokens > target:
                        chunks_text.append(" ".join(buf))
                        buf = [word]
                        buf_tokens = w_tokens
                    else:
                        buf.append(word)
                        buf_tokens += w_tokens
                if buf:
                    chunks_text.append(" ".join(buf))
        for t in chunks_text:
            units.append(_Unit(text=t, kind="paragraph", atomic=False, ctx=ctx, page=page))
        return units
        return units

    # ----- packing (GLOBAL lintas-block) -----
    def _pack_units(self, units: list[_Unit]) -> list[list[_Unit]]:
        """Kelompokkan seluruh unit menjadi groups, masing-masing <= max_tokens.

        Strategi: heading bersifat "pemisah" - chunk baru dimulai pada heading
        bila chunk saat ini sudah cukup besar (>= min_tokens). Ini menjaga
        struktur: setiap section idealnya dimulai chunk sendiri jika memungkinkan,
        namun section kecil akan digabung dengan section sebelumnya agar tidak
        undersized.
        """
        target = self.cfg.target_tokens
        maximum = self.cfg.max_tokens
        minimum = self.cfg.min_tokens
        overlap = self.cfg.overlap_tokens

        groups: list[list[_Unit]] = []
        current: list[_Unit] = []
        current_tokens = 0

        i = 0
        while i < len(units):
            unit = units[i]
            unit_tokens = self.counter(unit.text)

            # atomic & sangat besar (> target) -> chunk sendiri bila current cukup besar
            if unit.atomic and unit_tokens > maximum:
                if current:
                    groups.append(current)
                    current = []
                    current_tokens = 0
                groups.append([unit])
                i += 1
                continue

            # heading sebagai pemisah:
            # - respect_heading_boundary=True (default): heading SELALU memulai
            #   chunk baru (hard boundary). Mencegah konten lintas-bab tercampur.
            # - False: heading hanya pemisah bila current sudah >= minimum (soft).
            if unit.kind == "heading" and current:
                should_split = (
                    current_tokens >= minimum
                    or self.cfg.respect_heading_boundary
                )
                if should_split:
                    groups.append(current)
                    current = []
                    current_tokens = 0

            # bila menambahkan unit melebihi max, tutup current + overlap
            if current and current_tokens + unit_tokens > maximum:
                groups.append(current)
                carry = self._overlap_carry(current, overlap)
                current = carry
                current_tokens = sum(self.counter(u.text) for u in carry)

            current.append(unit)
            current_tokens += unit_tokens
            i += 1

        if current:
            groups.append(current)

        # merge chunk kecil di akhir / bertetangga bila memungkinkan
        groups = self._merge_small(groups, minimum, maximum)
        return groups or [[]]

    def _overlap_carry(self, current: list[_Unit], overlap_tokens: int) -> list[_Unit]:
        """Bawa unit akhir (non-atomic) hingga mencapai ~overlap_tokens."""
        carry: list[_Unit] = []
        tokens = 0
        for unit in reversed(current):
            if unit.kind == "heading":
                continue  # heading tidak di-overlap
            if unit.atomic:
                break  # jangan pecah atomic untuk overlap
            carry.insert(0, unit)
            tokens += self.counter(unit.text)
            if tokens >= overlap_tokens:
                break
        return carry

    def _merge_small(self, groups: list[list[_Unit]], minimum: int,
                     maximum: int) -> list[list[_Unit]]:
        """Gabungkan group bertetangga bila ada yang di bawah minimum.

        PENTING: bila ``respect_heading_boundary`` aktif, JANGAN gabung group
        yang dipisahkan oleh heading. Setiap group yang dimulai dengan heading
        harus tetap terpisah agar konten lintas-bab/pasal tidak bercampur
        (hard boundary). Merge hanya terjadi antar group yang berisi paragraf
        biasa (tanpa heading di awal).
        """
        if len(groups) <= 1:
            return groups
        respect_boundary = self.cfg.respect_heading_boundary
        merged: list[list[_Unit]] = []
        for group in groups:
            if not merged:
                merged.append(group)
                continue
            prev_tokens = sum(self.counter(u.text) for u in merged[-1])
            cur_tokens = sum(self.counter(u.text) for u in group)
            # cek: apakah group ini dimulai dengan heading? (batas bab/pasal)
            starts_with_heading = bool(group) and group[0].kind == "heading"
            # gabung bila group sebelumnya KECIL DAN hasil gabung <= maximum
            # DAN (bukan hard boundary ATAU group ini bukan dimulai heading)
            can_merge = (
                prev_tokens < minimum
                and prev_tokens + cur_tokens <= maximum
                and not (respect_boundary and starts_with_heading)
            )
            if can_merge:
                merged[-1].extend(group)
            else:
                merged.append(group)
        return merged

    # ----- metadata context -----
    def _derive_context(self, group_units: list[_Unit],
                        blocks: list[SemanticBlock]) -> dict:
        """Ambil chapter/section/page/block_type dari unit dalam chunk.

        Strategi: page_start = min, page_end = max.
        chapter/section = dari unit pertama non-overlap (heading/paragraph utama).
        block_type = dari unit dominan (pertama).
        """
        pages = [u.page or u.ctx.page_start for u in group_units if u.page or u.ctx.page_start]
        page_start = min(pages) if pages else 1
        page_end = max([u.page or u.ctx.page_end for u in group_units
                        if u.page or u.ctx.page_end] or [page_start])

        # cari unit pertama yang bukan overlap (punya heading atau paragraph utama)
        primary = group_units[0] if group_units else None
        chapter = primary.ctx.chapter if primary else ""
        section = primary.ctx.section if primary else ""
        block_type = primary.ctx.block_type if primary else "paragraph"

        return {
            "page_start": page_start,
            "page_end": page_end,
            "chapter": chapter,
            "section": section,
            "block_type": block_type,
        }

    def _context_header(self, ctx: dict) -> str:
        """Bangun baris header konteks: '[Chapter > Section]' bila keduanya
        berbeda, atau '[Chapter]' bila sama. Kosong bila tak ada konteks."""
        chapter = ctx.get("chapter", "").strip()
        section = ctx.get("section", "").strip()
        if chapter and section and chapter != section:
            return f"[{chapter} > {section}]\n"
        if chapter:
            return f"[{chapter}]\n"
        if section:
            return f"[{section}]\n"
        return ""

    # ----- helpers -----
    def _join_units(self, units: list[_Unit]) -> str:
        """Gabung unit menjadi teks chunk. Sisipkan penanda transisi chapter
        bila konteks chapter berubah di tengah chunk (lintas-bab digabung)."""
        parts: list[str] = []
        prev_chapter: Optional[str] = None
        for u in units:
            if not u.text.strip():
                continue
            chapter = u.ctx.chapter
            # bila chapter berubah & bukan unit pertama, sisipkan penanda bab
            if prev_chapter is not None and chapter and chapter != prev_chapter:
                parts.append(f"[{chapter}]")
            parts.append(u.text)
            prev_chapter = chapter
        return "\n".join(parts)


class _BlockCtx:
    """Konteks block yang dibawa tiap unit (untuk metadata chunk)."""

    __slots__ = ("chapter", "section", "page_start", "page_end", "block_type")

    def __init__(self, *, chapter: str, section: str, page_start: int,
                 page_end: int, block_type: str) -> None:
        self.chapter = chapter
        self.section = section
        self.page_start = page_start
        self.page_end = page_end
        self.block_type = block_type


class _Unit:
    """Unit teks utuh + konteks block-nya."""

    __slots__ = ("text", "kind", "atomic", "ctx", "page")

    def __init__(self, text: str, kind: str = "paragraph", atomic: bool = False,
                 ctx: Optional[_BlockCtx] = None,
                 page: Optional[int] = None) -> None:
        self.text = text
        self.kind = kind
        self.atomic = atomic
        self.ctx = ctx or _BlockCtx(chapter="", section="", page_start=1,
                                    page_end=1, block_type="paragraph")
        self.page = page
