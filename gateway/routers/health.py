from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from core.database import get_db
from core.redis_client import get_redis
import time

router = APIRouter()


@router.get("")
async def health():
    return {"status": "ok", "service": "nexusllm-gateway"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    checks = {}
    try:
        t0 = time.perf_counter()
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}
    try:
        redis = get_redis()
        t0 = time.perf_counter()
        await redis.ping()
        checks["redis"] = {"status": "ok", "latency_ms": round((time.perf_counter() - t0) * 1000, 2)}
    except Exception as e:
        checks["redis"] = {"status": "error", "detail": str(e)}
    all_ok = all(v["status"] == "ok" for v in checks.values())
    return {"status": "ready" if all_ok else "degraded", "checks": checks}