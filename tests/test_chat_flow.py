"""
Authors: Jacob Wills-Brennan, Luke Vogel, Belqis Wahidi

End-to-end tests that run the full flow through every module: login, chat, AI answer,
escalation to a ticket, and agent handling. Also covers input validation, access control,
AI failure handling, and response time.
"""

import time
import uuid

import pytest

CHAT_URL = "/api/v1/chat/messages"


def test_health_check(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_full_customer_and_agent_flow(client, customer_headers, agent_headers):
    # 1. Customer asks a question the knowledge base can answer.
    answer = client.post(
        CHAT_URL, json={"message": "How long do refunds take?"}, headers=customer_headers
    ).json()
    assert answer["escalated"] is False
    assert answer["ticket_id"] is None
    assert len(answer["cited_article_ids"]) == 1
    assert "business days" in answer["reply"]
    conversation_id = answer["conversation_id"]

    # 2. Customer follows up in the same conversation and asks for a person.
    handoff = client.post(
        CHAT_URL,
        json={"conversation_id": conversation_id, "message": "I'd like to talk to a human"},
        headers=customer_headers,
    ).json()
    assert handoff["conversation_id"] == conversation_id
    assert handoff["escalated"] is True

    # 3. The conversation history has all four messages in order.
    history = client.get(f"/api/v1/conversations/{conversation_id}", headers=customer_headers)
    body = history.json()
    assert body["status"] == "escalated"
    assert [m["role"] for m in body["messages"]] == [
        "customer",
        "assistant",
        "customer",
        "assistant",
    ]

    # 4. An agent sees the ticket, can read the conversation, and resolves the ticket.
    tickets = client.get("/api/v1/agent/tickets", headers=agent_headers).json()["items"]
    assert tickets[0]["ticket_id"] == handoff["ticket_id"]
    agent_view = client.get(f"/api/v1/conversations/{conversation_id}", headers=agent_headers)
    assert agent_view.status_code == 200
    resolved = client.patch(
        f"/api/v1/agent/tickets/{handoff['ticket_id']}",
        json={"status": "resolved"},
        headers=agent_headers,
    )
    assert resolved.json()["status"] == "resolved"


def test_customer_cannot_read_another_customers_conversation(
    client, customer_headers, other_customer_headers
):
    chat = client.post(
        CHAT_URL, json={"message": "What are your store hours?"}, headers=customer_headers
    ).json()
    url = f"/api/v1/conversations/{chat['conversation_id']}"
    assert client.get(url, headers=other_customer_headers).status_code == 403

    reply = client.post(
        CHAT_URL,
        json={"conversation_id": chat["conversation_id"], "message": "hi"},
        headers=other_customer_headers,
    )
    assert reply.status_code == 403


def test_unknown_conversation_returns_404(client, customer_headers):
    response = client.get(f"/api/v1/conversations/{uuid.uuid4()}", headers=customer_headers)
    assert response.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"message": ""},
        {"message": "   "},
        {"message": "x" * 2001},
        {},
        {"message": "hi", "user_id": "someone-else"},
        {"message": "hi", "conversation_id": "not-a-uuid"},
    ],
)
def test_invalid_chat_input_is_rejected(client, customer_headers, body):
    response = client.post(CHAT_URL, json=body, headers=customer_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"


def test_ai_failure_gives_fallback_reply_and_ticket(app, client, customer_headers, monkeypatch):
    def broken_respond(message):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(app.state.orchestrator, "respond", broken_respond)
    response = client.post(
        CHAT_URL, json={"message": "Where is my order?"}, headers=customer_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalated"] is True
    assert body["ticket_id"] is not None
    assert "trouble" in body["reply"]


def test_chat_response_time_is_under_one_second(client, customer_headers):
    start = time.perf_counter()
    response = client.post(
        CHAT_URL, json={"message": "Do you price match?"}, headers=customer_headers
    )
    elapsed = time.perf_counter() - start
    assert response.status_code == 200
    assert elapsed < 1.0
