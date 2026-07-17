"""Single application entrypoint for workflow-media batch generation."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.workflow_media.application.direct_av import DirectAvCommand, generate_direct_av_batch
from app.features.workflow_media.application.generate_separate_media import generate_separate_media_batch
from app.features.workflow_media.application.load_context import load_workflow_media_context
from app.features.workflow_media.schemas import WorkflowMediaBatchRequest, WorkflowMediaBatchResponse


@dataclass(frozen=True)
class WorkflowMediaCommand:
    db: AsyncSession
    user_id: str
    workflow_id: str
    request: WorkflowMediaBatchRequest


async def generate_workflow_media_batch(
    command: WorkflowMediaCommand,
) -> WorkflowMediaBatchResponse:
    context = await load_workflow_media_context(
        command.db, command.user_id, command.workflow_id, command.request,
    )
    if command.request.strategy == "separate_video_tts":
        return await generate_separate_media_batch(context, command.request)
    return await generate_direct_av_batch(DirectAvCommand(context, command.request))
