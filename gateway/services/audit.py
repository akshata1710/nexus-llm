import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from models.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    user_id: str,
    api_key_id: str | None,
    method: str,
    path: str,
    status_code: int,
    latency_ms: int,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    ip_address: str | None = None,
    error_message: str | None = None,
):
    """
    Write a single audit log entry. Called after every proxy request.
    Stores metadata only — never the prompt or completion content.
    """
    import uuid
    log = AuditLog(
        user_id=uuid.UUID(user_id) if user_id else None,
        api_key_id=uuid.UUID(api_key_id) if api_key_id else None,
        method=method,
        path=path,
        status_code=status_code,
        latency_ms=latency_ms,
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        timestamp=datetime.utcnow(),
        ip_address=ip_address,
        error_message=error_message,
    )
    db.add(log)
    await db.commit()