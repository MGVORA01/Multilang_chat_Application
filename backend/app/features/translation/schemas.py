"""Schemas for the ad-hoc translation endpoint (composer preview, testing)."""

from pydantic import Field, field_validator

from app.core.languages import validate_language
from app.shared.schemas import ApiModel


class TranslateRequest(ApiModel):
    text: str = Field(min_length=1, max_length=2000)
    source_language: str
    target_language: str

    _langs = field_validator("source_language", "target_language")(validate_language)


class TranslateResponse(ApiModel):
    translated_text: str
    source_language: str
    target_language: str
    model_name: str
    duration_ms: int
    cached: bool
