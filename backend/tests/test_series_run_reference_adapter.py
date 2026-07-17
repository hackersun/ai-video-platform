from types import SimpleNamespace

import pytest

from app.services.series_run_reference_preparation import (
    ConfiguredReferenceAdapter,
    ReferencePreSubmitRejected,
    _persist_qiniu_reference,
)
from app.services.series_reference_provider import (
    ReferenceAdapterStageError,
    parse_public_url_expiry,
)


class _FakeDB:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


async def _async_result(value):
    return value


def test_public_url_expiry_parser_accepts_signed_url_iso_timestamp() -> None:
    parsed = parse_public_url_expiry("2100-01-01T08:00:00+08:00")

    assert parsed is not None
    assert parsed.isoformat() == "2100-01-01T08:00:00+08:00"


@pytest.mark.parametrize("value", ["not-a-date", "2100-01-01T00:00:00", ""])
def test_public_url_expiry_parser_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        parse_public_url_expiry(value)


@pytest.mark.asyncio
async def test_minimax_reference_adapter_requests_url_then_reuploads_qiniu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object()
    provider_url = "https://provider.invalid/temporary-reference.png"

    async def get_config(db, user_id, *, config_id):
        assert user_id == "user-1"
        assert config_id == "image-config"
        return "secret", "minimax", "image-01", "https://api.minimax.chat/v1"

    async def call_provider(received_service, **kwargs):
        assert received_service is service
        assert kwargs["minimax_response_format"] == "url"
        return {
            "id": "image-task-1",
            "data": {"image_urls": [provider_url]},
            "metadata": {"success_count": "1", "failed_count": "0"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }

    monkeypatch.setattr(
        "app.core.api_key_utils.get_user_image_model_config", get_config,
    )
    monkeypatch.setattr(
        "app.core.api_key_utils.create_image_generation_service",
        lambda api_key, provider_name, base_url: service,
    )
    monkeypatch.setattr(
        "app.services.image_generation_pipeline.call_image_generation_provider",
        call_provider,
    )

    async def persist(url, **kwargs):
        assert url == provider_url
        assert kwargs["subdir"] == "series-references"
        return "/static/generated/series-references/reference.png"

    async def deliver(db, user_id, url, **kwargs):
        assert user_id == "user-1"
        assert url == "/static/generated/series-references/reference.png"
        return {
            "provider_url": "https://qiniu.example.com/reference.png?e=4102444800&token=signed",
            "delivery_method": "qiniu_object_upload", "storage_config_id": "storage-qiniu",
            "object_key": "static/generated/series-references/reference.png",
        }

    monkeypatch.setattr("app.services.media_persistence.persist_remote_media_url", persist)
    monkeypatch.setattr("app.services.media_delivery.resolve_provider_media_url", deliver)
    monkeypatch.setattr(
        "app.services.series_reference_provider.bind_provider_operation_task",
        lambda db, operation, *, provider_task_id: _async_result(operation),
    )

    db = _FakeDB()
    run = SimpleNamespace(user_id="user-1", run_metadata={})
    result = await ConfiguredReferenceAdapter().generate(
        db=db,
        run=run,
        prompt="reference board",
        image_config_id="image-config",
        operation=SimpleNamespace(id="operation-1"),
    )

    assert result["status"] == "completed"
    assert result["public_url"].startswith("https://qiniu.example.com/reference.png?")
    assert result["public_url_expires_at"] == "2100-01-01T00:00:00+00:00"
    assert result["storage_delivery"] == {
        "delivery_method": "qiniu_object_upload", "storage_config_id": "storage-qiniu",
        "object_key": "static/generated/series-references/reference.png",
        "canonical_local_url": "/static/generated/series-references/reference.png",
    }
    assert result["provider_task_id"] == "image-task-1"
    assert db.commits == 1
    evidence = run.run_metadata["provider_response_evidence"]["operation-1"]
    assert evidence["payload_counts"] == {"base64": 0, "url": 1}
    assert provider_url not in repr(evidence)


@pytest.mark.asyncio
async def test_minimax_reference_adapter_retains_id_without_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = object()

    async def get_config(db, user_id, *, config_id):
        return "secret", "minimax", "image-01", "https://api.minimax.chat/v1"

    async def call_provider(received_service, **kwargs):
        return {
            "id": "image-filtered-1",
            "data": {"image_urls": []},
            "metadata": {"success_count": "0", "failed_count": "1"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        }

    monkeypatch.setattr("app.core.api_key_utils.get_user_image_model_config", get_config)
    monkeypatch.setattr("app.core.api_key_utils.create_image_generation_service", lambda *args: service)
    monkeypatch.setattr("app.services.image_generation_pipeline.call_image_generation_provider", call_provider)
    monkeypatch.setattr(
        "app.services.series_reference_provider.bind_provider_operation_task",
        lambda db, operation, *, provider_task_id: _async_result(operation),
    )

    db = _FakeDB()
    run = SimpleNamespace(user_id="user-1", run_metadata={})
    result = await ConfiguredReferenceAdapter().generate(
        db=db, run=run, prompt="reference board", image_config_id="image-config",
        operation=SimpleNamespace(id="operation-filtered"),
    )

    assert result["status"] == "accepted"
    assert result["provider_task_id"] == "image-filtered-1"
    assert result["public_url"] is None
    assert run.run_metadata["provider_response_evidence"]["operation-filtered"]["artifact_returned"] is False


@pytest.mark.asyncio
async def test_qiniu_failure_after_image_generation_requires_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def persist(url, **kwargs):
        return "/static/generated/series-references/reference.png"

    async def deliver(db, user_id, url, **kwargs):
        return {"provider_url": None, "delivery_method": None}

    monkeypatch.setattr("app.services.media_persistence.persist_remote_media_url", persist)
    monkeypatch.setattr("app.services.media_delivery.resolve_provider_media_url", deliver)

    with pytest.raises(ReferenceAdapterStageError) as caught:
        await _persist_qiniu_reference(object(), "user-1", "https://cdn.example.com/reference.png", "operation-1")

    assert caught.value.stage == "qiniu_upload"
    assert caught.value.provider_task_id is None
    assert "cdn.example.com" not in str(caught.value)
    assert not isinstance(caught.value, ReferencePreSubmitRejected)


@pytest.mark.asyncio
async def test_local_reference_persistence_failure_is_staged_and_redacted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def persist(url, **kwargs):
        raise RuntimeError("local-path=/secret/must-not-leak.png")

    monkeypatch.setattr("app.services.media_persistence.persist_remote_media_url", persist)

    with pytest.raises(ReferenceAdapterStageError) as caught:
        await _persist_qiniu_reference(
            object(), "user-1", "https://cdn.example.com/reference.png", "operation-1",
        )

    assert caught.value.stage == "local_persistence"
    assert "must-not-leak" not in str(caught.value)


@pytest.mark.asyncio
async def test_reference_adapter_binds_provider_task_before_qiniu_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    async def get_config(db, user_id, *, config_id):
        return "secret", "minimax", "image-01", "https://provider.invalid/v1"

    async def call_provider(*args, **kwargs):
        return {
            "id": "image-task-bound-first",
            "data": {"image_urls": ["https://provider.invalid/secret-image.png"]},
            "metadata": {"success_count": "1", "failed_count": "0"},
        }

    async def bind_task(db, operation, *, provider_task_id):
        assert provider_task_id == "image-task-bound-first"
        events.append("bound")
        operation.provider_task_id = provider_task_id
        return operation

    async def persist(url, **kwargs):
        events.append("persisted")
        return "/static/generated/series-references/reference.png"

    async def deliver(db, user_id, url, **kwargs):
        events.append("qiniu")
        return {"provider_url": None, "delivery_method": None}

    monkeypatch.setattr("app.core.api_key_utils.get_user_image_model_config", get_config)
    monkeypatch.setattr("app.core.api_key_utils.create_image_generation_service", lambda *args: object())
    monkeypatch.setattr("app.services.image_generation_pipeline.call_image_generation_provider", call_provider)
    monkeypatch.setattr("app.services.series_reference_provider.bind_provider_operation_task", bind_task)
    monkeypatch.setattr("app.services.media_persistence.persist_remote_media_url", persist)
    monkeypatch.setattr("app.services.media_delivery.resolve_provider_media_url", deliver)

    run = SimpleNamespace(user_id="user-1", run_metadata={})
    operation = SimpleNamespace(id="operation-bind", provider_task_id=None)
    with pytest.raises(ReferenceAdapterStageError) as caught:
        await ConfiguredReferenceAdapter().generate(
            db=_FakeDB(), run=run, prompt="reference board", image_config_id="image-config",
            operation=operation,
        )

    assert events == ["bound", "persisted", "qiniu"]
    assert caught.value.stage == "qiniu_upload"
    assert caught.value.provider_task_id == "image-task-bound-first"
    assert caught.value.provider_completed is True
    assert "secret-image" not in str(caught.value)


@pytest.mark.asyncio
async def test_reference_adapter_redacts_provider_call_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def get_config(db, user_id, *, config_id):
        return "secret", "minimax", "image-01", "https://provider.invalid/v1"

    async def call_provider(*args, **kwargs):
        raise RuntimeError("secret-token=must-not-leak")

    monkeypatch.setattr("app.core.api_key_utils.get_user_image_model_config", get_config)
    monkeypatch.setattr("app.core.api_key_utils.create_image_generation_service", lambda *args: object())
    monkeypatch.setattr("app.services.image_generation_pipeline.call_image_generation_provider", call_provider)

    with pytest.raises(ReferenceAdapterStageError) as caught:
        await ConfiguredReferenceAdapter().generate(
            db=_FakeDB(), run=SimpleNamespace(user_id="user-1", run_metadata={}),
            prompt="reference board", image_config_id="image-config",
            operation=SimpleNamespace(id="operation-call", provider_task_id=None),
        )

    assert caught.value.stage == "provider_call"
    assert caught.value.provider_task_id is None
    assert caught.value.provider_completed is False
    assert "must-not-leak" not in str(caught.value)


@pytest.mark.asyncio
async def test_minimax_explicit_business_rejection_is_pre_submit_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.minimax_errors import MiniMaxProviderRejected

    async def get_config(db, user_id, *, config_id):
        return "secret", "minimax", "image-01", "https://provider.invalid/v1"

    async def call_provider(*args, **kwargs):
        raise MiniMaxProviderRejected("图像生成", 1008, "secret-message-must-not-leak")

    monkeypatch.setattr("app.core.api_key_utils.get_user_image_model_config", get_config)
    monkeypatch.setattr("app.core.api_key_utils.create_image_generation_service", lambda *args: object())
    monkeypatch.setattr("app.services.image_generation_pipeline.call_image_generation_provider", call_provider)

    with pytest.raises(ReferencePreSubmitRejected) as caught:
        await ConfiguredReferenceAdapter().generate(
            db=_FakeDB(), run=SimpleNamespace(user_id="user-1", run_metadata={}),
            prompt="reference board", image_config_id="image-config",
            operation=SimpleNamespace(id="operation-rejected", provider_task_id=None),
        )

    assert "must-not-leak" not in str(caught.value)


@pytest.mark.asyncio
async def test_minimax_rejection_with_task_id_remains_manual_reconcile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.minimax_errors import MiniMaxProviderRejected

    async def get_config(db, user_id, *, config_id):
        return "secret", "minimax", "image-01", "https://provider.invalid/v1"

    async def call_provider(*args, **kwargs):
        raise MiniMaxProviderRejected(
            "图像生成", 1008, "unknown outcome", provider_task_id="provider-task-uncertain",
        )

    monkeypatch.setattr("app.core.api_key_utils.get_user_image_model_config", get_config)
    monkeypatch.setattr("app.core.api_key_utils.create_image_generation_service", lambda *args: object())
    monkeypatch.setattr("app.services.image_generation_pipeline.call_image_generation_provider", call_provider)

    with pytest.raises(ReferenceAdapterStageError) as caught:
        await ConfiguredReferenceAdapter().generate(
            db=_FakeDB(), run=SimpleNamespace(user_id="user-1", run_metadata={}),
            prompt="reference board", image_config_id="image-config",
            operation=SimpleNamespace(id="operation-uncertain", provider_task_id=None),
        )

    assert caught.value.stage == "provider_call"
    assert caught.value.provider_task_id == "provider-task-uncertain"


@pytest.mark.asyncio
async def test_reference_adapter_redacts_response_parse_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def get_config(db, user_id, *, config_id):
        return "secret", "minimax", "image-01", "https://provider.invalid/v1"

    async def call_provider(*args, **kwargs):
        return {"opaque": "secret-response-must-not-leak"}

    def classify(*args, **kwargs):
        raise ValueError("secret-response-must-not-leak")

    monkeypatch.setattr("app.core.api_key_utils.get_user_image_model_config", get_config)
    monkeypatch.setattr("app.core.api_key_utils.create_image_generation_service", lambda *args: object())
    monkeypatch.setattr("app.services.image_generation_pipeline.call_image_generation_provider", call_provider)
    monkeypatch.setattr("app.services.image_provider_response_contract.classify_image_provider_response", classify)

    with pytest.raises(ReferenceAdapterStageError) as caught:
        await ConfiguredReferenceAdapter().generate(
            db=_FakeDB(), run=SimpleNamespace(user_id="user-1", run_metadata={}),
            prompt="reference board", image_config_id="image-config",
            operation=SimpleNamespace(id="operation-parse", provider_task_id=None),
        )

    assert caught.value.stage == "response_parse"
    assert caught.value.provider_task_id is None
    assert "must-not-leak" not in str(caught.value)
