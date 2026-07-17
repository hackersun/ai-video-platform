"""Real relational-chain SQLite proof for scoped-reference backfill."""

from __future__ import annotations

import hashlib
import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.features.series_run_story_locks.domain.scoped_reference import (
    build_scoped_reference, sign_history_record, sign_merge_edge,
)
from app.features.series_run_story_locks.repositories.scoped_ref_backfill_async import (
    apply_scoped_ref_manifest, write_scoped_ref_manifest,
)


async def _database(path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    content, user, novel, chapter = "第一章来源文本", "user-1", "novel-1", "chapter-1"
    episode = {"episode_number": 1, "chapter_ids": [chapter], "input_hash": "episode-input-1",
               "canonical_ids": {"workflow_id": "workflow-1", "shot_ids": ["shot-1"]}}
    evidence = {"status": "verified", "chapter_id": chapter, "source_span": [0, 2],
                "content_hash": hashlib.sha256(content.encode()).hexdigest(), "source_excerpt": content[:2],
                "parser_version": "deterministic-extraction-v2"}
    context = {"run_id": "run-1", "series_run_id": "run-1", "shot_id": "shot-1", "episode_number": 1,
               "episode_input_hash": "episode-input-1", "chapter_id": chapter, "chapter_ids": [chapter],
               "script_id": "script-1", "storyboard_id": "board-1", "prompt": "镜头提示", "dialogue": "",
               "visual_description": "雨夜", "source_text": content, "shot_text": "镜头提示  雨夜"}
    source = {"id": "source-1", "user_id": user, "novel_id": novel, "chapter_id": chapter,
              "entity_type": "character", "canonical_name": "沈砚", "evidence_contract": evidence}
    reference = build_scoped_reference(context=context, source=source, chapter={"id": chapter, "content": content,
        "content_hash": hashlib.sha256(content.encode()).hexdigest(), "content_length": len(content)})
    history = sign_history_record({"owner_user_id": user, "owner_novel_id": novel, "owner_entity_type": "character",
        "canonical_entity_id": "canonical-1", "source_entity_id": "source-1", "chapter_id": chapter,
        "evidence_ref_id": reference["evidence_ref_id"], "metadata": {"evidence_contract": reference["evidence"]},
        "merge_audit": {"canonical_identity_sha256": reference["canonical_identity_sha256"]}})
    edge = sign_merge_edge({"source_entity_id": "source-1", "canonical_entity_id": "canonical-1",
        "user_id": user, "novel_id": novel, "entity_type": "character",
        "canonical_identity_sha256": reference["canonical_identity_sha256"]})
    async with engine.begin() as connection:
        for ddl in [
            "CREATE TABLE series_production_runs (id TEXT PRIMARY KEY,user_id TEXT,novel_id TEXT,series_plan_version TEXT,version INTEGER,run_metadata JSON,episodes JSON,updated_at TEXT)",
            "CREATE TABLE workflows (id TEXT PRIMARY KEY,user_id TEXT,novel_id TEXT,chapter_id TEXT,script_id TEXT,storyboard_id TEXT,metadata JSON)",
            "CREATE TABLE storyboards (id TEXT PRIMARY KEY,user_id TEXT,novel_id TEXT,script_id TEXT)",
            "CREATE TABLE shots (id TEXT PRIMARY KEY,storyboard_id TEXT,user_id TEXT,version INTEGER,prompt TEXT,dialogue TEXT,visual_description TEXT,extra_data JSON,updated_at TEXT)",
            "CREATE TABLE chapters (id TEXT PRIMARY KEY,novel_id TEXT,user_id TEXT,chapter_number INTEGER,content TEXT,updated_at TEXT)",
            "CREATE TABLE story_entities (id TEXT PRIMARY KEY,user_id TEXT,novel_id TEXT,chapter_id TEXT,entity_type TEXT,name TEXT,canonical_name TEXT,version INTEGER,extra_data JSON)",
        ]: await connection.execute(text(ddl))
        metadata = {"source_version": "source-1", "lock_contract_version": "required_entity_closure_v1"}
        await connection.execute(text("INSERT INTO series_production_runs VALUES ('run-1',:u,:n,'plan-1',1,:m,:e,NULL)"),
                                 {"u": user, "n": novel, "m": json.dumps(metadata), "e": json.dumps([episode])})
        await connection.execute(text("INSERT INTO workflows VALUES ('workflow-1',:u,:n,:c,'script-1','board-1','{}')"), {"u":user,"n":novel,"c":chapter})
        await connection.execute(text("INSERT INTO storyboards VALUES ('board-1',:u,:n,'script-1')"), {"u":user,"n":novel})
        shot_extra = {"chapter_id": chapter, "entity_refs": {
            "characters": [{"entity_id":"source-1","entity_type":"character"}],
            "scenes": [], "props": [], "events": []}, "refs_version": "legacy"}
        await connection.execute(text("INSERT INTO shots VALUES ('shot-1','board-1',:u,1,'镜头提示','','雨夜',:x,NULL)"), {"u":user,"x":json.dumps(shot_extra)})
        await connection.execute(text("INSERT INTO chapters VALUES (:c,:n,:u,1,:body,'2026-07-13 00:00:00')"), {"c":chapter,"n":novel,"u":user,"body":content})
        await connection.execute(text("INSERT INTO story_entities VALUES ('source-1',:u,:n,:c,'character','沈砚','沈砚',1,:x)"),
                                 {"u":user,"n":novel,"c":chapter,"x":json.dumps({"evidence_contract":evidence,"merge_edges":[edge]})})
        await connection.execute(text("INSERT INTO story_entities VALUES ('canonical-1',:u,:n,:c,'character','沈砚','沈砚',1,:x)"),
                                 {"u":user,"n":novel,"c":chapter,"x":json.dumps({"canonical_histories":[history]})})
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_real_chain_builds_full_resolvable_ref_and_audit(tmp_path):
    engine, sessions = await _database(tmp_path / "backfill.db"); manifest = tmp_path / "manifest.json"
    async with sessions() as db:
        preview = await write_scoped_ref_manifest(db, run_id="run-1", manifest_path=manifest, database_path=tmp_path/"backfill.db")
    proposed = json.loads(manifest.read_text())["ref_decisions"][0]["proposed_ref"]
    assert proposed["contract_version"] == "chapter_evidence_ref_v1" and proposed["evidence_ref_id"]
    async with sessions() as db:
        result = await apply_scoped_ref_manifest(db, manifest_path=manifest, expected_manifest_hash=preview["manifest_sha256"], database_path=tmp_path/"backfill.db")
        audit = json.loads((await db.execute(text("SELECT run_metadata FROM series_production_runs"))).scalar_one())["scoped_ref_backfill_audit"][0]
    assert result["updated_ref_count"] == 1 and audit["actor_user_id"] == "user-1"
    assert audit["affected_shots"][0]["shot_id"] == "shot-1" and audit["timestamp_utc"].endswith("+00:00")
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["after_first_ref","after_last_ref","after_audit","before_commit"])
async def test_all_failpoints_rollback_real_rows(tmp_path, failure):
    engine, sessions = await _database(tmp_path/f"{failure}.db"); manifest=tmp_path/f"{failure}.json"
    async with sessions() as db: preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=tmp_path/f"{failure}.db")
    async with sessions() as db:
        with pytest.raises(RuntimeError,match="injected"):
            await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=preview["manifest_sha256"],database_path=tmp_path/f"{failure}.db",fail_at=failure)
    async with sessions() as db: extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
    assert extra["refs_version"] == "legacy"
    await engine.dispose()


