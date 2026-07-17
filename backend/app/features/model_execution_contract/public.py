"""Public facade for model execution contracts."""

from app.features.model_execution_contract.domain import ModelExecutionContract
from app.features.model_execution_contract.registry import resolve_model_execution_contract

__all__ = ["ModelExecutionContract", "resolve_model_execution_contract"]
