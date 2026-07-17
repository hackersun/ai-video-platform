from __future__ import annotations

from contextlib import asynccontextmanager
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.core.database import Base


def _checksum(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()


@asynccontextmanager
async def _isolated_session(tmp_path):
    from app.db_migrations.runner import register_production_models

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / f'{uuid4()}.db'}")
    register_production_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            yield session
    finally:
        await engine.dispose()


def _profile(*, user_id: str, key: str, task: str):
    from app.models import PromptProfile

    return PromptProfile(
        id=str(uuid4()), user_id=user_id, key=key, name=key, task=task,
    )


def _version(profile_id: str, *, version: int, content: str, routing: dict, status: str):
    from app.models import PromptProfileVersion

    return PromptProfileVersion(
        id=str(uuid4()), profile_id=profile_id, version=version, stage="analysis",
        content=content, variables={}, routing=routing, output_contract="json_array",
        evaluation={}, status=status, checksum=_checksum(content),
    )


async def _seed_version(
    db: AsyncSession, *, user_id: str, key: str, task: str, routing: dict,
    content: str | None = None, version: int = 1, status: str = "published",
):
    profile = _profile(user_id=user_id, key=key, task=task)
    row = _version(
        profile.id, version=version, content=content or key, routing=routing, status=status,
    )
    db.add_all((profile, row))
    await db.commit()
    return profile, row


@pytest.mark.asyncio
async def test_prompt_profile_tables_are_registered(tmp_path) -> None:
    from app.db_migrations.runner import register_production_models

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'schema.db'}")
    register_production_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        tables = await connection.run_sync(lambda bind: set(inspect(bind).get_table_names()))
    await engine.dispose()

    assert {"prompt_profiles", "prompt_profile_versions"} <= tables


@pytest.mark.asyncio
async def test_published_prompt_edit_creates_new_draft_and_preserves_history(tmp_path) -> None:
    from app.features.prompt_profiles.public import edit_prompt_profile

    async with _isolated_session(tmp_path) as db:
        _, published = await _seed_version(
            db, user_id="user-1", key="script.minimax", task="script_generation",
            routing={"model_filter": ["MiniMax-M3"]}, content="old", version=3,
        )
        draft = await edit_prompt_profile(db, published.id, {"content": "new"})
        await db.refresh(published)

        assert draft.version == 4
        assert draft.status == "draft"
        assert draft.content == "new"
        assert published.content == "old"
        assert published.status == "published"


@pytest.mark.asyncio
async def test_published_prompt_rows_reject_update_and_delete(tmp_path) -> None:
    async with _isolated_session(tmp_path) as db:
        _, published = await _seed_version(
            db, user_id="user-1", key="script.safe", task="script_generation",
            routing={}, content="immutable",
        )
        published_id = published.id
        published_type = type(published)
        published.content = "mutated"
        with pytest.raises(ValueError, match="append-only"):
            await db.commit()
        await db.rollback()

        published = await db.get(published_type, published_id)
        await db.delete(published)
        with pytest.raises(ValueError, match="append-only"):
            await db.commit()


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_published_prompt_rows_reject_direct_database_mutation(tmp_path, operation) -> None:
    from app.db_migrations.model_center import add_model_center_links
    from app.db_migrations.runner import register_production_models
    from app.models import PromptProfile, PromptProfileVersion

    engine = create_engine(f"sqlite:///{tmp_path / f'guard-{operation}.db'}")
    register_production_models()
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(PromptProfile(
            id="profile-1", user_id="user-1", key="guard", name="Guard",
            task="script_generation",
        ))
        db.add(PromptProfileVersion(
            id="version-1", profile_id="profile-1", version=1, content="immutable",
            variables={}, routing={}, evaluation={}, status="published", checksum="a" * 64,
        ))
        db.commit()
    add_model_center_links(engine)
    statement = (
        text("UPDATE prompt_profile_versions SET content = 'changed' WHERE id = 'version-1'")
        if operation == "update"
        else text("DELETE FROM prompt_profile_versions WHERE id = 'version-1'")
    )

    with pytest.raises(DBAPIError, match="append-only"):
        with engine.begin() as connection:
            connection.execute(statement)
    engine.dispose()


