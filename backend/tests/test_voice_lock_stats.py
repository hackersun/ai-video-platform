import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models import Chapter, Novel, Script, Shot, Storyboard, TTSJob, Workflow
from init_db import init_db
from main import app


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def _auth_headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {user_id}"}


async def _seed_voice_lock_workflow(user_id: str) -> dict[str, str]:
    novel_id = f"novel-{uuid4()}"
    chapter_id = f"chapter-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    workflow_id = f"workflow-{uuid4()}"
    shot_ids = [f"shot-{uuid4()}" for _ in range(3)]
    tts_job_ids = [f"tts-{uuid4()}" for _ in range(3)]

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="Voice stats novel"))
        db.add(
            Chapter(
                id=chapter_id,
                novel_id=novel_id,
                user_id=user_id,
                title="Chapter",
                content="Dialogue chapter",
                chapter_number=1,
            )
        )
        db.add(
            Script(
                id=script_id,
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                title="Script",
                content="Dialogue script",
                status="draft",
            )
        )
        db.add(
            Storyboard(
                id=storyboard_id,
                user_id=user_id,
                script_id=script_id,
                novel_id=novel_id,
                title="Storyboard",
                shot_count=3,
            )
        )
        db.add(
            Workflow(
                id=workflow_id,
                user_id=user_id,
                title="Voice lock stats workflow",
                status="active",
                novel_id=novel_id,
                chapter_id=chapter_id,
                script_id=script_id,
                storyboard_id=storyboard_id,
                tts_job_ids=tts_job_ids,
            )
        )
        for index, (shot_id, character_name) in enumerate(
            zip(shot_ids, ["Shen Yan", "Su Mian", "Lin Lan"]),
            start=1,
        ):
            db.add(
                Shot(
                    id=shot_id,
                    user_id=user_id,
                    storyboard_id=storyboard_id,
                    shot_number=index,
                    duration=4,
                    prompt=f"Shot {index}",
                    dialogue=f"{character_name}: line {index}",
                    extra_data={"subtitle_text": f"{character_name}: line {index}"},
                )
            )

        db.add(
            TTSJob(
                id=tts_job_ids[0],
                user_id=user_id,
                workflow_id=workflow_id,
                storyboard_id=storyboard_id,
                shot_id=shot_ids[0],
                title="TTS 1",
                text="Shen Yan: line 1",
                status="succeeded",
                extra_data={"voice_source": "story_bible", "voice_character_name": "Shen Yan"},
            )
        )
        db.add(
            TTSJob(
                id=tts_job_ids[1],
                user_id=user_id,
                workflow_id=workflow_id,
                storyboard_id=storyboard_id,
                shot_id=shot_ids[1],
                title="TTS 2",
                text="Su Mian: line 2",
                status="succeeded",
                extra_data={
                    "voice_source": "request",
                    "voice_character_name": "Su Mian",
                    "voice_lock_snapshot": {"voice": "story-bible-su-mian"},
                },
            )
        )
        db.add(
            TTSJob(
                id=tts_job_ids[2],
                user_id=user_id,
                workflow_id=workflow_id,
                storyboard_id=storyboard_id,
                shot_id=shot_ids[2],
                title="TTS 3",
                text="Lin Lan: line 3",
                status="succeeded",
                extra_data={"voice_source": "request", "voice_character_name": "Lin Lan"},
            )
        )
        await db.commit()

    return {"workflow_id": workflow_id, "unlocked_shot_id": shot_ids[2]}


async def _seed_voice_lock_workflow_with_stale_locked_tts(user_id: str) -> dict[str, str]:
    novel_id = f"novel-{uuid4()}"
    chapter_id = f"chapter-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    workflow_id = f"workflow-{uuid4()}"
    shot_id = f"shot-{uuid4()}"
    old_tts_job_id = f"tts-{uuid4()}"
    latest_tts_job_id = f"tts-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="Stale voice stats novel"))
        db.add(
            Chapter(
                id=chapter_id,
                novel_id=novel_id,
                user_id=user_id,
                title="Chapter",
                content="Dialogue chapter",
                chapter_number=1,
            )
        )
        db.add(
            Script(
                id=script_id,
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                title="Script",
                content="Dialogue script",
                status="draft",
            )
        )
        db.add(
            Storyboard(
                id=storyboard_id,
                user_id=user_id,
                script_id=script_id,
                novel_id=novel_id,
                title="Storyboard",
                shot_count=1,
            )
        )
        db.add(
            Workflow(
                id=workflow_id,
                user_id=user_id,
                title="Stale voice lock stats workflow",
                status="active",
                novel_id=novel_id,
                chapter_id=chapter_id,
                script_id=script_id,
                storyboard_id=storyboard_id,
                tts_job_ids=[old_tts_job_id, latest_tts_job_id],
            )
        )
        db.add(
            Shot(
                id=shot_id,
                user_id=user_id,
                storyboard_id=storyboard_id,
                shot_number=1,
                duration=4,
                prompt="Shot 1",
                dialogue="Mo Ran: current line",
                extra_data={
                    "subtitle_text": "Mo Ran: current line",
                    "latest_tts_job_id": latest_tts_job_id,
                },
            )
        )
        db.add(
            TTSJob(
                id=old_tts_job_id,
                user_id=user_id,
                workflow_id=workflow_id,
                storyboard_id=storyboard_id,
                shot_id=shot_id,
                title="Old locked TTS",
                text="Mo Ran: old line",
                status="succeeded",
                extra_data={"voice_source": "story_bible", "voice_character_name": "Mo Ran"},
            )
        )
        db.add(
            TTSJob(
                id=latest_tts_job_id,
                user_id=user_id,
                workflow_id=workflow_id,
                storyboard_id=storyboard_id,
                shot_id=shot_id,
                title="Latest unlocked TTS",
                text="Mo Ran: current line",
                status="succeeded",
                extra_data={"voice_source": "request", "voice_character_name": "Mo Ran"},
            )
        )
        await db.commit()

    return {"workflow_id": workflow_id, "shot_id": shot_id}


