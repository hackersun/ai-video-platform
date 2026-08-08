from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_COMPOSE = ROOT / "infra" / "compose" / "production.yml"
STAGING_COMPOSE = ROOT / "infra" / "compose" / "staging.yml"


def test_production_compose_is_secret_driven_and_private() -> None:
    content = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "${POSTGRES_PASSWORD:?" in content
    assert "${FERNET_KEY:?" in content
    assert "${JWT_SECRET_KEY:?" in content
    assert "${OBJECT_STORAGE_PROVIDER:?" in content
    assert "postgres:password" not in content
    assert "minioadmin" not in content
    assert '"5432:5432"' not in content
    assert '"6379:6379"' not in content
    assert "./backend:/app" not in content
    assert "./frontend:/app" not in content
    assert "npm run dev" not in content
    assert "generated_media:/app/static/generated" not in content
    assert "generated_media:" not in content


def test_static_media_mount_is_disabled_outside_local_test() -> None:
    from main import should_mount_local_static

    assert should_mount_local_static("local") is True
    assert should_mount_local_static("test") is True
    assert should_mount_local_static("staging") is False
    assert should_mount_local_static("production") is False


def test_api_waits_for_successful_one_shot_migration() -> None:
    content = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "migrate:" in content
    assert '"python", "scripts/upgrade_database.py"' in content
    assert "condition: service_completed_successfully" in content
    assert "condition: service_healthy" in content
    assert "auth-notifications:" in content
    assert '"python", "scripts/run_auth_notification_worker.py"' in content


def test_staging_reuses_the_production_contract() -> None:
    content = STAGING_COMPOSE.read_text(encoding="utf-8")

    assert "production.yml" in content
    assert "APP_ENV: staging" in content


def test_production_compose_uses_durable_task_worker() -> None:
    content = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "task-worker:" in content
    assert '"python", "scripts/run_task_worker.py"' in content