@pytest.mark.asyncio
async def test_same_user_cross_novel_chain_is_zero_write(tmp_path):
    engine,sessions=await _database(tmp_path/"foreign.db"); manifest=tmp_path/"foreign.json"
    async with sessions() as db:
        await db.execute(text("UPDATE storyboards SET novel_id='other-novel'")); await db.commit()
        with pytest.raises(ValueError,match="novel"):
            await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=tmp_path/"foreign.db")
    assert not manifest.exists(); await engine.dispose()


@pytest.mark.asyncio
async def test_exact_apply_is_idempotent_with_one_audit(tmp_path):
    path=tmp_path/"repeat.db"; engine,sessions=await _database(path); manifest=tmp_path/"repeat.json"
    async with sessions() as db: preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    async with sessions() as db: first=await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=preview["manifest_sha256"],database_path=path)
    async with sessions() as db: second=await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=preview["manifest_sha256"],database_path=path)
    async with sessions() as db: metadata=json.loads((await db.execute(text("SELECT run_metadata FROM series_production_runs"))).scalar_one())
    assert first["updated_ref_count"] == 1 and second == {"idempotent":True,"updated_ref_count":0}
    assert len(metadata["scoped_ref_backfill_audit"]) == 1; await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["run","episodes","chapter","shot","history","merge","cross_run"])
