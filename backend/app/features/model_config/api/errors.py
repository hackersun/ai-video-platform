"""HTTP mapping for stable, actionable Model Center failures."""

from fastapi import HTTPException

from app.features.model_config.api import service


def unsupported(operation: str):
    try:
        service.unavailable(operation)
    except service.ManagementOperationError as error:
        raise_http(error)


def raise_http(error: service.ManagementOperationError):
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": str(error), "action_code": error.action_code},
    ) from error
