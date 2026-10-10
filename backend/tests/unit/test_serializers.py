"""Delivery-status aggregation over per-recipient receipts."""

import uuid
from datetime import UTC, datetime

from app.features.messages.models import Message, MessageReceipt
from app.features.messages.serializers import delivery_status

NOW = datetime.now(UTC)


def _message(*receipts: tuple[datetime | None, datetime | None]) -> Message:
    sender = uuid.uuid4()
    message = Message(id=uuid.uuid4(), sender_id=sender)
    message.receipts = [MessageReceipt(user_id=uuid.uuid4(), delivered_at=d, read_at=r) for d, r in receipts]
    return message


def test_delivery_status_aggregates_all_recipients() -> None:
    assert delivery_status(_message()) == "sent"  # no recipients
    assert delivery_status(_message((None, None))) == "sent"
    assert delivery_status(_message((NOW, None))) == "delivered"
    assert delivery_status(_message((NOW, NOW))) == "read"
    # group-style: everyone must reach the state
    assert delivery_status(_message((NOW, NOW), (NOW, None))) == "delivered"
    assert delivery_status(_message((NOW, NOW), (None, None))) == "sent"
