from app.services.deterministic_provider_fake import deterministic_provider_fake_enabled


def test_setup_endpoint_is_hidden_when_adapter_is_off(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)
    response = TestClient(app).post(
        "/api/v1/series-runs/deterministic-acceptance/setup",
        json={"novel_id": "missing"},
        headers={"Authorization": "Bearer deterministic-owner"},
    )
    assert response.status_code == 404


def test_setup_expands_canonical_run_to_six_full_coverage_shots(monkeypatch):
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from main import app
    from init_db import init_db

    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    init_db()
    client = TestClient(app)
    owner = f"deterministic-{uuid4()}"
    headers = {"Authorization": f"Bearer {owner}"}
    novel = client.post("/api/v1/novels", json={"title": "四章确定性验收"}, headers=headers).json()
    chapters = []
    for number in range(1, 5):
        chapters.append(client.post("/api/v1/chapters", json={"novel_id": novel["id"], "title": f"第{number}章", "chapter_number": number, "content": "主角携带道具进入新场景，事件转折并最终完成。角色说：继续。", "status": "completed"}, headers=headers).json()["id"])
    run = client.post("/api/v1/series-runs", json={"novel_id": novel["id"], "series_plan_version": "v1", "idempotency_key": "deterministic", "requested_stages": ["scripts", "storyboards", "shots"], "episodes": [{"episode_number": i, "chapter_ids": [chapter], "input_hash": f"h{i}"} for i, chapter in enumerate(chapters, 1)]}, headers=headers).json()
    assert client.post(f"/api/v1/series-runs/{run['id']}/execute", headers=headers).status_code == 200
    from app.core.database import SyncSessionLocal
    from app.models import Script, Shot, Storyboard, Workflow
    from app.models.series_production_run import SeriesProductionRun
    with SyncSessionLocal() as session:
        stored = session.get(SeriesProductionRun, run["id"])
        episodes = [dict(item) for item in stored.episodes]
        canonical = dict(episodes[0]["canonical_ids"])
        workflow = session.get(Workflow, canonical["workflow_id"])
        workflow.script_id = workflow.storyboard_id = None
        for shot in session.query(Shot).filter(Shot.storyboard_id == canonical["storyboard_id"]).all():
            session.delete(shot)
        session.delete(session.get(Storyboard, canonical["storyboard_id"]))
        session.delete(session.get(Script, canonical["script_id"]))
        episodes[0] = {**episodes[0], "stage": "workflow_ready",
                       "canonical_ids": {"workflow_id": canonical["workflow_id"]}}
        stored.episodes = episodes
        stored.status = "episodes_building"
        session.commit()
    setup = client.post("/api/v1/series-runs/deterministic-acceptance/setup", json={"novel_id": novel["id"]}, headers=headers)
    assert setup.status_code == 200, setup.text
    resumed = client.post(f"/api/v1/series-runs/{run['id']}/execute", headers=headers)
    assert resumed.status_code == 200, resumed.text
    repeated_setup = client.post("/api/v1/series-runs/deterministic-acceptance/setup", json={"novel_id": novel["id"]}, headers=headers)
    assert repeated_setup.status_code == 200, repeated_setup.text
    plan = client.get(f"/api/v1/series-runs/{run['id']}/live-preflight-plan", headers=headers)
    assert plan.status_code == 200, plan.text
    assert plan.json()["voice_options"]["options"] == [
        {"voice_id": "deterministic-protagonist-voice", "label": "deterministic-protagonist-voice"}
    ]
    anchors = client.get(f"/api/v1/series-runs/{run['id']}/anchor-shots", headers=headers).json()
    assert len(anchors["full"]) == 6
    assert anchors["blockers"]["full"] is None
    assert {item["episode_number"] for item in anchors["full"]} == {1, 2, 3, 4}
    selected = [item["shot_id"] for item in anchors["full"]]
    assert client.put(f"/api/v1/series-runs/{run['id']}/anchor-shots", json={"shot_ids": selected, "mode": "full"}, headers=headers).status_code == 200
    generated = client.post(f"/api/v1/series-runs/{run['id']}/generate-selected", json={"shot_ids": selected, "mode": "full"}, headers=headers)
    assert generated.status_code == 409, generated.text
    assert generated.json()["detail"]["code"] == "generation_preflight_blocked"
    # Deterministic mode replaces only the provider. It must not manufacture
    # jobs/evaluations before Story Locks, reference evidence and Task4 gates.
    persisted = client.get(f"/api/v1/series-runs/{run['id']}", headers=headers).json()
    assert not persisted["run_metadata"].get("anchor_quality_reports")


def test_deterministic_provider_fake_is_explicit_and_fail_closed(monkeypatch):
    monkeypatch.delenv("DETERMINISTIC_PROVIDER_FAKE", raising=False)
    assert deterministic_provider_fake_enabled() is False
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "true")
    assert deterministic_provider_fake_enabled() is False
    monkeypatch.setenv("DETERMINISTIC_PROVIDER_FAKE", "1")
    assert deterministic_provider_fake_enabled() is True
