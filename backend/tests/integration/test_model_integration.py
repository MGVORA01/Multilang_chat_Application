"""Optional: loads the real IndicTrans2 checkpoints on CPU.

    RUN_MODEL_TESTS=1 TEST_DATABASE_URL=... pytest tests/test_model_integration.py -s

Requires `pip install -r requirements-ml.txt` and Hugging Face access to the gated models.
"""

import asyncio
import os
import re

import pytest

from app.core.config import get_settings

pytestmark = [
    pytest.mark.model,
    pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="set RUN_MODEL_TESTS=1 to run"),
]

SCRIPTS = {
    "hin_Deva": re.compile(r"[ऀ-ॿ]"),
    "guj_Gujr": re.compile(r"[઀-૿]"),
    "eng_Latn": re.compile(r"[A-Za-z]"),
}

CASES = [
    ("guj_Gujr", "hin_Deva", "તમે કેમ છો?"),
    ("hin_Deva", "guj_Gujr", "मैं ठीक हूँ, धन्यवाद।"),
    ("eng_Latn", "hin_Deva", "How are you?"),
    ("hin_Deva", "eng_Latn", "आप कैसे हैं?"),
    ("guj_Gujr", "eng_Latn", "તમે કેમ છો?"),
    ("eng_Latn", "guj_Gujr", "I am fine, thank you."),
]


def test_real_model_directions() -> None:
    from app.features.translation.service import TranslationService
    from app.integrations.translation.indictrans2 import IndicTrans2Engine

    settings = get_settings().model_copy(update={"TRANSLATION_BACKEND": "indictrans2"})
    svc = TranslationService(settings, IndicTrans2Engine(settings))

    async def go() -> None:
        await svc.startup()
        await svc._preload_task  # startup() loads in the background
        status = svc.engine.status()
        errors = {k: v["error"] for k, v in status.items() if v["state"] != "ready"}
        assert not errors, errors
        for src, tgt, text in CASES:
            result = await svc.translate(text, src, tgt)
            print(f"{src}->{tgt} [{result.duration_ms} ms] {text!r} -> {result.text!r}")
            assert result.text.strip()
            assert SCRIPTS[tgt].search(result.text), f"output not in {tgt} script: {result.text}"
        await svc.shutdown()

    asyncio.run(go())
