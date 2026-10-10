"""Builds the configured translation engine (heavy ML imports only for the real backend)."""

from app.core.config import Settings
from app.integrations.translation.base import TranslationEngine


def build_engine(settings: Settings) -> TranslationEngine:
    """Return the engine selected by TRANSLATION_BACKEND (indictrans2 | mock | disabled)."""
    if settings.TRANSLATION_BACKEND == "mock":
        from app.integrations.translation.mock import MockEngine

        return MockEngine(settings)
    if settings.TRANSLATION_BACKEND == "disabled":
        from app.integrations.translation.disabled import DisabledEngine

        return DisabledEngine()
    from app.integrations.translation.indictrans2 import IndicTrans2Engine

    return IndicTrans2Engine(settings)
