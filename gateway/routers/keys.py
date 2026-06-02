from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
import uuid

from core.database import get_db
from core.auth_deps import get_current_user
from core.security import generate_api_key
from models.models import APIKey, User

router = APIRouter()


class CreateKeyRequest(BaseModel):
    name: str
    rate_limit_rpm: int | None = None
    rate_limit_tpd: int | None = None
    expires_at: datetime | None = None


class APIKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str
    key_prefix: str
    created_at: datetime
    expires_at: datetime | None


class APIKeyListItem(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    rate_limit_rpm: int | None
    rate_limit_tpd: int | None


@router.post("", response_model=APIKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(body: CreateKeyRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    full_key, key_prefix, key_hash = generate_api_key()
    api_key = APIKey(
        user_id=current_user.id, name=body.name, key_prefix=key_prefix,
        key_hash=key_hash, rate_limit_rpm=body.rate_limit_rpm,
        rate_limit_tpd=body.rate_limit_tpd, expires_at=body.expires_at
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    return APIKeyCreatedResponse(
        id=str(api_key.id), name=api_key.name, key=full_key,
        key_prefix=key_prefix, created_at=api_key.created_at, expires_at=api_key.expires_at
    )


@router.get("", response_model=list[APIKeyListItem])
async def list_api_keys(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        APIKeyListItem(
            id=str(k.id), name=k.name, key_prefix=k.key_prefix, is_active=k.is_active,
            created_at=k.created_at, last_used_at=k.last_used_at, expires_at=k.expires_at,
            rate_limit_rpm=k.rate_limit_rpm, rate_limit_tpd=k.rate_limit_tpd
        ) for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(APIKey).where(APIKey.id == uuid.UUID(key_id), APIKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    api_key.is_active = False
    await db.commit()


@router.post("/{key_id}/rotate", response_model=APIKeyCreatedResponse)
async def rotate_api_key(key_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(APIKey).where(
            APIKey.id == uuid.UUID(key_id),
            APIKey.user_id == current_user.id,
            APIKey.is_active == True  # noqa: E712
        )
    )
    old_key = result.scalar_one_or_none()
    if not old_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active API key not found")
    old_key.is_active = False
    full_key, key_prefix, key_hash = generate_api_key()
    new_key = APIKey(
        user_id=current_user.id, name=f"{old_key.name} (rotated)",
        key_prefix=key_prefix, key_hash=key_hash,
        rate_limit_rpm=old_key.rate_limit_rpm,
        rate_limit_tpd=old_key.rate_limit_tpd, expires_at=old_key.expires_at
    )
    db.add(new_key)
    await db.commit()
    await db.refresh(new_key)
    return APIKeyCreatedResponse(
        id=str(new_key.id), name=new_key.name, key=full_key,
        key_prefix=key_prefix, created_at=new_key.created_at, expires_at=new_key.expires_at
    )