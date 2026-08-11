from __future__ import annotations

def test_project_routes_have_machine_readable_permission_declarations() -> None:
    from app.features.access_control import permission_matrix

    declared = {
        (entry["method"], entry["path"]): entry["permission"]
        for entry in permission_matrix.PERMISSION_MATRIX
    }

    assert declared[("GET", "/projects/{project_id}")] == "project.view"
    assert declared[("PUT", "/projects/{project_id}")] == "project.edit"
    assert declared[("DELETE", "/projects/{project_id}")] == "project.manage_members"
    assert declared[("GET", "/projects/{project_id}/members")] == "project.view"
    assert declared[("POST", "/projects/{project_id}/members")] == "project.manage_members"
    assert declared[("PUT", "/projects/{project_id}/members/{member_user_id}")] == "project.manage_members"
    assert declared[("DELETE", "/projects/{project_id}/members/{member_user_id}")] == "project.manage_members"


def test_permission_matrix_uses_known_access_levels() -> None:
    from app.features.access_control import permission_matrix

    assert permission_matrix.PERMISSION_MATRIX
    assert {entry["access"] for entry in permission_matrix.PERMISSION_MATRIX} <= {
        "authenticated",
        "project_role",
        "organization_role",
        "platform_role",
    }


def test_access_control_read_only_routes_are_registered() -> None:
    from main import app

    routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    assert ("GET", "/api/v1/access-control/permission-matrix") in routes
    assert ("GET", "/api/v1/access-control/organizations") in routes
    assert ("GET", "/api/v1/access-control/workspaces") in routes
    assert ("GET", "/api/v1/access-control/audit-events") in routes