async def test_authoritative_toctou_is_zero_write(tmp_path, mutation):
    path=tmp_path/f"{mutation}.db"; engine,sessions=await _database(path); manifest=tmp_path/f"{mutation}.json"
    async with sessions() as db: preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    statements={
        "run":"UPDATE series_production_runs SET version=2",
        "episodes":"UPDATE series_production_runs SET episodes='[]'",
        "chapter":"UPDATE chapters SET content='changed'",
        "shot":"UPDATE shots SET version=2",
        "history":"UPDATE story_entities SET version=2 WHERE id='canonical-1'",
        "merge":"UPDATE story_entities SET version=2 WHERE id='source-1'",
        "cross_run":"UPDATE series_production_runs SET episodes=:episodes",
    }
    values = ({"episodes": json.dumps([{"episode_number":1,"chapter_ids":["chapter-1"],"input_hash":"x",
               "canonical_ids":{"workflow_id":"workflow-1","shot_ids":[]}}])} if mutation == "cross_run" else {})
    async with sessions() as db: await db.execute(text(statements[mutation]), values); await db.commit()
    async with sessions() as db:
        with pytest.raises(ValueError): await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=preview["manifest_sha256"],database_path=path)
    async with sessions() as db:
        extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
        metadata=json.loads((await db.execute(text("SELECT run_metadata FROM series_production_runs"))).scalar_one())
    assert extra["refs_version"] == "legacy" and "scoped_ref_backfill_audit" not in metadata
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", ["permissions","body","expected_hash"])
async def test_manifest_security_rejects_before_real_writes(tmp_path, tamper):
    path=tmp_path/f"{tamper}.db"; engine,sessions=await _database(path); manifest=tmp_path/f"{tamper}.json"
    async with sessions() as db: preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    expected=preview["manifest_sha256"]
    if tamper == "permissions": manifest.chmod(0o644)
    elif tamper == "body": manifest.write_text(manifest.read_text().replace("plan-1","plan-x")); manifest.chmod(0o600)
    else: expected="f"*64
    async with sessions() as db:
        with pytest.raises(ValueError): await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=expected,database_path=path)
    async with sessions() as db: extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
    assert extra["refs_version"] == "legacy"; await engine.dispose()


@pytest.mark.asyncio
async def test_already_complete_v1_refs_are_the_only_zero_decision_noop(tmp_path):
    path=tmp_path/"noop.db"; engine,sessions=await _database(path); first=tmp_path/"first.json"
    async with sessions() as db: preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=first,database_path=path)
    async with sessions() as db: await apply_scoped_ref_manifest(db,manifest_path=first,expected_manifest_hash=preview["manifest_sha256"],database_path=path)
    second=tmp_path/"second.json"
    async with sessions() as db: noop=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=second,database_path=path)
    assert noop["eligible"] is True and noop["eligible_ref_count"] == 0
    assert json.loads(second.read_text())["no_op"] is True; await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("attack", ["empty","flat","ambiguous","wrong_owner"])
async def test_unrecognized_or_ambiguous_real_refs_fail_before_manifest(tmp_path, attack):
    path=tmp_path/f"{attack}.db"; engine,sessions=await _database(path); manifest=tmp_path/f"{attack}.json"
    async with sessions() as db:
        if attack in {"empty","flat"}:
            extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
            extra["entity_refs"] = ({"characters":[],"scenes":[],"props":[],"events":[]} if attack=="empty" else [{"entity_id":"source-1"}])
            await db.execute(text("UPDATE shots SET extra_data=:x"),{"x":json.dumps(extra)})
        elif attack == "wrong_owner":
            await db.execute(text("UPDATE story_entities SET user_id='other-user' WHERE id='source-1'"))
        else:
            await db.execute(text("INSERT INTO story_entities SELECT 'source-2',user_id,novel_id,chapter_id,entity_type,'别名','其他名',1,extra_data FROM story_entities WHERE id='source-1'"))
        await db.commit()
        with pytest.raises(ValueError,match="zero|shape|source|ambiguous"):
            await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    assert not manifest.exists(); await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("source_form", ["source-1", {"id":"source-1"}, {"story_entity_id":"source-1"}])
