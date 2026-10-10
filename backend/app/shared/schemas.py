"""Cross-feature schema building blocks: base model, pagination envelopes, payload helpers."""

import uuid
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(ApiModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class CursorPage(ApiModel, Generic[T]):
    items: list[T]
    # Pass as `before` to fetch the next (older) page; null when there is nothing older.
    next_cursor: str | None
    has_more: bool


def to_payload(model: BaseModel) -> dict[str, Any]:
    """JSON-safe dict for WebSocket event payloads."""
    return model.model_dump(mode="json")


def uuid_strings(values: list[uuid.UUID]) -> list[str]:
    return [str(v) for v in values]
