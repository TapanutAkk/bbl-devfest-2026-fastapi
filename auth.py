import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from database import SessionDep, User

# Logged-in sessions live in memory: token -> user id. Restarting the
# server logs everyone out.
auth_sessions: dict[str, int] = {}

PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(check.hex(), digest)


def create_session(user: User) -> str:
    token = secrets.token_urlsafe(32)
    auth_sessions[token] = user.id
    return token


def extract_token(request: Request) -> str | None:
    """Token from the Bearer header (API clients) or the session cookie
    (browser)."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.removeprefix("Bearer ")
    return request.cookies.get("session_token")


def get_optional_user(request: Request, session: SessionDep) -> User | None:
    token = extract_token(request)
    user_id = auth_sessions.get(token) if token else None
    return session.get(User, user_id) if user_id is not None else None


def require_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentUser = Annotated[User, Depends(require_user)]
