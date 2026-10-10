"""System/meta schemas."""

from app.shared.schemas import ApiModel


class LanguageOut(ApiModel):
    code: str
    name: str
    native_name: str
