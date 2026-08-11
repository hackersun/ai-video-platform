"""Public task execution API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class TaskExecutionSummary(BaseModel):
    id: str
    project_id: str | None = None
    task_type: str
    status: str
    status_label: str
    attempt_count: int
    max_attempts: int
    provider_task_id: str | None = None
    last_error_code: str | None = None
    last_error_message: str | None = None
    can_cancel: bool
    can_retry: bool
    requires_confirmation: bool
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class TaskExecutionEventSummary(BaseModel):
    event_type: str
    status: str
    message: str
    created_at: datetime


class TaskExecutionDetail(TaskExecutionSummary):
    events: list[TaskExecutionEventSummary] = Field(default_factory=list)


class TaskExecutionList(BaseModel):
    items: list[TaskExecutionSummary]


class RetryTaskRequest(BaseModel):
    confirm_uncertain: bool = False
