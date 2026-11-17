"""
Author: Belqis Wahidi

AIOrchestrator: decides how the AI responds to a customer message.

The orchestrator checks for messages that must go to a person, searches the approved knowledge
base, and returns an AIResult with the reply, a confidence score, the cited article, and whether
the conversation needs to be escalated to a support agent.
"""

import logging
import re
from dataclasses import dataclass, field

from app.retriever import KnowledgeRetriever

logger = logging.getLogger(__name__)

# Phrases that mean the customer wants a person instead of the AI.
# "agent" only counts when it follows a request verb, so "the agent I spoke with" does not
# trigger a handoff on its own.
AGENT_REQUEST_PATTERNS = (
    r"\b(real|live) person\b",
    r"\bhuman\b",
    r"\brepresentative\b",
    r"\b(manager|supervisor)\b",
    r"\b(speak|talk|chat|connect|transfer)\b.*\b(agent|someone|somebody)\b",
)

# Account changes the AI is not allowed to make, so a person has to handle them.
ACCOUNT_CHANGE_PATTERNS = (
    r"\bpassword\b",
    r"\bcredit card\b",
    r"\bpayment (method|info|information|details)\b",
    r"\b(delete|close|deactivate|cancel) my account\b",
    r"\b(change|update)\b.*\baccount\b",
)

ESCALATION_REPLY = (
    "I want to make sure you get the right help, so I'm connecting you with a support agent."
)
LOW_CONFIDENCE_REPLY = (
    "I'm not confident I have the right answer for that, so I'm passing your question to a "
    "support agent."
)


@dataclass
class AIResult:
    reply: str
    confidence: float
    cited_article_ids: list[str] = field(default_factory=list)
    needs_escalation: bool = False
    reason: str | None = None


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


class AIOrchestrator:
    """Coordinates escalation rules and knowledge retrieval for one customer message."""

    def __init__(self, retriever: KnowledgeRetriever, confidence_threshold: float) -> None:
        if not 0.0 <= confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0.")
        self._retriever = retriever
        self._threshold = confidence_threshold

    def respond(
        self,
        message: str,
        sanitized_context: list[str] | None = None,
        customer_scope: str | None = None,
    ) -> AIResult:
        """Matches the Unit 3 interface. sanitized_context and customer_scope are accepted now
        so callers do not change later; the Alpha does not use them yet."""
        text = message.lower()

        if _matches_any(text, AGENT_REQUEST_PATTERNS):
            return AIResult(
                ESCALATION_REPLY, 0.0, needs_escalation=True, reason="customer_requested_agent"
            )

        if _matches_any(text, ACCOUNT_CHANGE_PATTERNS):
            return AIResult(
                ESCALATION_REPLY, 0.0, needs_escalation=True, reason="account_change_requires_agent"
            )

        matches = self._retriever.search(message, top_k=1)
        if not matches:
            return AIResult(
                LOW_CONFIDENCE_REPLY, 0.0, needs_escalation=True, reason="no_approved_answer"
            )

        best = matches[0]
        if best.relevance_score < self._threshold:
            return AIResult(
                LOW_CONFIDENCE_REPLY,
                best.relevance_score,
                needs_escalation=True,
                reason="low_confidence",
            )

        article = self._retriever.get_article(best.article_id)
        if article is None:
            # The index and article list disagree; hand off instead of failing.
            logger.warning("Matched article %s was not found; escalating.", best.article_id)
            return AIResult(
                LOW_CONFIDENCE_REPLY, 0.0, needs_escalation=True, reason="no_approved_answer"
            )

        return AIResult(
            reply=article.body,
            confidence=best.relevance_score,
            cited_article_ids=[best.article_id],
        )
