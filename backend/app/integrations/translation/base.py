"""Translation engine contract, checkpoint routing and translation errors (shared by engines and service)."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.core.config import Settings
from app.core.languages import ENGLISH


class TranslationError(Exception):
    code = "translation_failed"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class UnsupportedLanguagePairError(TranslationError):
    code = "unsupported_language_pair"


class TranslationQueueFullError(TranslationError):
    code = "translation_queue_full"


class TranslationTimeoutError(TranslationError):
    code = "translation_timeout"


class ModelUnavailableError(TranslationError):
    code = "model_unavailable"


class Direction(StrEnum):
    INDIC_INDIC = "indic-indic"
    EN_INDIC = "en-indic"
    INDIC_EN = "indic-en"


@dataclass(frozen=True)
class TranslationResult:
    text: str
    model_name: str
    duration_ms: int
    cached: bool = False


class ModelRegistry:
    """Maps a (source, target) pair to the correct IndicTrans2 checkpoint.

    English pairs always use the dedicated en-indic / indic-en checkpoints; the indic-indic
    checkpoint is never used for English.
    """

    def __init__(self, settings: Settings) -> None:
        self.checkpoints: dict[Direction, str] = {
            Direction.INDIC_INDIC: settings.INDIC_INDIC_MODEL,
            Direction.EN_INDIC: settings.EN_INDIC_MODEL,
            Direction.INDIC_EN: settings.INDIC_EN_MODEL,
        }
        self.enabled = set(settings.enabled_languages)

    def direction(self, src: str, tgt: str) -> Direction:
        if src not in self.enabled or tgt not in self.enabled:
            raise UnsupportedLanguagePairError(f"Unsupported language pair: {src} -> {tgt}")
        if src == tgt:
            raise UnsupportedLanguagePairError("Source and target language are the same")
        if src == ENGLISH:
            return Direction.EN_INDIC
        if tgt == ENGLISH:
            return Direction.INDIC_EN
        return Direction.INDIC_INDIC

    def checkpoint(self, src: str, tgt: str) -> str:
        return self.checkpoints[self.direction(src, tgt)]


class TranslationEngine(Protocol):
    """Blocking engine. Called only from the translation service's worker threads."""

    def load(self, direction: Direction) -> None: ...

    def translate_batch(self, texts: list[str], src: str, tgt: str, direction: Direction) -> list[str]: ...

    def status(self) -> dict[str, dict[str, object]]: ...
