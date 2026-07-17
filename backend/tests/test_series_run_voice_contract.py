from app.features.series_run_story_locks.application.voice_contract import (
    provider_voice_allowlist,
)


def test_volcano_seed_tts_uses_the_verified_v3_default_voice() -> None:
    assert provider_voice_allowlist("volcano") == (
        "zh_female_vv_uranus_bigtts",
    )
