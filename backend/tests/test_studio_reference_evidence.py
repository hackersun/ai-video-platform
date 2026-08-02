from types import SimpleNamespace

from app.services.studio_snapshot import _reference_package_summary


def test_reference_package_summary_keeps_traceable_sources_without_urls() -> None:
    job = SimpleNamespace(extra_data={
        "reference_package_mode": "multimodal",
        "reference_package": {
            "image_count": 1,
            "video_count": 1,
            "items": [
                {
                    "type": "image", "role_tag": "protagonist", "entity_name": "顾清霜",
                    "view_key": "front", "canonical_asset_id": "asset-character-front",
                    "url": "https://secret.example.com/character.png",
                },
                {
                    "type": "video", "role_tag": "previous_shot", "source_shot_id": "shot-previous",
                    "url": "https://secret.example.com/previous.mp4",
                },
            ],
            "dropped": [],
        },
    })

    summary = _reference_package_summary(job)["reference_package"]

    assert summary["items"] == [
        {
            "type": "image", "role_tag": "protagonist", "entity_name": "顾清霜",
            "view_key": "front", "canonical_asset_id": "asset-character-front",
        },
        {"type": "video", "role_tag": "previous_shot", "source_shot_id": "shot-previous"},
    ]
    assert "secret.example.com" not in str(summary)
