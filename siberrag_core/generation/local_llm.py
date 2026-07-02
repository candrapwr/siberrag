"""LLM lokal via Hugging Face Transformers.

Provider ini memuat model causal/instruct dari Hugging Face langsung, tanpa
OpenAI-compatible API server. Cocok untuk mode ``llm.provider: local``.
"""

from __future__ import annotations

from typing import Optional

from siberrag_core.config import AppConfig, LLMConfig
from siberrag_core.generation.base import BaseLLM
from siberrag_core.utils.logging import logger

try:
    import torch  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    _HAS_TRANSFORMERS = True
except Exception:  # pragma: no cover - opsional
    torch = None  # type: ignore
    _HAS_TRANSFORMERS = False


def is_available() -> bool:
    """True bila transformers + torch terpasang."""
    return _HAS_TRANSFORMERS


class LocalTransformersLLM(BaseLLM):
    """LLM lokal via Hugging Face Transformers."""

    name = "local"

    def __init__(self, config: Optional[LLMConfig | AppConfig] = None) -> None:
        super().__init__(config)
        if not _HAS_TRANSFORMERS:
            raise RuntimeError(
                "transformers/torch tidak terpasang. Install dengan: pip install -e '.[rag]'"
            )
        self._tokenizer = None
        self._model = None

    def _get_tokenizer(self):
        if self._tokenizer is None:
            logger.info(f"Memuat tokenizer LLM lokal: {self.config.model}")
            self._tokenizer = AutoTokenizer.from_pretrained(self.config.model)
            if self._tokenizer.pad_token_id is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token
        return self._tokenizer

    def _get_model(self):
        if self._model is None:
            logger.info(f"Memuat model LLM lokal: {self.config.model}")
            kwargs = {}
            if torch is not None:
                kwargs["torch_dtype"] = "auto"
                if torch.cuda.is_available():
                    kwargs["device_map"] = "auto"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    kwargs["device_map"] = {"": "mps"}
            self._model = AutoModelForCausalLM.from_pretrained(self.config.model, **kwargs)
            if "device_map" not in kwargs and torch is not None:
                self._model.to("cpu")
            self._model.eval()
            logger.info(f"Model LLM lokal siap: {self.config.model}")
        return self._model

    def _build_prompt(self, messages: list[dict[str, str]]) -> str:
        tokenizer = self._get_tokenizer()
        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        parts: list[str] = []
        for message in messages:
            role = message.get("role", "user").strip().upper()
            content = message.get("content", "")
            parts.append(f"{role}:\n{content}")
        parts.append("ASSISTANT:\n")
        return "\n\n".join(parts)

    def generate(self, messages: list[dict[str, str]]) -> str:
        tokenizer = self._get_tokenizer()
        model = self._get_model()
        prompt = self._build_prompt(messages)
        inputs = tokenizer(prompt, return_tensors="pt")
        device = next(model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        do_sample = self.config.temperature > 0
        generate_kwargs = {
            "max_new_tokens": self.config.max_tokens,
            "do_sample": do_sample,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if do_sample:
            generate_kwargs["temperature"] = self.config.temperature

        with torch.no_grad():
            output_ids = model.generate(**inputs, **generate_kwargs)

        new_tokens = output_ids[0][inputs["input_ids"].shape[-1]:]
        return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
