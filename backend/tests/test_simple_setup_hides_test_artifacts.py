from app.services.simple_model_setup import is_internal_test_artifact


def test_test_artifacts_are_hidden():
    for name in [
        "live-text-3db10f7c-fa3e-4b14-b421-f8ecd1e4fded",
        "tts-provider-01960feb-35ae-419e-ad3b-7aae1c2fd571",
        "contract-text",
        "contract video",
        "test-final-provider-video-6ed06323-f8b1-4f0e-9d4e-d622c8ffc289",
        "预检供应商",
    ]:
        assert is_internal_test_artifact(name), name


def test_real_catalog_names_stay_visible():
    for name in ["volcano", "火山引擎", "doubao-seedance-2-0-260128", "豆包Seed-1.8", "MiniMax-M2.7", "deepseek-v4-flash", "speech-2.6-hd", None, ""]:
        assert not is_internal_test_artifact(name), name
