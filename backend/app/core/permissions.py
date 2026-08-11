"""Compatibility facade for the commercial access-control feature."""

from app.features.access_control import (
    PROJECT_ROLES,
    allowed_roles_for_query,
    get_project_access,
    has_role_at_least,
    normalize_project_role,
    project_role_allows,
    require_project_role,
)

__all__ = [
    "PROJECT_ROLES",
    "allowed_roles_for_query",
    "get_project_access",
    "has_role_at_least",
    "normalize_project_role",
    "project_role_allows",
    "require_project_role",
]
