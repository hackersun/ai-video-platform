"""Helpers for chapter label normalization across storyboard and shot flows."""

from __future__ import annotations

import re
from typing import Optional


_CHAPTER_NUMERAL = r"[一二三四五六七八九十百千万两\d\s]+?"
_CHAPTER_LABEL_PATTERN = re.compile(rf"^\s*第\s*({_CHAPTER_NUMERAL})\s*[章节卷集回]\s*[：:、.\s-]*")
_BRACKETED_DUPLICATE_CHAPTER_LABEL_PATTERN = re.compile(
    rf"第\s*{_CHAPTER_NUMERAL}\s*[章节卷集回]\s*([《「“\"'])\s*"
    rf"第\s*({_CHAPTER_NUMERAL})\s*[章节卷集回]\s*[：:、.\s-]*([^》」”\"'\n]*)([》」”\"'])"
)
_DUPLICATE_CHAPTER_LABEL_PATTERN = re.compile(
    rf"第\s*{_CHAPTER_NUMERAL}\s*[章节卷集回]\s+第\s*({_CHAPTER_NUMERAL})\s*[章节卷集回]\s*"
)


def split_chapter_label(title: Optional[str], chapter_number: Optional[int] = None) -> tuple[str, str]:
    """Return the chapter number token and title without duplicated chapter prefixes."""
    fallback_number = chapter_number or 1
    remaining = (title or "").strip()
    explicit_number: Optional[str] = None

    while remaining:
        match = _CHAPTER_LABEL_PATTERN.match(remaining)
        if not match:
            break
        explicit_number = re.sub(r"\s+", "", match.group(1))
        remaining = remaining[match.end():].strip()

    return str(explicit_number or fallback_number), remaining


def format_chapter_label(title: Optional[str], chapter_number: Optional[int] = None) -> str:
    """Return a single clean chapter label like `第2章 宗门测试`."""
    chapter_number_token, remaining = split_chapter_label(title, chapter_number)
    return f"第{chapter_number_token}章" + (f" {remaining}" if remaining else "")


def format_chapter_bracket_label(title: Optional[str], chapter_number: Optional[int] = None) -> str:
    """Return a clean chapter label for Chinese title contexts, e.g. `第2章《宗门测试》`."""
    chapter_number_token, remaining = split_chapter_label(title, chapter_number)
    return f"第{chapter_number_token}章" + (f"《{remaining}》" if remaining else "")


def normalize_duplicate_chapter_label_text(value: Optional[str]) -> Optional[str]:
    """Clean already-saved text containing duplicated chapter labels."""
    if not value:
        return value
    text = str(value)

    def bracketed_replacement(match: re.Match[str]) -> str:
        opener, chapter_number, chapter_title, closer = match.groups()
        clean_number = re.sub(r"\s+", "", chapter_number)
        clean_title = chapter_title.strip()
        return f"第{clean_number}章{opener}{clean_title}{closer}" if clean_title else f"第{clean_number}章"

    def replacement(match: re.Match[str]) -> str:
        chapter_number = re.sub(r"\s+", "", match.group(1))
        return f"第{chapter_number}章 "

    previous = None
    while previous != text:
        previous = text
        text = _BRACKETED_DUPLICATE_CHAPTER_LABEL_PATTERN.sub(bracketed_replacement, text)
        text = _DUPLICATE_CHAPTER_LABEL_PATTERN.sub(replacement, text)
    text = re.sub(r"(第[一二三四五六七八九十百千万两\d]+章)\s+([，。！？、：:；;])", r"\1\2", text)
    return re.sub(r"\s{2,}", " ", text).strip()
