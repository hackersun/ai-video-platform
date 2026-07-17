"""Certification and impact routes reserved by the versioned API."""

from fastapi import APIRouter

from app.features.model_config.api.errors import unsupported
from app.features.model_config.api.schemas import CertificationRequest


router = APIRouter()


@router.post("/certifications")
async def create_certification(request: CertificationRequest):
    del request
    return unsupported("certification.create")


@router.get("/certifications/{run_id}")
async def get_certification(run_id: str):
    del run_id
    return unsupported("certification.get")


@router.get("/impact")
async def get_impact():
    return unsupported("impact.get")
