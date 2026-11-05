import pytest

from app.core.runtime_env import assert_production_safe


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("APP_ENV", "ENVIRONMENT", "DEV_MODE", "DEV_USER_ID", "DEV_TOKEN", "DEV_AUTH_TOKEN", "ALLOW_DEV_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_non_production_allows_dev_mode(monkeypatch):
    monkeypatch.setenv("DEV_MODE", "true")
    assert_production_safe()


def test_production_defaults_are_safe(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    assert_production_safe()


@pytest.mark.parametrize("name,value", [("DEV_MODE", "true"), ("DEV_USER_ID", "dev-user-001"), ("DEV_TOKEN", "x")])
def test_production_with_dev_settings_fails(monkeypatch, name, value):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match="Refusing to start"):
        assert_production_safe()


def test_lifespan_refuses_start(monkeypatch):
    from fastapi.testclient import TestClient

    from main import app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_MODE", "true")
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass


def test_production_refuses_deterministic_provider_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_MODE", "false")
    monkeypatch.delenv("DEV_USER_ID", raising=False)
    for name in ("DEV_TOKEN", "DEV_AUTH_TOKEN", "ALLOW_DEV_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    with pytest.raises(RuntimeError, match="DETERMINISTIC_PROVIDER_FAKE"):
        assert_production_safe()

