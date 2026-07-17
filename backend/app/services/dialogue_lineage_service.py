"""Deterministic lineage extraction for explicit, named Chinese dialogue."""

from __future__ import annotations

import re


_SPEECH_VERB = r"(?:说道|说|问|喊|答)"
_NAME = r"[\u4e00-\u9fff]{2,4}"
_PREFIX = rf"(?P<speaker>{_NAME}){_SPEECH_VERB}\s*[：:]?\s*|(?P<colon_speaker>{_NAME})\s*[：:]\s*"
_DIALOGUE = re.compile(
    rf"(?<![\u4e00-\u9fff])(?:{_PREFIX})(?:"
    r"“(?P<curly>[^\n“”]{1,500})”"
    r"|「(?P<corner>[^\n「」]{1,500})」"
    r"|『(?P<double_corner>[^\n『』]{1,500})』"
    r'|"(?P<ascii>[^\n"]{1,500})"'
    r")"
)

# These tokens can grammatically precede a speech verb, but do not identify a
# stable character.  Keeping them out of lineage is safer than inventing one.
_NON_NAMES = frozenset({
    "他们", "她们", "它们", "我们", "你们", "咱们", "自己", "对方",
    "有人", "众人", "大家", "所有人", "旁人", "别人",
    "老师", "先生", "女士", "医生", "护士", "警察", "同学", "同事",
    "父亲", "母亲", "爸爸", "妈妈", "哥哥", "姐姐", "弟弟", "妹妹",
    "爷爷", "奶奶", "老板", "经理", "队长", "主任", "院长", "首领",
})
_SPEECH_VERB_SUFFIXES = ("说道", "说", "问", "喊", "答")


def _inside_unclosed_quote(text: str, position: int) -> bool:
    """Return whether the candidate starts inside an earlier bad quote."""
    line_start = text.rfind("\n", 0, position) + 1
    prefix = text[line_start:position]
    return any(prefix.count(opening) != prefix.count(closing) for opening, closing in (
        ("“", "”"), ("「", "」"), ("『", "』"), ('"', '"'),
    ))


def extract_explicit_dialogue(text: str) -> list[dict[str, object]]:
    source = text or ""
    lines: list[dict[str, object]] = []
    for match in _DIALOGUE.finditer(source):
        if _inside_unclosed_quote(source, match.start()):
            continue
        speaker = str(match.group("speaker") or match.group("colon_speaker") or "").strip()
        spoken = str(
            match.group("curly")
            or match.group("corner")
            or match.group("double_corner")
            or match.group("ascii")
            or ""
        ).strip()
        if speaker in _NON_NAMES or speaker.endswith(_SPEECH_VERB_SUFFIXES) or not spoken:
            continue
        lines.append({
            "speaker": speaker,
            "spoken_text": spoken,
            "dialogue": f"{speaker}：{spoken}",
            "source_span": [match.start(), match.end()],
        })
    return lines


__all__ = ["extract_explicit_dialogue"]
