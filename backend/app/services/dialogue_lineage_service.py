"""Deterministic lineage extraction for explicit, named Chinese dialogue."""

from __future__ import annotations

import re


_SPEECH_VERB = r"(?:低声提醒|轻声提醒|沉声提醒|低声说|轻声说|大声说|高声说|沉声说|冷声说|提醒|说道|喊道|回答|说|问|喊|答)"
_NAME = r"[\u4e00-\u9fff]{2,4}"
_PREFIX = rf"(?P<speaker>[\u4e00-\u9fff]{{2,4}}?){_SPEECH_VERB}\s*[：:]?\s*|(?P<colon_speaker>{_NAME})\s*[：:]\s*"
_DIALOGUE = re.compile(
    rf"(?<![\u4e00-\u9fff])(?:{_PREFIX})(?:"
    r"“(?P<curly>[^\n“”]{1,500})”"
    r"|「(?P<corner>[^\n「」]{1,500})」"
    r"|『(?P<double_corner>[^\n『』]{1,500})』"
    r'|"(?P<ascii>[^\n"]{1,500})"'
    r")"
)
_NARRATED_DIALOGUE = re.compile(
    rf"(?P<verb>{_SPEECH_VERB})\s*[：:]?\s*(?:"
    r"“(?P<curly>[^\n“”]{1,500})”"
    r"|「(?P<corner>[^\n「」]{1,500})」"
    r"|『(?P<double_corner>[^\n『』]{1,500})』"
    r'|"(?P<ascii>[^\n"]{1,500})"'
    r")"
)
_UNQUOTED_DIALOGUE = re.compile(
    rf"(?<![\u4e00-\u9fff])(?P<lead>[\u4e00-\u9fff]{{2,16}}?){_SPEECH_VERB}\s*[：:]\s*"
    r"(?P<plain>[^。！？\n：:“”「」『』\"]{1,200}[。！？])"
)
_COMPOUND_SURNAMES = frozenset({
    "欧阳", "司马", "上官", "诸葛", "东方", "皇甫", "尉迟", "公孙", "慕容", "宇文",
})

# These tokens can grammatically precede a speech verb, but do not identify a
# stable character.  Keeping them out of lineage is safer than inventing one.
_NON_NAMES = frozenset({
    "他们", "她们", "它们", "我们", "你们", "咱们", "自己", "对方",
    "有人", "众人", "大家", "所有人", "旁人", "别人",
    "却仍",
    "老师", "先生", "女士", "医生", "护士", "警察", "同学", "同事",
    "父亲", "母亲", "爸爸", "妈妈", "哥哥", "姐姐", "弟弟", "妹妹",
    "爷爷", "奶奶", "老板", "经理", "队长", "主任", "院长", "首领",
})
_SPEECH_VERB_SUFFIXES = (
    "低声提醒", "轻声提醒", "沉声提醒", "提醒",
    "低声说", "轻声说", "大声说", "高声说", "沉声说", "冷声说",
    "说道", "喊道", "回答", "说", "问", "喊", "答",
)
_MODIFIED_PRONOUN = re.compile(r"^[他她它](?:低声|轻声|大声|高声|沉声|冷声)$")
_PRONOUN_SPEECH_FRAGMENT = re.compile(r"^[他她它](?:回|说|问|答|喊)$")
_NARRATED_SPEAKER = re.compile(
    r"^(?:"
    r"[他她它](?:低声|轻声|大声|高声|沉声|冷声|睁眼|抬头|回头|转身|平静|坚定|冷静)?"
    r"|(?:清晰|平静|坚定|冷静|缓慢|严肃|认真)(?:地)?"
    r")$"
)
_CLEAR_SUBJECT = re.compile(
    rf"(?<![\u4e00-\u9fff])(?P<name>{_NAME})(?="
    r"把|将|接回|举起|拿起|握紧|指向|扳下|跃上|冲进|走进|进入|"
    r"抬起|拔出|对着|沿|抬头|挥动|侧身|闭上|发现|故意|松开|"
    r"睁眼|认出|仰望|带着|抵达|独自抵达|停顿|"
    r"低声提醒|轻声提醒|沉声提醒|提醒|"
    r"低声说|轻声说|大声说|高声说|沉声说|冷声说|说道|喊道|回答|说|问|喊|答)"
)
_SPEECH_ONLY = re.compile(rf"^(?:{_SPEECH_VERB})$")


