import pytest

from app.core import redis_client


def test_key_helpers_use_stable_prefix(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    assert redis_client.KEY_PREFIX == "avp:series_run:"
    assert redis_client.queue_key() == "avp:series_run:queue"
    assert redis_client.processing_key() == "avp:series_run:processing"
    assert redis_client.lock_key("run-1") == "avp:series_run:lock:run-1"
    assert redis_client.heartbeat_key("run-1") == "avp:series_run:heartbeat:run-1"
    assert redis_client.pause_key("run-1") == "avp:series_run:pause:run-1"


def test_get_redis_url_fail_closed_when_missing(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL"):
        redis_client.get_redis_url()


def test_redis_client_disables_socket_timeout_for_blocking_commands(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_client.reset_redis_client_cache()
    client = redis_client._client_for(redis_client.get_redis_url())
    assert client.connection_pool.connection_kwargs.get("socket_timeout") is None
