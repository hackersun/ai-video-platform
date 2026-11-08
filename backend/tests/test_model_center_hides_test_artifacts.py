"""模型中心展示层隐藏自动化测试遗留的临时供应商（复用 P0 is_internal_test_artifact 规则）。"""

import asyncio
from types import SimpleNamespace

from app.features.model_config import management_repository


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows

    async def scalars(self, _statement):
        return _Scalars(self._rows)


def _provider(pid, code, name):
    return SimpleNamespace(
        id=pid, code=code, display_name=name, name=code, name_en=None, name_cn=name,
        provider_family=code, is_builtin=True, enabled=True, revision=1, base_url=None, description=None,
    )


def test_provider_page_hides_live_uuid_and_contract_providers_but_keeps_real_ones():
    rows = [
        _provider("p1", "volcano", "火山引擎"),
        _provider("p2", "live-video-e0e55e44-df7f-4a0c-970c-7053c05a8a89", "live-video-e0e55e44-df7f-4a0c-970c-7053c05a8a89"),
        _provider("p3", "deepseek", "DeepSeek 官方"),
        _provider("p4", "contract-text", "contract text"),
    ]
    page = asyncio.run(management_repository.provider_page(_FakeDb(rows), 1, 20))
    assert [item["display_name"] for item in page["items"]] == ["火山引擎", "DeepSeek 官方"]
    assert page["meta"]["total"] == 2


def test_catalog_page_hides_uuid_named_models_and_test_providers(monkeypatch):
    from app.features.model_config import management

    def _model(provider_name, provider_code, model_name, api_model_id):
        return SimpleNamespace(
            provider_name=provider_name, provider_code=provider_code, model_name=model_name,
            api_model_id=api_model_id, capabilities={"video_generation"},
        )

    models = [
        _model("火山引擎", "volcano", "Seedance 2.0", "doubao-seedance-2-0-260128"),
        _model("火山引擎", "volcano", "custom-video-c154a4b1-3b65-4d6e-9f00-000000000000", "doubao-custom-video-route"),
        _model("live-video-e0e55e44-df7f-4a0c-970c-7053c05a8a89", "live-video-x", "video", "api-video"),
    ]

    async def _fake_catalog(*args, **kwargs):
        return SimpleNamespace(models=models)

    monkeypatch.setattr(management, "list_product_catalog", _fake_catalog)
    monkeypatch.setattr(management, "asdict", lambda item: dict(vars(item)))
    page = asyncio.run(management.catalog_page(None, "user-1", 1, 20))
    assert [item["model_name"] for item in page["items"]] == ["Seedance 2.0"]
    assert page["meta"]["total"] == 1
