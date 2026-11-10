"""ASGI middleware: tiered rate limits for auth / generate / upload traffic."""

from __future__ import annotations

import re
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.rate_limit import (
    RateLimitExceeded,
    auth_rule,
    enforce_rate_limit,
    privacy_safe_key,
    traffic_rule,
)

_AUTH_LOGIN = re.compile(r"^/api/v1/auth/login/?$")
_AUTH_REGISTER = re.compile(r"^/api/v1/auth/register/?$")
_AUTH_FORGOT = re.compile(r"^/api/v1/auth/forgot-password/?$")
_AUTH_RESET = re.compile(r"^/api/v1/auth/reset-password/?$")
_AUTH_REFRESH = re.compile(r"^/api/v1/auth/refresh/?$")
_GENERATE = re.compile(
    r"^/api/v1/.+/(generate|generate-[a-z-]+|regenerate|execute-async|execute|media/start)(/|$)"
    r"|^/api/v1/series-runs/?$"
    r"|^/api/v1/(images|media|tts)/generate/?$"
    r"|^/api/v1/novels/generate/?$"
    r"|^/api/v1/chapters/generate/?$"
)
_UPLOAD = re.compile(
    r"^/api/v1/.+/upload/?$"
    r"|^/api/v1/assets/upload/?$"
    r"|^/api/v1/novels/import/(preview|confirm)/?$"
)


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _auth_identity(request: Request) -> str:
    hint = (request.headers.get("x-avp-auth-identity") or "").strip()
    return hint or _client_ip(request)


class CommercialRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method.upper() not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)

        path = request.url.path
        try:
            if _AUTH_LOGIN.match(path):
                rule = auth_rule("login")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request), _auth_identity(request)), rule)
            elif _AUTH_REGISTER.match(path):
                rule = auth_rule("register")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request), _auth_identity(request)), rule)
            elif _AUTH_FORGOT.match(path):
                rule = auth_rule("forgot")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request), _auth_identity(request)), rule)
            elif _AUTH_RESET.match(path):
                rule = auth_rule("reset")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request), _auth_identity(request)), rule)
            elif _AUTH_REFRESH.match(path):
                rule = auth_rule("refresh")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request), _auth_identity(request)), rule)
            elif _UPLOAD.match(path):
                rule = traffic_rule("upload")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request)), rule)
            elif _GENERATE.match(path):
                rule = traffic_rule("generate")
                await enforce_rate_limit(privacy_safe_key(rule.name, _client_ip(request)), rule)
        except RateLimitExceeded as exc:
            return JSONResponse(
                status_code=429,
                content={"detail": str(exc) or "操作过于频繁，请稍后再试", "success": False},
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


__all__ = ["CommercialRateLimitMiddleware"]
