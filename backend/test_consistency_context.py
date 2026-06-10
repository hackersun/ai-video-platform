"""测试 consistency_context.py 的实体匹配功能"""

import sys
sys.path.insert(0, "/Users/sunqinyue/Documents/work/BJDEV/claude/ai-video-platform/backend")

from app.services.consistency_context import (
    match_entities_to_text,
    _compact_ids,
    _json_dict,
)


class MockStoryEntity:
    """模拟 StoryEntity 对象"""
    def __init__(self, entity_type: str, name: str, aliases: list = None):
        self.id = f"id-{name.lower()}"
        self.entity_type = entity_type
        self.name = name
        self.aliases = aliases or []


def test_match_entities_to_text_exact_match():
    """测试精确匹配"""
    entities = [
        MockStoryEntity("character", "张三", ["Zhang San"]),
        MockStoryEntity("scene", "森林", ["树林"]),
        MockStoryEntity("prop", "魔法杖", ["法杖"]),
        MockStoryEntity("event", "战斗", ["战争"]),
    ]
    text = "张三来到森林，拿起魔法杖，开始战斗"

    matched = match_entities_to_text(entities, text)

    assert "character" in matched
    assert len(matched["character"]) == 1
    assert matched["character"][0].name == "张三"

    assert "scene" in matched
    assert len(matched["scene"]) == 1
    assert matched["scene"][0].name == "森林"

    assert "prop" in matched
    assert len(matched["prop"]) == 1
    assert matched["prop"][0].name == "魔法杖"

    assert "event" in matched
    assert len(matched["event"]) == 1
    assert matched["event"][0].name == "战斗"

    print("[PASS] 精确匹配")


def test_match_entities_to_text_alias_match():
    """测试别名匹配"""
    entities = [
        MockStoryEntity("character", "李四", ["Li Si"]),
        MockStoryEntity("scene", "城堡", ["城"]),
    ]
    text = "Li Si走进了城堡"

    matched = match_entities_to_text(entities, text)

    assert "character" in matched
    assert matched["character"][0].name == "李四"

    assert "scene" in matched
    assert matched["scene"][0].name == "城堡"

    print("[PASS] 别名匹配")


def test_match_entities_to_text_case_insensitive():
    """测试大小写不敏感"""
    entities = [
        MockStoryEntity("character", "Alice", ["Bob"]),
    ]
    text = "alice在城堡中遇见bob"

    matched = match_entities_to_text(entities, text)

    assert "character" in matched
    assert len(matched["character"]) == 1
    assert matched["character"][0].name == "Alice"

    print("[PASS] 大小写不敏感匹配")


def test_match_entities_to_text_no_match():
    """测试无匹配情况"""
    entities = [
        MockStoryEntity("character", "王五"),
        MockStoryEntity("scene", "海边"),
    ]
    text = "赵六在山顶看着日落"

    matched = match_entities_to_text(entities, text)

    assert len(matched) == 0
    print("[PASS] 无匹配情况")


def test_match_entities_to_text_empty_text():
    """测试空文本"""
    entities = [
        MockStoryEntity("character", "张三"),
    ]
    text = ""

    matched = match_entities_to_text(entities, text)

    assert len(matched) == 0
    print("[PASS] 空文本处理")


def test_match_entities_to_text_empty_entities():
    """测试空实体列表"""
    entities = []
    text = "张三在森林里"

    matched = match_entities_to_text(entities, text)

    assert len(matched) == 0
    print("[PASS] 空实体列表处理")


def test_match_entities_to_text_partial_match():
    """测试部分匹配"""
    entities = [
        MockStoryEntity("character", "张三"),
        MockStoryEntity("character", "李四"),
        MockStoryEntity("scene", "森林"),
        MockStoryEntity("scene", "海边"),
    ]
    text = "张三和李四在森林里散步"

    matched = match_entities_to_text(entities, text)

    assert "character" in matched
    assert len(matched["character"]) == 2

    assert "scene" in matched
    assert len(matched["scene"]) == 1
    assert matched["scene"][0].name == "森林"

    print("[PASS] 部分匹配")


def test_compact_ids():
    """测试 _compact_ids 函数"""
    assert _compact_ids(["a", "b", "a", "c", None, "b"]) == ["a", "b", "c"]
    assert _compact_ids([]) == []
    assert _compact_ids([None, None]) == []
    print("[PASS] _compact_ids 函数")


def test_json_dict():
    """测试 _json_dict 函数"""
    assert _json_dict({"key": "value"}) == {"key": "value"}
    assert _json_dict(None) == {}
    assert _json_dict([]) == {}
    print("[PASS] _json_dict 函数")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("测试 consistency_context.py 实体匹配功能")
    print("=" * 60)

    tests = [
        test_match_entities_to_text_exact_match,
        test_match_entities_to_text_alias_match,
        test_match_entities_to_text_case_insensitive,
        test_match_entities_to_text_no_match,
        test_match_entities_to_text_empty_text,
        test_match_entities_to_text_empty_entities,
        test_match_entities_to_text_partial_match,
        test_compact_ids,
        test_json_dict,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print("=" * 60)
    print(f"测试结果: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)