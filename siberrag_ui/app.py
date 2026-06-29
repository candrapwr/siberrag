"""Gradio Web UI untuk SiberRAG RAG.

Chat interface sederhana: input pertanyaan -> jawaban + source citations.
Dapat dijalankan standalone atau di-mount di FastAPI.

Usage:
    python -m siberrag_ui.app
    # atau via CLI
    siberrag serve  # menyajikan API; UI terpisah
"""

from __future__ import annotations

import os
from typing import Optional

from siberrag_core.config import load_config

_config_path = os.environ.get("SIBERRAG_CONFIG", "").strip()
CONFIG = load_config(_config_path or None)

_query_pipeline = None


def get_query_pipeline():
    global _query_pipeline
    if _query_pipeline is None:
        from siberrag_core.query_pipeline import QueryPipeline
        _query_pipeline = QueryPipeline(CONFIG)
    return _query_pipeline


def format_sources(sources) -> str:
    """Format source citations menjadi markdown."""
    if not sources:
        return "_Tidak ada sumber relevan._"
    lines = ["### 📚 Sumber Referensi\n"]
    for i, hit in enumerate(sources, 1):
        m = hit.chunk.metadata
        loc_parts = []
        if m.chapter:
            loc_parts.append(m.chapter)
        if m.section and m.section != m.chapter:
            loc_parts.append(m.section)
        if m.page_start:
            loc_parts.append(f"hal. {m.page_start}")
        location = " > ".join(loc_parts) if loc_parts else m.filename or "tidak diketahui"
        lines.append(f"**{i}.** {location} _(skor: {hit.score:.3f})_")
        lines.append(f"> {hit.chunk.text[:200]}...\n")
    return "\n".join(lines)


def ask(question: str, top_k: int, history: list) -> tuple[str, list]:
    """Handler chat: panggil QueryPipeline, kembalikan jawaban + sources.

    Gradio 6.x memakai format 'messages': setiap pesan adalah dict
    {'role': 'user'|'assistant', 'content': '...'}.
    """
    if not question.strip():
        return "", history
    try:
        pipeline = get_query_pipeline()
        answer = pipeline.query(question, top_k=max(1, top_k))
        sources_md = format_sources(answer.sources.hits)
        response = f"{answer.text}\n\n---\n{sources_md}"
    except Exception as exc:
        response = f"❌ Error: {exc}"
    # format messages: tambah pesan user + assistant
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": response})
    return "", history


def build_ui():
    """Bangun Gradio interface."""
    import gradio as gr

    with gr.Blocks(title="SiberRAG") as demo:
        gr.Markdown(
            "# 🚀 SiberRAG\n"
            "Sistem tanya-jawab dokumen berbasis RAG. "
            "Index dokumen via CLI/API, lalu ajukan pertanyaan di sini."
        )

        with gr.Row():
            top_k = gr.Slider(1, 20, value=5, step=1, label="Top-K (jumlah sumber)")

        chatbot = gr.Chatbot(height=500, label="Percakapan")
        with gr.Row():
            question = gr.Textbox(
                placeholder="Ketik pertanyaan tentang dokumen yang sudah di-index...",
                label="Pertanyaan", scale=4,
            )
            submit = gr.Button("Tanya", variant="primary", scale=1)

        gr.Markdown(
            "---\n"
            f"_Embedding: {CONFIG.embedding.provider} ({CONFIG.embedding.model}) · "
            f"LLM: {CONFIG.llm.model}_"
        )

        # events
        submit.click(ask, [question, top_k, chatbot], [question, chatbot])
        question.submit(ask, [question, top_k, chatbot], [question, chatbot])

    return demo


def main(host: str = "127.0.0.1", port: int = 7860):
    """Jalankan Gradio UI server."""
    demo = build_ui()
    demo.launch(server_name=host, server_port=port, theme="Soft")


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="SiberRAG Web UI (Gradio)")
    parser.add_argument("--host", default="127.0.0.1", help="Host bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=7860, help="Port (default: 7860)")
    parser.add_argument("--config", default=None, help="Path file config.yaml custom")
    args = parser.parse_args()

    if args.config:
        os.environ["SIBERRAG_CONFIG"] = args.config
    main(host=args.host, port=args.port)
