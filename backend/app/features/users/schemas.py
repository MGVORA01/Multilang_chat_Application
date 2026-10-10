"""User request/response schemas."""

import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, Field, field_validator

from app.core.languages import validate_language
from app.shared.schemas import ApiModel


class UserPublic(ApiModel):
    id: uuid.UUID
    username: str
    display_name: str
    preferred_language: str
    profile_image_url: str | None
    last_seen_at: datetime | None
    is_online: bool = False
    is_deleted: bool = False


class UserMe(UserPublic):
    email: str
    created_at: datetime
    is_active: bool


class UpdateProfileRequest(ApiModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    profile_image_url: AnyHttpUrl | None = Field(default=None, max_length=512)

    @field_validator("profile_image_url")
    @classmethod
    def _https_only(cls, v: AnyHttpUrl | None) -> AnyHttpUrl | None:
        # Images load in other users' browsers: no plain-http (mixed content, tampering).
        if v is not None and v.scheme != "https":
            raise ValueError("Profile image URL must use https://")
        return v


class UpdateLanguageRequest(ApiModel):
    preferred_language: str

    _lang = field_validator("preferred_language")(validate_language)


class DeleteAccountRequest(ApiModel):
    # Re-authentication: deleting an account requires the current password.
    password: str = Field(min_length=1, max_length=128)
