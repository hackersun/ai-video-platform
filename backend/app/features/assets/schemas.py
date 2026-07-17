from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AssetEntityOption(BaseModel):
    id: str
    name: str
    entity_type: str
    novel_id: Optional[str] = None
    chapter_id: Optional[str] = None
    script_id: Optional[str] = None
    description: Optional[str] = None
    appearance: Optional[str] = None
    visual_prompt: Optional[str] = None
    lifecycle_status: str
    active_asset_count: int = 0


class DeactivateAssetEntityRequest(BaseModel):
    reason: str = Field(default="用户从资产工作台停用", max_length=500)


class DeactivateAssetEntityResponse(BaseModel):
    entity_id: str
    entity_name: str
    lifecycle_status: str
    archived_asset_count: int
    already_inactive: bool
