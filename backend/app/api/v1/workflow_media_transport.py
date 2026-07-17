"""FastAPI transport adapter for workflow-media application results."""

from fastapi import HTTPException

from app.features.workflow_media.errors import WorkflowMediaError


async def workflow_media_result(awaitable):
    try:
        return await awaitable
    except WorkflowMediaError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
