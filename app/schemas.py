"""
Author: Luke Vogel

Request and response contracts for the public API. Requests reject unknown fields, IDs are
UUID strings, and timestamps are ISO 8601 in UTC.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TicketStatus = Literal["open", "assigned", "resolved"]


def to_utc_iso(value: datetime) -> str:
    # SQLite returns timestamps without a time zone, but they are always stored in UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_email(value: str) -> str:
    """Emails are compared case-insensitively, so they are always stored and checked lowercase."""
    return value.strip().lower()


class LoginRequest(RequestModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        return normalize_email(value)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


# Documented error responses, so /docs shows the shared error format the API really returns.
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid input or invalid status change"},
    401: {"model": ErrorResponse, "description": "Missing, invalid, or expired token"},
    403: {"model": ErrorResponse, "description": "Wrong role, or not your conversation"},
    404: {"model": ErrorResponse, "description": "Conversation or ticket not found"},
}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ChatMessageRequest(RequestModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message cannot be blank")
        return value.strip()


class ChatResult(BaseModel):
    conversation_id: str
    message_id: str
    reply: str
    confidence: float
    cited_article_ids: list[str]
    escalated: bool
    ticket_id: str | None = None


class MessageOut(BaseModel):
    message_id: str
    role: str
    text: str
    timestamp: str


class ConversationOut(BaseModel):
    id: str
    status: str
    messages: list[MessageOut]


class TicketOut(BaseModel):
    ticket_id: str
    conversation_id: str
    reason: str
    summary: str
    status: TicketStatus
    assigned_agent_id: str | None
    created_at: str
    updated_at: str


class TicketList(BaseModel):
    items: list[TicketOut]


class TicketUpdateRequest(RequestModel):
    status: TicketStatus
    assigned_agent_id: uuid.UUID | None = None


# Ready-made request bodies shown in the /docs "Try it out" forms. The first example in each
# group is filled in automatically; the others can be picked from the Examples dropdown.
LOGIN_EXAMPLES = {
    "customer": {
        "summary": "Demo customer account",
        "value": {"email": "customer@timberwickexample.com", "password": "customer-demo-pass"},
    },
    "agent": {
        "summary": "Demo agent account",
        "value": {"email": "agent@timberwickexample.com", "password": "agent-demo-pass"},
    },
}

CHAT_EXAMPLES = {
    "answered": {
        "summary": "New question the AI can answer",
        "value": {"message": "Is my broken tent zipper covered by the warranty?"},
    },
    "ask_for_person": {
        "summary": "Ask for a person (paste your conversation_id)",
        "value": {
            "conversation_id": "PASTE-CONVERSATION-ID-HERE",
            "message": "I want to talk to a real person",
        },
    },
    "not_covered": {
        "summary": "New question with no approved answer",
        "value": {"message": "Do you sell kayaks?"},
    },
    "account_change": {
        "summary": "New question that needs an account change",
        "value": {"message": "I forgot my password"},
    },
}

TICKET_UPDATE_EXAMPLES = {
    "resolve": {"summary": "Resolve the ticket", "value": {"status": "resolved"}},
    "assign": {"summary": "Assign the ticket to yourself", "value": {"status": "assigned"}},
}
