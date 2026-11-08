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
