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
                        "public": "/static/generated/b.png",
                        "already": "/static/exports/c.mp4?exp=1&sig=x"}).encode()
    out = _json.loads(sign_export_urls_in_json(body))
    nested = out["extra_data"]["render_artifacts"]["srt_url"]
    assert nested.startswith("/static/exports/a.srt?exp=")
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(nested).query)
    assert verify_media_signature("/static/exports/a.srt", q["exp"][0], q["sig"][0])
    assert out["public"] == "/static/generated/b.png"
    assert out["already"] == "/static/exports/c.mp4?exp=1&sig=x"
