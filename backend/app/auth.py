import logging

import httpx
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

logger = logging.getLogger(__name__)
bearer = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer),
) -> dict:
    token = credentials.credentials
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.supabase_url}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_anon_key,
                },
            )
        if resp.status_code != 200:
            logger.warning("Supabase token rejected: %s %s", resp.status_code, resp.text)
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return resp.json()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Auth verification error: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token")
