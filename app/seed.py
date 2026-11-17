"""
Authors: Jacob Wills-Brennan, Belqis Wahidi

Creates one demo customer and one demo agent so the Alpha can be tried from /docs.

Run with:  python -m app.seed
Passwords come from DEMO_CUSTOMER_PASSWORD and DEMO_AGENT_PASSWORD when set.
"""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import load_settings
from app.database import init_db, make_engine, make_session_factory
from app.models import User
from app.schemas import normalize_email

DEMO_USERS = (
    ("customer@timberwickexample.com", "customer", "DEMO_CUSTOMER_PASSWORD", "customer-demo-pass"),
    ("agent@timberwickexample.com", "agent", "DEMO_AGENT_PASSWORD", "agent-demo-pass"),
)


def seed_demo_users(session: Session) -> list[tuple[str, str]]:
    created = []
    for raw_email, role, env_name, default_password in DEMO_USERS:
        email = normalize_email(raw_email)
        if session.scalar(select(User).where(User.email == email)) is not None:
            continue
        password = os.getenv(env_name, default_password)
        session.add(User(email=email, role=role, password_hash=hash_password(password)))
        created.append((email, password))
    session.commit()
    return created


def main() -> None:
    engine = make_engine(load_settings().database_url)
    init_db(engine)
    with make_session_factory(engine)() as session:
        created = seed_demo_users(session)

    if not created:
        print("Demo users already exist.")
    for email, password in created:
        print(f"Created {email} with password {password}")


if __name__ == "__main__":
    main()
