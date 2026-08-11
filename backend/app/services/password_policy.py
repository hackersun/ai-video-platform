"""Commercial password validation rules."""

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
}


def validate_password(password: str, *, username: str = "", email: str = "") -> None:
    if len(password) < 12:
        raise PasswordPolicyError("密码至少需要 12 位")

    lowered = password.lower()
    simplified = re.sub(r"[^a-z0-9]", "", lowered)
    if any(simplified.startswith(root) for root in _COMMON_PASSWORD_ROOTS):
        raise PasswordPolicyError("这个密码过于常见，请更换更难猜的密码")

    identity_parts = {username.lower(), email.split("@", 1)[0].lower()}
    if any(part and len(part) >= 3 and part in lowered for part in identity_parts):
        raise PasswordPolicyError("密码不能包含用户名或邮箱名称")

    checks = (
        (re.search(r"[a-z]", password), "密码需要包含小写字母"),
        (re.search(r"[A-Z]", password), "密码需要包含大写字母"),
        (re.search(r"\d", password), "密码需要包含数字"),
        (re.search(r"[^A-Za-z0-9]", password), "密码需要包含特殊字符"),
    )
    for matched, message in checks:
        if not matched:
            raise PasswordPolicyError(message)
