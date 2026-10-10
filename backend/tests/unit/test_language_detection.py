"""Script-based source-language detection."""

from app.features.translation.language_detection import detect_language

ENABLED = ["eng_Latn", "guj_Gujr", "hin_Deva", "mar_Deva", "ben_Beng", "asm_Beng", "tam_Taml"]


def test_detect_language() -> None:
    assert detect_language("Hello this is meet.", "hin_Deva", ENABLED) == "eng_Latn"
    assert detect_language("તમે કેમ છો?", "eng_Latn", ENABLED) == "guj_Gujr"
    assert detect_language("आप कैसे हैं?", "eng_Latn", ENABLED) == "hin_Deva"
    # shared script: preferred language wins
    assert detect_language("तू कसा आहेस?", "mar_Deva", ENABLED) == "mar_Deva"
    assert detect_language("তুমি কেমন আছ?", "asm_Beng", ENABLED) == "asm_Beng"
    # mixed: dominant script decides
    assert detect_language("ok भाई, कल मिलते हैं", "eng_Latn", ENABLED) == "hin_Deva"
    # nothing to detect -> preferred
    assert detect_language("👍 123", "guj_Gujr", ENABLED) == "guj_Gujr"
