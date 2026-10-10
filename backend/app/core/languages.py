"""Language catalog.

`CATALOG` lists every language code supported by the IndicTrans2 models (FLORES-200 style
codes, from the official AI4Bharat IndicTrans2 README). Which ones are *enabled* is controlled
by the SUPPORTED_LANGUAGES setting, so adding a language is a configuration change.
"""

from dataclasses import dataclass

from app.core.config import get_settings

ENGLISH = "eng_Latn"


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native_name: str


CATALOG: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("eng_Latn", "English", "English"),
        Language("asm_Beng", "Assamese", "অসমীয়া"),
        Language("ben_Beng", "Bengali", "বাংলা"),
        Language("brx_Deva", "Bodo", "बड़ो"),
        Language("doi_Deva", "Dogri", "डोगरी"),
        Language("gom_Deva", "Konkani", "कोंकणी"),
        Language("guj_Gujr", "Gujarati", "ગુજરાતી"),
        Language("hin_Deva", "Hindi", "हिन्दी"),
        Language("kan_Knda", "Kannada", "ಕನ್ನಡ"),
        Language("kas_Arab", "Kashmiri (Arabic)", "کٲشُر"),
        Language("kas_Deva", "Kashmiri (Devanagari)", "कॉशुर"),
        Language("mai_Deva", "Maithili", "मैथिली"),
        Language("mal_Mlym", "Malayalam", "മലയാളം"),
        Language("mar_Deva", "Marathi", "मराठी"),
        Language("mni_Beng", "Manipuri (Bengali)", "মৈতৈলোন্"),
        Language("mni_Mtei", "Manipuri (Meitei)", "ꯃꯤꯇꯩꯂꯣꯟ"),
        Language("npi_Deva", "Nepali", "नेपाली"),
        Language("ory_Orya", "Odia", "ଓଡ଼ିଆ"),
        Language("pan_Guru", "Punjabi", "ਪੰਜਾਬੀ"),
        Language("san_Deva", "Sanskrit", "संस्कृतम्"),
        Language("sat_Olck", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ"),
        Language("snd_Arab", "Sindhi (Arabic)", "سنڌي"),
        Language("snd_Deva", "Sindhi (Devanagari)", "सिन्धी"),
        Language("tam_Taml", "Tamil", "தமிழ்"),
        Language("tel_Telu", "Telugu", "తెలుగు"),
        Language("urd_Arab", "Urdu", "اردو"),
    ]
}


def enabled_languages() -> list[Language]:
    codes = get_settings().enabled_languages
    unknown = [c for c in codes if c not in CATALOG]
    if unknown:
        raise ValueError(f"SUPPORTED_LANGUAGES contains codes not supported by IndicTrans2: {unknown}")
    return [CATALOG[c] for c in codes]


def is_enabled(code: str) -> bool:
    return code in get_settings().enabled_languages


def validate_language(code: str) -> str:
    """Pydantic validator body: accept only enabled language codes."""
    if not is_enabled(code):
        raise ValueError(f"Unsupported language: {code}")
    return code
