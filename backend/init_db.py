"""
初始化数据库表
"""

from app.core.database import Base, engine, sync_engine


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


async def migrate_add_shot_image_fields_async():
    """Add image_url, image_status, image_asset_id to shots table (async)."""
    from sqlalchemy import text, inspect

    async with engine.begin() as conn:
        inspector = inspect(engine)
        existing = {col["name"] for col in inspector.get_columns("shots")}
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

    Base.metadata.create_all(bind=sync_engine)
    print("✅ 数据库表创建成功！")

    # Run migrations
    migrate_add_shot_image_fields()


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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ 数据库表创建成功（异步）！")

    # Run migrations
    await migrate_add_shot_image_fields_async()


if __name__ == "__main__":
    init_db()
