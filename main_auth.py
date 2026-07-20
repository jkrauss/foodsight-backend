"""JWT authentication and password hashing for Foodsight."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import toml
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv(".env")

config = toml.load("pipeline/data/customer.toml")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
ALGORITHM = os.environ.get("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = config["base"]["login_valid_minutes"]
SLACK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")

_users_db: list[dict] = config["users"]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Token(BaseModel):
    """JWT token returned to the client after successful login."""
    access_token: str
    token_type: str
    expires: str


class TokenData(BaseModel):
    """Data extracted from a validated JWT."""
    username: Optional[str] = None


class User(BaseModel):
    """Public user representation (no password)."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    """User with hashed password, as stored in the config."""
    hashed_password: str


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    return _pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return _pwd_context.hash(password)


# ---------------------------------------------------------------------------
# User lookup
# ---------------------------------------------------------------------------

def _get_user(db: list[dict], username: str) -> Optional[UserInDB]:
    result = [e for e in db if e["username"] == username]
    return UserInDB(**result[0]) if result else None


def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """Return the user if credentials are valid, else None."""
    user = _get_user(_users_db, username)
    if not user or not _verify_password(password, user.hashed_password):
        return None
    return user


# ---------------------------------------------------------------------------
# JWT creation & validation
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a signed JWT and return (token, expiry_datetime)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode["exp"] = expire
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire.astimezone()


async def _get_current_user(token: str = Depends(_oauth2_scheme)) -> User:
    """Decode the JWT from the Authorization header and return the user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = _get_user(_users_db, username=username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(_get_current_user)) -> User:
    """Ensure the authenticated user is not disabled."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
