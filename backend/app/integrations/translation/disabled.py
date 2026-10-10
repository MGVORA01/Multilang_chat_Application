"""Engine used when TRANSLATION_BACKEND=disabled: every request fails cleanly."""

from app.integrations.translation.base import Direction, ModelUnavailableError


class DisabledEngine:
    def load(self, direction: Direction) -> None:
        return None

    def translate_batch(self, texts: list[str], src: str, tgt: str, direction: Direction) -> list[str]:
        raise ModelUnavailableError("Translation is disabled on this server (TRANSLATION_BACKEND=disabled)")

    def status(self) -> dict[str, dict[str, object]]:
        return {}
