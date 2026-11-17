"""
Author: Luke Vogel

Authentication and role checks: password hashing, short-lived bearer tokens, and the login
endpoint. The user's identity always comes from the token, never from a request body.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Body, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import AuthenticationError, AuthorizationError
from app.models import User
from app.schemas import ERROR_RESPONSES, LOGIN_EXAMPLES, LoginRequest, TokenResponse

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
    responses={code: ERROR_RESPONSES[code] for code in (400, 401)},
)
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${salt.hex()}${digest.hex()}"


# Checked when an email is not found, so unknown emails take as long as wrong passwords.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_access_token(user: User, secret_key: str, minutes: int) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": user.id,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(claims, secret_key, algorithm=ALGORITHM)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")
    try:
        claims = jwt.decode(
            credentials.credentials, request.app.state.settings.secret_key, algorithms=[ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired.", code="token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid token.") from exc

    user = db.get(User, claims.get("sub"))
    if user is None:
        raise AuthenticationError("Invalid token.")
    return user


def require_role(role: str):
    def check_role(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise AuthorizationError(f"This action requires the {role} role.")
        return user

    return check_role


require_agent = require_role("agent")


@router.post("/login", response_model=TokenResponse)
def login(
    body: Annotated[LoginRequest, Body(openapi_examples=LOGIN_EXAMPLES)],
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == body.email))
    # Always run one password check so response time does not reveal which emails exist.
    stored_hash = user.password_hash if user is not None else _DUMMY_HASH
    password_ok = verify_password(body.password, stored_hash)
    if user is None or not password_ok:
        raise AuthenticationError("Incorrect email or password.", code="invalid_credentials")

    settings = request.app.state.settings
    token = create_access_token(user, settings.secret_key, settings.token_minutes)
    return TokenResponse(access_token=token, role=user.role)
