"""Stable role-to-capability contracts for project authorization."""

from typing import Iterable

from fastapi import HTTPException, status


PROJECT_ROLES = {"owner", "editor", "reviewer", "viewer"}
PROJECT_ROLE_CAPABILITIES = {
    "owner": frozenset({"view", "edit", "review", "manage_members"}),
    "editor": frozenset({"view", "edit"}),
    "reviewer": frozenset({"view", "review"}),
    "viewer": frozenset({"view"}),
}
REQUIRED_ROLE_CAPABILITY = {
    "owner": "manage_members",
    "editor": "edit",
    "reviewer": "review",
    "viewer": "view",
}


def normalize_project_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in PROJECT_ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="角色必须是 owner、editor、reviewer 或 viewer",
        )
    return normalized


def project_role_allows(role: str, capability: str) -> bool:
    normalized = normalize_project_role(role)
    return capability in PROJECT_ROLE_CAPABILITIES[normalized]


def has_role_at_least(actual_role: str, required_role: str) -> bool:
    required = normalize_project_role(required_role)
    return project_role_allows(actual_role, REQUIRED_ROLE_CAPABILITY[required])


def allowed_roles_for_query(required_role: str = "viewer") -> Iterable[str]:
    required = normalize_project_role(required_role)
    return [role for role in PROJECT_ROLES if has_role_at_least(role, required)]
