"""
FastAPI 应用入口
"""

import os
import logging
import time
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

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.features.access_control.api import router as access_control_router
from app.features.task_execution.api import router as task_execution_router
from app.features.billing.api import router as billing_router
from app.features.private_media.api import router as private_media_router
from app.core.credential_encryption import require_stable_encryption_key
from app.core.csrf import csrf_is_valid
from app.core.operational_health import collect_operational_snapshot
from app.core.request_observability import (
    REQUEST_METRICS,
    metrics_access_allowed,
    normalize_request_id,
    render_operational_metrics,
)
from app.core.runtime_environment import validate_runtime_environment
from app.core.validation_errors import redact_credential_validation_errors
from app.services.auth_rate_limit import RateLimitExceeded

ALLOWED_ORIGIN_REGEX = (
    r"^https://([a-z0-9-]+--)?hackersun-ai-video-platform\.netlify\.app$"
    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def persistent_credential_encryption_lifespan(_: FastAPI):
    validate_runtime_environment()
    require_stable_encryption_key()
    yield


app = FastAPI(
    title="AI视频平台",
    description="纳米漫剧 AI视频生成平台",
    version="1.0.0",
    lifespan=persistent_credential_encryption_lifespan,
)

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
async def enforce_cookie_csrf(request: Request, call_next):
    if not csrf_is_valid(request):
        return JSONResponse(
            status_code=403,
            content={"detail": "页面安全校验已过期，请刷新页面后重试"},
        )
    return await call_next(request)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    if os.getenv("APP_ENV", "local").lower() in {"staging", "production"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def add_private_network_cors_header(request: Request, call_next):
    response = await call_next(request)
    if request.headers.get("origin"):
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.middleware("http")
async def observe_request(request: Request, call_next):
    request_id = normalize_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    started = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - started
    route = request.scope.get("route")
    route_path = getattr(route, "path", "unmatched")
    REQUEST_METRICS.observe(request.method, route_path, response.status_code, duration)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
        request_id,
        request.method,
        route_path,
        response.status_code,
        duration * 1000,
    )
    return response


@app.exception_handler(RequestValidationError)
async def credential_safe_validation_error_handler(request: Request, exc: RequestValidationError):
    del request
    detail = redact_credential_validation_errors(exc.errors())
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": detail}))


@app.exception_handler(RateLimitExceeded)
async def auth_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    del request
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Hide internal failures from clients while retaining controlled logs."""
    logger.error(
        "Unhandled request failure request_id=%s method=%s path=%s error_type=%s",
        getattr(request.state, "request_id", "unavailable"),
        request.method,
        request.url.path,
        type(exc).__name__,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "detail": "服务暂时不可用，请稍后重试",
            "request_id": getattr(request.state, "request_id", "unavailable"),
        },
    )


# 注册API路由
app.include_router(api_router, prefix="/api/v1")
app.include_router(access_control_router, prefix="/api/v1")
app.include_router(task_execution_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(private_media_router, prefix="/api/v1")

def should_mount_local_static(app_env: str) -> bool:
    return str(app_env or "local").strip().lower() in {"local", "test"}


if should_mount_local_static(os.getenv("APP_ENV", "local")):
    STATIC_DIR = Path(__file__).resolve().parent / "static"
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "AI视频平台",
        "version": "1.0.0"
    }


@app.get("/health/live")
async def liveness_check():
    return {"status": "alive", "service": "AI视频平台", "version": "1.0.0"}


@app.get("/health/ready")
async def readiness_check(request: Request):
    try:
        checks = await collect_operational_snapshot()
    except Exception as exc:
        logger.warning(
            "readiness_failed request_id=%s error_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "detail": "服务尚未准备好，请稍后重试",
                "request_id": request.state.request_id,
            },
        )
    return {"status": "ready", "checks": checks}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request):
    if not metrics_access_allowed(request.headers.get("Authorization")):
        raise HTTPException(status_code=401, detail="运营监控凭证无效")
    try:
        snapshot = await collect_operational_snapshot()
    except Exception as exc:
        logger.warning(
            "metrics_dependency_failed request_id=%s error_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        snapshot = {"database": {"status": "error"}, "task_queue": {"status": "unavailable"}}
    return PlainTextResponse(
        REQUEST_METRICS.render() + render_operational_metrics(snapshot),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "AI视频平台 API",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
