"""Async translation service with bounded, controlled CPU inference.

- Blocking inference runs in a dedicated ThreadPoolExecutor, never on the event loop.
- At most TRANSLATION_MAX_CONCURRENT_JOBS inferences run at once; the slot is held until the
  worker thread actually finishes, even if the awaiting caller timed out.
- At most TRANSLATION_MAX_QUEUE_SIZE jobs may be waiting or running; beyond that callers get
  TranslationQueueFullError immediately (no unbounded memory growth).
- An LRU cache avoids re-translating identical (src, tgt, text) triples.

Limitations (single process): the queue lives in memory, so pending jobs are lost on restart
(they are marked failed at startup and can be retried). See docs/architecture.md.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

from app.core.config import Settings
from app.core.metrics import metrics
from app.integrations.translation.base import (
    Direction,
    ModelRegistry,
    TranslationEngine,
    TranslationError,
    TranslationQueueFullError,
    TranslationResult,
    TranslationTimeoutError,
    UnsupportedLanguagePairError,
)

logger = logging.getLogger(__name__)


_PUBLIC_ERRORS = {
    "model_unavailable": "Translation is temporarily unavailable",
    "translation_timeout": "Translation took too long",
    "translation_queue_full": "Translation service is busy, try again shortly",
    "empty_translation": "The translation was unreliable",
    "degenerate_translation": "The translation was unreliable",
}


def public_error_message(exc: TranslationError) -> str:
    """Message safe to store and show to chat members (details like model names stay in the logs)."""
    if isinstance(exc, UnsupportedLanguagePairError):
        return exc.message
    return _PUBLIC_ERRORS.get(exc.code, "Translation failed")


def is_degenerate(source: str, output: str) -> bool:
    """Last-line check so junk like 300 chars of "हिहिहि" is never shown as a translation."""
    if len(output) > 4 * len(source) + 60:
        return True
    # Same short chunk repeated many times (>= 6 repeats covering most of the output).
    compact = "".join(output.split())
    for size in range(1, 7):
        chunk = compact[:size]
        if chunk and compact.count(chunk) * size >= 0.8 * len(compact) and compact.count(chunk) >= 6:
            return True
    return False


class TranslationService:
    """Async facade over a blocking engine: bounded queue, concurrency limit, timeout and LRU cache."""

    def __init__(self, settings: Settings, engine: TranslationEngine) -> None:
        self.settings = settings
        self.engine = engine
        self.registry = ModelRegistry(settings)
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, settings.TRANSLATION_MAX_CONCURRENT_JOBS), thread_name_prefix="translate"
        )
        self._slots = asyncio.Semaphore(max(1, settings.TRANSLATION_MAX_CONCURRENT_JOBS))
        self._inflight = 0
        self._cache: OrderedDict[tuple[str, str, str], tuple[str, str]] = OrderedDict()

    @property
    def backend(self) -> str:
        return self.settings.TRANSLATION_BACKEND

    async def startup(self) -> None:
        """Start loading models in the background so the API is usable immediately.

        The first start downloads several GB; blocking startup on it would make every REST call
        fail until the download finishes. Translation requests that arrive meanwhile wait on the
        per-model lock inside the engine.
        """
        if self.settings.TRANSLATION_BACKEND != "indictrans2" or not self.settings.TRANSLATION_PRELOAD:
            return
        self._preload_task = asyncio.create_task(self._preload(), name="translation-preload")

    async def _preload(self) -> None:
        loop = asyncio.get_running_loop()
        for direction in Direction:
            # Sequential: loading three checkpoints at once would spike memory.
            await loop.run_in_executor(self._executor, self.engine.load, direction)
        logger.info("translation models preloaded", extra={"models": self.engine.status()})

    async def shutdown(self) -> None:
        task = getattr(self, "_preload_task", None)
        if task is not None:
            task.cancel()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def status(self) -> dict[str, object]:
        return {
            "backend": self.settings.TRANSLATION_BACKEND,
            "queue_length": self._inflight,
            "max_queue_size": self.settings.TRANSLATION_MAX_QUEUE_SIZE,
            "max_concurrent_jobs": self.settings.TRANSLATION_MAX_CONCURRENT_JOBS,
            "models": self.engine.status(),
        }

    def model_name(self, src: str, tgt: str) -> str:
        return self.registry.checkpoint(src, tgt)

    async def translate(self, text: str, src: str, tgt: str, *, adhoc: bool = False) -> TranslationResult:
        """Translate `text`. `adhoc` requests (previews) may only use part of the queue."""
        direction = self.registry.direction(src, tgt)  # raises UnsupportedLanguagePairError
        model_name = self.registry.checkpoints[direction]
        key = (src, tgt, text)
        if key in self._cache:
            self._cache.move_to_end(key)
            cached_text, cached_model = self._cache[key]
            metrics.incr("translation_cache_hits")
            return TranslationResult(cached_text, cached_model, 0, cached=True)

        limit = self.settings.TRANSLATION_MAX_QUEUE_SIZE
        if adhoc:
            limit = max(1, int(limit * self.settings.TRANSLATION_ADHOC_QUEUE_SHARE))
        if self._inflight >= limit:
            metrics.incr("translation_queue_rejections")
            raise TranslationQueueFullError("Translation queue is full, try again later")

        self._inflight += 1
        metrics.gauge("translation_queue_length", self._inflight)
        start = time.perf_counter()
        acquired = handed_off = False
        try:
            await self._slots.acquire()
            acquired = True
            loop = asyncio.get_running_loop()
            future = loop.run_in_executor(self._executor, self.engine.translate_batch, [text], src, tgt, direction)

            def _release(_: object) -> None:
                self._slots.release()

            # The slot is released when the worker thread finishes, not when we stop waiting.
            future.add_done_callback(_release)
            handed_off = True
            try:
                outputs = await asyncio.wait_for(asyncio.shield(future),
                                                 timeout=self.settings.TRANSLATION_TIMEOUT_SECONDS)
            except TimeoutError as exc:
                metrics.incr("translation_timeouts")
                raise TranslationTimeoutError(
                    f"Translation timed out after {self.settings.TRANSLATION_TIMEOUT_SECONDS:.0f}s"
                ) from exc
        except TranslationError as exc:
            metrics.incr("translation_failures")
            logger.warning("translation failed", extra={"src": src, "tgt": tgt, "code": exc.code,
                                                        "reason": exc.message})
            raise
        except Exception as exc:
            metrics.incr("translation_failures")
            logger.exception("translation crashed", extra={"src": src, "tgt": tgt})
            raise TranslationError(f"Translation failed: {type(exc).__name__}") from exc
        finally:
            if acquired and not handed_off:
                self._slots.release()
            self._inflight -= 1
            metrics.gauge("translation_queue_length", self._inflight)

        translated = (outputs[0] or "").strip()
        duration = time.perf_counter() - start
        if not translated:
            metrics.incr("translation_failures")
            raise TranslationError("Model returned an empty translation", code="empty_translation")
        if is_degenerate(text, translated):
            metrics.incr("translation_failures")
            raise TranslationError("Model output looked unreliable (runaway repetition)",
                                   code="degenerate_translation")

        metrics.incr("translation_successes")
        metrics.observe(f"translation_seconds.{direction.value}", duration)
        logger.info("translated", extra={"src": src, "tgt": tgt, "model": model_name,
                                         "chars": len(text), "ms": int(duration * 1000)})
        self._cache[key] = (translated, model_name)
        if len(self._cache) > self.settings.TRANSLATION_CACHE_SIZE:
            self._cache.popitem(last=False)
        return TranslationResult(translated, model_name, int(duration * 1000))
