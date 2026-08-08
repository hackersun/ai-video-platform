"""Browser authentication cookie contract."""

import secrets

from fastapi import Response

from app.core.runtime_environment import AppEnvironment, effective_environment


ACCESS_COOKIE_SECONDS = 15 * 60
REFRESH_COOKIE_SECONDS = 30 * 24 * 60 * 60


def _secure() -> bool:
    return effective_environment() in {AppEnvironment.STAGING, AppEnvironment.PRODUCTION}


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> str:
    secure = _secure()
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        "access_token", access_token, max_age=ACCESS_COOKIE_SECONDS,
        httponly=True, secure=secure, samesite="lax", path="/",
    )
    response.set_cookie(
        "refresh_token", refresh_token, max_age=REFRESH_COOKIE_SECONDS,
        httponly=True, secure=secure, samesite="strict", path="/api/v1/auth",
    )
    response.set_cookie(
        "csrf_token", csrf_token, max_age=REFRESH_COOKIE_SECONDS,
        httponly=False, secure=secure, samesite="lax", path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/api/v1/auth")
    response.delete_cookie("csrf_token", path="/")