async def _seed_voice_lock_workflow_with_unlisted_stale_tts(user_id: str) -> dict[str, str]:
    novel_id = f"novel-{uuid4()}"
    chapter_id = f"chapter-{uuid4()}"
    script_id = f"script-{uuid4()}"
    storyboard_id = f"storyboard-{uuid4()}"
    workflow_id = f"workflow-{uuid4()}"
    shot_id = f"shot-{uuid4()}"
    stale_tts_job_id = f"tts-{uuid4()}"

    async with AsyncSessionLocal() as db:
        db.add(Novel(id=novel_id, user_id=user_id, title="Unlisted stale voice stats novel"))
        db.add(
            Chapter(
                id=chapter_id,
                novel_id=novel_id,
                user_id=user_id,
                title="Chapter",
                content="Dialogue chapter",
                chapter_number=1,
            )
        )
        db.add(
            Script(
                id=script_id,
                user_id=user_id,
                novel_id=novel_id,
                chapter_id=chapter_id,
                title="Script",
                content="Dialogue script",
                status="draft",
            )
        )
        db.add(
            Storyboard(
                id=storyboard_id,
                user_id=user_id,
                script_id=script_id,
                novel_id=novel_id,
                title="Storyboard",
                shot_count=1,
            )
        )
        db.add(
            Workflow(
                id=workflow_id,
                user_id=user_id,
                title="Unlisted stale voice lock stats workflow",
                status="active",
                novel_id=novel_id,
                chapter_id=chapter_id,
                script_id=script_id,
                storyboard_id=storyboard_id,
                tts_job_ids=[],
            )
        )
        db.add(
            Shot(
                id=shot_id,
                user_id=user_id,
                storyboard_id=storyboard_id,
                shot_number=1,
                duration=4,
                prompt="Shot 1",
                dialogue="Mo Ran: current line",
                extra_data={"subtitle_text": "Mo Ran: current line"},
            )
        )
        db.add(
            TTSJob(
                id=stale_tts_job_id,
                user_id=user_id,
                workflow_id=workflow_id,
                storyboard_id=storyboard_id,
                shot_id=shot_id,
                title="Unlisted stale locked TTS",
                text="Mo Ran: old line",
                status="succeeded",
                extra_data={"voice_source": "story_bible", "voice_character_name": "Mo Ran"},
            )
        )
        await db.commit()

    return {"workflow_id": workflow_id, "shot_id": shot_id}


def test_voice_lock_stats_counts_story_bible_hits_and_misses(client: TestClient) -> None:
    user_id = str(uuid4())
    seeded = asyncio.run(_seed_voice_lock_workflow(user_id))

    response = client.get(
        f"/api/v1/production-control/workflow/{seeded['workflow_id']}/voice-lock-stats",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["workflow_id"] == seeded["workflow_id"]
    assert payload["total_dialogue_shots"] == 3
    assert payload["voice_locked"] == 2
    assert payload["hit_rate"] == pytest.approx(0.67)
    assert payload["misses"] == [
        {
            "shot_id": seeded["unlocked_shot_id"],
            "shot_number": 3,
            "character_name": "Lin Lan",
        }
    ]


def test_voice_lock_stats_uses_latest_tts_job_instead_of_stale_locked_hit(client: TestClient) -> None:
    user_id = str(uuid4())
    seeded = asyncio.run(_seed_voice_lock_workflow_with_stale_locked_tts(user_id))

    response = client.get(
        f"/api/v1/production-control/workflow/{seeded['workflow_id']}/voice-lock-stats",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_dialogue_shots"] == 1
    assert payload["voice_locked"] == 0
    assert payload["hit_rate"] == 0.0
    assert payload["misses"] == [
        {
            "shot_id": seeded["shot_id"],
            "shot_number": 1,
            "character_name": "Mo Ran",
        }
    ]


def test_voice_lock_stats_fallback_ignores_tts_jobs_not_listed_on_workflow(client: TestClient) -> None:
    user_id = str(uuid4())
    seeded = asyncio.run(_seed_voice_lock_workflow_with_unlisted_stale_tts(user_id))

    response = client.get(
        f"/api/v1/production-control/workflow/{seeded['workflow_id']}/voice-lock-stats",
        headers=_auth_headers(user_id),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total_dialogue_shots"] == 1
    assert payload["voice_locked"] == 0
    assert payload["hit_rate"] == 0.0
    assert payload["misses"] == [
        {
            "shot_id": seeded["shot_id"],
            "shot_number": 1,
            "character_name": "Mo Ran",
        }
    ]
