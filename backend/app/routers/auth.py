import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.auth import authenticate_user, create_access_token, verify_sso_token
from app.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    user = await authenticate_user(body.username, body.password)
    token = create_access_token(
        {
            "sub": str(user["id"]),
            "user": user["user"],
            "area": user["area"],
            "site": user["site"],
            "cambridgeUser": user["cambridgeUser"],
            "sellerId": user["sellerId"],
            "zoneId": user["zoneId"],
        }
    )
    return LoginResponse(access_token=token)


class SsoExchangeRequest(BaseModel):
    token: str


@router.post("/sso/exchange", response_model=LoginResponse)
async def sso_exchange(body: SsoExchangeRequest):
    user_id = verify_sso_token(body.token)

    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Source DB not configured")

    async with SessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT id, `user`, area, site, cambridgeUser, sellerId, zoneId "
                "FROM auth WHERE id = :uid LIMIT 1"
            ),
            {"uid": user_id},
        )
        row = result.mappings().first()

    if not row:
        logger.warning("SSO exchange: no user found for sub=%s", user_id)
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(
        {
            "sub": str(row["id"]),
            "user": row["user"],
            "area": row["area"],
            "site": row["site"],
            "cambridgeUser": row["cambridgeUser"],
            "sellerId": row["sellerId"],
            "zoneId": row["zoneId"],
        }
    )
    return LoginResponse(access_token=access_token)
