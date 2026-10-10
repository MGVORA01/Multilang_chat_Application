"""AI4Bharat IndicTrans2 engine (CPU inference with Hugging Face Transformers).

Heavy imports (torch, transformers) happen lazily so the API and test suite can run without them.
Each checkpoint is loaded once and guarded by its own lock: generate() on a shared model instance
is not documented as thread-safe, so access per model is serialized.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.core.metrics import metrics
from app.integrations.translation.base import Direction, ModelRegistry, ModelUnavailableError, TranslationError

logger = logging.getLogger(__name__)


@dataclass
class _LoadedModel:
    name: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    model: Any = None
    tokenizer: Any = None
    processor: Any = None
    state: str = "not_loaded"  # not_loaded | loading | ready | error
    error: str | None = None
    load_seconds: float | None = None


def _describe_load_error(name: str, exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    lowered = text.lower()
    if "gated" in lowered or "401" in lowered or "403" in lowered or "access" in lowered and "restricted" in lowered:
        return (f"Access to {name} is gated. Accept the model terms at https://huggingface.co/{name} "
                "and authenticate with `hf auth login` (or set HF_TOKEN in your shell, not in git).")
    if "connection" in lowered or "resolve" in lowered or "offline" in lowered:
        return f"Could not download {name}: network error ({type(exc).__name__})."
    return f"Failed to load {name}: {text[:300]}"


class IndicTrans2Engine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = ModelRegistry(settings)
        self._models = {d: _LoadedModel(name=n) for d, n in self.registry.checkpoints.items()}
        self._torch_configured = False

    def _configure_torch(self) -> None:
        if self._torch_configured:
            return
        import torch

        torch.set_num_threads(max(1, self.settings.TRANSLATION_TORCH_THREADS))
        self._torch_configured = True

    def load(self, direction: Direction) -> None:
        entry = self._models[direction]
        with entry.lock:
            if entry.state == "ready":
                return
            entry.state = "loading"
            start = time.perf_counter()
            try:
                self._configure_torch()
                import torch
                from IndicTransToolkit.processor import IndicProcessor
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

                # trust_remote_code runs the repo's Python: only ever at a pinned, reviewed commit.
                revision = self.settings.model_revision(entry.name)
                if revision is None:
                    logger.warning("model revision not pinned", extra={"model": entry.name})
                entry.tokenizer = AutoTokenizer.from_pretrained(
                    entry.name, trust_remote_code=True, revision=revision
                )
                model = AutoModelForSeq2SeqLM.from_pretrained(
                    entry.name, trust_remote_code=True, revision=revision, dtype=torch.float32
                )
                entry.model = model.to(self.settings.TRANSLATION_DEVICE).eval()
                entry.processor = IndicProcessor(inference=True)
            except Exception as exc:  # noqa: BLE001 - surface any load failure as a status
                entry.state = "error"
                entry.error = _describe_load_error(entry.name, exc)
                metrics.incr("translation_model_load_failures")
                logger.error("model load failed", extra={"model": entry.name, "reason": entry.error})
                return
            entry.load_seconds = round(time.perf_counter() - start, 2)
            entry.state = "ready"
            entry.error = None
            metrics.observe(f"model_init_seconds.{direction.value}", entry.load_seconds)
            logger.info("model loaded", extra={"model": entry.name, "seconds": entry.load_seconds})

    def translate_batch(self, texts: list[str], src: str, tgt: str, direction: Direction) -> list[str]:
        entry = self._models[direction]
        if entry.state != "ready":
            self.load(direction)
        if entry.state != "ready":
            raise ModelUnavailableError(entry.error or f"Model {entry.name} unavailable")
        import torch

        with entry.lock:
            batch = entry.processor.preprocess_batch(texts, src_lang=src, tgt_lang=tgt)
            inputs = entry.tokenizer(
                batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True
            ).to(self.settings.TRANSLATION_DEVICE)
            with torch.inference_mode():
                generated = entry.model.generate(
                    **inputs,
                    use_cache=self.settings.TRANSLATION_USE_CACHE,
                    min_length=0,
                    # Output length scales with input; stops runaway generations early.
                    max_length=min(self.settings.TRANSLATION_MAX_NEW_TOKENS,
                                   int(inputs["input_ids"].shape[1] * 3) + 16),
                    repetition_penalty=self.settings.TRANSLATION_REPETITION_PENALTY,
                    no_repeat_ngram_size=self.settings.TRANSLATION_NO_REPEAT_NGRAM_SIZE,
                    num_beams=self.settings.TRANSLATION_NUM_BEAMS,
                    num_return_sequences=1,
                )
            decoded = entry.tokenizer.batch_decode(
                generated, skip_special_tokens=True, clean_up_tokenization_spaces=True
            )
            outputs = entry.processor.postprocess_batch(decoded, lang=tgt)
        if len(outputs) != len(texts):
            raise TranslationError("Model returned an unexpected number of outputs")
        return outputs

    def status(self) -> dict[str, dict[str, object]]:
        return {
            d.value: {"model": m.name, "state": m.state, "error": m.error, "load_seconds": m.load_seconds}
            for d, m in self._models.items()
        }
