"""ORM -> API conversions for messages and translations."""

from app.features.messages.models import Message, MessageTranslation
from app.features.messages.schemas import DeliveryStatus, MessageOut, TranslationOut


def delivery_status(message: Message) -> DeliveryStatus:
    """Aggregate receipt state over all recipients: read > delivered > sent."""
    receipts = [r for r in message.receipts if r.user_id != message.sender_id]
    if not receipts:
        return "sent"
    if all(r.read_at for r in receipts):
        return "read"
    if all(r.delivered_at for r in receipts):
        return "delivered"
    return "sent"


def translation_out(translation: MessageTranslation) -> TranslationOut:
    return TranslationOut.model_validate(translation)


def message_out(message: Message) -> MessageOut:
    return MessageOut(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        client_message_id=message.client_message_id,
        original_text=message.original_text,
        source_language=message.source_language,
        created_at=message.created_at,
        translations=[translation_out(t) for t in sorted(message.translations, key=lambda t: t.target_language)],
        status=delivery_status(message),
    )
