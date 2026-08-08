from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_existing_users_are_verified_and_session_schema_is_added(tmp_path) -> None:
    database_path = tmp_path / "legacy-auth.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id VARCHAR(36) PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, "
                "email VARCHAR(100) UNIQUE NOT NULL, hashed_password VARCHAR(128) NOT NULL, "
                "is_active BOOLEAN, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, is_active) "
                "VALUES ('legacy-user', 'legacy', 'legacy@example.test', 'hash', 1)"
            )
        )

    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)
    result = subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "20260809_0005" in result.stdout
    assert inspect(engine).has_table("user_sessions")
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"account_status", "email_verified_at", "email_verification_token_hash"} <= user_columns
    with engine.connect() as connection:
        status, verified_at = connection.execute(
            text("SELECT account_status, email_verified_at FROM users WHERE id='legacy-user'")
        ).one()
    assert status == "active"
    assert verified_at is not None


def test_existing_projects_receive_a_personal_workspace(tmp_path) -> None:
    database_path = tmp_path / "legacy-project.db"
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users ("
                "id VARCHAR(36) PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, "
                "email VARCHAR(100) UNIQUE NOT NULL, hashed_password VARCHAR(128) NOT NULL, "
                "is_active BOOLEAN, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE projects ("
                "id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL, "
                "name VARCHAR(200) NOT NULL, created_at DATETIME, updated_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE project_members ("
                "id VARCHAR(36) PRIMARY KEY, project_id VARCHAR(36) NOT NULL, "
                "user_id VARCHAR(36) NOT NULL, role VARCHAR(20), is_active BOOLEAN, "
                "invited_at DATETIME, joined_at DATETIME, created_at DATETIME)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, is_active) "
                "VALUES ('owner-1', 'owner', 'owner@example.test', 'hash', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, is_active) "
                "VALUES ('reviewer-1', 'reviewer', 'reviewer@example.test', 'hash', 1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects (id, user_id, name) "
                "VALUES ('project-1', 'owner-1', '旧项目')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO project_members "
                "(id, project_id, user_id, role, is_active) "
                "VALUES ('member-1', 'project-1', 'reviewer-1', 'reviewer', 1)"
            )
        )

    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+aiosqlite:///{database_path}"
    environment.pop("E2E_REQUIRE_ISOLATED_DB", None)
    result = subprocess.run(
        [sys.executable, "scripts/upgrade_database.py"],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "20260809_0005" in result.stdout
    inspector = inspect(engine)
    assert {"organizations", "organization_members", "workspaces", "workspace_members", "audit_events"} <= set(
        inspector.get_table_names()
    )
    assert "workspace_id" in {column["name"] for column in inspector.get_columns("projects")}
    with engine.connect() as connection:
        workspace_id, organization_id = connection.execute(
            text(
                "SELECT p.workspace_id, w.organization_id FROM projects p "
                "JOIN workspaces w ON w.id=p.workspace_id WHERE p.id='project-1'"
            )
        ).one()
        owner_role = connection.execute(
            text(
                "SELECT role FROM project_members "
                "WHERE project_id='project-1' AND user_id='owner-1' AND is_active=1"
            )
        ).scalar_one()
        reviewer_workspace_role = connection.execute(
            text(
                "SELECT role FROM workspace_members "
                "WHERE workspace_id=:workspace_id AND user_id='reviewer-1' AND is_active=1"
            ),
            {"workspace_id": workspace_id},
        ).scalar_one()
        reviewer_organization_role = connection.execute(
            text(
                "SELECT role FROM organization_members "
                "WHERE organization_id=:organization_id AND user_id='reviewer-1' AND is_active=1"
            ),
            {"organization_id": organization_id},
        ).scalar_one()
    assert workspace_id
    assert owner_role == "owner"
    assert reviewer_workspace_role == "member"
    assert reviewer_organization_role == "member"
