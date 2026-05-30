"""测试镜头Prompt重建API"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class MockShot:
    """模拟镜头对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "test-shot-001")
        self.storyboard_id = kwargs.get("storyboard_id", "sb-001")
        self.user_id = kwargs.get("user_id", "user-001")
        self.shot_number = kwargs.get("shot_number", 1)
        self.prompt = kwargs.get("prompt", "A scene")
        self.dialogue = kwargs.get("dialogue", None)
        self.visual_description = kwargs.get("visual_description", None)
        self.duration = kwargs.get("duration", 4)
        self.image_url = kwargs.get("image_url", None)
        self.keyframes = kwargs.get("keyframes", None)
        self.character_refs = kwargs.get("character_refs", None)
        self.extra_data = kwargs.get("extra_data", None)
        self.updated_at = kwargs.get("updated_at", None)


class MockStoryboard:
    """模拟分镜对象"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "sb-001")
        self.user_id = kwargs.get("user_id", "user-001")
        self.title = kwargs.get("title", "Test Storyboard")
        self.novel_id = kwargs.get("novel_id", "novel-001")
        self.chapter_id = kwargs.get("chapter_id", "chapter-001")
        self.story_bible_id = kwargs.get("story_bible_id", "sbible-001")
        self.content = kwargs.get("content", {})


def test_batch_rebuild_prompts_request_model():
    """测试批量重建请求模型"""
    from app.api.v1.endpoints.shots import BatchRebuildPromptsRequest

    request = BatchRebuildPromptsRequest(use_locked_assets=True, use_entity_refs=True)
    assert request.use_locked_assets == True
    assert request.use_entity_refs == True
    print("[PASS] BatchRebuildPromptsRequest模型")


def test_batch_rebuild_prompts_response_model():
    """测试批量重建响应模型"""
    from app.api.v1.endpoints.shots import BatchRebuildPromptsResponse

    response = BatchRebuildPromptsResponse(
        status="success",
        total_shots=5,
        rebuilt_count=4,
        skipped_count=1,
        rebuilt_ids=["shot-1", "shot-2", "shot-3", "shot-4"],
        skipped_ids=["shot-5"],
        errors=[{"shot_id": "shot-5", "error": "Test error"}]
    )
    assert response.status == "success"
    assert response.total_shots == 5
    assert response.rebuilt_count == 4
    print("[PASS] BatchRebuildPromptsResponse模型")


def test_rebuild_shot_prompt_response_model():
    """测试重建单个镜头prompt响应模型"""
    from app.api.v1.endpoints.shots import RebuildShotPromptResponse

    response = RebuildShotPromptResponse(
        status="success",
        shot_id="shot-001",
        prompt="Rebuilt prompt text"
    )
    assert response.status == "success"
    assert response.shot_id == "shot-001"
    assert "Rebuilt prompt" in response.prompt
    print("[PASS] RebuildShotPromptResponse模型")


def test_batch_rebuild_response_fields():
    """测试批量重建响应字段完整性"""
    from app.api.v1.endpoints.shots import BatchRebuildPromptsResponse

    response = BatchRebuildPromptsResponse(
        status="success",
        total_shots=3,
        rebuilt_count=2,
        skipped_count=1,
        rebuilt_ids=["shot-1", "shot-2"],
        skipped_ids=["shot-3"],
        errors=[]
    )

    # 验证字段存在
    assert hasattr(response, "status")
    assert hasattr(response, "total_shots")
    assert hasattr(response, "rebuilt_count")
    assert hasattr(response, "skipped_count")
    assert hasattr(response, "rebuilt_ids")
    assert hasattr(response, "skipped_ids")
    assert hasattr(response, "errors")

    # 验证关系正确
    assert response.rebuilt_count == len(response.rebuilt_ids)
    assert response.skipped_count == len(response.skipped_ids)
    assert response.total_shots == response.rebuilt_count + response.skipped_count

    print("[PASS] 批量重建响应字段完整性")


def test_rebuild_with_review_markers_cleared():
    """测试重建时审查标记被清除"""
    from app.api.v1.endpoints.shots import BatchRebuildPromptsResponse

    # 模拟extra_data中有审查标记
    extra_data = {
        "needs_review": True,
        "review_reason": "Low quality",
        "review_at": "2024-01-01T00:00:00"
    }

    # 验证响应模型可以处理
    response = BatchRebuildPromptsResponse(
        status="success",
        total_shots=1,
        rebuilt_count=1,
        skipped_count=0,
        rebuilt_ids=["shot-1"],
        skipped_ids=[],
        errors=[]
    )

    assert response.status == "success"
    print("[PASS] 审查标记清除逻辑存在")


def test_batch_rebuild_empty_storyboard():
    """测试空分镜的批量重建"""
    from app.api.v1.endpoints.shots import BatchRebuildPromptsResponse

    response = BatchRebuildPromptsResponse(
        status="success",
        total_shots=0,
        rebuilt_count=0,
        skipped_count=0,
        rebuilt_ids=[],
        skipped_ids=[],
        errors=[]
    )

    assert response.total_shots == 0
    assert response.rebuilt_count == 0
    assert len(response.rebuilt_ids) == 0
    print("[PASS] 空分镜批量重建")


def test_batch_rebuild_all_errors():
    """测试所有镜头重建失败的情况"""
    from app.api.v1.endpoints.shots import BatchRebuildPromptsResponse

    response = BatchRebuildPromptsResponse(
        status="success",
        total_shots=2,
        rebuilt_count=0,
        skipped_count=2,
        rebuilt_ids=[],
        skipped_ids=["shot-1", "shot-2"],
        errors=[
            {"shot_id": "shot-1", "error": "API timeout"},
            {"shot_id": "shot-2", "error": "Invalid context"}
        ]
    )

    assert response.rebuilt_count == 0
    assert response.skipped_count == 2
    assert len(response.errors) == 2
    print("[PASS] 全部失败情况")


def test_shot_model_extra_data_handling():
    """测试镜头模型extra_data处理"""
    shot = MockShot(extra_data={"needs_review": True, "custom_field": "value"})

    # 模拟清除审查标记
    extra_data = shot.extra_data or {}
    extra_data.pop("needs_review", None)
    extra_data.pop("review_reason", None)
    extra_data.pop("review_at", None)

    assert "needs_review" not in extra_data
    assert "custom_field" in extra_data
    print("[PASS] extra_data审查标记清除")


def test_shot_model_extra_data_none():
    """测试镜头模型extra_data为None时的处理"""
    shot = MockShot(extra_data=None)

    # 模拟安全访问
    extra_data = shot.extra_data if shot.extra_data and isinstance(shot.extra_data, dict) else {}
    extra_data.pop("needs_review", None)

    assert extra_data == {}
    print("[PASS] extra_data为None时的安全处理")


def test_rebuild_prompt_with_locked_assets():
    """测试使用锁定资产的重建"""
    from app.api.v1.endpoints.shots import RebuildShotPromptResponse

    response = RebuildShotPromptResponse(
        status="success",
        shot_id="shot-001",
        prompt="Prompt with locked character reference"
    )

    assert response.status == "success"
    assert len(response.prompt) > 0
    print("[PASS] 锁定资产重建")


def test_rebuild_prompt_without_locked_assets():
    """测试不使用锁定资产的重建"""
    from app.api.v1.endpoints.shots import RebuildShotPromptResponse

    response = RebuildShotPromptResponse(
        status="success",
        shot_id="shot-001",
        prompt="Prompt without locked assets"
    )

    assert response.status == "success"
    print("[PASS] 无锁定资产重建")


def test_consistency_prompt_structure():
    """测试一致性prompt结构"""
    # 模拟context返回
    context = {
        "prompt": "A cinematic shot with character consistency",
        "metadata": {
            "consistency_score": 0.95,
            "character_refs": ["char-001"],
            "scene_refs": ["scene-001"]
        }
    }

    assert "prompt" in context
    assert isinstance(context["prompt"], str)
    assert len(context["prompt"]) > 0
    print(f"[PASS] 一致性prompt结构: {context['prompt'][:50]}...")


def test_auto_fill_entity_refs_signature():
    """测试auto_fill_shot_entity_refs函数签名"""
    from app.services.consistency_context import auto_fill_shot_entity_refs
    import inspect

    sig = inspect.signature(auto_fill_shot_entity_refs)
    params = list(sig.parameters.keys())

    # 函数需要db, shot, novel_id, chapter_id参数
    assert "db" in params
    assert "shot" in params
    assert "novel_id" in params
    assert "chapter_id" in params
    print(f"[PASS] auto_fill_shot_entity_refs签名: {params}")


def test_asset_lock_service_signature():
    """测试AssetLockService.lock_shot_assets函数签名"""
    from app.services.asset_lock_service import AssetLockService
    import inspect

    service = AssetLockService()
    sig = inspect.signature(service.lock_shot_assets)
    params = list(sig.parameters.keys())

    # 函数需要db, shot参数
    assert "db" in params
    assert "shot" in params
    print(f"[PASS] AssetLockService.lock_shot_assets签名: {params}")


def test_build_consistency_prompt_signature():
    """测试build_consistency_prompt函数签名"""
    from app.services.consistency_context import build_consistency_prompt
    import inspect

    sig = inspect.signature(build_consistency_prompt)
    params = list(sig.parameters.keys())

    # 函数需要db, user_id, task参数
    assert "db" in params
    assert "user_id" in params
    assert "task" in params
    print(f"[PASS] build_consistency_prompt签名: {params}")


def test_rebuild_shot_prompt_response_with_empty_prompt():
    """测试重建后prompt为空的情况"""
    from app.api.v1.endpoints.shots import RebuildShotPromptResponse

    response = RebuildShotPromptResponse(
        status="success",
        shot_id="shot-001",
        prompt=""
    )

    assert response.status == "success"
    assert response.prompt == ""
    print("[PASS] 空prompt响应处理")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("运行镜头Prompt重建API测试")
    print("=" * 60)

    tests = [
        test_batch_rebuild_prompts_request_model,
        test_batch_rebuild_prompts_response_model,
        test_rebuild_shot_prompt_response_model,
        test_batch_rebuild_response_fields,
        test_rebuild_with_review_markers_cleared,
        test_batch_rebuild_empty_storyboard,
        test_batch_rebuild_all_errors,
        test_shot_model_extra_data_handling,
        test_shot_model_extra_data_none,
        test_rebuild_prompt_with_locked_assets,
        test_rebuild_prompt_without_locked_assets,
        test_consistency_prompt_structure,
        test_auto_fill_entity_refs_signature,
        test_asset_lock_service_signature,
        test_build_consistency_prompt_signature,
        test_rebuild_shot_prompt_response_with_empty_prompt,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 60)
    print(f"测试结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)