import importlib
from types import SimpleNamespace

import pytest


def _contract_module():
    return importlib.import_module("app.services.image_provider_response_contract")


def test_minimax_completed_response_has_secret_safe_structural_evidence() -> None:
    result = {
        "id": "generation-1",
        "data": {"image_base64": ["secret-base64-payload" * 20]},
        "metadata": {"success_count": "1", "failed_count": "0"},
        "base_resp": {"status_code": 0, "status_msg": "success secret-message"},
        "api_key": "sk-must-not-survive",
    }

    classified = _contract_module().classify_image_provider_response(result, "minimax")

    assert classified["status"] == "completed"
    assert classified["provider_task_id"] == "generation-1"
    assert len(classified["image_urls"]) == 1
    evidence = classified["evidence"]
    assert evidence["schema_version"] == "image-provider-response-shape-v1"
    assert evidence["provider"] == "minimax"
    assert evidence["provider_task_id_present"] is True
    assert evidence["payload_counts"] == {"base64": 1, "url": 0}
    assert evidence["metadata_counts"] == {"failed": 0, "success": 1}
    assert evidence["base_status_code"] == "0"
    serialized = repr(evidence)
    for forbidden in ("secret-base64", "secret-message", "sk-must", "image_base64"):
        assert forbidden not in serialized


def test_minimax_id_without_artifact_is_accepted_and_recoverable() -> None:
    result = {
        "id": "generation-filtered-1",
        "data": {"image_urls": []},
        "metadata": {"success_count": "0", "failed_count": "1"},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }

    classified = _contract_module().classify_image_provider_response(result, "minimax")

    assert classified["status"] == "accepted"
    assert classified["provider_task_id"] == "generation-filtered-1"
    assert classified["image_urls"] == []
    assert classified["evidence"]["artifact_returned"] is False


@pytest.mark.asyncio
async def test_response_evidence_is_persisted_by_operation_without_raw_payload() -> None:
    class FakeDB:
        commits = 0

        async def commit(self):
            self.commits += 1

    db = FakeDB()
    run = SimpleNamespace(run_metadata={})
    evidence = {
        "schema_version": "image-provider-response-shape-v1",
        "provider": "minimax",
        "artifact_returned": False,
    }

    await _contract_module().persist_image_response_evidence(
        db, run, operation_id="operation-1", evidence=evidence,
    )

    assert db.commits == 1
    assert run.run_metadata["provider_response_evidence"] == {"operation-1": evidence}
