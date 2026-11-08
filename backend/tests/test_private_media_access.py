"""R02: finished exports are private; served only via short-lived signed URLs."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.core.media_access import sign_media_url, verify_media_signature
from app.models.publication_pipeline import NovelPublicationPipeline
from init_db import init_db
from main import app

EXPORTS = Path(__file__).resolve().parents[1] / "static" / "exports"


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


@pytest.fixture()
def export_file():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = EXPORTS / f"test-private-{uuid4()}.mp4"
    path.write_bytes(b"fake-mp4")
    yield path
    path.unlink(missing_ok=True)


def _h(uid: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {uid}"}


def test_unsigned_export_is_denied(client: TestClient, export_file: Path) -> None:
    assert client.get(f"/static/exports/{export_file.name}").status_code == 403


def test_signed_export_is_served(client: TestClient, export_file: Path) -> None:
    url = sign_media_url(f"/static/exports/{export_file.name}")
    resp = client.get(url)
    assert resp.status_code == 200 and resp.content == b"fake-mp4"


def test_tampered_or_expired_signature_denied(client: TestClient, export_file: Path, tmp_path) -> None:
    url = sign_media_url(f"/static/exports/{export_file.name}")
    other = url.replace(export_file.name, "other.mp4")
    assert client.get(other).status_code == 403
    expired = sign_media_url(f"/static/exports/{export_file.name}", ttl_seconds=-10)
    assert client.get(expired).status_code == 403
    q = parse_qs(urlparse(url).query)
    assert verify_media_signature(f"/static/exports/{export_file.name}", q["exp"][0], q["sig"][0])


def test_non_private_static_unchanged(client: TestClient) -> None:
    assert sign_media_url("/static/starter/x.png") == "/static/starter/x.png"
    assert sign_media_url("https://cdn.example.com/a.mp4") == "https://cdn.example.com/a.mp4"
    assert sign_media_url(None) is None


def test_generated_intermediates_require_signature(client: TestClient, tmp_path) -> None:
    from pathlib import Path as P
    from app.core.media_access import unsigned_media_url
    gen = P(__file__).resolve().parents[1] / "static" / "generated" / "images"
    gen.mkdir(parents=True, exist_ok=True)
    path = gen / f"priv-{uuid4()}.png"
    path.write_bytes(b"png")
    try:
        assert client.get(f"/static/generated/images/{path.name}").status_code == 403
        url = sign_media_url(f"/static/generated/images/{path.name}")
        assert client.get(url).status_code == 200
        assert "sig=" in url
        assert unsigned_media_url(url) == f"/static/generated/images/{path.name}"
    finally:
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_pipeline_url_signed_for_owner_and_cross_user_denied(client: TestClient, export_file: Path) -> None:
    owner, other = f"own-{uuid4()}", f"oth-{uuid4()}"
    novel = client.post("/api/v1/novels", json={"title": f"pm {uuid4()}", "description": "x"}, headers=_h(owner))
    novel_id = novel.json()["id"]
    pid = str(uuid4())
    async with AsyncSessionLocal() as db:
        db.add(NovelPublicationPipeline(
            id=pid, user_id=owner, novel_id=novel_id, series_plan_version="v1",
            idempotency_key=f"k-{uuid4()}", status="succeeded", stage="published",
            final_video_url=f"/static/exports/{export_file.name}",
        ))
        await db.commit()
    mine = client.get(f"/api/v1/publication-pipelines/{pid}", headers=_h(owner))
    assert mine.status_code == 200
    signed = mine.json()["final_video_url"]
    assert "sig=" in signed and client.get(signed).status_code == 200
    assert client.get(f"/api/v1/publication-pipelines/{pid}", headers=_h(other)).status_code == 404
    assert client.get(f"/api/v1/novels/{novel_id}/publication-pipelines", headers=_h(other)).status_code == 404


@pytest.mark.asyncio
async def test_cross_user_publication_denied(client: TestClient, export_file: Path) -> None:
    from app.models.publication import Publication

    owner, other = f"own-{uuid4()}", f"oth-{uuid4()}"
    pub_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        db.add(Publication(id=pub_id, user_id=owner, title="t", video_url=f"/static/exports/{export_file.name}",
                           export_url=f"/static/exports/{export_file.name}", artifact_path=str(export_file)))
        await db.commit()
    mine = client.get(f"/api/v1/synthesis/publications/{pub_id}", headers=_h(owner))
    assert mine.status_code == 200 and "sig=" in mine.json()["video_url"]
    for path in (f"/api/v1/synthesis/publications/{pub_id}", f"/api/v1/synthesis/publications/{pub_id}/download"):
        assert client.get(path, headers=_h(other)).status_code == 404


def test_nested_export_urls_in_json_are_signed_and_signed_ones_untouched():
    from app.core.media_access import sign_export_urls_in_json, verify_media_signature
    import json as _json

    body = _json.dumps({"extra_data": {"render_artifacts": {"srt_url": "/static/exports/a.srt"}},
                        "generated": "/static/generated/b.png",
                        "already": "/static/exports/c.mp4?exp=1&sig=x",
                        "public": "/static/starter/ok.png"}).encode()
    out = _json.loads(sign_export_urls_in_json(body))
    nested = out["extra_data"]["render_artifacts"]["srt_url"]
    assert nested.startswith("/static/exports/a.srt?exp=")
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(nested).query)
    assert verify_media_signature("/static/exports/a.srt", q["exp"][0], q["sig"][0])
    gen = out["generated"]
    assert gen.startswith("/static/generated/b.png?exp=")
    gq = parse_qs(urlparse(gen).query)
    assert verify_media_signature("/static/generated/b.png", gq["exp"][0], gq["sig"][0])
    assert out["public"] == "/static/starter/ok.png"
    assert out["already"] == "/static/exports/c.mp4?exp=1&sig=x"


@pytest.mark.asyncio
async def test_cloud_render_request_uses_long_ttl_signed_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    """External renderer receives signed private URLs; TTL is longer than default API TTL."""
    from types import SimpleNamespace

    from app.api.v1.endpoints import workflow as wf
    from app.core.media_access import (
        CLOUD_RENDER_TTL_SECONDS,
        DEFAULT_TTL_SECONDS,
        unsigned_media_urls_in_obj,
        verify_media_signature,
    )
    from urllib.parse import parse_qs, urlparse

    captured = {}

    class _Resp:
        status_code = 200
        headers = {"content-type": "application/json"}
        text = "{}"

        def json(self):
            return {"task_id": "t1"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(wf.httpx, "AsyncClient", _Client)

    config = SimpleNamespace(
        custom_base_url="https://render.example",
        timeout=30,
        extra_config={"submit_path": "/render"},
        get_api_key_decrypted=lambda: "",
    )
    provider = SimpleNamespace(base_url=None, auth_type="none", auth_header="Authorization")

    payload = {
        "workflow_id": "w1",
        "synthesis_job_id": "s1",
        "render_manifest_url": "/static/exports/manifest.json",
        "timeline_url": "/static/exports/timeline.json",
        "srt_url": "/static/generated/videos/clip.mp4",
        "segments": [{"video_url": "/static/generated/videos/a.mp4"}],
        "burn_subtitles": True,
        "quality_profile": "standard",
    }
    task_id, adapter_status, _ = await wf._submit_cloud_render_job(
        config=config, provider=provider, render_id="r1", payload=payload,
    )
    assert task_id == "t1"
    assert adapter_status == "cloud_pending"
    body = captured["json"]
    assert "sig=" in (body["manifest_url"] or "")
    assert "sig=" in (body["srt_url"] or "")
    assert "sig=" in body["segments"][0]["video_url"]
    # Cloud TTL should outlive default API TTL (compare exp values).
    mq = parse_qs(urlparse(body["manifest_url"]).query)
    assert verify_media_signature("/static/exports/manifest.json", mq["exp"][0], mq["sig"][0])
    assert int(mq["exp"][0]) - int(__import__("time").time()) > DEFAULT_TTL_SECONDS
    stored = unsigned_media_urls_in_obj(body)
    assert stored["manifest_url"] == "/static/exports/manifest.json"
    assert stored["srt_url"] == "/static/generated/videos/clip.mp4"
    assert stored["segments"][0]["video_url"] == "/static/generated/videos/a.mp4"
    assert CLOUD_RENDER_TTL_SECONDS > DEFAULT_TTL_SECONDS


def test_download_flag_sets_attachment_disposition(client: TestClient, export_file: Path) -> None:
    url = sign_media_url(f"/static/exports/{export_file.name}")
    plain = client.get(url)
    assert "content-disposition" not in plain.headers
    resp = client.get(url + "&download=1")
    assert resp.status_code == 200 and resp.content == b"fake-mp4"
    assert resp.headers["content-disposition"].startswith(f'attachment; filename="{export_file.name}"')
    assert client.get(f"/static/exports/{export_file.name}?download=1").status_code == 403
