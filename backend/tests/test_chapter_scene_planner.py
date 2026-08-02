from __future__ import annotations

from app.services.chapter_scene_planner import plan_chapter_scenes


def _paragraph(label: str, detail: str) -> str:
    return f"{label}\n" + (detail * 45) + "。"


def test_long_chapter_is_split_into_ordered_storyboard_units() -> None:
    content = "\n\n".join(
        [
            _paragraph("【玄霜殿】", "顾清霜在殿中检查星盘，沈砚守在门外"),
            _paragraph("【断云桥】", "两人穿过风雪，青铜剑匣发出鸣响"),
            _paragraph("【归墟塔】", "守塔人拦路，顾清霜拔剑迎战"),
        ]
    )

    plan = plan_chapter_scenes(content, chapter_title="第三章·归墟之门")

    assert len(plan) >= 3
    assert [item.scene_index for item in plan] == list(range(1, len(plan) + 1))
    assert all(item.shot_count >= 2 for item in plan)
    assert "玄霜殿" in plan[0].title
    assert "归墟塔" in plan[-1].title
    assert "".join(item.source_text for item in plan).replace("\n", "") == content.replace("\n", "")


def test_unformatted_long_chapter_uses_sentence_boundaries_without_losing_text() -> None:
    sentences = [f"顾清霜沿石阶前行并观察第{i}道阵纹。" for i in range(1, 90)]
    content = "".join(sentences)

    plan = plan_chapter_scenes(content, chapter_title="无标题长章")

    assert len(plan) >= 2
    assert all(350 <= len(item.source_text) <= 1000 for item in plan)
    assert "".join(item.source_text for item in plan) == content
    assert plan[0].continuity["next_scene_index"] == 2
    assert plan[-1].continuity["previous_scene_index"] == len(plan) - 1


def test_short_legacy_chapter_remains_one_unit() -> None:
    plan = plan_chapter_scenes("顾清霜推门而入。沈砚问：‘找到星灯了吗？’", chapter_title="短章")

    assert len(plan) == 1
    assert plan[0].shot_count == 1
    assert plan[0].source_text.startswith("顾清霜")
