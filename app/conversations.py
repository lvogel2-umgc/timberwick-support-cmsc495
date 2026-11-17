"""
Authors: Jacob Wills-Brennan, Belqis Wahidi

ConversationService: the integration point between chat, the AI, and support tickets.

A customer message is saved, sent to the AIOrchestrator, and the AI reply is saved. If the AI
says the conversation needs a person, the EscalationService creates a ticket. If the AI fails,
the customer gets a safe fallback reply and a ticket instead of an error.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.errors import AuthorizationError, NotFoundError
from app.models import Conversation, Message, User
from app.orchestrator import AIOrchestrator, AIResult
from app.schemas import (
    CHAT_EXAMPLES,
    ERROR_RESPONSES,
    ChatMessageRequest,
    ChatResult,
    ConversationOut,
    MessageOut,
    to_utc_iso,
)
from app.tickets import EscalationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"], responses=ERROR_RESPONSES)

FALLBACK_REPLY = (
    "Sorry, I'm having trouble answering right now. I've passed your question to a support agent."
)


class ConversationService:
    def __init__(self, db: Session, orchestrator: AIOrchestrator) -> None:
        self._db = db
        self._orchestrator = orchestrator
        self._escalation = EscalationService(db)

    def _load_for_user(self, conversation_id: str, user: User) -> Conversation:
        conversation = self._db.get(Conversation, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation not found.")
        # Customers can only see their own conversations; agents can see any conversation.
        if user.role != "agent" and conversation.customer_id != user.id:
            raise AuthorizationError("You do not have access to this conversation.")
        return conversation

    def _ask_ai(self, message: str) -> AIResult:
        try:
            return self._orchestrator.respond(message)
        except Exception:
            logger.exception("AI orchestrator failed; using fallback reply.")
            return AIResult(FALLBACK_REPLY, 0.0, needs_escalation=True, reason="ai_unavailable")

    def send_message(self, user: User, message: str, conversation_id: str | None) -> ChatResult:
        if user.role != "customer":
            raise AuthorizationError("Only customers can send chat messages.")

        if conversation_id is None:
            conversation = Conversation(customer_id=user.id)
            self._db.add(conversation)
            self._db.flush()
        else:
            conversation = self._load_for_user(conversation_id, user)

        self._db.add(Message(conversation_id=conversation.id, role="customer", text=message))
        result = self._ask_ai(message)

        reply = result.reply
        ticket_id = None
        if result.needs_escalation:
            ticket = self._escalation.create_ticket(conversation, result.reason, message)
            conversation.status = "escalated"
            ticket_id = ticket.id
            reply = f"{reply} Your ticket number is {ticket.id}."

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            text=reply,
            confidence=result.confidence,
            cited_article_ids=result.cited_article_ids,
        )
        self._db.add(assistant_message)
        self._db.commit()

        return ChatResult(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            reply=reply,
            confidence=result.confidence,
            cited_article_ids=result.cited_article_ids,
            escalated=result.needs_escalation,
            ticket_id=ticket_id,
        )

    def get_conversation(self, user: User, conversation_id: str) -> ConversationOut:
        conversation = self._load_for_user(conversation_id, user)
        return ConversationOut(
            id=conversation.id,
            status=conversation.status,
            messages=[
                MessageOut(
                    message_id=message.id,
                    role=message.role,
                    text=message.text,
                    timestamp=to_utc_iso(message.created_at),
                )
                for message in conversation.messages
            ],
        )


def get_conversation_service(request: Request, db: Session = Depends(get_db)):
    return ConversationService(db, request.app.state.orchestrator)


@router.post("/chat/messages", response_model=ChatResult)
def send_message(
    body: Annotated[ChatMessageRequest, Body(openapi_examples=CHAT_EXAMPLES)],
    user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ChatResult:
    conversation_id = str(body.conversation_id) if body.conversation_id else None
    return service.send_message(user, body.message, conversation_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationOut:
    return service.get_conversation(user, str(conversation_id))
