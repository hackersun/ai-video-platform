from datetime import datetime, timedelta, timezone

from app.features.private_media.domain import is_private_delivery_url, lifecycle_policy, sanitize_provider_url


def test_lifecycle_classes_have_private_prefixes_and_distinct_retention() -> None:
    original = lifecycle_policy("original", user_id="u-1", filename="ref.png")
    process = lifecycle_policy("process", user_id="u-1", filename="frame.png")
    final = lifecycle_policy("final", user_id="u-1", filename="movie.mp4")

    assert original.object_key == "private/original/u-1/ref.png"
    assert process.object_key == "private/process/u-1/frame.png"
    assert final.object_key == "private/final/u-1/movie.mp4"
    assert original.retention_days < process.retention_days < final.retention_days


def test_provider_evidence_never_contains_signed_query_values() -> None:
    evidence = sanitize_provider_url(
        "https://private.example.test/private/ref.jpg?e=1700000300&token=ak:secret",
        now=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )

    assert evidence.canonical_url == "https://private.example.test/private/ref.jpg"
    assert evidence.expires_at == datetime.fromtimestamp(1_700_000_300, tz=timezone.utc)
    assert "token" not in evidence.url_fingerprint
    assert "secret" not in evidence.url_fingerprint


def test_private_delivery_requires_a_current_short_lived_signature() -> None:
    now = datetime(2026, 8, 9, tzinfo=timezone.utc)
    deadline = int((now + timedelta(minutes=5)).timestamp())

    assert is_private_delivery_url(
        f"https://private.example.test/ref.jpg?e={deadline}&token=ak:signature", now=now,
    ) is True
    assert is_private_delivery_url("https://private.example.test/ref.jpg", now=now) is False
    assert is_private_delivery_url(
        f"https://private.example.test/ref.jpg?e={deadline + 3600}&token=ak:signature", now=now,
    ) is False
