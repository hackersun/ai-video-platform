"""
初始化数据库表
"""

from app.core.database import Base, engine, sync_engine
from app.db_migrations.script_chapter_lineage import (
    add_script_chapter_lineage,
    add_script_chapter_lineage_async,
)


# Migration: Add shot image fields
def migrate_add_shot_image_fields():
    """Add image_url, image_status, image_asset_id to shots table."""
    from sqlalchemy import text, inspect
    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        existing = {col["name"] for col in inspector.get_columns("shots")}
        new_cols = {"image_url", "image_status", "image_asset_id"} - existing
        if not new_cols:
            return  # already migrated
        for col in new_cols:
            if col == "image_status":
                conn.execute(text("ALTER TABLE shots ADD COLUMN image_status VARCHAR(20) DEFAULT 'pending'"))
            elif col == "image_url":
                conn.execute(text("ALTER TABLE shots ADD COLUMN image_url TEXT"))
            elif col == "image_asset_id":
                conn.execute(text("ALTER TABLE shots ADD COLUMN image_asset_id VARCHAR(36)"))
        conn.commit()
        print("✅ Shot image fields migration completed.")
    finally:
        conn.close()


def migrate_add_job_lineage_fields():
    """Add project_id/workflow_id lineage columns to generation job tables."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        table_columns = {
            table_name: {col["name"] for col in inspector.get_columns(table_name)}
            for table_name in ("video_jobs", "tts_jobs", "synthesis_jobs")
            if inspector.has_table(table_name)
        }
        expected_columns = {
            "video_jobs": ("project_id", "workflow_id", "shot_id"),
            "tts_jobs": (
                "project_id",
                "workflow_id",
                "novel_id",
                "chapter_id",
                "script_id",
                "storyboard_id",
                "shot_id",
                "character_id",
            ),
            "synthesis_jobs": ("project_id", "workflow_id"),
        }
        for table_name, existing in table_columns.items():
            for col in expected_columns.get(table_name, ()):
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} VARCHAR(36)"))
        conn.commit()
        print("✅ Job lineage fields migration completed.")
    finally:
        conn.close()


def migrate_add_workflow_context_fields():
    """Add workflow context columns used by current ORM models."""
    from sqlalchemy import text, inspect

    column_specs = {
        "storyboards": {
            "novel_id": "VARCHAR(36)",
            "style": "VARCHAR(50)",
            "genre": "VARCHAR(50)",
            "characters": "JSON",
        },
        "tts_jobs": {
            "novel_id": "VARCHAR(36)",
            "chapter_id": "VARCHAR(36)",
            "script_id": "VARCHAR(36)",
            "storyboard_id": "VARCHAR(36)",
            "shot_id": "VARCHAR(36)",
            "character_id": "VARCHAR(36)",
            "api_provider": "VARCHAR(20)",
        },
        "shots": {
            "camera_movement": "VARCHAR(50)",
            "movement_speed": "FLOAT DEFAULT 1.0",
            "movement_start_pos": "VARCHAR(50)",
            "movement_end_pos": "VARCHAR(50)",
            "emotion": "VARCHAR(50)",
            "emotion_intensity": "FLOAT DEFAULT 0.5",
            "lighting": "VARCHAR(50)",
            "color_grading": "VARCHAR(50)",
            "music_cue": "VARCHAR(500)",
            "sfx_cue": "VARCHAR(500)",
            "ambient_sound": "VARCHAR(500)",
            "keyframes": "JSON",
            "version": "INTEGER DEFAULT 1",
            "parent_shot_id": "VARCHAR(36)",
            "version_note": "VARCHAR(200)",
            "timeline_track": "INTEGER DEFAULT 0",
            "timeline_position": "FLOAT DEFAULT 0.0",
            "character_refs": "JSON",
            "extra_data": "JSON",
        },
        "llm_models": {
            "base_url": "VARCHAR(500)",
        },
    }

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        for table_name, specs in column_specs.items():
            if not inspector.has_table(table_name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for col, sql_type in specs.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"))
        conn.commit()
        print("✅ Workflow context fields migration completed.")
    finally:
        conn.close()


def migrate_add_character_scope_fields():
    """Add novel/chapter ownership columns to characters."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        if not inspector.has_table("characters"):
            return
        existing = {col["name"] for col in inspector.get_columns("characters")}
        for col in ("novel_id", "chapter_id"):
            if col not in existing:
                conn.execute(text(f"ALTER TABLE characters ADD COLUMN {col} VARCHAR(36)"))
        conn.commit()
        print("✅ Character scope fields migration completed.")
    finally:
        conn.close()


