from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from app.features.workflow_media.application.prepare_separate_media import _audio_model


def test_volcano_speech_runtime_uses_the_same_configured_endpoint_as_connection_test() -> None:
    config = SimpleNamespace(
        id="config-1",
        extra_params={"app_id": "1234567890", "resource_id": "seed-tts-2.0"},
        test_status="success",
        get_api_key_decrypted=lambda: "secret-not-asserted",
    )
    model = SimpleNamespace(
        model_id="seed-tts-2.0",
        model_name_cn="豆包语音 Seed-TTS 2.0",
        model_name="Doubao Seed TTS 2.0",
        capabilities=["text-to-speech"],
        base_url="https://openspeech.bytedance.com/api/v3/tts/unidirectional",
    )
    provider = SimpleNamespace(id="volcano", name="volcano", base_url=None)

    runtime = _audio_model(config, model, provider)
    query = parse_qs(urlsplit(runtime["base_url"]).query)

    assert query == {
        "app_id": ["1234567890"],
        "resource_id": ["seed-tts-2.0"],
    }
