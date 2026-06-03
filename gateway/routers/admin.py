from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta

from core.database import get_db
from core.auth_deps import get_current_user
from models.models import User, AuditLog, APIKey

router = APIRouter()


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Usage summary for the dashboard header cards."""
    since = datetime.utcnow() - timedelta(hours=24)

    # Total requests last 24h
    total_req = await db.execute(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= since)
    )
    total_requests = total_req.scalar() or 0

    # Total tokens last 24h
    total_tok = await db.execute(
        select(func.sum(AuditLog.prompt_tokens + AuditLog.completion_tokens))
        .where(AuditLog.timestamp >= since)
    )
    total_tokens = total_tok.scalar() or 0

    # Average latency last 24h
    avg_lat = await db.execute(
        select(func.avg(AuditLog.latency_ms)).where(AuditLog.timestamp >= since)
    )
    avg_latency = round(avg_lat.scalar() or 0, 1)

    # Requests by provider
    by_provider = await db.execute(
        select(AuditLog.provider, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= since, AuditLog.provider.isnot(None))
        .group_by(AuditLog.provider)
    )
    provider_breakdown = {row[0]: row[1] for row in by_provider.fetchall()}

    # Requests by model
    by_model = await db.execute(
        select(AuditLog.model, func.count(AuditLog.id))
        .where(AuditLog.timestamp >= since, AuditLog.model.isnot(None))
        .group_by(AuditLog.model)
        .order_by(desc(func.count(AuditLog.id)))
        .limit(5)
    )
    model_breakdown = [{"model": row[0], "requests": row[1]} for row in by_model.fetchall()]

    # Total users
    total_users = await db.execute(select(func.count(User.id)))
    user_count = total_users.scalar() or 0

    # Error rate
    error_req = await db.execute(
        select(func.count(AuditLog.id))
        .where(AuditLog.timestamp >= since, AuditLog.status_code >= 400)
    )
    error_count = error_req.scalar() or 0
    error_rate = round((error_count / total_requests * 100) if total_requests > 0 else 0, 1)

    return {
        "total_requests_24h": total_requests,
        "total_tokens_24h": total_tokens,
        "avg_latency_ms": avg_latency,
        "error_rate_pct": error_rate,
        "total_users": user_count,
        "by_provider": provider_breakdown,
        "by_model": model_breakdown,
    }


@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(20, le=100),
    provider: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Paginated audit log for the dashboard table."""
    query = select(AuditLog).order_by(desc(AuditLog.timestamp))

    if provider:
        query = query.where(AuditLog.provider == provider)

    query = query.offset((page - 1) * limit).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat(),
            "method": log.method,
            "path": log.path,
            "status_code": log.status_code,
            "latency_ms": log.latency_ms,
            "provider": log.provider,
            "model": log.model,
            "prompt_tokens": log.prompt_tokens,
            "completion_tokens": log.completion_tokens,
            "ip_address": log.ip_address,
        }
        for log in logs
    ]


@router.get("/users")
async def get_users(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User list with API key counts."""
    result = await db.execute(
        select(User).order_by(desc(User.created_at))
    )
    users = result.scalars().all()

    user_list = []
    for user in users:
        key_count = await db.execute(
            select(func.count(APIKey.id))
            .where(APIKey.user_id == user.id, APIKey.is_active == True)  # noqa: E712
        )
        user_list.append({
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "team": user.team,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "active_keys": key_count.scalar() or 0,
        })

    return user_list