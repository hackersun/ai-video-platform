"""Backend-wide pytest isolation (applies to test_*.py and tests/).

1. Ambient e2e shells (``source /tmp/avp-e2e/env.sh``) export switches such as
   ``DETERMINISTIC_PROVIDER_FAKE=1`` and redis queue backends. Real-path tests
   must not inherit them; tests that need the fake opt in via ``monkeypatch.setenv``.
2. Tests must never share the developer's ``backend/ai_video.db`` (or the e2e DB):
   leftover rows from earlier runs leak into fixed-user assertions. Each pytest
   session gets a fresh SQLite file under /tmp. Set ``AVP_TEST_DATABASE_URL`` to
   deliberately run against another database (e.g. PostgreSQL contract runs).

This runs at conftest import time, before any ``app`` module creates its engine.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_AMBIENT_E2E_ENV = (
    "DETERMINISTIC_PROVIDER_FAKE",
    "DETERMINISTIC_REFERENCE_URL",
    "SERIES_RUN_QUEUE_BACKEND",
    "PUBLICATION_PIPELINE_QUEUE_BACKEND",
    "PUBLICATION_PIPELINE_ENABLED",
    "REDIS_URL",
    "E2E_REQUIRE_ISOLATED_DB",
    # Commercial-gate / e2e shell knobs must not leak into the full suite.
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "AUTH_RATE_LIMIT_LOGIN",
    "AUTH_RATE_LIMIT_REGISTER",
    "AUTH_RATE_LIMIT_FORGOT",
    "AUTH_RATE_LIMIT_RESET",
    "AUTH_RATE_LIMIT_REFRESH",
    "AUTH_RATE_LIMIT_WINDOW_SECONDS",
    "API_RATE_LIMIT_GENERATE",
    "API_RATE_LIMIT_UPLOAD",
    "API_RATE_LIMIT_WINDOW_SECONDS",
)
for _name in _AMBIENT_E2E_ENV:
    os.environ.pop(_name, None)

# Prefer in-process limiter during pytest so Redis/e2e rate counters cannot starve the suite.
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")
os.environ.setdefault("REFRESH_TOKEN_STORE", "memory")
# Raise traffic ceilings for the shared TestClient IP; commercial-gate tests monkeypatch lower.
os.environ.setdefault("API_RATE_LIMIT_GENERATE", "100000")
os.environ.setdefault("API_RATE_LIMIT_UPLOAD", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_LOGIN", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_REGISTER", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_FORGOT", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_RESET", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_REFRESH", "100000")
os.environ.setdefault("DEV_MODE", "true")

def _ensure_test_fernet_key() -> None:
    """Drop invalid ambient FERNET_KEY; provide a session key so encryption tests can run."""
    raw = (os.environ.get("FERNET_KEY") or "").strip()
    if raw:
        try:
            from cryptography.fernet import Fernet

            Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)
            return
        except Exception:
            os.environ.pop("FERNET_KEY", None)
    from cryptography.fernet import Fernet

    os.environ["FERNET_KEY"] = Fernet.generate_key().decode("utf-8")


_ensure_test_fernet_key()

_explicit_url = os.environ.get("AVP_TEST_DATABASE_URL")
if _explicit_url:
    os.environ["DATABASE_URL"] = _explicit_url
else:
    _db_dir = Path(tempfile.mkdtemp(prefix="avp-pytest-", dir="/tmp")).resolve()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_dir / 'test.db'}"
    os.environ["E2E_REQUIRE_ISOLATED_DB"] = "true"


import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limits_between_tests():
    from app.core.rate_limit import reset_rate_limits

    reset_rate_limits()
    yield
    reset_rate_limits()
