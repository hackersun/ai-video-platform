"""Machine-readable API authorization declarations."""


PERMISSION_MATRIX = (
    {"method": "GET", "path": "/projects", "access": "authenticated", "permission": "project.list"},
    {"method": "POST", "path": "/projects", "access": "authenticated", "permission": "project.create"},
    {"method": "GET", "path": "/projects/{project_id}", "access": "project_role", "permission": "project.view"},
    {"method": "PUT", "path": "/projects/{project_id}", "access": "project_role", "permission": "project.edit"},
    {"method": "DELETE", "path": "/projects/{project_id}", "access": "project_role", "permission": "project.manage_members"},
    {"method": "GET", "path": "/projects/{project_id}/members", "access": "project_role", "permission": "project.view"},
    {"method": "POST", "path": "/projects/{project_id}/members", "access": "project_role", "permission": "project.manage_members"},
    {"method": "PUT", "path": "/projects/{project_id}/members/{member_user_id}", "access": "project_role", "permission": "project.manage_members"},
    {"method": "DELETE", "path": "/projects/{project_id}/members/{member_user_id}", "access": "project_role", "permission": "project.manage_members"},
    {"method": "GET", "path": "/access-control/organizations", "access": "authenticated", "permission": "organization.list"},
    {"method": "GET", "path": "/access-control/workspaces", "access": "authenticated", "permission": "workspace.list"},
    {"method": "GET", "path": "/access-control/audit-events", "access": "project_role", "permission": "project.manage_members"},
    {"method": "GET", "path": "/billing/account", "access": "authenticated", "permission": "billing.view_own"},
    {"method": "GET", "path": "/billing/ledger", "access": "authenticated", "permission": "billing.view_own"},
    {"method": "GET", "path": "/billing/usage", "access": "authenticated", "permission": "billing.view_own"},
    {"method": "GET", "path": "/billing/reconciliations", "access": "authenticated", "permission": "billing.view_own"},
)
