from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal
from app.models import PromptSkill
from app.services.consistency_context import build_consistency_prompt
from app.services.prompt_composer import compose_generation_prompt
from init_db import init_db
from main import app
from test_short_video_production import _auth_headers


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DEV_MODE", "true")
    return TestClient(app)


def test_prompt_skill_preview_renders_selected_inactive_skill(client: TestClient) -> None:
    user_id = f"prompt-skill-preview-user-{uuid4()}"
    create_response = client.post(
        "/api/v1/prompt-skills",
        json={
            "name": "待激活镜头技能",
            "task": "shot_video",
            "stage": "consistency",
            "content": "技能约束: 使用{tone}，避免{bad_case}。",
            "variables": {"tone": "冷蓝光影", "bad_case": "角色漂移"},
            "priority": 10,
            "inject_position": "before_constraints",
            "is_active": False,
        },
        headers=_auth_headers(user_id),
    )
    assert create_response.status_code == 201
    skill_id = create_response.json()["id"]

    preview_response = client.post(
        "/api/v1/prompt-skills/preview",
        json={
            "task": "shot_video",
            "skill_ids": [skill_id],
            "context": {"tone": "冷蓝月光", "bad_case": "脸型变化"},
        },
        headers=_auth_headers(user_id),
    )

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["skill_count"] == 1
    assert "技能约束: 使用冷蓝月光，避免脸型变化。" in preview["prompt"]
    assert preview["prompt"].index("技能约束: 使用冷蓝月光") < preview["prompt"].index("视频一致性约束:")


def test_prompt_skill_blocks_preserve_video_and_locked_asset_constraints() -> None:
    prompt = compose_generation_prompt(
        task="shot_video",
        skill_blocks=["技能约束: 保持冷蓝月光，不改变主角脸型。"],
        locked_assets=[
            {"type": "character", "name": "林夏"},
            {"type": "scene", "name": "旧天台"},
        ],
    )

    assert "Prompt技能约束:" in prompt
    assert "技能约束: 保持冷蓝月光，不改变主角脸型。" in prompt
    assert "视频一致性约束:" in prompt
    assert "【锁定资产一致性约束】" in prompt
    assert "林夏" in prompt
    assert "旧天台" in prompt
    assert prompt.index("技能约束: 保持冷蓝月光") < prompt.index("视频一致性约束:")
    assert prompt.index("视频一致性约束:") < prompt.index("【锁定资产一致性约束】")


@pytest.mark.asyncio
async def test_build_consistency_prompt_injects_active_prompt_skill_blocks() -> None:
    user_id = f"prompt-skill-context-user-{uuid4()}"
    skill_id = f"skill-{uuid4()}"
    async with AsyncSessionLocal() as db:
        db.add(
            PromptSkill(
                id=skill_id,
                user_id=user_id,
                name="一致性补强技能",
                task="shot_video",
                stage="consistency",
                content="技能约束: 使用{tone}，避免{bad_case}。",
                variables={"tone": "冷蓝光影", "bad_case": "角色漂移"},
                priority=10,
                inject_position="before_constraints",
                version=4,
                is_active=True,
            )
        )
        await db.commit()

        context = await build_consistency_prompt(
            db,
            user_id,
            task="shot_video",
            base_prompt="主角走入旧天台",
            extra_context={"tone": "冷蓝月光", "bad_case": "脸型变化"},
        )

    assert "技能约束: 使用冷蓝月光，避免脸型变化。" in context["prompt"]
    assert context["prompt"].index("技能约束: 使用冷蓝月光") < context["prompt"].index("视频一致性约束:")
    assert context["metadata"]["prompt_skill_count"] == 1
    assert context["metadata"]["prompt_skills"][0]["id"] == skill_id
    assert context["metadata"]["prompt_skills"][0]["version"] == 4
