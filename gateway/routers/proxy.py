import time
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.database import get_db
from core.redis_client import get_redis
from core.auth_deps import get_current_user
from core.config import settings
from services.rate_limiter import rate_limiter
from services.router import provider_router, LLMRequest
from services.audit import write_audit_log
from models.models import User

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    max_tokens: int = 1024
    temperature: float = 0.7


class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: dict
    rate_limit: dict


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Main proxy endpoint. Accepts a unified chat request,
    routes to the right LLM provider, enforces rate limits,
    and logs everything to the audit trail.
    """
    start = time.perf_counter()
    redis = get_redis()

    # Resolve rate limits — use key-specific limits or fall back to defaults
    rpm_limit = settings.default_rate_limit_rpm
    tpd_limit = settings.default_rate_limit_tpd

    # Enforce requests-per-minute limit
    rate_info = await rate_limiter.check_rpm(redis, str(current_user.id), rpm_limit)

    provider = None
    model = None
    prompt_tokens = None
    completion_tokens = None
    status_code = 200
    error_message = None

    try:
        llm_request = LLMRequest(
            model=body.model,
            messages=[{"role": m.role, "content": m.content} for m in body.messages],
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )

        response = await provider_router.route(llm_request)

        provider = response.provider
        model = response.model
        prompt_tokens = response.prompt_tokens
        completion_tokens = response.completion_tokens

        # Enforce tokens-per-day limit after the call
        tpd_info = await rate_limiter.check_tpd(
            redis, str(current_user.id), response.total_tokens, tpd_limit
        )

        latency_ms = int((time.perf_counter() - start) * 1000)

        # Write audit log — metadata only, never content
        await write_audit_log(
            db=db,
            user_id=str(current_user.id),
            api_key_id=None,
            method="POST",
            path="/proxy/chat",
            status_code=200,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            ip_address=request.client.host if request.client else None,
        )

        return ChatResponse(
            provider=response.provider,
            model=response.model,
            content=response.content,
            usage={
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.total_tokens,
            },
            rate_limit=rate_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        status_code = 500
        error_message = str(e)
        latency_ms = int((time.perf_counter() - start) * 1000)
        await write_audit_log(
            db=db,
            user_id=str(current_user.id),
            api_key_id=None,
            method="POST",
            path="/proxy/chat",
            status_code=500,
            latency_ms=latency_ms,
            provider=provider,
            model=model,
            error_message=error_message,
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=500, detail=error_message)