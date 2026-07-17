"""Fernet key loading and credential encryption boundary."""

import os
import warnings
from pathlib import Path
from typing import Optional


def _configured_encryption_key() -> Optional[bytes]:
    """Read a configured Fernet key without generating a development key."""
    key = os.getenv("FERNET_KEY")
    if not key:
        for env_path in (Path(__file__).resolve().parents[2] / ".env", Path(__file__).resolve().parents[3] / ".env"):
            if not env_path.exists():
                continue
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                env_key, env_value = line.split("=", 1)
                if env_key.strip() == "FERNET_KEY":
                    key = env_value.strip().strip("\"'")
                    os.environ.setdefault("FERNET_KEY", key)
                    break
            if key:
                break
    if key:
        return key.encode() if isinstance(key, str) else key
    return None


def get_encryption_key() -> bytes:
    """Return the configured key or a transient development-only key."""
    key = _configured_encryption_key()
    if key:
        return key
    warnings.warn(
        "FERNET_KEY environment variable not set. Using a transient key. "
        "API keys will NOT persist correctly across restarts. "
        "Set FERNET_KEY to a valid 32-byte base64-encoded key for production.",
        UserWarning,
        stacklevel=2,
    )
    from cryptography.fernet import Fernet as _Fernet
    return _Fernet.generate_key()


_fernet_cache: Optional[tuple[Optional[bytes], "Fernet"]] = None


def require_stable_encryption_key() -> None:
    """Validate and install the production Fernet instance before startup."""
    if os.getenv("DEV_MODE", "true").lower() in {"true", "1", "yes"}:
        return
    key = _configured_encryption_key()
    if not key:
        raise RuntimeError("FERNET_KEY is required when DEV_MODE=false")
    try:
        from cryptography.fernet import Fernet as _Fernet
        fernet = _Fernet(key)
    except Exception as error:
        raise RuntimeError("FERNET_KEY must be a valid Fernet key when DEV_MODE=false") from error
    global _fernet_cache
    _fernet_cache = (key, fernet)


def _get_fernet() -> "Fernet":
    """Return a Fernet instance bound to the effective configured key."""
    global _fernet_cache
    configured_key = _configured_encryption_key()
    if _fernet_cache is not None and _fernet_cache[0] == configured_key:
        return _fernet_cache[1]
    key = configured_key or get_encryption_key()
    from cryptography.fernet import Fernet as _Fernet
    fernet = _Fernet(key)
    _fernet_cache = (configured_key, fernet)
    return fernet


def encrypt_key(api_key: str) -> str:
    """Encrypt a non-empty credential value."""
    if not api_key:
        return ""
    return _get_fernet().encrypt(api_key.encode()).decode()


def decrypt_key(encrypted_key: str) -> str:
    """Decrypt a token while retaining legacy plaintext read compatibility."""
    if not encrypted_key:
        return ""
    try:
        return _get_fernet().decrypt(encrypted_key.encode()).decode()
    except Exception:
        if encrypted_key.startswith("gAAAAA"):
            return ""
        return encrypted_key
