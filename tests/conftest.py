"""
Author: Jacob Wills-Brennan

Shared test fixtures. Every test gets a fresh app backed by an in-memory SQLite database.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.main import create_app
from app.models import User

PASSWORD = "test-password-123"


@pytest.fixture
def app():
    app = create_app(database_url="sqlite://")
    yield app
    # Tests that never start the app still need their database connection closed.
    app.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(app):
    def _make_user(email: str, role: str) -> User:
        with app.state.session_factory() as session:
            user = User(email=email, role=role, password_hash=hash_password(PASSWORD))
            session.add(user)
            session.commit()
            return user

    return _make_user


@pytest.fixture
def password() -> str:
    return PASSWORD


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def customer_headers(client, make_user):
    make_user("customer@timberwickexample.com", "customer")
    return login(client, "customer@timberwickexample.com")


@pytest.fixture
def other_customer_headers(client, make_user):
    make_user("other@timberwickexample.com", "customer")
    return login(client, "other@timberwickexample.com")


@pytest.fixture
def agent_headers(client, make_user):
    make_user("agent@timberwickexample.com", "agent")
    return login(client, "agent@timberwickexample.com")