@pytest.mark.asyncio
async def test_same_task_can_publish_different_model_specific_profiles(tmp_path) -> None:
    from app.features.prompt_profiles.public import select_prompt_profile_version

    async with _isolated_session(tmp_path) as db:
        _, minimax = await _seed_version(
            db, user_id="user-1", key="script.minimax", task="script_generation",
            routing={"model_filter": ["MiniMax-M3"]},
        )
        _, doubao = await _seed_version(
            db, user_id="user-1", key="script.doubao", task="script_generation",
            routing={"model_filter": ["doubao-seed-*"]},
        )
        selected_minimax = await select_prompt_profile_version(
            db, user_id="user-1", task="script_generation", provider_id="minimax",
            model_id="MiniMax-M3", capabilities={"text_generation"},
            output_contract="json_array",
        )
        selected_doubao = await select_prompt_profile_version(
            db, user_id="user-1", task="script_generation", provider_id="volcano",
            model_id="doubao-seed-1-8-251228", capabilities={"text_generation"},
            output_contract="json_array",
        )

        assert selected_minimax.id == minimax.id
        assert selected_doubao.id == doubao.id


@pytest.mark.asyncio
async def test_prompt_routing_uses_explicit_specificity_precedence(tmp_path) -> None:
    from app.features.prompt_profiles.public import select_prompt_profile_version

    async with _isolated_session(tmp_path) as db:
        candidates = (
            ("generic", {}),
            ("capability", {"capability_filter": ["text_generation"]}),
            ("provider", {"provider_filter": ["volcano"]}),
            ("family", {"model_filter": ["doubao-seed-*"]}),
            ("exact", {"model_filter": ["doubao-seed-1-8-251228"]}),
        )
        seeded = {}
        for key, routing in candidates:
            _, seeded[key] = await _seed_version(
                db, user_id="user-1", key=f"script.{key}", task="script_generation",
                routing=routing,
            )
        selected = await select_prompt_profile_version(
            db, user_id="user-1", task="script_generation", provider_id="volcano",
            model_id="doubao-seed-1-8-251228", capabilities={"text_generation"},
            output_contract="json_array",
        )

        assert selected.id == seeded["exact"].id


@pytest.mark.asyncio
async def test_prompt_routing_tie_break_is_deterministic(tmp_path) -> None:
    from app.features.prompt_profiles.public import select_prompt_profile_version

    async with _isolated_session(tmp_path) as db:
        first_profile, first = await _seed_version(
            db, user_id="user-1", key="a-profile", task="script_generation", routing={},
        )
        await _seed_version(
            db, user_id="user-1", key="z-profile", task="script_generation", routing={},
        )
        selections = [
            await select_prompt_profile_version(
                db, user_id="user-1", task="script_generation", provider_id="unknown",
                model_id="unknown", capabilities=set(), output_contract="json_array",
            )
            for _ in range(3)
        ]

        assert {item.id for item in selections} == {first.id}
        assert first.profile_id == first_profile.id


@pytest.mark.asyncio
async def test_evaluation_evidence_persists_hashes_without_prompts_or_secrets(tmp_path) -> None:
    from app.features.prompt_profiles.public import (
        build_evaluation_evidence,
        record_prompt_evaluation,
    )

    async with _isolated_session(tmp_path) as db:
        _, draft = await _seed_version(
            db, user_id="user-1", key="script.eval", task="script_generation",
            routing={}, status="draft",
        )
        evidence = build_evaluation_evidence(
            fixture_id="fixture-1", status="passed", prompt="private prompt body",
            output="private model output", metrics={
                "score": 0.95, "api_key": "secret-key",
                "model_note": "private prompt body",
                "nested": {"authorization": "Bearer secret", "parse_ok": True},
            },
        )
        recorded = await record_prompt_evaluation(db, draft.id, evidence)
        serialized = str(recorded.evaluation)

        assert recorded.evaluation["prompt_hash"] == _checksum("private prompt body")
        assert recorded.evaluation["output_hash"] == _checksum("private model output")
        assert "private prompt body" not in serialized
        assert "private model output" not in serialized
        assert "secret-key" not in serialized
        assert "Bearer secret" not in serialized
        assert "model_note" not in recorded.evaluation["metrics"]
        assert recorded.evaluation["metrics"]["nested"] == {"parse_ok": True}
