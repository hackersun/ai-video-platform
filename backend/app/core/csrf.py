"""Double-submit CSRF validation for cookie-authenticated browser writes."""

import secrets

from fastapi import Request


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
_PUBLIC_AUTH_WRITES = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/forgot-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/verify-email",
}


def csrf_is_valid(request: Request) -> bool:
    if request.method.upper() in _SAFE_METHODS or request.url.path in _PUBLIC_AUTH_WRITES:
        return True
    if request.headers.get("authorization"):
        return True
    if not (request.cookies.get("access_token") or request.cookies.get("refresh_token")):
        return True
    cookie_token = request.cookies.get("csrf_token", "")
    header_token = request.headers.get("x-csrf-token", "")
    return bool(cookie_token and header_token) and secrets.compare_digest(cookie_token, header_token)