async def test_public_normalizer_source_forms_produce_real_decisions(tmp_path, source_form):
    path=tmp_path/"forms.db"; engine,sessions=await _database(path); manifest=tmp_path/"forms.json"
    async with sessions() as db:
        extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
        extra["entity_refs"]["characters"]=[source_form]
        await db.execute(text("UPDATE shots SET extra_data=:x"),{"x":json.dumps(extra)}); await db.commit()
        result=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    assert result["eligible_ref_count"] == 1
    assert json.loads(manifest.read_text())["ref_decisions"][0]["proposed_ref"]["source_entity_id"] == "source-1"
    await engine.dispose()


@pytest.mark.asyncio
async def test_two_same_category_refs_are_grouped_into_one_shot_update(tmp_path):
    path=tmp_path/"multi.db"; engine,sessions=await _database(path); manifest=tmp_path/"multi.json"
    async with sessions() as db:
        source=json.loads((await db.execute(text("SELECT extra_data FROM story_entities WHERE id='source-1'"))).scalar_one())
        evidence=dict(source["evidence_contract"]); evidence.update(source_span=[2,4],source_excerpt="章来")
        await db.execute(text("INSERT INTO story_entities VALUES ('source-2','user-1','novel-1','chapter-1','character','顾川','顾川',1,:x)"),
                         {"x":json.dumps({"evidence_contract":evidence})})
        extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
        extra["entity_refs"]["characters"].append({"story_entity_id":"source-2"})
        await db.execute(text("UPDATE shots SET extra_data=:x"),{"x":json.dumps(extra)}); await db.commit()
        preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    assert preview["eligible_ref_count"] == 2
    async with sessions() as db: await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=preview["manifest_sha256"],database_path=path)
    async with sessions() as db:
        row=await db.execute(text("SELECT version,extra_data FROM shots")); version,extra=row.one(); refs=json.loads(extra)["entity_refs"]["characters"]
        audit=json.loads((await db.execute(text("SELECT run_metadata FROM series_production_runs"))).scalar_one())["scoped_ref_backfill_audit"][0]
    assert version == 2 and [item["source_entity_id"] for item in refs] == ["source-1","source-2"]
    assert audit["updated_ref_count"] == 2 and audit["updated_shot_count"] == 1
    assert audit["affected_shots"][0]["affected_entity_ids"] == ["source-1","source-2"]
    await engine.dispose()


@pytest.mark.asyncio
async def test_two_shots_report_ref_and_shot_counts_consistently(tmp_path):
    path=tmp_path/"two-shots.db"; engine,sessions=await _database(path); manifest=tmp_path/"two-shots.json"
    async with sessions() as db:
        extra=json.loads((await db.execute(text("SELECT extra_data FROM shots"))).scalar_one())
        await db.execute(text("INSERT INTO shots VALUES ('shot-2','board-1','user-1',1,'镜头提示','','雨夜',:x,NULL)"),{"x":json.dumps(extra)})
        episodes=json.loads((await db.execute(text("SELECT episodes FROM series_production_runs"))).scalar_one())
        episodes[0]["canonical_ids"]["shot_ids"].append("shot-2")
        await db.execute(text("UPDATE series_production_runs SET episodes=:x"),{"x":json.dumps(episodes)}); await db.commit()
        preview=await write_scoped_ref_manifest(db,run_id="run-1",manifest_path=manifest,database_path=path)
    async with sessions() as db:
        result=await apply_scoped_ref_manifest(db,manifest_path=manifest,expected_manifest_hash=preview["manifest_sha256"],database_path=path)
        metadata=json.loads((await db.execute(text("SELECT run_metadata FROM series_production_runs"))).scalar_one())
    audit=metadata["scoped_ref_backfill_audit"][0]
    assert result["updated_ref_count"] == audit["updated_ref_count"] == 2
    assert audit["updated_shot_count"] == 2 and len(audit["affected_shots"]) == 2
    await engine.dispose()
