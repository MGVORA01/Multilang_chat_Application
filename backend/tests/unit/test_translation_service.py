"""TranslationService and checkpoint routing (no database)."""

import asyncio
import threading
import time

import pytest

from app.core.config import get_settings
from app.features.translation.service import TranslationService
from app.integrations.translation.base import (
    Direction,
    ModelRegistry,
    TranslationError,
    TranslationQueueFullError,
    TranslationTimeoutError,
    UnsupportedLanguagePairError,
)


def test_registry_routes_by_direction() -> None:
    reg = ModelRegistry(get_settings())
    assert reg.direction("guj_Gujr", "hin_Deva") is Direction.INDIC_INDIC
    assert reg.direction("eng_Latn", "tam_Taml") is Direction.EN_INDIC
    assert reg.direction("ben_Beng", "eng_Latn") is Direction.INDIC_EN
    assert reg.checkpoint("eng_Latn", "hin_Deva") == "ai4bharat/indictrans2-en-indic-dist-200M"
    with pytest.raises(UnsupportedLanguagePairError):
        reg.direction("guj_Gujr", "guj_Gujr")
    with pytest.raises(UnsupportedLanguagePairError):
        reg.direction("guj_Gujr", "fra_Latn")


class SlowEngine:
    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def load(self, direction: Direction) -> None: ...

    def status(self) -> dict:  # type: ignore[type-arg]
        return {}

    def translate_batch(self, texts, src, tgt, direction):  # type: ignore[no-untyped-def]
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        time.sleep(self.delay)
        with self.lock:
            self.active -= 1
        return [f"ok:{t}" for t in texts]


def _service(engine, **overrides) -> TranslationService:  # type: ignore[no-untyped-def]
    settings = get_settings().model_copy(update=overrides)
    return TranslationService(settings, engine)


def test_concurrency_is_bounded_and_cache_used() -> None:
    engine = SlowEngine(0.05)
    svc = _service(engine, TRANSLATION_MAX_CONCURRENT_JOBS=1, TRANSLATION_MAX_QUEUE_SIZE=50)

    async def go() -> None:
        results = await asyncio.gather(*[svc.translate(f"t{i}", "guj_Gujr", "hin_Deva") for i in range(5)])
        assert [r.text for r in results] == [f"ok:t{i}" for i in range(5)]
        again = await svc.translate("t0", "guj_Gujr", "hin_Deva")
        assert again.cached is True

    asyncio.run(go())
    assert engine.max_active == 1


def test_event_loop_not_blocked_during_inference() -> None:
    svc = _service(SlowEngine(0.3))

    async def go() -> float:
        task = asyncio.create_task(svc.translate("x", "guj_Gujr", "hin_Deva"))
        start = time.perf_counter()
        await asyncio.sleep(0.01)  # would take >=0.3s if inference ran on the loop
        elapsed = time.perf_counter() - start
        await task
        return elapsed

    assert asyncio.run(go()) < 0.1


def test_queue_full_rejected() -> None:
    svc = _service(SlowEngine(0.2), TRANSLATION_MAX_QUEUE_SIZE=2)

    async def go() -> None:
        tasks = [asyncio.create_task(svc.translate(f"q{i}", "guj_Gujr", "hin_Deva")) for i in range(2)]
        await asyncio.sleep(0.01)
        with pytest.raises(TranslationQueueFullError):
            await svc.translate("overflow", "guj_Gujr", "hin_Deva")
        await asyncio.gather(*tasks)

    asyncio.run(go())


def test_timeout() -> None:
    svc = _service(SlowEngine(0.5), TRANSLATION_TIMEOUT_SECONDS=0.05)

    async def go() -> None:
        with pytest.raises(TranslationTimeoutError):
            await svc.translate("slow", "guj_Gujr", "hin_Deva")

    asyncio.run(go())


def test_empty_output_is_failure() -> None:
    from app.integrations.translation.mock import MockEngine

    svc = _service(MockEngine(get_settings()))

    async def go() -> None:
        with pytest.raises(TranslationError) as exc:
            await svc.translate("__empty__", "guj_Gujr", "hin_Deva")
        assert exc.value.code == "empty_translation"

    asyncio.run(go())


def test_degenerate_output_detection() -> None:
    from app.features.translation.service import is_degenerate

    assert is_degenerate("hii hindi", "हि" * 170)
    assert is_degenerate("hii hindi", "हिहिहिहिहिहिहिहि")
    assert not is_degenerate("hahahaha", "हाहाहा")
    assert not is_degenerate("hmm ok ok", "हम्म ठीक है ठीक है।")
    assert not is_degenerate("The meeting is at 5 pm.", "बैठक शाम 5 बजे है।")
    assert not is_degenerate("ok", "ठीक है")
