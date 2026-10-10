"""Conversation endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import ManagerDep, SessionDep
from app.features.auth.dependencies import CurrentUser
from app.features.conversations.schemas import ConversationOut, CreateConversationRequest
from app.features.conversations.service import ConversationService
from app.shared.schemas import Page

router = APIRouter(prefix="/conversations", tags=["conversations"])


def get_conversation_service(session: SessionDep, manager: ManagerDep) -> ConversationService:
    return ConversationService(session, manager)


ConversationServiceDep = Annotated[ConversationService, Depends(get_conversation_service)]


@router.get("", response_model=Page[ConversationOut])
async def list_conversations(
    user: CurrentUser, conversations: ConversationServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ConversationOut]:
    items, total = await conversations.list_for_user(user.id, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED,
             responses={200: {"description": "Existing direct conversation returned"}})
async def create_conversation(body: CreateConversationRequest, user: CurrentUser,
                              conversations: ConversationServiceDep, response: Response) -> ConversationOut:
    conversation, created = await conversations.get_or_create_direct(user.id, body.participant_id)
    if not created:
        response.status_code = status.HTTP_200_OK
    return conversation


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: uuid.UUID, user: CurrentUser,
                           conversations: ConversationServiceDep) -> ConversationOut:
    return await conversations.get(user.id, conversation_id)
