from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_COMPOSE = ROOT / "infra" / "compose" / "production.yml"
STAGING_COMPOSE = ROOT / "infra" / "compose" / "staging.yml"


def test_production_compose_is_secret_driven_and_private() -> None:
    content = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "${POSTGRES_PASSWORD:?" in content
    assert "${FERNET_KEY:?" in content
    assert "postgres:password" not in content
    assert "minioadmin" not in content
    assert '"5432:5432"' not in content
    assert '"6379:6379"' not in content
    assert "./backend:/app" not in content
    assert "./frontend:/app" not in content
    assert "npm run dev" not in content


def test_api_waits_for_successful_one_shot_migration() -> None:
    content = PRODUCTION_COMPOSE.read_text(encoding="utf-8")

    assert "migrate:" in content
    assert '"python", "scripts/upgrade_database.py"' in content
    assert "condition: service_completed_successfully" in content
    assert "condition: service_healthy" in content


def test_staging_reuses_the_production_contract() -> None:
    content = STAGING_COMPOSE.read_text(encoding="utf-8")

    assert "production.yml" in content
    assert "APP_ENV: staging" in content
