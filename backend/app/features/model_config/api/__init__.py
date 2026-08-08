"""Versioned Model Center API composition."""

from fastapi import APIRouter, Depends

from app.core.security import get_current_user_id
from app.features.model_config.api import (
    bindings, catalog, certifications, connections, profiles, prompt_usage, prompts, recipes,
)


router = APIRouter(
    prefix="/model-center", dependencies=[Depends(get_current_user_id)],
)
router.include_router(connections.router, tags=["模型中心-连接"])
router.include_router(catalog.router, tags=["模型中心-目录"])
router.include_router(profiles.router, tags=["模型中心-模型档案"])
router.include_router(bindings.router, tags=["模型中心-绑定"])
router.include_router(recipes.router, tags=["模型中心-方案"])
router.include_router(prompts.router, tags=["模型中心-提示词"])
router.include_router(prompt_usage.router, tags=["模型中心-提示词使用"])
router.include_router(certifications.router, tags=["模型中心-测试"])


__all__ = ["router"]
