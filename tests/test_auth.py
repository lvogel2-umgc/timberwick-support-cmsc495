"""
Author: Luke Vogel

Tests for login, tokens, password hashing, and role checks.
"""

from types import SimpleNamespace

from app import auth
from app.auth import create_access_token, hash_password, verify_password


def assert_error(response, status_code: int, code: str) -> None:
    assert response.status_code == status_code
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_password_is_hashed_and_verifies():
    stored = hash_password("correct horse")
    assert "correct horse" not in stored
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("anything", "not-a-valid-hash")


def test_login_returns_token_and_role(client, make_user, password):
    make_user("agent@timberwickexample.com", "agent")
    response = client.post(
        "/api/v1/auth/login", json={"email": "agent@timberwickexample.com", "password": password}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["role"] == "agent"
    assert body["access_token"]


def test_login_with_wrong_password_fails(client, make_user):
    make_user("customer@timberwickexample.com", "customer")
    response = client.post(
        "/api/v1/auth/login", json={"email": "customer@timberwickexample.com", "password": "nope"}
    )
    assert_error(response, 401, "invalid_credentials")


def test_unknown_email_gets_same_error_as_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@timberwickexample.com", "password": "nope"}
    )
    assert_error(response, 401, "invalid_credentials")


def test_missing_token_is_rejected(client):
    response = client.get("/api/v1/agent/tickets")
    assert_error(response, 401, "unauthenticated")


def test_invalid_token_is_rejected(client):
    response = client.get(
        "/api/v1/agent/tickets", headers={"Authorization": "Bearer not.a.real.token"}
    )
    assert_error(response, 401, "unauthenticated")


def test_expired_token_is_rejected(app, client, make_user):
    user = make_user("agent@timberwickexample.com", "agent")
    token = create_access_token(
        SimpleNamespace(id=user.id, role=user.role), app.state.settings.secret_key, minutes=-1
    )
    response = client.get("/api/v1/agent/tickets", headers={"Authorization": f"Bearer {token}"})
    assert_error(response, 401, "token_expired")


def test_customer_cannot_use_agent_endpoints(client, customer_headers):
    response = client.get("/api/v1/agent/tickets", headers=customer_headers)
    assert_error(response, 403, "forbidden")


def test_agent_cannot_send_chat_messages(client, agent_headers):
    response = client.post(
        "/api/v1/chat/messages", json={"message": "hello"}, headers=agent_headers
    )
    assert_error(response, 403, "forbidden")


def test_login_email_is_case_insensitive(client, make_user, password):
    make_user("customer@timberwickexample.com", "customer")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "  Customer@TimberwickExample.COM ", "password": password},
    )
    assert response.status_code == 200


def test_unknown_email_still_runs_a_password_check(client, monkeypatch):
    calls = []
    real_verify = auth.verify_password

    def counting_verify(password, stored_hash):
        calls.append(stored_hash)
        return real_verify(password, stored_hash)

    monkeypatch.setattr(auth, "verify_password", counting_verify)
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@timberwickexample.com", "password": "nope"}
    )
    assert response.status_code == 401
    assert len(calls) == 1


def test_docs_show_real_error_responses(app):
    paths = app.openapi()["paths"]
    chat = paths["/api/v1/chat/messages"]["post"]["responses"]
    assert "400" in chat and "401" in chat
    assert all("422" not in op["responses"] for path in paths.values() for op in path.values())
