from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_prometheus_alerts_cover_p0_and_p1_actions_in_chinese() -> None:
    rules = (ROOT / "infra/monitoring/prometheus-alerts.yml").read_text(encoding="utf-8")

    for alert_name in (
        "AiVideoApiUnavailable",
        "AiVideoDatabaseNotReady",
        "AiVideoHighServerErrorRate",
        "AiVideoDeadLetterTasks",
        "AiVideoTasksNeedAttention",
        "AiVideoStalledTasks",
    ):
        assert f"alert: {alert_name}" in rules
    assert 'up{job="ai-video-api"} == 0' in rules
    assert "ai_video_database_ready == 0" in rules
    assert "ai_video_task_oldest_active_age_seconds > 900" in rules
    assert "action:" in rules
    assert "停止" in rules or "暂停" in rules


def test_monitoring_overlay_keeps_metrics_private_and_routes_alerts_externally() -> None:
    compose = (ROOT / "infra/compose/monitoring.yml").read_text(encoding="utf-8")
    prometheus = (ROOT / "infra/monitoring/prometheus.yml").read_text(encoding="utf-8")
    alertmanager = (ROOT / "infra/monitoring/alertmanager.yml.example").read_text(encoding="utf-8")

    assert "127.0.0.1" in compose
    assert "OPERATIONS_TOKEN_FILE" in compose
    assert "ALERTMANAGER_CONFIG_FILE" in compose
    assert "latest" not in compose
    assert "credentials_file: /run/secrets/operations_token" in prometheus
    assert "api:8000" in prometheus
    assert "alertmanager:9093" in prometheus
    assert "replace-with-on-call-webhook" in alertmanager
    assert "真实值班地址" in alertmanager


def test_recovery_container_pins_the_production_postgres_major() -> None:
    dockerfile = (ROOT / "infra/docker/postgres-recovery.Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.startswith("FROM postgres:15.13-alpine")
    assert "USER recovery" in dockerfile
    assert 'ENTRYPOINT ["python3"]' in dockerfile
