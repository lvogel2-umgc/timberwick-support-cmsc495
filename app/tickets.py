"""
Author: Jacob Wills-Brennan

EscalationService and the agent ticket endpoints. Tickets are created when the AI hands a
conversation to a person, and agents move them through open, assigned, and resolved.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_agent
from app.database import get_db
from app.errors import InvalidInputError, NotFoundError
from app.models import Conversation, Ticket, User
from app.schemas import (
    ERROR_RESPONSES,
    TICKET_UPDATE_EXAMPLES,
    TicketList,
    TicketOut,
    TicketStatus,
    TicketUpdateRequest,
    to_utc_iso,
)

router = APIRouter(
    prefix="/api/v1/agent/tickets", tags=["agent tickets"], responses=ERROR_RESPONSES
)

ALLOWED_TRANSITIONS = {
    "open": {"assigned", "resolved"},
    "assigned": {"open", "resolved"},
    "resolved": set(),
}


def ticket_to_out(ticket: Ticket) -> TicketOut:
    return TicketOut(
        ticket_id=ticket.id,
        conversation_id=ticket.conversation_id,
        reason=ticket.reason,
        summary=ticket.summary,
        status=ticket.status,
        assigned_agent_id=ticket.assigned_agent_id,
        created_at=to_utc_iso(ticket.created_at),
        updated_at=to_utc_iso(ticket.updated_at),
    )


class EscalationService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_ticket(self, conversation: Conversation, reason: str, summary: str) -> Ticket:
        """Create a ticket, or return the conversation's existing unresolved ticket."""
        existing = self._db.scalar(
            select(Ticket).where(
                Ticket.conversation_id == conversation.id, Ticket.status != "resolved"
            )
        )
        if existing is not None:
            return existing

        ticket = Ticket(conversation_id=conversation.id, reason=reason, summary=summary[:255])
        self._db.add(ticket)
        self._db.flush()
        return ticket

    def list_tickets(self, status: str | None, limit: int) -> list[Ticket]:
        query = select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)
        if status is not None:
            query = query.where(Ticket.status == status)
        return list(self._db.scalars(query))

    def update_ticket(
        self, ticket_id: str, status: str, assigned_agent_id: str | None, acting_agent: User
    ) -> Ticket:
        ticket = self._db.get(Ticket, ticket_id)
        if ticket is None:
            raise NotFoundError("Ticket not found.")

        if status != ticket.status and status not in ALLOWED_TRANSITIONS[ticket.status]:
            raise InvalidInputError(
                f"Cannot change a ticket from {ticket.status} to {status}.",
                code="invalid_transition",
            )

        if status == "assigned":
            agent_id = assigned_agent_id or acting_agent.id
            agent = self._db.get(User, agent_id)
            if agent is None or agent.role != "agent":
                raise InvalidInputError("assigned_agent_id must belong to an agent.")
            ticket.assigned_agent_id = agent_id
        elif status == "open":
            ticket.assigned_agent_id = None

        ticket.status = status
        self._db.commit()
        return ticket


@router.get("", response_model=TicketList)
def list_tickets(
    status: TicketStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> TicketList:
    tickets = EscalationService(db).list_tickets(status, limit)
    return TicketList(items=[ticket_to_out(ticket) for ticket in tickets])


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: uuid.UUID,
    body: Annotated[TicketUpdateRequest, Body(openapi_examples=TICKET_UPDATE_EXAMPLES)],
    agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> TicketOut:
    assigned = str(body.assigned_agent_id) if body.assigned_agent_id else None
    ticket = EscalationService(db).update_ticket(str(ticket_id), body.status, assigned, agent)
    return ticket_to_out(ticket)
