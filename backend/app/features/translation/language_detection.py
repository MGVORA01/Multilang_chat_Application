"""Detect a message's source language from its Unicode script.

Each script maps to one or more IndicTrans2 codes. When a script is shared (Devanagari: Hindi,
Marathi, …; Bengali: Bengali, Assamese) the sender's preferred language wins if it uses that
script, otherwise a sensible default is chosen.

Limitation: romanized Indic text ("kaise ho") is Latin script and is detected as English; users can
still pick the language manually in the composer.
"""

from collections import Counter

# (start, end, script suffix used in IndicTrans2 codes)
_RANGES: list[tuple[int, int, str]] = [
    (0x0900, 0x097F, "Deva"),
    (0x0980, 0x09FF, "Beng"),
    (0x0A00, 0x0A7F, "Guru"),
    (0x0A80, 0x0AFF, "Gujr"),
    (0x0B00, 0x0B7F, "Orya"),
    (0x0B80, 0x0BFF, "Taml"),
    (0x0C00, 0x0C7F, "Telu"),
    (0x0C80, 0x0CFF, "Knda"),
    (0x0D00, 0x0D7F, "Mlym"),
    (0x0600, 0x06FF, "Arab"),
    (0x1C50, 0x1C7F, "Olck"),
    (0xABC0, 0xABFF, "Mtei"),
]

_DEFAULT_FOR_SCRIPT = {"Latn": "eng_Latn", "Deva": "hin_Deva", "Beng": "ben_Beng", "Arab": "urd_Arab"}


def _script_of(ch: str) -> str | None:
    cp = ord(ch)
    if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
        return "Latn"
    for start, end, script in _RANGES:
        if start <= cp <= end:
            return script
    return None


def dominant_script(text: str) -> str | None:
    counts = Counter(s for s in map(_script_of, text) if s)
    return counts.most_common(1)[0][0] if counts else None


def detect_language(text: str, preferred: str, enabled: list[str]) -> str:
    """Best-guess IndicTrans2 code for `text`; falls back to `preferred` (e.g. emoji/digits only)."""
    script = dominant_script(text)
    if script is None or preferred.endswith(f"_{script}"):
        return preferred
    candidates = [code for code in enabled if code.endswith(f"_{script}")]
    if not candidates:
        return preferred
    default = _DEFAULT_FOR_SCRIPT.get(script)
    return default if default in candidates else candidates[0]
