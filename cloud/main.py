from contextlib import asynccontextmanager
import time
import logging

from fastapi import FastAPI, Request, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from config import get_settings
from routers import machines, tasks, projects, templates

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables if needed (dev convenience)
    from database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
# Development mode: accepts any non-empty key with minimum length
async def verify_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    settings = get_settings()
    if api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key


# Health check (no auth required)
@app.get("/health")
async def health_check():
    return {"status": "ok"}


# Register routers with API key dependency
app.include_router(machines.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(tasks.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(projects.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
app.include_router(templates.router, prefix="/api/v1", dependencies=[Security(verify_api_key)])