def migrate_add_media_subtitle_fields():
    """Add compatibility columns for media/subtitle production objects."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        table_specs = {
            "media_generation_jobs": {
                "capabilities": "JSON",
                "input_assets": "JSON",
                "source_job_ids": "JSON",
                "quality_report": "JSON",
                "extra_data": "JSON",
                "is_active": "BOOLEAN DEFAULT 1",
            },
            "subtitle_tracks": {
                "export_urls": "JSON",
                "metadata": "JSON",
                "is_active": "BOOLEAN DEFAULT 1",
            },
            "subtitle_segments": {
                "style": "JSON",
                "metadata": "JSON",
                "is_active": "BOOLEAN DEFAULT 1",
            },
            "video_jobs": {
                "audio_url": "TEXT",
                "subtitle_track_id": "VARCHAR(36)",
                "media_type": "VARCHAR(50)",
                "task_type": "VARCHAR(50)",
            },
        }
        for table_name, specs in table_specs.items():
            if not inspector.has_table(table_name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for col, sql_type in specs.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"))
        conn.commit()
        print("✅ Media/subtitle compatibility migration completed.")
    finally:
        conn.close()


def migrate_add_user_account_fields():
    """Add account recovery/profile columns to users."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        if not inspector.has_table("users"):
            return
        existing = {col["name"] for col in inspector.get_columns("users")}
        specs = {
            "avatar": "VARCHAR(500)",
            "reset_token_hash": "VARCHAR(128)",
            "reset_token_expires_at": "DATETIME",
            "account_status": "VARCHAR(32) DEFAULT 'active'",
            "email_verified_at": "DATETIME",
            "email_verification_token_hash": "VARCHAR(64)",
            "email_verification_token_expires_at": "DATETIME",
        }
        for col, sql_type in specs.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {sql_type}"))
        conn.execute(text("UPDATE users SET account_status = 'active' WHERE account_status IS NULL"))
        conn.execute(
            text(
                "UPDATE users SET email_verified_at = COALESCE(email_verified_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE is_active IS TRUE"
            )
        )
        conn.commit()
        print("✅ User account fields migration completed.")
    finally:
        conn.close()


