from pathlib import Path

import yaml

from app.models.prompt_skill import PromptSkill


ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "compose.production.yml"
DEPLOY_ROOT = ROOT / "ops" / "deploy"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_production_compose_has_one_public_entry_and_private_stateful_services() -> None:
    compose = _compose()
    services = compose["services"]
    assert set(services) == {"proxy", "frontend", "api", "postgres", "redis"}
    assert services["proxy"]["ports"] == ["${APP_HTTP_PORT:-8080}:80"]
    for name in ("frontend", "api", "postgres", "redis"):
        assert not services[name].get("ports"), name
    assert services["postgres"]["volumes"] == [
        "${AI_VIDEO_DATA_ROOT:-/srv/ai-video-platform/data}/postgres:/var/lib/postgresql/data"
    ]
    assert "${AI_VIDEO_DATA_ROOT:-/srv/ai-video-platform/data}/media:/app/static" in services["api"]["volumes"]
    assert services["redis"]["volumes"] == [
        "${AI_VIDEO_DATA_ROOT:-/srv/ai-video-platform/data}/redis:/data"
    ]
    assert all("healthcheck" in service for service in services.values())


def test_production_compose_rejects_development_mounts_commands_and_weak_passwords() -> None:
    text = COMPOSE_PATH.read_text(encoding="utf-8")
    assert "npm run dev" not in text
    assert "--reload" not in text
    assert "./frontend:/app" not in text
    assert "./backend:/app" not in text
    assert "POSTGRES_PASSWORD: password" not in text
    assert "minioadmin" not in text
    assert "dev-jwt-secret-change-in-production" not in text
    assert "DEV_MODE: \"false\"" in text
    assert "JWT_SECRET_KEY: ${JWT_SECRET_KEY:?" in text
    assert "FERNET_KEY: ${FERNET_KEY:?" in text
    api_command = " ".join(_compose()["services"]["api"]["command"])
    assert "python bootstrap_production.py" in api_command


def test_proxy_and_frontend_use_same_origin_api_contract() -> None:
    caddy = (DEPLOY_ROOT / "Caddyfile").read_text(encoding="utf-8")
    dockerfile = (ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert "handle /api/*" in caddy
    assert "reverse_proxy api:8000" in caddy
    assert "reverse_proxy frontend:3000" in caddy
    assert "ARG NEXT_PUBLIC_API_URL=/api/v1" in dockerfile
    assert "ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}" in dockerfile


def test_release_scripts_are_backup_first_and_rollback_capable() -> None:
    deploy = (DEPLOY_ROOT / "deploy.sh").read_text(encoding="utf-8")
    rollback = (DEPLOY_ROOT / "rollback.sh").read_text(encoding="utf-8")
    health = (DEPLOY_ROOT / "healthcheck.sh").read_text(encoding="utf-8")
    for content in (deploy, rollback, health):
        assert "set -euo pipefail" in content
    assert deploy.index("pg_dump") < deploy.index("up -d")
    assert "previous" in deploy and "current" in deploy
    assert "previous" in rollback and "current" in rollback
    assert "/health" in health and "/api/v1/versions" in health
    assert "/srv/ai-video-platform" in deploy
    assert "chown 70:70" in deploy
    assert "chown 999:999" in deploy
    assert "10001:10001" in deploy
    assert "seq 1" in health
    assert "sleep" in health


def test_ubuntu_installer_uses_distribution_docker_packages() -> None:
    installer = (DEPLOY_ROOT / "install-docker-ubuntu.sh").read_text(encoding="utf-8")
    assert "docker.io" in installer
    assert "docker-compose-v2" in installer
    assert "download.docker.com" not in installer


def test_production_bootstrap_seeds_only_shared_catalogs() -> None:
    bootstrap = (ROOT / "backend" / "bootstrap_production.py").read_text(encoding="utf-8")
    assert "init_llm_providers_and_models" in bootstrap
    assert "ensure_standard_prompt_skills" in bootstrap
    assert "apply_prompt_recovery" in bootstrap
    for private_model in ("Novel", "Chapter", "Script", "Storyboard", "Shot", "LLMConfig"):
        assert private_model not in bootstrap


def test_prompt_skill_primary_key_can_store_builtin_catalog_ids() -> None:
    assert PromptSkill.__table__.c.id.type.length >= 80


def test_environment_example_contains_placeholders_not_live_secrets() -> None:
    env_text = (DEPLOY_ROOT / "production.env.example").read_text(encoding="utf-8")
    required = {"POSTGRES_PASSWORD", "JWT_SECRET_KEY", "FERNET_KEY"}
    values = {}
    for raw in env_text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    assert required <= values.keys()
    assert all(values[key].startswith("CHANGE_ME_") for key in required)


def test_release_package_excludes_runtime_media_and_test_artifacts() -> None:
    package_script = (DEPLOY_ROOT / "package-release.sh").read_text(encoding="utf-8")
    for excluded_path in (
        "backend/static/**",
        "backend/backend/static/**",
        "e2e/test-results/**",
        "test-results/**",
        "tmp/**",
    ):
        assert f":(exclude){excluded_path}" in package_script
