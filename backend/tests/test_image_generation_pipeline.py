import asyncio

from app.services.minimax_errors import minimax_provider_rejection
from app.services.image_generation_pipeline import call_image_generation_provider, provider_task_id
from app.services.image_prompt_policy import GLOBAL_IMAGE_NEGATIVE_CONSTRAINT


def test_minimax_trace_id_is_not_treated_as_image_task_id() -> None:
    assert provider_task_id({"id": "trace-only"}, provider_name="minimax") is None


def test_minimax_official_generation_id_is_preserved() -> None:
    result = {
        "id": "generation-1",
        "data": {"image_urls": []},
        "metadata": {"success_count": "0", "failed_count": "1"},
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }

    assert provider_task_id(result, provider_name="minimax") == "generation-1"


def test_minimax_real_task_id_is_preserved() -> None:
    assert provider_task_id({"id": "trace-id", "task_id": "task-1"}, provider_name="minimax") == "task-1"


def test_minimax_business_rejection_request_id_is_not_a_provider_task() -> None:
    rejection = minimax_provider_rejection({
        "id": "request-trace-only",
        "base_resp": {"status_code": 1008, "status_msg": "invalid request"},
    }, "image generation")

    assert rejection is not None
    assert rejection.provider_task_id is None


def test_volcano_id_is_still_treated_as_task_id() -> None:
    assert provider_task_id({"id": "volcano-task"}, provider_name="volcano") == "volcano-task"


def test_minimax_image_prompt_is_compacted_below_provider_limit() -> None:
    calls: list[dict] = []

    class _FakeService:
        async def generate_image(self, **kwargs):
            calls.append(kwargs)
            return {"data": {"image_base64": ["iVBORw0KGgoAAAANSUhEUgAA"]}}

    long_context = "、".join([f"连续章节事件{i}：主角在山门、洞府、街市之间推进剧情并保留道具状态" for i in range(120)])
    prompt = "\n".join(
        [
            "角色姓名：林青岚",
            "外貌特征：女性剑修，青色长袍，黑色长发，眉眼清冷，银色发簪。",
            f"剧情上下文：{long_context}",
            "背面视图硬约束：角色必须背对镜头，画面展示后脑勺、后背、服装背部结构和背后配饰；脸部不可见。",
            GLOBAL_IMAGE_NEGATIVE_CONSTRAINT,
        ]
    )

    asyncio.run(
        call_image_generation_provider(
            _FakeService(),
            provider_name="minimax",
            model_id="image-01",
            prompt=prompt,
        )
    )

    sent_prompt = calls[0]["prompt"]
    assert len(sent_prompt) < 1500
    assert "角色姓名：林青岚" in sent_prompt
    assert "背面视图硬约束" in sent_prompt
    assert "通用负面约束" in sent_prompt


def test_non_minimax_image_prompt_is_not_compacted() -> None:
    calls: list[dict] = []

    class _FakeService:
        async def generate_image(self, **kwargs):
            calls.append(kwargs)
            return {"data": [{"url": "https://example.com/a.png"}]}

    prompt = "A" * 2000

    asyncio.run(
        call_image_generation_provider(
            _FakeService(),
            provider_name="volcano",
            model_id="seedream",
            prompt=prompt,
        )
    )

    assert calls[0]["prompt"] == prompt