def migrate_add_entity_asset_scope_fields():
    """Add novel/chapter/script/entity scope columns for entities and assets."""
    from sqlalchemy import text, inspect

    table_specs = {
        "story_entities": {
            "script_id": "VARCHAR(36)",
        },
        "assets": {
            "novel_id": "VARCHAR(36)",
            "chapter_id": "VARCHAR(36)",
            "script_id": "VARCHAR(36)",
            "entity_id": "VARCHAR(36)",
            "entity_type": "VARCHAR(20)",
            "source_url": "TEXT",
            "generation_params": "JSON",
            "version": "INTEGER DEFAULT 1",
            "is_locked": "BOOLEAN DEFAULT 0",
            "locked_at": "DATETIME",
            "locked_by": "VARCHAR(36)",
            "is_final": "BOOLEAN DEFAULT 0",
            "replaced_by_id": "VARCHAR(36)",
            "source_job_id": "VARCHAR(36)",
            "source_prompt": "TEXT",
        },
    }

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        for table_name, specs in table_specs.items():
            if not inspector.has_table(table_name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for col, sql_type in specs.items():
                if col not in existing:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"))
        conn.commit()
        print("✅ Entity/asset scope fields migration completed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def migrate_add_shot_image_fields_async():
    """Add image_url, image_status, image_asset_id to shots table (async)."""
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            if not inspector.has_table("shots"):
                return set()
            return {col["name"] for col in inspector.get_columns("shots")}

        existing = await conn.run_sync(_inspect)
        new_cols = {"image_url", "image_status", "image_asset_id"} - existing
        if not new_cols:
            return  # already migrated
        for col in new_cols:
            if col == "image_status":
                await conn.execute(text("ALTER TABLE shots ADD COLUMN image_status VARCHAR(20) DEFAULT 'pending'"))
            elif col == "image_url":
                await conn.execute(text("ALTER TABLE shots ADD COLUMN image_url TEXT"))
            elif col == "image_asset_id":
                await conn.execute(text("ALTER TABLE shots ADD COLUMN image_asset_id VARCHAR(36)"))
        print("✅ Shot image fields migration completed (async).")


async def migrate_add_job_lineage_fields_async():
    """Add project_id/workflow_id lineage columns to generation job tables (async)."""
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return {
                table_name: {col["name"] for col in inspector.get_columns(table_name)}
                for table_name in ("video_jobs", "tts_jobs", "synthesis_jobs")
                if inspector.has_table(table_name)
            }

        table_columns = await conn.run_sync(_inspect)
        expected_columns = {
            "video_jobs": ("project_id", "workflow_id", "shot_id"),
            "tts_jobs": (
                "project_id",
                "workflow_id",
                "novel_id",
                "chapter_id",
                "script_id",
                "storyboard_id",
                "shot_id",
                "character_id",
            ),
            "synthesis_jobs": ("project_id", "workflow_id"),
        }
        for table_name, existing in table_columns.items():
            for col in expected_columns.get(table_name, ()):
                if col not in existing:
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} VARCHAR(36)"))
        print("✅ Job lineage fields migration completed (async).")


async def migrate_add_workflow_context_fields_async():
    """Add workflow context columns used by current ORM models (async)."""
    from sqlalchemy import text, inspect

    column_specs = {
        "storyboards": {
            "novel_id": "VARCHAR(36)",
            "style": "VARCHAR(50)",
            "genre": "VARCHAR(50)",
            "characters": "JSON",
        },
        "tts_jobs": {
            "novel_id": "VARCHAR(36)",
            "chapter_id": "VARCHAR(36)",
            "script_id": "VARCHAR(36)",
            "storyboard_id": "VARCHAR(36)",
            "shot_id": "VARCHAR(36)",
            "character_id": "VARCHAR(36)",
            "api_provider": "VARCHAR(20)",
        },
        "shots": {
            "camera_movement": "VARCHAR(50)",
            "movement_speed": "FLOAT DEFAULT 1.0",
            "movement_start_pos": "VARCHAR(50)",
            "movement_end_pos": "VARCHAR(50)",
            "emotion": "VARCHAR(50)",
            "emotion_intensity": "FLOAT DEFAULT 0.5",
            "lighting": "VARCHAR(50)",
            "color_grading": "VARCHAR(50)",
            "music_cue": "VARCHAR(500)",
            "sfx_cue": "VARCHAR(500)",
            "ambient_sound": "VARCHAR(500)",
            "keyframes": "JSON",
            "version": "INTEGER DEFAULT 1",
            "parent_shot_id": "VARCHAR(36)",
            "version_note": "VARCHAR(200)",
            "timeline_track": "INTEGER DEFAULT 0",
            "timeline_position": "FLOAT DEFAULT 0.0",
            "character_refs": "JSON",
            "extra_data": "JSON",
        },
        "llm_models": {
            "base_url": "VARCHAR(500)",
        },
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return {
                table_name: {col["name"] for col in inspector.get_columns(table_name)}
                for table_name in column_specs
                if inspector.has_table(table_name)
            }

        table_columns = await conn.run_sync(_inspect)
        for table_name, existing in table_columns.items():
            for col, sql_type in column_specs[table_name].items():
                if col not in existing:
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"))
        print("✅ Workflow context fields migration completed (async).")


async def migrate_add_character_scope_fields_async():
    """Add novel/chapter ownership columns to characters (async)."""
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            if not inspector.has_table("characters"):
                return set()
            return {col["name"] for col in inspector.get_columns("characters")}

        existing = await conn.run_sync(_inspect)
        for col in ("novel_id", "chapter_id"):
            if col not in existing:
                await conn.execute(text(f"ALTER TABLE characters ADD COLUMN {col} VARCHAR(36)"))
        print("✅ Character scope fields migration completed (async).")


async def migrate_add_media_subtitle_fields_async():
    """Add compatibility columns for media/subtitle production objects (async)."""
    from sqlalchemy import text, inspect

    table_specs = {
        "media_generation_jobs": {
            "capabilities": "JSON",
            "input_assets": "JSON",
            "source_job_ids": "JSON",
            "quality_report": "JSON",
            "extra_data": "JSON",
            "is_active": "BOOLEAN DEFAULT 1",
        },
        "subtitle_tracks": {
            "export_urls": "JSON",
            "metadata": "JSON",
            "is_active": "BOOLEAN DEFAULT 1",
        },
        "subtitle_segments": {
            "style": "JSON",
            "metadata": "JSON",
            "is_active": "BOOLEAN DEFAULT 1",
        },
        "video_jobs": {
            "audio_url": "TEXT",
            "subtitle_track_id": "VARCHAR(36)",
            "media_type": "VARCHAR(50)",
            "task_type": "VARCHAR(50)",
        },
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return {
                table_name: {col["name"] for col in inspector.get_columns(table_name)}
                for table_name in table_specs
                if inspector.has_table(table_name)
            }

        table_columns = await conn.run_sync(_inspect)
        for table_name, existing in table_columns.items():
            for col, sql_type in table_specs[table_name].items():
                if col not in existing:
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"))
        print("✅ Media/subtitle compatibility migration completed (async).")


async def migrate_add_user_account_fields_async():
    """Add account recovery/profile columns to users (async)."""
    from sqlalchemy import text, inspect

    specs = {
        "avatar": "VARCHAR(500)",
        "reset_token_hash": "VARCHAR(128)",
        "reset_token_expires_at": "DATETIME",
        "account_status": "VARCHAR(32) DEFAULT 'active'",
        "email_verified_at": "DATETIME",
        "email_verification_token_hash": "VARCHAR(64)",
        "email_verification_token_expires_at": "DATETIME",
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            if not inspector.has_table("users"):
                return set()
            return {col["name"] for col in inspector.get_columns("users")}

        existing = await conn.run_sync(_inspect)
        for col, sql_type in specs.items():
            if col not in existing:
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {sql_type}"))
        await conn.execute(text("UPDATE users SET account_status = 'active' WHERE account_status IS NULL"))
        await conn.execute(
            text(
                "UPDATE users SET email_verified_at = COALESCE(email_verified_at, created_at, CURRENT_TIMESTAMP) "
                "WHERE is_active IS TRUE"
            )
        )
        print("✅ User account fields migration completed (async).")


async def migrate_add_entity_asset_scope_fields_async():
    """Add novel/chapter/script/entity scope columns for entities and assets (async)."""
    from sqlalchemy import text, inspect

    table_specs = {
        "story_entities": {
            "script_id": "VARCHAR(36)",
        },
        "assets": {
            "novel_id": "VARCHAR(36)",
            "chapter_id": "VARCHAR(36)",
            "script_id": "VARCHAR(36)",
            "entity_id": "VARCHAR(36)",
            "entity_type": "VARCHAR(20)",
            "source_url": "TEXT",
            "generation_params": "JSON",
            "version": "INTEGER DEFAULT 1",
            "is_locked": "BOOLEAN DEFAULT 0",
            "locked_at": "DATETIME",
            "locked_by": "VARCHAR(36)",
            "is_final": "BOOLEAN DEFAULT 0",
            "replaced_by_id": "VARCHAR(36)",
            "source_job_id": "VARCHAR(36)",
            "source_prompt": "TEXT",
        },
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return {
                table_name: {col["name"] for col in inspector.get_columns(table_name)}
                for table_name in table_specs
                if inspector.has_table(table_name)
            }

        table_columns = await conn.run_sync(_inspect)
        for table_name, existing in table_columns.items():
            for col, sql_type in table_specs[table_name].items():
                if col not in existing:
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col} {sql_type}"))
        print("✅ Entity/asset scope fields migration completed (async).")


def migrate_add_story_entity_extended_fields():
    """Add extended fields for story entity model: canonical_name, appearance, visual_prompt, relations, state_changes, etc."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        if not inspector.has_table("story_entities"):
            return
        existing = {col["name"] for col in inspector.get_columns("story_entities")}
        new_fields = {
            "canonical_name": "VARCHAR(200)",
            "appearance": "TEXT",
            "visual_prompt": "TEXT",
            "first_seen_chapter_id": "VARCHAR(36)",
            "relations": "JSON DEFAULT '[]'",
            "state_changes": "JSON DEFAULT '[]'",
            "version": "INTEGER DEFAULT 1",
            "is_approved": "BOOLEAN DEFAULT 0",
            "consistency_score": "FLOAT DEFAULT 1.0",
            "tags": "JSON DEFAULT '[]'",
            "extra_data": "JSON DEFAULT '{}'",
        }
        for col, sql_type in new_fields.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE story_entities ADD COLUMN {col} {sql_type}"))
        conn.commit()
        print("✅ Story entity extended fields migration completed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def migrate_add_story_entity_extended_fields_async():
    """Add extended fields for story entity model (async)."""
    from sqlalchemy import text, inspect

    new_fields = {
        "canonical_name": "VARCHAR(200)",
        "appearance": "TEXT",
        "visual_prompt": "TEXT",
        "first_seen_chapter_id": "VARCHAR(36)",
        "relations": "JSON DEFAULT '[]'",
        "state_changes": "JSON DEFAULT '[]'",
        "version": "INTEGER DEFAULT 1",
        "is_approved": "BOOLEAN DEFAULT 0",
        "consistency_score": "FLOAT DEFAULT 1.0",
        "tags": "JSON DEFAULT '[]'",
        "extra_data": "JSON DEFAULT '{}'",
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            if not inspector.has_table("story_entities"):
                return set()
            return {col["name"] for col in inspector.get_columns("story_entities")}

        existing = await conn.run_sync(_inspect)
        for col, sql_type in new_fields.items():
            if col not in existing:
                await conn.execute(text(f"ALTER TABLE story_entities ADD COLUMN {col} {sql_type}"))
        print("✅ Story entity extended fields migration completed (async).")


def migrate_add_project_id_fields():
    """Add project_id to resource tables for permission isolation."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        table_specs = {
            "novels": "VARCHAR(36)",
            "characters": "VARCHAR(36)",
            "scripts": "VARCHAR(36)",
            "storyboards": "VARCHAR(36)",
            "shots": "VARCHAR(36)",
            "workflows": "VARCHAR(36)",
        }
        for table_name, sql_type in table_specs.items():
            if not inspector.has_table(table_name):
                continue
            existing = {col["name"] for col in inspector.get_columns(table_name)}
            if "project_id" not in existing:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN project_id {sql_type}"))
        conn.commit()
        print("✅ Project ID fields migration completed.")
    finally:
        conn.close()


async def migrate_add_project_id_fields_async():
    """Add project_id to resource tables for permission isolation (async)."""
    from sqlalchemy import text, inspect

    table_specs = {
        "novels": "VARCHAR(36)",
        "characters": "VARCHAR(36)",
        "scripts": "VARCHAR(36)",
        "storyboards": "VARCHAR(36)",
        "shots": "VARCHAR(36)",
        "workflows": "VARCHAR(36)",
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return {
                table_name: {col["name"] for col in inspector.get_columns(table_name)}
                for table_name in table_specs
                if inspector.has_table(table_name)
            }

        table_columns = await conn.run_sync(_inspect)
        for table_name, existing in table_columns.items():
            if "project_id" not in existing:
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN project_id {table_specs[table_name]}"))
        print("✅ Project ID fields migration completed (async).")


def migrate_add_publication_fields():
    """Add current Publication ORM columns to older SQLite databases."""
    from sqlalchemy import text, inspect

    column_specs = {
        "description": "TEXT",
        "video_url": "VARCHAR(500)",
        "cover_url": "VARCHAR(500)",
        "duration_seconds": "FLOAT",
        "format": "VARCHAR(20) DEFAULT 'mp4'",
        "resolution": "VARCHAR(20) DEFAULT '1080p'",
        "orientation": "VARCHAR(20) DEFAULT 'landscape'",
        "status": "VARCHAR(20) DEFAULT 'succeeded'",
        "visibility": "VARCHAR(20) DEFAULT 'private'",
        "tags": "JSON",
        "view_count": "INTEGER DEFAULT 0",
        "like_count": "INTEGER DEFAULT 0",
        "export_url": "TEXT",
        "artifact_path": "TEXT",
        "provider": "VARCHAR(50) DEFAULT 'local'",
        "metadata": "JSON",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)
        if not inspector.has_table("publications"):
            return
        existing = {col["name"] for col in inspector.get_columns("publications")}
        for col, sql_type in column_specs.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE publications ADD COLUMN {col} {sql_type}"))
        conn.commit()
        print("✅ Publication fields migration completed.")
    finally:
        conn.close()


async def migrate_add_publication_fields_async():
    """Add current Publication ORM columns to older SQLite databases (async)."""
    from sqlalchemy import text, inspect

    column_specs = {
        "description": "TEXT",
        "video_url": "VARCHAR(500)",
        "cover_url": "VARCHAR(500)",
        "duration_seconds": "FLOAT",
        "format": "VARCHAR(20) DEFAULT 'mp4'",
        "resolution": "VARCHAR(20) DEFAULT '1080p'",
        "orientation": "VARCHAR(20) DEFAULT 'landscape'",
        "status": "VARCHAR(20) DEFAULT 'succeeded'",
        "visibility": "VARCHAR(20) DEFAULT 'private'",
        "tags": "JSON",
        "view_count": "INTEGER DEFAULT 0",
        "like_count": "INTEGER DEFAULT 0",
        "export_url": "TEXT",
        "artifact_path": "TEXT",
        "provider": "VARCHAR(50) DEFAULT 'local'",
        "metadata": "JSON",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
    }

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            if not inspector.has_table("publications"):
                return set()
            return {col["name"] for col in inspector.get_columns("publications")}

        existing = await conn.run_sync(_inspect)
        for col, sql_type in column_specs.items():
            if col not in existing:
                await conn.execute(text(f"ALTER TABLE publications ADD COLUMN {col} {sql_type}"))
        print("✅ Publication fields migration completed (async).")


def init_db():
    """同步方式创建所有表"""
    from app.models.character import Character
    from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog
    from app.models.external_api import ExternalAPIConfig
    from app.models.ai_model import ModelConfig
    from app.models.user import User
    from app.models.novel import Novel
    from app.models.chapter import Chapter
    from app.models.script import Script
    from app.models.storyboard import Storyboard
    from app.models.shot import Shot
    from app.models.tts_job import TTSJob
    from app.models.synthesis_job import SynthesisJob
    from app.models.video_job import VideoJob
    # 新增模型
    from app.models.project import Project, ProjectMember
    from app.models.asset import Asset, AssetCategory
    from app.models.timeline import Timeline, Track, Clip
    from app.models.activity import Activity
    from app.models.image_job import ImageJob
    from app.models.workflow import Workflow
    from app.models.story_bible import StoryBible
    from app.models.publication import Publication
    from app.models.novel_import import NovelImportJob
    from app.models.story_entity import StoryEntity
    from app.models.media_generation_job import MediaGenerationJob
    from app.models.subtitle import SubtitleTrack, SubtitleSegment
    from app.models.batch_job import BatchJob, BatchJobItem
    from app.models.template import Template
    from app.models.version import Version, VersionRule
    from app.models.studio_review import StudioRepairAction, StudioReviewRun
    from app.models.prompt_skill import PromptSkill
    from app.db_migrations.runner import register_production_models, run_schema_migrations

    register_production_models()

    Base.metadata.create_all(bind=sync_engine)
    print("✅ 数据库表创建成功！")

    # Run migrations
    migrate_add_shot_image_fields()
    migrate_add_job_lineage_fields()
    migrate_add_workflow_context_fields()
    migrate_add_character_scope_fields()
    migrate_add_media_subtitle_fields()
    migrate_add_user_account_fields()
    add_script_chapter_lineage(sync_engine)
    migrate_add_entity_asset_scope_fields()
    migrate_add_story_entity_extended_fields()
    migrate_add_project_id_fields()
    migrate_add_publication_fields()
    migrate_add_version_tables()
    run_schema_migrations(sync_engine)


def migrate_add_version_tables():
    """Add version and version_rules tables."""
    from sqlalchemy import text, inspect

    conn = sync_engine.connect()
    try:
        inspector = inspect(sync_engine)

        # Create versions table
        if not inspector.has_table("versions"):
            conn.execute(text("""
                CREATE TABLE versions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    resource_type VARCHAR(20) NOT NULL,
                    resource_id VARCHAR(36) NOT NULL,
                    version_number INTEGER NOT NULL,
                    version_label VARCHAR(100),
                    snapshot JSON,
                    change_summary TEXT,
                    created_at DATETIME,
                    created_by VARCHAR(36),
                    INDEX idx_versions_user_id (user_id),
                    INDEX idx_versions_resource (resource_type, resource_id)
                )
            """))
            conn.commit()
            print("✅ Versions table created.")

        # Create version_rules table
        if not inspector.has_table("version_rules"):
            conn.execute(text("""
                CREATE TABLE version_rules (
                    resource_type VARCHAR(20) PRIMARY KEY,
                    max_versions INTEGER DEFAULT 10,
                    auto_snapshot BOOLEAN DEFAULT 1,
                    auto_cleanup BOOLEAN DEFAULT 1
                )
            """))
            conn.commit()
            print("✅ Version rules table created.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def init_db_async():
    """异步方式创建所有表"""
    from app.models.character import Character
    from app.models.llm_config import LLMProvider, LLMModel, LLMConfig, LLMUsageLog
    from app.models.external_api import ExternalAPIConfig
    from app.models.ai_model import ModelConfig
    from app.models.user import User
    from app.models.novel import Novel
    from app.models.chapter import Chapter
    from app.models.script import Script
    from app.models.storyboard import Storyboard
    from app.models.shot import Shot
    from app.models.tts_job import TTSJob
    from app.models.synthesis_job import SynthesisJob
    from app.models.video_job import VideoJob
    # 新增模型
    from app.models.project import Project, ProjectMember
    from app.models.asset import Asset, AssetCategory
    from app.models.timeline import Timeline, Track, Clip
    from app.models.activity import Activity
    from app.models.image_job import ImageJob
    from app.models.workflow import Workflow
    from app.models.story_bible import StoryBible
    from app.models.publication import Publication
    from app.models.novel_import import NovelImportJob
    from app.models.story_entity import StoryEntity
    from app.models.media_generation_job import MediaGenerationJob
    from app.models.subtitle import SubtitleTrack, SubtitleSegment
    from app.models.batch_job import BatchJob, BatchJobItem
    from app.models.template import Template
    from app.models.version import Version, VersionRule
    from app.models.studio_review import StudioRepairAction, StudioReviewRun
    from app.models.prompt_skill import PromptSkill
    from app.db_migrations.runner import (
        register_production_models,
        run_schema_migrations_async,
    )

    register_production_models()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建成功（异步）！")

    # Run migrations
    await migrate_add_shot_image_fields_async()
    await migrate_add_job_lineage_fields_async()
    await migrate_add_workflow_context_fields_async()
    await migrate_add_character_scope_fields_async()
    await migrate_add_media_subtitle_fields_async()
    await migrate_add_user_account_fields_async()
    await add_script_chapter_lineage_async(engine)
    await migrate_add_entity_asset_scope_fields_async()
    await migrate_add_story_entity_extended_fields_async()
    await migrate_add_project_id_fields_async()
    await migrate_add_publication_fields_async()
    await migrate_add_version_tables_async()
    await run_schema_migrations_async(engine)


async def migrate_add_version_tables_async():
    """Add version and version_rules tables (async)."""
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        def _inspect(sync_conn):
            inspector = inspect(sync_conn)
            return {
                "versions": inspector.has_table("versions"),
                "version_rules": inspector.has_table("version_rules"),
            }

        tables = await conn.run_sync(_inspect)

        if not tables["versions"]:
            await conn.execute(text("""
                CREATE TABLE versions (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    resource_type VARCHAR(20) NOT NULL,
                    resource_id VARCHAR(36) NOT NULL,
                    version_number INTEGER NOT NULL,
                    version_label VARCHAR(100),
                    snapshot JSON,
                    change_summary TEXT,
                    created_at DATETIME,
                    created_by VARCHAR(36)
                )
            """))
            await conn.execute(text("CREATE INDEX idx_versions_user_id ON versions(user_id)"))
            await conn.execute(text("CREATE INDEX idx_versions_resource ON versions(resource_type, resource_id)"))
            print("✅ Versions table created (async).")

        if not tables["version_rules"]:
            await conn.execute(text("""
                CREATE TABLE version_rules (
                    resource_type VARCHAR(20) PRIMARY KEY,
                    max_versions INTEGER DEFAULT 10,
                    auto_snapshot BOOLEAN DEFAULT 1,
                    auto_cleanup BOOLEAN DEFAULT 1
                )
            """))
            print("✅ Version rules table created (async).")


if __name__ == "__main__":
    init_db()
