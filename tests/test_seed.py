"""
Author: Jacob Wills-Brennan

Tests for the demo account seed script.
"""

from sqlalchemy import select

from app.auth import verify_password
from app.database import init_db, make_engine, make_session_factory
from app.models import User
from app.seed import seed_demo_users


def make_session():
    engine = make_engine("sqlite://")
    init_db(engine)
    return engine, make_session_factory(engine)()


def test_seed_creates_demo_accounts_once(monkeypatch):
    monkeypatch.setenv("DEMO_AGENT_PASSWORD", "agent-test-pass")
    engine, session = make_session()
    try:
        created = seed_demo_users(session)
        assert len(created) == 2
        assert seed_demo_users(session) == []

        users = {user.email: user for user in session.scalars(select(User))}
        assert set(users) == {"customer@timberwickexample.com", "agent@timberwickexample.com"}
        agent = users["agent@timberwickexample.com"]
        assert agent.role == "agent"
        assert verify_password("agent-test-pass", agent.password_hash)
    finally:
        session.close()
        engine.dispose()
