from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.database import AsyncSessionLocal
from app.models import PromptSkill
from init_db import init_db

ROUTING_TEST_TASK = "entity_extraction_route_test"


@pytest.fixture(scope="module", autouse=True)
def _init_database() -> None:
    init_db()


def _run(coro):
    return asyncio.run(coro)


def _skill(
    *,
    user_id: str,
    name: str,
    content: str,
    is_builtin: bool,
    routing: dict,
    priority: int = 50,
) -> PromptSkill:
    return PromptSkill(
        id=f"routing-skill-{uuid4()}",
        user_id=user_id,
        name=name,
        task=ROUTING_TEST_TASK,
        stage="analysis",
        content=content,
        variables={"routing": routing},
        priority=priority,
        is_active=True,
        is_builtin=is_builtin,
    )


def test_prompt_router_selects_provider_and_output_contract_template() -> None:
    async def scenario() -> dict:
        from app.services.prompt_template_router import select_prompt_skill_for_model

        user_id = f"route-user-{uuid4().hex[:20]}"
        async with AsyncSessionLocal() as db:
            db.add(
                _skill(
                    user_id="system",
                    name="DashScope JSON 抽取",
                    content="dashscope-json-template",
                    is_builtin=True,
                    routing={"provider_filter": ["dashscope"], "model_filter": ["qwen-*"], "output_contract": "json_array"},
                )
            )
            db.add(
                _skill(
                    user_id="system",
                    name="通用抽取",
                    content="generic-template",
                    is_builtin=True,
                    routing={"output_contract": "json_array"},
                    priority=90,
                )
            )
            await db.commit()

            route = await select_prompt_skill_for_model(
                db,
                user_id=user_id,
                task=ROUTING_TEST_TASK,
                provider_name="dashscope",
                model_id="qwen-plus",
                model_capabilities=["json_mode"],
                output_contract="json_array",
                context={"entity_types": "character"},
            )
            return route

    result = _run(scenario())

    assert result["prompt_skill_name"] == "DashScope JSON 抽取"
    assert result["output_contract"] == "json_array"
    assert result["routing_reason"] in {"provider_model_contract_match", "model_contract_match"}


def test_prompt_router_prefers_user_owned_matching_template_over_builtin() -> None:
    async def scenario() -> dict:
        from app.services.prompt_template_router import select_prompt_skill_for_model

        user_id = f"route-user-{uuid4().hex[:20]}"
        async with AsyncSessionLocal() as db:
            db.add(
                _skill(
                    user_id="system",
                    name="Volcano 内置模板",
                    content="builtin-volcano",
                    is_builtin=True,
                    routing={"provider_filter": ["volcano"], "model_filter": ["doubao-*"], "output_contract": "json_schema"},
                )
            )
            db.add(
                _skill(
                    user_id=user_id,
                    name="我的火山模板",
                    content="user-volcano",
                    is_builtin=False,
                    routing={"provider_filter": ["volcano"], "model_filter": ["doubao-*"], "output_contract": "json_schema"},
                    priority=99,
                )
            )
            await db.commit()

            route = await select_prompt_skill_for_model(
                db,
                user_id=user_id,
                task=ROUTING_TEST_TASK,
                provider_name="volcano",
                model_id="doubao-seed-1-8",
                model_capabilities=["json_schema"],
                output_contract="json_schema",
                context={},
            )
            return route

    result = _run(scenario())

    assert result["prompt_skill_name"] == "我的火山模板"
    assert result["selected_scope"] == "user"


def test_prompt_router_falls_back_to_task_template_for_unknown_provider() -> None:
    async def scenario() -> dict:
        from app.services.prompt_template_router import select_prompt_skill_for_model

        user_id = f"route-user-{uuid4().hex[:20]}"
        async with AsyncSessionLocal() as db:
            db.add(
                PromptSkill(
                    id=f"routing-skill-{uuid4()}",
                    user_id=user_id,
                    name="任务级模板",
                    task=ROUTING_TEST_TASK,
                    stage="analysis",
                    content="task-only-template",
                    variables={},
                    priority=10,
                    is_active=True,
                    is_builtin=False,
                )
            )
            await db.commit()

            route = await select_prompt_skill_for_model(
                db,
                user_id=user_id,
                task=ROUTING_TEST_TASK,
                provider_name="unknown",
                model_id="mystery-model",
                model_capabilities=[],
                output_contract="json_array",
                context={},
            )
            return route

    result = _run(scenario())

    assert result["prompt_skill_name"] == "任务级模板"
    assert result["fallback_reason"] == "task_only_template"


def test_prompt_router_exposes_known_model_contract_without_prompt_text_evidence() -> None:
    async def scenario() -> dict:
        from app.services.prompt_template_router import select_prompt_skill_for_model

        user_id = f"route-user-{uuid4().hex[:20]}"
        async with AsyncSessionLocal() as db:
            db.add(_skill(
                user_id="system", name="MiniMax 文本模板", content="minimax-template",
                is_builtin=True,
                routing={"provider_filter": ["minimax"], "model_filter": ["MiniMax-M3"]},
            ))
            await db.commit()
            return await select_prompt_skill_for_model(
                db, user_id=user_id, task=ROUTING_TEST_TASK, provider_name="minimax",
                model_id="MiniMax-M3", capability="text", internal_prompt="小说原文不得进入证据",
            )

    result = _run(scenario())

    assert result["model_contract_version"] == "minimax.text.m3.v1"
    assert result["prompt_profile"] == "minimax.text.m3"
    assert result["model_verification_status"] == "verified"
    evidence = {key: value for key, value in result.items() if key != "prompt"}
    assert "小说原文不得进入证据" not in str(evidence)
