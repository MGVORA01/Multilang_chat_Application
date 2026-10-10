"""Registry of every ORM model, so Alembic and SQLAlchemy see the full metadata.

Models live in their feature packages; import them from here or from the feature.
"""

from app.db.base import Base
from app.features.auth.models import RefreshToken
from app.features.conversations.models import Conversation, ConversationMember, ConversationType
from app.features.messages.models import Message, MessageReceipt, MessageTranslation, TranslationStatus
from app.features.users.models import User

__all__ = [
    "Base",
    "Conversation",
    "ConversationMember",
    "ConversationType",
    "Message",
    "MessageReceipt",
    "MessageTranslation",
    "RefreshToken",
    "TranslationStatus",
    "User",
]
