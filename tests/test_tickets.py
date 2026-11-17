"""
Author: Jacob Wills-Brennan

Tests for ticket creation through escalation and the agent ticket endpoints.
"""

import uuid

import pytest

TICKETS_URL = "/api/v1/agent/tickets"


def escalate(client, headers, conversation_id=None) -> dict:
    body = {"message": "I want to talk to a real person"}
    if conversation_id:
        body["conversation_id"] = conversation_id
    response = client.post("/api/v1/chat/messages", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_escalation_creates_open_ticket(client, customer_headers, agent_headers):
    chat = escalate(client, customer_headers)
    assert chat["escalated"] is True
    assert chat["ticket_id"] in chat["reply"]

    items = client.get(TICKETS_URL, headers=agent_headers).json()["items"]
    assert len(items) == 1
    ticket = items[0]
    assert ticket["ticket_id"] == chat["ticket_id"]
    assert ticket["conversation_id"] == chat["conversation_id"]
    assert ticket["status"] == "open"
    assert ticket["reason"] == "customer_requested_agent"
    assert ticket["created_at"].endswith("+00:00")


def test_repeat_escalation_reuses_the_same_ticket(client, customer_headers, agent_headers):
    first = escalate(client, customer_headers)
    second = escalate(client, customer_headers, first["conversation_id"])
    assert first["ticket_id"] == second["ticket_id"]
    assert len(client.get(TICKETS_URL, headers=agent_headers).json()["items"]) == 1


def test_agent_assigns_then_resolves_ticket(client, customer_headers, agent_headers):
    ticket_id = escalate(client, customer_headers)["ticket_id"]

    assigned = client.patch(
        f"{TICKETS_URL}/{ticket_id}", json={"status": "assigned"}, headers=agent_headers
    )
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"
    assert assigned.json()["assigned_agent_id"] is not None

    resolved = client.patch(
        f"{TICKETS_URL}/{ticket_id}", json={"status": "resolved"}, headers=agent_headers
    )
    assert resolved.json()["status"] == "resolved"


def test_resolved_ticket_cannot_be_reopened(client, customer_headers, agent_headers):
    ticket_id = escalate(client, customer_headers)["ticket_id"]
    client.patch(f"{TICKETS_URL}/{ticket_id}", json={"status": "resolved"}, headers=agent_headers)

    response = client.patch(
        f"{TICKETS_URL}/{ticket_id}", json={"status": "open"}, headers=agent_headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_transition"


def test_cannot_assign_ticket_to_a_customer(client, make_user, customer_headers, agent_headers):
    customer = make_user("someone@timberwickexample.com", "customer")
    ticket_id = escalate(client, customer_headers)["ticket_id"]
    response = client.patch(
        f"{TICKETS_URL}/{ticket_id}",
        json={"status": "assigned", "assigned_agent_id": customer.id},
        headers=agent_headers,
    )
    assert response.status_code == 400


def test_filter_tickets_by_status(client, customer_headers, other_customer_headers, agent_headers):
    first = escalate(client, customer_headers)["ticket_id"]
    escalate(client, other_customer_headers)
    client.patch(f"{TICKETS_URL}/{first}", json={"status": "resolved"}, headers=agent_headers)

    open_items = client.get(f"{TICKETS_URL}?status=open", headers=agent_headers).json()["items"]
    resolved = client.get(f"{TICKETS_URL}?status=resolved", headers=agent_headers).json()["items"]
    assert len(open_items) == 1
    assert [item["ticket_id"] for item in resolved] == [first]


def test_unknown_ticket_returns_404(client, agent_headers):
    response = client.patch(
        f"{TICKETS_URL}/{uuid.uuid4()}", json={"status": "resolved"}, headers=agent_headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


@pytest.mark.parametrize("query", ["?limit=0", "?limit=101", "?status=closed"])
def test_invalid_ticket_queries_are_rejected(client, agent_headers, query):
    response = client.get(f"{TICKETS_URL}{query}", headers=agent_headers)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_input"
