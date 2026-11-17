"""
Author: Belqis Wahidi

Unit tests for the KnowledgeRetriever and AIOrchestrator.
"""

import pytest

from app.config import load_settings
from app.orchestrator import AIOrchestrator
from app.retriever import Article, KnowledgeRetriever


@pytest.fixture(scope="module")
def retriever():
    return KnowledgeRetriever.from_json(load_settings().knowledge_base_path)


@pytest.fixture(scope="module")
def orchestrator(retriever):
    return AIOrchestrator(retriever, confidence_threshold=0.30)


def test_retriever_finds_matching_article(retriever):
    matches = retriever.search("How long do refunds take?")
    assert matches[0].title == "Refund timing"
    assert 0.0 < matches[0].relevance_score <= 1.0


def test_retriever_results_are_sorted_and_limited(retriever):
    matches = retriever.search("return shipping label for my order", top_k=3)
    assert 1 <= len(matches) <= 3
    scores = [match.relevance_score for match in matches]
    assert scores == sorted(scores, reverse=True)


def test_retriever_returns_empty_list_when_nothing_matches(retriever):
    assert retriever.search("quantum chromodynamics lattice") == []


def test_retriever_rejects_bad_top_k(retriever):
    with pytest.raises(ValueError):
        retriever.search("refund", top_k=0)


def test_retriever_needs_articles():
    with pytest.raises(ValueError):
        KnowledgeRetriever([])


def test_retriever_works_with_custom_articles():
    articles = [
        Article("a1", "Gift cards", "Gift cards never expire.", ("Do gift cards expire?",)),
        Article("a2", "Store hours", "Open 9 to 9.", ("When are you open?",)),
    ]
    matches = KnowledgeRetriever(articles).search("Do gift cards expire?")
    assert matches[0].article_id == "a1"


def test_orchestrator_answers_with_citation(orchestrator, retriever):
    result = orchestrator.respond("Do you offer free shipping?")
    assert not result.needs_escalation
    assert result.confidence >= 0.30
    assert len(result.cited_article_ids) == 1
    cited = retriever.get_article(result.cited_article_ids[0])
    assert cited.title == "Shipping options and costs"
    assert result.reply == cited.body


@pytest.mark.parametrize(
    "message",
    [
        "I want to talk to a real person",
        "Can I speak with an agent?",
        "human please",
        "Can I talk to a manager?",
        "I need a supervisor",
        "Can you connect me with an agent?",
    ],
)
def test_orchestrator_escalates_when_customer_asks_for_person(orchestrator, message):
    result = orchestrator.respond(message)
    assert result.needs_escalation
    assert result.reason == "customer_requested_agent"
    assert result.cited_article_ids == []


@pytest.mark.parametrize(
    "message", ["Please update the credit card on my account", "I forgot my password"]
)
def test_orchestrator_escalates_account_changes(orchestrator, message):
    result = orchestrator.respond(message)
    assert result.needs_escalation
    assert result.reason == "account_change_requires_agent"


def test_orchestrator_escalates_when_no_article_matches(orchestrator):
    result = orchestrator.respond("Tell me a joke")
    assert result.needs_escalation
    assert result.reason == "no_approved_answer"
    assert result.confidence == 0.0


def test_orchestrator_escalates_low_confidence(retriever):
    strict = AIOrchestrator(retriever, confidence_threshold=0.99)
    result = strict.respond("Can I rent a tent for the weekend?")
    assert result.needs_escalation
    assert result.reason == "low_confidence"
    assert 0.0 < result.confidence < 0.99


def test_orchestrator_rejects_invalid_threshold(retriever):
    with pytest.raises(ValueError):
        AIOrchestrator(retriever, confidence_threshold=1.5)


def test_mentioning_an_agent_is_not_a_request_for_one(orchestrator, retriever):
    result = orchestrator.respond(
        "The agent I spoke with said my refund was approved, when will I get it?"
    )
    assert not result.needs_escalation
    assert retriever.get_article(result.cited_article_ids[0]).title == "Refund timing"


def test_respond_accepts_unit3_interface_arguments(orchestrator):
    result = orchestrator.respond(
        "Do you offer free shipping?", sanitized_context=[], customer_scope="customer"
    )
    assert not result.needs_escalation


def test_missing_article_escalates_instead_of_crashing():
    class BrokenIndex(KnowledgeRetriever):
        def get_article(self, article_id):
            return None

    articles = [Article("a1", "Gift cards", "Gift cards never expire.", ("Do gift cards expire?",))]
    result = AIOrchestrator(BrokenIndex(articles), 0.30).respond("Do gift cards expire?")
    assert result.needs_escalation
    assert result.reason == "no_approved_answer"
