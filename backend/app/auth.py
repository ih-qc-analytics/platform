import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal

logger = logging.getLogger(__name__)
bearer = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_HOURS = 8

# In-memory JTI replay protection for SSO tokens (single-instance safe).
# key: jti str, value: exp unix timestamp used for cleanup.
_used_jtis: dict[str, float] = {}


def create_access_token(payload: dict) -> str:
    data = payload.copy()
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=_ACCESS_TOKEN_EXPIRE_HOURS)
    return jwt.encode(data, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
) -> dict:
    """Dependency for protected routes — pure crypto, no DB call."""
    return decode_access_token(credentials.credentials)


def _consume_jti(jti: str, exp: float) -> None:
    """Mark a JTI as used. Cleans up expired entries on each call."""
    now = time.time()
    for k in [k for k, v in _used_jtis.items() if v < now]:
        del _used_jtis[k]
    if jti in _used_jtis:
        raise HTTPException(status_code=401, detail="Token already used")
    _used_jtis[jti] = exp


def verify_sso_token(token: str) -> str:
    """
    Validate an SSO handoff token from the main portal.
    Returns the user's auth.id (as str) on success.
    Raises HTTPException(401) on any failure — never leaks secret material to logs.
    """
    if not settings.sso_shared_secret:
        raise HTTPException(status_code=503, detail="SSO not configured")
    try:
        payload = jwt.decode(
            token,
            settings.sso_shared_secret,
            algorithms=["HS256"],  # pinned — never infer from header
        )
    except JWTError:
        logger.warning("SSO token rejected: invalid signature or expired")
        raise HTTPException(status_code=401, detail="Invalid or expired SSO token")

    jti = payload.get("jti")
    exp = payload.get("exp")
    sub = payload.get("sub")

    if not jti or not sub:
        logger.warning("SSO token rejected: missing required claims")
        raise HTTPException(status_code=401, detail="Invalid SSO token")

    _consume_jti(jti, float(exp))  # raises 401 if replayed
    return str(sub)


def _parse_dev_users() -> dict[str, dict]:
    """Parse DEV_AUTH_USERS="email:pass,email2:pass2" into a lookup dict."""
    users: dict[str, dict] = {}
    for i, entry in enumerate(settings.dev_auth_users.split(",")):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":", 1)
        if len(parts) != 2:
            continue
        username, password = parts
        users[username.strip()] = {
            "id": -(i + 1),  # negative IDs to distinguish from prod users
            "user": username.strip(),
            "password": password.strip(),
            "area": "dev",
            "site": "dev",
            "cambridgeUser": None,
            "sellerId": None,
            "zoneId": None,
        }
    return users


async def authenticate_user(username: str, password: str) -> dict:
    """
    Verify credentials and return the user dict.

    Non-prod: checks DEV_AUTH_USERS env var only (plain-text comparison).
              MySQL is never queried, so no source DB connection is needed.
    Prod:     queries the MySQL auth table once and verifies the bcrypt hash.
    """
    if settings.env_mode != "prod":
        dev_users = _parse_dev_users()
        user = dev_users.get(username)
        if user and user["password"] == password:
            return user
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Prod path — single MySQL query
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Source DB not configured")

    async with SessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT id, `user`, password, area, site, cambridgeUser, sellerId, zoneId "
                "FROM auth WHERE `user` = :username LIMIT 1"
            ),
            {"username": username},
        )
        row = result.mappings().first()

    if not row or not pwd_context.verify(password, row["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return dict(row)
