from app.services.minimax_tts_request import build_minimax_tts_request


def test_internal_model_id_builds_provider_tts_payload() -> None:
    request = build_minimax_tts_request(
        model_id="MiniMax-speech-2.6-hd",
        text="你好",
        voice_id="male-qn-qingse",
        speed=1.0,
    )

    assert request.contract_version == "minimax.tts.v2.v1"
    assert request.url_path == "/t2a_v2"
    assert request.payload == {
        "model": "speech-2.6-hd",
        "text": "你好",
        "stream": False,
        "output_format": "url",
        "voice_setting": {
            "voice_id": "male-qn-qingse",
            "speed": 1.0,
            "vol": 1.0,
            "pitch": 0,
        },
        "language_boost": "auto",
    }


def test_safe_evidence_excludes_text_and_provider_credentials() -> None:
    request = build_minimax_tts_request(
        model_id="speech-2.6-hd",
        text="不应出现在证据中的小说对白",
        voice_id="male-qn-qingse",
        speed=1.0,
    )

    evidence = request.safe_evidence()

    assert set(evidence) == {
        "request_contract_version",
        "api_model_id",
        "voice_id",
        "payload_fields",
    }
    assert evidence["payload_fields"] == sorted(request.payload)
    assert "不应出现在证据中的小说对白" not in str(evidence)
