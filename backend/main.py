"""
FastAPI 应用入口
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path


def _load_local_env() -> None:
    """Load simple KEY=VALUE pairs before importing app modules."""
    for env_path in (Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_local_env()

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.media_access import PrivateAwareStaticFiles, SignExportUrlsMiddleware

from app.api.v1.router import api_router
from app.core.credential_encryption import require_stable_encryption_key
from app.core.validation_errors import redact_credential_validation_errors

ALLOWED_ORIGIN_REGEX = (
    r"^https://([a-z0-9-]+--)?hackersun-ai-video-platform\.netlify\.app$"
    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
)


@asynccontextmanager
async def persistent_credential_encryption_lifespan(_: FastAPI):
    from app.core.runtime_env import assert_production_safe

    assert_production_safe()
    require_stable_encryption_key()
    await _startup_user_terms_columns()
    await _startup_model_center_migration()
    yield


async def _startup_user_terms_columns() -> None:
    """Idempotent schema bootstrap (no Alembic): create_all + focused migrations.

    Existing databases otherwise miss newly added tables/columns (e.g. user_billing_settings,
    users.terms_accepted_*). Disable with DB_AUTO_MIGRATE=false when schema is managed externally.
    """
    if os.getenv("DB_AUTO_MIGRATE", "true").strip().lower() in {"0", "false", "no", "off"}:
        from app.core.database import engine
        from app.db_migrations.user_terms_acceptance import add_user_terms_columns_async

        await add_user_terms_columns_async(engine)
        return
    from init_db import init_db_async

    await init_db_async()


async def _startup_model_center_migration() -> None:
    """Best-effort, idempotent legacy -> model_config migration (counts only are logged)."""
    if os.getenv("MODEL_CENTER_STARTUP_SYNC", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    import logging

    try:
        from app.core.database import AsyncSessionLocal
        from app.features.model_config.legacy_sync import migrate_all

        async with AsyncSessionLocal() as session:
            counts = await migrate_all(session)
        logging.getLogger(__name__).info("model center migration: %s", counts)
    except Exception as error:  # startup must not fail on migration; reads migrate lazily
        logging.getLogger(__name__).warning("model center migration skipped: %s", type(error).__name__)


app = FastAPI(
    title="AI视频平台",
    description="纳米漫剧 AI视频生成平台",
    version="1.0.0",
    lifespan=persistent_credential_encryption_lifespan,
)

app.add_middleware(SignExportUrlsMiddleware)
from app.middleware.commercial_rate_limit import CommercialRateLimitMiddleware
app.add_middleware(CommercialRateLimitMiddleware)
# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)


@app.middleware("http")
async def add_private_network_cors_header(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get("origin"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.exception_handler(RequestValidationError)
async def credential_safe_validation_error_handler(request: Request, exc: RequestValidationError):
    del request
    detail = redact_credential_validation_errors(exc.errors())
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": detail}))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器，确保所有错误响应都带CORS头；不向客户端泄露 SQL/堆栈细节"""
    import logging
    logging.getLogger(__name__).exception(
        "Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Private-Network": "true",
        },
    )


# 注册API路由
app.include_router(api_router, prefix="/api/v1")

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", PrivateAwareStaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health_check():
    """Liveness: process is up. Dependency checks live on /ready."""
    return {
        "status": "healthy",
        "service": "AI视频平台",
        "version": "1.0.0",
        "probe": "liveness",
    }


@app.get("/ready")
async def readiness_check():
    """Readiness: DB required; Redis required when REDIS_URL is set."""
    from fastapi.responses import JSONResponse

    from app.core.health import build_readiness

    payload = await build_readiness()
    code = 200 if payload.get("status") == "ready" else 503
    return JSONResponse(content=payload, status_code=code)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "AI视频平台 API",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
