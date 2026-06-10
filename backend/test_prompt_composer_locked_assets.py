"""测试 prompt_composer 中 locked_assets 参数功能"""

import pytest
from app.services.prompt_composer import compose_generation_prompt


class MockShot:
    """模拟镜头对象"""
    def __init__(self, **kwargs):
        self.prompt = kwargs.get("prompt", "角色在场景中行动")
        self.visual_description = kwargs.get("visual_description", "高清画面")
        self.dialogue = kwargs.get("dialogue", "你好")
        self.camera_angle = kwargs.get("camera_angle", "平视")
        self.emotion = kwargs.get("emotion", "平静")


class MockCharacter:
    """模拟角色对象"""
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "张三")
        self.appearance = kwargs.get("appearance", "帅气")
        self.personality = kwargs.get("personality", "勇敢")


class MockProject:
    """模拟项目对象"""
    def __init__(self, **kwargs):
        self.global_style = kwargs.get("global_style", "动漫风格")
        self.global_seed = kwargs.get("global_seed", "seed123")
        self.global_negative_prompt = kwargs.get("global_negative_prompt", None)


class MockStoryBible:
    """模拟Story Bible对象"""
    def __init__(self, **kwargs):
        self.style = kwargs.get("style", "奇幻")
        self.worldview = kwargs.get("worldview", "现代都市")
        self.character_rules = kwargs.get("character_rules", [])
        self.scene_rules = kwargs.get("scene_rules", [])
        self.extra_data = kwargs.get("extra_data", {})


def test_compose_generation_prompt_without_locked_assets():
    """测试不带锁定资产的prompt生成"""
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        characters=[MockCharacter()],
    )

    assert "任务: shot_video" in prompt
    assert "当前镜头:" in prompt
    assert "本镜头角色:" in prompt
    assert "视频一致性约束:" in prompt
    assert "锁定资产一致性约束" not in prompt
    print("[PASS] 不带锁定资产测试")


def test_compose_generation_prompt_with_empty_locked_assets():
    """测试带空列表锁定资产的prompt生成"""
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        characters=[MockCharacter()],
        locked_assets=[],
    )

    assert "锁定资产一致性约束" not in prompt
    print("[PASS] 空锁定资产列表测试")


def test_compose_generation_prompt_with_single_locked_asset():
    """测试带单个锁定资产的prompt生成"""
    locked_assets = [
        {"type": "character", "name": "主角A", "description": "蓝发少年"}
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        characters=[MockCharacter()],
        locked_assets=locked_assets,
    )

    assert "锁定资产一致性约束" in prompt
    assert "主角A" in prompt
    assert "严格保持外观与锁定资产一致" in prompt
    print("[PASS] 单个锁定资产测试")


def test_compose_generation_prompt_with_multiple_locked_assets():
    """测试带多个锁定资产的prompt生成"""
    locked_assets = [
        {"type": "character", "name": "主角A", "description": "蓝发少年"},
        {"type": "scene", "name": "咖啡厅", "description": "温馨的咖啡厅"},
        {"type": "prop", "name": "魔法棒", "description": "发光的魔杖"},
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        characters=[MockCharacter()],
        locked_assets=locked_assets,
    )

    assert "锁定资产一致性约束" in prompt
    assert "主角A" in prompt
    assert "咖啡厅" in prompt
    assert "魔法棒" in prompt
    assert prompt.count("严格保持外观与锁定资产一致") == 3
    print("[PASS] 多个锁定资产测试")


def test_compose_generation_prompt_locked_assets_missing_fields():
    """测试锁定资产缺失字段时的处理"""
    locked_assets = [
        {"name": "只给名字的资产"},
        {"type": "scene"},
        {},  # 空字典
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        locked_assets=locked_assets,
    )

    assert "锁定资产一致性约束" in prompt
    assert "只给名字的资产" in prompt
    assert "Unknown" in prompt  # 缺失name时使用默认值
    print("[PASS] 缺失字段处理测试")


def test_compose_generation_prompt_non_video_task_ignores_locked_assets():
    """测试非视频任务忽略锁定资产参数"""
    locked_assets = [
        {"type": "character", "name": "主角A"}
    ]
    prompt = compose_generation_prompt(
        task="image_generation",  # 不是shot_video
        locked_assets=locked_assets,
    )

    assert "锁定资产一致性约束" not in prompt
    print("[PASS] 非视频任务忽略锁定资产测试")


def test_compose_generation_prompt_with_project_context():
    """测试带项目上下文的锁定资产注入"""
    locked_assets = [
        {"type": "character", "name": "主角B"}
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        project=MockProject(),
        locked_assets=locked_assets,
    )

    assert "项目风格:" in prompt
    assert "锁定资产一致性约束" in prompt
    assert "主角B" in prompt
    print("[PASS] 项目上下文测试")


def test_compose_generation_prompt_with_story_bible_context():
    """测试带Story Bible上下文的锁定资产注入"""
    locked_assets = [
        {"type": "scene", "name": "古代宫殿"}
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        story_bible=MockStoryBible(),
        locked_assets=locked_assets,
    )

    assert "故事风格:" in prompt
    assert "锁定资产一致性约束" in prompt
    assert "古代宫殿" in prompt
    print("[PASS] Story Bible上下文测试")


def test_compose_generation_prompt_locked_assets_order():
    """测试锁定资产按顺序注入"""
    locked_assets = [
        {"type": "character", "name": "资产1"},
        {"type": "scene", "name": "资产2"},
        {"type": "prop", "name": "资产3"},
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        locked_assets=locked_assets,
    )

    # 验证顺序：资产1应该在资产2之前，资产2应该在资产3之前
    idx1 = prompt.find("资产1")
    idx2 = prompt.find("资产2")
    idx3 = prompt.find("资产3")
    assert idx1 < idx2 < idx3, "锁定资产应该按顺序出现在prompt中"
    print("[PASS] 锁定资产顺序测试")


def test_compose_generation_prompt_locked_assets_in_final_section():
    """测试锁定资产约束出现在prompt末尾"""
    locked_assets = [
        {"type": "character", "name": "测试资产"}
    ]
    prompt = compose_generation_prompt(
        task="shot_video",
        shot=MockShot(),
        characters=[MockCharacter()],
        locked_assets=locked_assets,
    )

    lines = prompt.split("\n")
    # 找到包含"锁定资产一致性约束"的行
    lock_section_idx = None
    for i, line in enumerate(lines):
        if "锁定资产一致性约束" in line:
            lock_section_idx = i
            break

    assert lock_section_idx is not None
    # 后续行应该只包含锁定资产，不应该有其他内容
    for line in lines[lock_section_idx:]:
        if line.strip() and "锁定资产一致性约束" not in line:
            assert "测试资产" in line
    print("[PASS] 锁定资产位置测试")


if __name__ == "__main__":
    print("=" * 60)
    print("开始运行 prompt_composer locked_assets 功能测试")
    print("=" * 60)

    # 运行所有测试
    test_compose_generation_prompt_without_locked_assets()
    test_compose_generation_prompt_with_empty_locked_assets()
    test_compose_generation_prompt_with_single_locked_asset()
    test_compose_generation_prompt_with_multiple_locked_assets()
    test_compose_generation_prompt_locked_assets_missing_fields()
    test_compose_generation_prompt_non_video_task_ignores_locked_assets()
    test_compose_generation_prompt_with_project_context()
    test_compose_generation_prompt_with_story_bible_context()
    test_compose_generation_prompt_locked_assets_order()
    test_compose_generation_prompt_locked_assets_in_final_section()

    print("=" * 60)
    print("所有测试完成!")
    print("=" * 60)