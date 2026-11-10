from app.services.novel_import_service import parse_novel_import


def _title(name: str, text: str) -> str:
    return parse_novel_import(name, text.encode("utf-8")).title


def test_short_first_line_is_title():
    assert _title("x.txt", "雾港铜铃\n\n第一章 来客\n沈砚到了。") == "雾港铜铃"


def test_markdown_heading_is_title():
    assert _title("x.md", "# 雾港铜铃\n\n## 第一章 来客\n沈砚到了。") == "雾港铜铃"


def test_body_paragraph_is_not_title_falls_back_to_filename():
    text = "沈砚穿着深蓝旧呢大衣抵达雾港。码头上，林晚提着一盏铜灯等候。\n第一章 来客\n正文。"
    assert _title("雾港故事.txt", text) == "雾港故事"


def test_chapter_first_uses_filename():
    assert _title("雾港故事.txt", "第一章 雾港来客\n沈砚到了。\n第二章 铜铃\n林晚说。") == "雾港故事"


def test_pasted_text_without_title_gets_neutral_name():
    assert _title("pasted.txt", "第一章 雾港来客\n沈砚穿着深蓝旧呢大衣抵达雾港，林晚等候。") == "未命名小说"
