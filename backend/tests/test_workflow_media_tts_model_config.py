from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from app.features.workflow_media.application.prepare_separate_media import _audio_model
from app.services import volcano_speech_tts


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


def test_volcano_speech_config_test_and_production_share_request_contract() -> None:
    common = {
        "access_token": "secret-not-asserted",
        "base_url": (
            "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
            "?app_id=1234567890&resource_id=seed-tts-2.0"
        ),
        "voice": "zh_female_shuangkuaisisi_moon_bigtts",
        "speed": 1.0,
        "request_id": "request-1",
    }

    test_request = volcano_speech_tts.build_volcano_speech_request(
        **common, text="模型中心连接测试"
    )
    production_request = volcano_speech_tts.build_volcano_speech_request(
        **common, text="不应出现在安全证据中的小说对白"
    )

    assert test_request.contract_version == production_request.contract_version
    assert sorted(test_request.payload) == sorted(production_request.payload)
    assert test_request.safe_evidence() == production_request.safe_evidence()
    assert "模型中心连接测试" not in str(test_request.safe_evidence())
    assert "小说对白" not in str(production_request.safe_evidence())
    assert "secret-not-asserted" not in str(test_request.safe_evidence())
