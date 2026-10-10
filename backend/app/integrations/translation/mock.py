"""Deterministic fake engine for tests and UI development without downloading models.

- Output: "[<tgt>] <text>"
- Text containing "__fail__" raises a TranslationError.
- Text containing "__empty__" returns an empty string (exercises the empty-output guard).
"""

import time

from app.core.config import Settings
from app.integrations.translation.base import Direction, ModelRegistry, TranslationError


class MockEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.registry = ModelRegistry(settings)
        self.calls: list[tuple[str, str, str]] = []
        self.fail_all = False

    def load(self, direction: Direction) -> None:
        return None

    def translate_batch(self, texts: list[str], src: str, tgt: str, direction: Direction) -> list[str]:
        if self.settings.MOCK_TRANSLATION_DELAY:
            time.sleep(self.settings.MOCK_TRANSLATION_DELAY)
        out = []
        for text in texts:
            self.calls.append((text, src, tgt))
            if self.fail_all or "__fail__" in text:
                raise TranslationError("Mock translation failure")
            out.append("" if "__empty__" in text else f"[{tgt}] {text}")
        return out

    def status(self) -> dict[str, dict[str, object]]:
        return {d.value: {"model": f"mock:{n}", "state": "ready", "error": None, "load_seconds": 0}
                for d, n in self.registry.checkpoints.items()}