def _previous_clear_subject(
    text: str, position: int, *, include_previous_sentence: bool = True,
) -> str | None:
    prefix = text[max(0, position - 180):position]
    if not include_previous_sentence:
        boundary = max(prefix.rfind(mark) for mark in "。！？\n")
        prefix = prefix[boundary + 1:]
    candidates = [
        str(match.group("name")).strip()
        for match in _CLEAR_SUBJECT.finditer(prefix)
        if (
            str(match.group("name")).strip() not in _NON_NAMES
            and not str(match.group("name")).strip().startswith(("在", "从", "向", "把", "将", "以", "被", "让"))
        )
    ]
    return candidates[-1] if candidates else None


def normalize_dialogue_speaker_label(
    label: object, *, source: str = "", position: int = 0,
) -> str:
    """Return a stable character label, resolving narration verbs to the prior subject."""
    speaker = str(label or "").strip()
    if (
        _SPEECH_ONLY.fullmatch(speaker)
        or _MODIFIED_PRONOUN.fullmatch(speaker)
        or _PRONOUN_SPEECH_FRAGMENT.fullmatch(speaker)
        or _NARRATED_SPEAKER.fullmatch(speaker)
    ):
        return _previous_clear_subject(source, position) or ""
    for suffix in _SPEECH_VERB_SUFFIXES:
        if speaker.endswith(suffix) and len(speaker) > len(suffix):
            speaker = speaker[:-len(suffix)].strip()
            break
    return "" if (
        len(speaker) < 2
        or speaker in _NON_NAMES
        or _SPEECH_ONLY.fullmatch(speaker)
    ) else speaker


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
        speaker = normalize_dialogue_speaker_label(
            match.group("speaker") or match.group("colon_speaker"),
            source=source, position=match.start(),
        )
        spoken = str(
            match.group("curly")
            or match.group("corner")
            or match.group("double_corner")
            or match.group("ascii")
            or ""
        ).strip()
        if not speaker or not spoken:
            continue
        lines.append({
            "speaker": speaker,
            "spoken_text": spoken,
            "dialogue": f"{speaker}：{spoken}",
            "source_span": [match.start(), match.end()],
        })
    occupied = [tuple(item["source_span"]) for item in lines]
    for match in _NARRATED_DIALOGUE.finditer(source):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        if _inside_unclosed_quote(source, match.start()):
            continue
        speaker = _previous_clear_subject(
            source, match.start(), include_previous_sentence=False,
        )
        if not speaker:
            prefix = source[:match.start()]
            boundary = max(prefix.rfind(mark) for mark in "。！？\n")
            current_sentence = prefix[boundary + 1:].lstrip()
            if current_sentence.startswith(("他", "她", "它")):
                speaker = _previous_clear_subject(source, match.start())
        spoken = str(
            match.group("curly") or match.group("corner")
            or match.group("double_corner") or match.group("ascii") or ""
        ).strip()
        if speaker and spoken:
            lines.append({
                "speaker": speaker, "spoken_text": spoken,
                "dialogue": f"{speaker}：{spoken}",
                "source_span": [match.start(), match.end()],
            })
            occupied.append((match.start(), match.end()))
    for match in _UNQUOTED_DIALOGUE.finditer(source):
        if any(start <= match.start() < end for start, end in occupied):
            continue
        lead = str(match.group("lead") or "")
        name_length = 3 if lead[:2] in _COMPOUND_SURNAMES else 2
        speaker = lead[:name_length]
        spoken = str(match.group("plain") or "").strip()
        if speaker in _NON_NAMES or not spoken:
            continue
        lines.append({
            "speaker": speaker,
            "spoken_text": spoken,
            "dialogue": f"{speaker}：{spoken}",
            "source_span": [match.start(), match.end()],
        })
    lines.sort(key=lambda item: item["source_span"][0])
    return lines


__all__ = ["extract_explicit_dialogue", "normalize_dialogue_speaker_label"]
