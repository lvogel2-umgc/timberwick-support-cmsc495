"""
Author: Belqis Wahidi

AI quality check on a reviewed test set. None of these questions are copied from the knowledge
base, so they measure how well the AI handles new wording. CI fails if quality drops below:
  answer accuracy >= 0.80, escalation recall >= 0.90, unsupported answer rate <= 0.15
"""

import pytest

from app.config import load_settings
from app.orchestrator import AIOrchestrator
from app.retriever import KnowledgeRetriever

# (question, title of the article that should answer it)
ANSWERABLE = [
    ("Is there a time limit for returning a jacket I haven't worn?", "Return policy"),
    ("I used my headlamp once and it stopped working, can I still return it?", "Return policy"),
    ("How do I mail back a pair of trekking poles?", "How to start a return"),
    ("Can I drop off my online return at a store?", "How to start a return"),
    ("How many business days until my refund is processed?", "Refund timing"),
    ("I haven't received a tracking number for my order", "Tracking an order"),
    ("What does expedited shipping cost?", "Shipping options and costs"),
    ("Is there free shipping on big orders?", "Shipping options and costs"),
    (
        "I need to change the size on an order I placed 10 minutes ago",
        "Changing or canceling an order",
    ),
    ("The seam on my tent started leaking, will you fix it?", "Tent and shelter warranty"),
    ("Is a broken tent zipper covered by the warranty?", "Tent and shelter warranty"),
    (
        "Down or synthetic, which sleeping bag is better for wet weather?",
        "Choosing a sleeping bag temperature rating",
    ),
    ("How do I measure myself for a backpack?", "Backpack sizing"),
    ("How much room should I leave at the toe of hiking boots?", "Hiking boot sizing and break-in"),
    ("Do you rent camp stoves?", "Gear rental program"),
    ("Are your stores open on Sundays?", "Store hours and locations"),
    ("Will you match a competitor's lower price?", "Price match policy"),
    ("My order showed up with a ripped box and a broken water filter", "Damaged or missing items"),
    ("How do I redeem my rewards points?", "Trailhead Rewards membership"),
    ("Can stove fuel be sent to a PO box?", "Shipping restrictions for stove fuel"),
]

# Questions that must go to a person: requests for a human, account changes, and topics the
# knowledge base does not cover.
SHOULD_ESCALATE = [
    "I want to talk to a real person",
    "Can I speak with an agent please",
    "Get me a human representative",
    "Please update the credit card on my account",
    "I need to reset my password",
    "Delete my account",
    "Do you sell kayaks?",
    "Can you help me file my taxes?",
    "What is the weather in Denver tomorrow?",
    "Tell me a joke",
]


@pytest.fixture(scope="module")
def metrics():
    settings = load_settings()
    retriever = KnowledgeRetriever.from_json(settings.knowledge_base_path)
    orchestrator = AIOrchestrator(retriever, settings.confidence_threshold)

    correct = unsupported = 0
    for question, expected_title in ANSWERABLE:
        result = orchestrator.respond(question)
        if result.needs_escalation:
            continue
        cited_title = retriever.get_article(result.cited_article_ids[0]).title
        if cited_title == expected_title:
            correct += 1
        else:
            unsupported += 1

    escalated = sum(orchestrator.respond(q).needs_escalation for q in SHOULD_ESCALATE)

    results = {
        "answer_accuracy": correct / len(ANSWERABLE),
        "unsupported_answer_rate": unsupported / len(ANSWERABLE),
        "escalation_recall": escalated / len(SHOULD_ESCALATE),
    }
    print(f"\nAI quality metrics: {results}")
    return results


def test_answer_accuracy(metrics):
    assert metrics["answer_accuracy"] >= 0.80


def test_escalation_recall(metrics):
    assert metrics["escalation_recall"] >= 0.90


def test_unsupported_answer_rate(metrics):
    assert metrics["unsupported_answer_rate"] <= 0.15
