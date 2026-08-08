"""Email verification and password-recovery HTTP routes."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_tokens import create_access_token
from app.core.database import get_db
from app.core.runtime_environment import allows_development_identity
from app.core.time_utils import utc_now
from app.features.auth.cookies import set_auth_cookies
from app.features.auth.passwords import hash_password, hash_reset_token, verify_password
from app.features.auth.presenters import to_user_response
from app.features.auth.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    MessageResponse,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.models.user import User
from app.services.auth_notifications import queue_auth_notification
from app.services.auth_rate_limit import enforce_auth_rate_limit
from app.services.auth_sessions import issue_session, revoke_all_user_sessions
from app.services.password_policy import PasswordPolicyError, validate_password


router = APIRouter(tags=["用户认证"])
_RESET_TOKEN_EXPIRE_MINUTES = 30


@router.post("/auth/verify-email")
async def verify_email(
    request: VerifyEmailRequest,
    http_request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit("verify", http_request, request.token)
    token_hash = hash_reset_token(request.token)
    user = (
        await db.execute(select(User).where(User.email_verification_token_hash == token_hash))
    ).scalar_one_or_none()
    if (
        user is None
        or user.email_verification_token_expires_at is None
        or user.email_verification_token_expires_at < utc_now()
    ):
        raise HTTPException(status_code=400, detail="邮箱验证链接无效或已过期")

    user.account_status = "active"
    user.is_active = True
    user.email_verified_at = utc_now()
    user.email_verification_token_hash = None
    user.email_verification_token_expires_at = None
    await db.commit()
    await db.refresh(user)
    access_token = create_access_token(user.id)
    session = await issue_session(db, user.id, http_request.headers.get("user-agent"))
    set_auth_cookies(response, access_token, session.refresh_token)
    return AuthResponse(
        message="邮箱验证成功，已为你登录",
        user=to_user_response(user),
        access_token=access_token,
        refresh_token=session.refresh_token if allows_development_identity() else None,
    )


@router.post("/auth/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit("forgot", http_request, request.email)
    user = (
        await db.execute(select(User).where(User.email == request.email))
    ).scalar_one_or_none()
    reset_token = None
    if user and user.is_active:
        reset_token = secrets.token_urlsafe(32)
        user.reset_token_hash = hash_reset_token(reset_token)
        user.reset_token_expires_at = utc_now() + timedelta(minutes=_RESET_TOKEN_EXPIRE_MINUTES)
        user.updated_at = utc_now()
        queue_auth_notification(
            db, user_id=user.id, recipient=user.email,
            kind="reset_password", token=reset_token,
        )
        await db.commit()

    result = MessageResponse(message="如果邮箱存在，系统已生成密码重置说明")
    if reset_token and allows_development_identity():
        result.reset_token = reset_token
        result.message = "DEV_MODE 已生成重置令牌，请在重置密码页面使用"
    return result


@router.post("/auth/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    await enforce_auth_rate_limit("reset", http_request, request.token)
    token_hash = hash_reset_token(request.token)
    user = (
        await db.execute(select(User).where(User.reset_token_hash == token_hash))
    ).scalar_one_or_none()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < utc_now():
        raise HTTPException(status_code=400, detail="重置令牌无效或已过期")
    if verify_password(request.new_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="新密码不能与当前密码相同")
    try:
        validate_password(request.new_password, username=user.username, email=user.email)
    except PasswordPolicyError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    user.hashed_password = hash_password(request.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    user.updated_at = utc_now()
    await revoke_all_user_sessions(db, user.id)
    return MessageResponse(message="密码重置成功，请重新登录")
