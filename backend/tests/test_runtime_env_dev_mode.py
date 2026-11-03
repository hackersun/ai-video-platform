"""Production-aware DEV_MODE defaults (P4 commercial fail-closed)."""

from __future__ import annotations

import pytest

from app.core.runtime_env import app_environment, is_dev_mode, is_production_environment


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DEV_MODE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)


def test_local_default_is_dev_mode_true():
    assert app_environment() == ""
    assert is_production_environment() is False
    assert is_dev_mode() is True


def test_production_app_env_defaults_dev_mode_false(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert is_production_environment() is True
    assert is_dev_mode() is False


def test_prod_environment_alias_defaults_dev_mode_false(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    assert is_dev_mode() is False


def test_explicit_dev_mode_true_wins_in_production(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_MODE", "true")
    assert is_dev_mode() is True


def test_explicit_dev_mode_false_wins_locally(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEV_MODE", "false")
    assert is_dev_mode() is False


def test_security_uses_runtime_is_dev_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DEV_MODE", raising=False)
    from app.core import security

    # Import path should see False without credentials → 401, not anonymous dev user.
    # We only assert the shared helper value security imports.
    from app.core.runtime_env import is_dev_mode as runtime_is_dev_mode

    assert runtime_is_dev_mode() is False
    assert security.is_dev_mode() is False
