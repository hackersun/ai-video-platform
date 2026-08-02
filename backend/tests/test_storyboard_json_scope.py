import pytest

from app.api.v1.endpoints import storyboards
from app.api.v1.endpoints.storyboards import generate_storyboard


def test_generate_storyboard_does_not_shadow_module_json() -> None:
    """Provider errors must not be masked by an unbound local json module."""

    assert "json" not in generate_storyboard.__code__.co_varnames


@pytest.mark.asyncio
async def test_storyboard_text_service_uses_canonical_default_binding(monkeypatch) -> None:
    expected = (object(), "volcano_agent_plan", "ark-code-latest", "https://ark.example")

    async def resolve(_db, _user_id):
        return expected

    monkeypatch.setattr(storyboards, "get_user_text_generation_service", resolve)

    assert await storyboards.get_storyboard_text_service(object(), "user-1") == expected
