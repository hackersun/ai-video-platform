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
)
for _name in _AMBIENT_E2E_ENV:
    os.environ.pop(_name, None)

_explicit_url = os.environ.get("AVP_TEST_DATABASE_URL")
if _explicit_url:
    os.environ["DATABASE_URL"] = _explicit_url
else:
    _db_dir = Path(tempfile.mkdtemp(prefix="avp-pytest-", dir="/tmp")).resolve()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_dir / 'test.db'}"
    os.environ["E2E_REQUIRE_ISOLATED_DB"] = "true"
