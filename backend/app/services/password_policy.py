"""Commercial password validation (compatible with existing 8+ letter+digit fixtures)."""

from __future__ import annotations

import re


class PasswordPolicyError(ValueError):
    pass


_COMMON_PASSWORD_ROOTS = {
    "password",
    "qwerty",
    "admin",
    "welcome",
    "letmein",
    "iloveyou",
    "123456",
    "111111",
    "abcdef",
}


def validate_password(password: str, *, username: str = "", email: str = "") -> None:
    if len(password) < 8:
        raise PasswordPolicyError("密码至少需要 8 位")
    if len(password) > 100:
        raise PasswordPolicyError("密码过长")

    lowered = password.lower()
    simplified = re.sub(r"[^a-z0-9]", "", lowered)
    if any(simplified.startswith(root) or simplified == root for root in _COMMON_PASSWORD_ROOTS):
        raise PasswordPolicyError("这个密码过于常见，请更换更难猜的密码")

    identity_parts = {username.lower().strip(), (email or "").split("@", 1)[0].lower().strip()}
    if any(part and len(part) >= 3 and part in lowered for part in identity_parts):
        raise PasswordPolicyError("密码不能包含用户名或邮箱名称")

    if not re.search(r"[A-Za-z]", password):
        raise PasswordPolicyError("密码需要包含字母")
    if not re.search(r"\d", password):
        raise PasswordPolicyError("密码需要包含数字")


__all__ = ["PasswordPolicyError", "validate_password"]
