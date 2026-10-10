"""Authentication request/response schemas."""

import re

from pydantic import EmailStr, Field, field_validator

from app.core.languages import validate_language
from app.features.users.schemas import UserMe
from app.shared.schemas import ApiModel

USERNAME_RE = re.compile(r"^[a-z0-9_.]{3,32}$")


class RegisterRequest(ApiModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=64)
    preferred_language: str

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("Username may contain only letters, digits, '_' and '.' (3-32 chars)")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.lower()

    @field_validator("display_name")
    @classmethod
    def _display(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Display name is required")
        return v

    _lang = field_validator("preferred_language")(validate_language)


class LoginRequest(ApiModel):
    login: str = Field(min_length=1, max_length=255, description="Username or email")
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(ApiModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserMe


class WsTicketResponse(ApiModel):
    ticket: str
    expires_in: int
