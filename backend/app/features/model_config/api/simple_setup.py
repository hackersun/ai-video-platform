"""Simple model setup routes: the default product surface for model settings."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_id
from app.services import simple_model_setup as svc

router = APIRouter()
Capability = Literal["text", "image", "video", "tts"]


class SimpleCard(BaseModel):
    model_id: Optional[str] = None
    api_key: Optional[str] = Field(None, max_length=4096, description="仅写入；留空沿用已保存密钥")
    extra_params: Optional[dict] = None


class SimpleSetupSaveRequest(BaseModel):
    provider_id: Optional[str] = None
    api_key: Optional[str] = Field(None, max_length=4096, description="主供应商 API Key，仅写入")
    capabilities: dict[Capability, SimpleCard]


class SimpleSetupTestRequest(BaseModel):
    capabilities: Optional[list[Capability]] = None


class NovelOverrideRequest(BaseModel):
    overrides: dict[Capability, Optional[str]]


def _fail(error: svc.SimpleSetupError):
    status = 404 if error.code.endswith("not_found") else 422
    raise HTTPException(status_code=status, detail={"code": error.code, "message": error.message})


@router.get("/simple-setup")
async def get_simple_setup(
    novel_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await svc.get_simple_setup(db, user_id, novel_id=novel_id)
    except svc.SimpleSetupError as error:
        _fail(error)


@router.put("/simple-setup")
async def save_simple_setup(
    request: SimpleSetupSaveRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await svc.save_simple_setup(db, user_id, request.model_dump(exclude_unset=True))
    except svc.SimpleSetupError as error:
        _fail(error)


@router.post("/simple-setup/test")
async def test_simple_setup(
    request: SimpleSetupTestRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    return await svc.test_simple_setup(db, user_id, request.capabilities)


@router.put("/simple-setup/novels/{novel_id}")
async def set_novel_overrides(
    novel_id: str, request: NovelOverrideRequest,
    db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user_id),
):
    try:
        return await svc.set_novel_overrides(db, user_id, novel_id, dict(request.overrides))
    except svc.SimpleSetupError as error:
        _fail(error)
