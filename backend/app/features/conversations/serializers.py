"""ORM -> API conversion for conversations."""

from app.features.conversations.models import Conversation
from app.features.conversations.schemas import ConversationOut
from app.features.messages.models import Message
from app.features.messages.serializers import message_out
from app.features.users.serializers import user_public
from app.websocket.manager import ConnectionManager


def conversation_out(conversation: Conversation, manager: ConnectionManager,
                     last_message: Message | None = None, unread: int = 0) -> ConversationOut:
    members = sorted(conversation.members, key=lambda m: m.joined_at)
    return ConversationOut(
        id=conversation.id,
        conversation_type=conversation.conversation_type,  # type: ignore[arg-type]
        title=conversation.title,
        created_at=conversation.created_at,
        last_message_at=conversation.last_message_at,
        members=[user_public(m.user, manager) for m in members],
        last_message=message_out(last_message) if last_message else None,
        unread_count=unread,
    )
