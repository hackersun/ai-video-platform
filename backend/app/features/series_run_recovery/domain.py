"""Pure recovery policy for provider operations."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RecoveryAction:
    code: str
    label: str


@dataclass(frozen=True)
class RecoveryDescriptor:
    operation_id: str
    capability: str
    stage: str
    operation_status: str
    title: str
    message: str
    cost_state: str
    safe_retry: bool
    retry_requires_confirmation: bool
    retry_scope: str | None
    actions: tuple[RecoveryAction, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


_UNCERTAIN = {"accepted", "reserved", "unknown_manual_reconcile"}
_STAGES = {"image": "image_submission", "tts": "tts_submission", "video": "video_submission"}


def _confirmed_actions(capability: str) -> tuple[RecoveryAction, ...]:
    edit = RecoveryAction("edit_voice", "修改声线") if capability == "tts" else RecoveryAction(
        "edit_binding", "修改模型配置",
    )
    return (
        edit,
        RecoveryAction("retest_config", "重新测试声音模型" if capability == "tts" else "重新测试模型配置"),
        RecoveryAction("retry_failed_stage", "修改后重试失败阶段"),
    )


def recovery_for_operation(operation: Any) -> RecoveryDescriptor:
    capability = str(operation.capability)
    stage = _STAGES.get(capability, f"{capability}_submission")
    status = str(operation.status)
    if status == "confirmed_rejected_before_acceptance":
        title = "声音生成未受理" if capability == "tts" else "供应商未受理"
        return RecoveryDescriptor(
            str(operation.id), capability, stage, status, title,
            "本次请求已明确未被供应商受理，费用预留已释放。修改并验证配置后可仅重试失败阶段。",
            "released", True, True, "failed_stage", _confirmed_actions(capability),
        )
    if status in _UNCERTAIN:
        return RecoveryDescriptor(
            str(operation.id), capability, stage, status, "等待确认供应商状态",
            "请求结果尚不确定。请先刷新或人工对账，不要再次提交，以免重复计费。",
            "held", False, False, None,
            (RecoveryAction("refresh_status", "刷新供应商状态"),
             RecoveryAction("manual_reconcile", "人工对账")),
        )
    return RecoveryDescriptor(
        str(operation.id), capability, stage, status, "无需恢复", "该阶段没有可执行的恢复操作。",
        "settled" if status in {"succeeded", "completed"} else "unknown",
        False, False, None, (),
    )
