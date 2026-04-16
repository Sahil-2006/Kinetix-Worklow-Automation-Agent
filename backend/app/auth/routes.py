"""Auth API routes — register, login, refresh, profile, Google OAuth."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any, Dict, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from ..core.config import GOOGLE_CLIENT_ID
from ..storage.db import TraceStore
from .dependencies import get_current_user
from .jwt_handler import create_access_token, create_refresh_token, verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# The store is injected at mount-time from main.py via the app state.
# We use a module-level holder so the router can be self-contained.
_store: TraceStore | None = None


def init_auth_routes(store: TraceStore) -> APIRouter:
    """Call once at startup to inject the DB store into the router."""
    global _store
    _store = store
    return router


def _get_store() -> TraceStore:
    if _store is None:
        raise RuntimeError("Auth store not initialised")
    return _store


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Pydantic schemas ──────────────────────────────────────────

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google ID token (JWT from GIS)")


# ── Register ──────────────────────────────────────────────────


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest):
    store = _get_store()

    # Check if username already exists
    existing = store.get_user_by_username(body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    # Create user
    user_id = str(uuid.uuid4())
    pw_hash = _hash_password(body.password)
    store.create_user(
        user_id=user_id,
        username=body.username,
        email=body.email,
        password_hash=pw_hash,
        role="user",
    )

    access_token = create_access_token(user_id, "user")
    refresh_token = create_refresh_token(user_id)

    logger.info("User registered: %s (id=%s)", body.username, user_id)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={"id": user_id, "username": body.username, "role": "user"},
    )


# ── Login ─────────────────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest):
    store = _get_store()

    user = store.get_user_by_username(body.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.get("password_hash") or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"])

    logger.info("User logged in: %s", body.username)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    )


# ── Google OAuth ──────────────────────────────────────────────


@router.post("/google", response_model=AuthResponse)
def google_login(body: GoogleAuthRequest):
    """Verify a Google ID token and log the user in (or auto-register)."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured on this server",
        )

    # Verify the token with Google
    try:
        idinfo = google_id_token.verify_oauth2_token(
            body.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        logger.warning("Google token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token",
        )

    google_sub = idinfo.get("sub")
    email = idinfo.get("email", "")
    name = idinfo.get("name", "")
    picture = idinfo.get("picture", "")

    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token missing required fields (sub, email)",
        )

    store = _get_store()

    # 1. Check if we already have a user with this Google ID
    user = store.get_user_by_google_id(google_sub)

    if not user:
        # 2. Check if a user with the same email exists (link accounts)
        user = store.get_user_by_email(email)
        if user:
            # Link the existing account to Google
            store.update_user_google_id(user["id"], google_sub, picture)
            user = store.get_user_by_id(user["id"])
        else:
            # 3. Create a brand-new user
            user_id = str(uuid.uuid4())
            # Generate a unique username from the email prefix
            base_username = email.split("@")[0].replace(".", "_").replace("+", "_")[:30]
            username = base_username
            # Ensure uniqueness
            counter = 1
            while store.get_user_by_username(username):
                username = f"{base_username}_{counter}"
                counter += 1

            store.create_user(
                user_id=user_id,
                username=username,
                email=email,
                password_hash=None,
                role="user",
                google_id=google_sub,
                avatar_url=picture,
            )
            user = store.get_user_by_id(user_id)

    access_token = create_access_token(user["id"], user["role"])
    refresh_token = create_refresh_token(user["id"])

    logger.info("Google login: %s (%s)", user["username"], email)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "avatar_url": user.get("avatar_url", ""),
        },
    )


# ── Refresh ───────────────────────────────────────────────────


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh", response_model=AuthResponse)
def refresh(body: RefreshRequest):
    payload = verify_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    store = _get_store()
    user = store.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    access_token = create_access_token(user["id"], user["role"])
    new_refresh = create_refresh_token(user["id"])

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user={
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
    )


# ── Profile ───────────────────────────────────────────────────


@router.get("/me")
def profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Return current user info. Note: no PII (email) is returned."""
    store = _get_store()
    user = store.get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "avatar_url": user.get("avatar_url", ""),
        "created_at": user["created_at"],
    }
