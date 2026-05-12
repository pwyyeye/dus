import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import time
import logging
import sys

# 配置日志：输出到 log 文件夹，级别 DEBUG
LOG_DIR = Path(__file__).parent / "log"
LOG_DIR.mkdir(exist_ok=True)

# 移除所有现有 handlers（包括 uvicorn 可能在 basicConfig 前设置的）
root_logger = logging.getLogger()
root_logger.handlers.clear()

file_handler = logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)
root_logger.setLevel(logging.DEBUG)

for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"]:
    l = logging.getLogger(logger_name)
    l.handlers.clear()
    l.addHandler(file_handler)
    l.addHandler(stream_handler)
    l.setLevel(logging.DEBUG)

logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)

from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models import Machine, ApiBan
from routers import machines, tasks, projects, templates, issues, ws, agents, comments, labels, autopilots, skills, inbox, analytics

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if needed (dev convenience)
    from database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Run alembic migrations to add missing columns to existing tables
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        alembic_cfg = AlembicConfig(str(Path(__file__).parent / "alembic.ini"))
        await asyncio.to_thread(alembic_command.upgrade, alembic_cfg, "head")
    except Exception as e:
        logger.warning(f"Alembic migration skipped/failed (non-fatal): {e}")
    # Start the reminder scheduler
    from scheduler import start_scheduler
    start_scheduler()
    yield
    # Shutdown scheduler and engine
    from scheduler import stop_scheduler
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="DUS Cloud API",
    description="分布式AI终端统一调度系统 - 云端API",
    version="1.0.0",
    lifespan=lifespan,
)

logger = logging.getLogger(__name__)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    raise exc


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 1)
    logger.info(
        "%s %s → %s (%dms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Key authentication dependency
# Looks up per-machine keys in the Machine table; falls back to global key
# for backward compatibility during the transition period.
async def verify_api_key(
    request: Request,
    api_key: str = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")

    client_ip = request.client.host if request.client else None

    # Check IP ban
    if client_ip:
        stmt = select(ApiBan).where(
            ApiBan.target_type == "ip",
            ApiBan.target_value == client_ip,
            ApiBan.is_active == True,
        )
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="IP address is banned")

    # Check key ban
    stmt = select(ApiBan).where(
        ApiBan.target_type == "key",
        ApiBan.target_value == api_key,
        ApiBan.is_active == True,
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="API key is banned")

    # Look up per-machine key
    stmt = select(Machine).where(Machine.api_key == api_key)
    result = await db.execute(stmt)
    machine = result.scalar_one_or_none()
    if machine:
        return api_key

    # Backward compatibility: accept the global API key during transition
    settings = get_settings()
    if api_key == settings.API_KEY:
        return api_key

    raise HTTPException(status_code=401, detail="Invalid API Key")


# Health check (no auth required)
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Register routers with API key dependency
app.include_router(machines.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
# Public router: no auth (registration endpoint)
app.include_router(machines.public_router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(projects.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(templates.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(issues.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(agents.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(comments.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(labels.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(autopilots.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(skills.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(inbox.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(analytics.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
# WebSocket router (no HTTP prefix; auth handled inside the endpoint)
app.include_router(ws.router)
