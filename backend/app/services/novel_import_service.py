"""
Plain text and Markdown novel import helpers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_IMPORT_EXTENSIONS = {".txt", ".md", ".markdown"}


@dataclass
class ParsedChapter:
    title: str
    content: str
    chapter_number: int
    word_count: int
    preview: str


@dataclass
class ParsedNovelImport:
    title: str
    description: str | None
    word_count: int
    chapters: list[ParsedChapter]
    metadata: dict[str, Any]


CHAPTER_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(第\s*[零〇一二三四五六七八九十百千万\d]+\s*[章节回部卷][^\n]*|Chapter\s+\d+[^\n]*|\d+[\.、]\s+\S[^\n]*)\s*$",
    re.IGNORECASE,
)


def validate_import_filename(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in SUPPORTED_IMPORT_EXTENSIONS:
        raise ValueError("仅支持 txt、md、markdown 文件")
    return suffix


def decode_import_bytes(raw: bytes) -> str:
    if not raw:
        raise ValueError("上传文件为空")
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            text = ""
    if not text:
        raise ValueError("文件编码必须为 UTF-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValueError("上传文件没有可导入内容")
    return text


def count_words(text: str) -> int:
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    latin_words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", text)
    return len(chinese_chars) + len(latin_words)


def _clean_heading(line: str) -> str:
    return re.sub(r"^\s*#{1,6}\s*", "", line).strip()


_SENTENCE_PUNCT_RE = re.compile(r"[，。！？；、“”\"「」…,.!?;:：]")
_GENERIC_STEMS = {"pasted", "paste", "untitled", "novel", "new", "新建文本文档", "未命名"}


def _looks_like_title(line: str) -> bool:
    """标题应是短句，不含句读；正文首段（如“沈砚穿着…，…。”）不能当书名。"""
    return 0 < len(line) <= 30 and not _SENTENCE_PUNCT_RE.search(line)


def _guess_title(filename: str, lines: list[str]) -> str:
    for line in lines[:20]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            heading = _clean_heading(stripped)
            if heading and not CHAPTER_HEADING_RE.match(heading):
                return heading[:200]
            break
        if CHAPTER_HEADING_RE.match(stripped):
            # 正文从章节开始，没有单独的书名行。
            break
        if _looks_like_title(stripped):
            return stripped
        break
    stem = Path(filename).stem.strip()
    if stem and stem.lower() not in _GENERIC_STEMS:
        return stem[:200]
    return "未命名小说"


def _chapter_preview(content: str, limit: int = 280) -> str:
    compact = re.sub(r"\s+", " ", content).strip()
    return compact[:limit]


def parse_novel_import(filename: str, raw: bytes) -> ParsedNovelImport:
    validate_import_filename(filename)
    text = decode_import_bytes(raw)
    lines = text.split("\n")
    title = _guess_title(filename, lines)

    chapters: list[ParsedChapter] = []
    current_title: str | None = None
    current_lines: list[str] = []
    preface_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if current_title is None:
            return
        content = "\n".join(current_lines).strip()
        chapters.append(
            ParsedChapter(
                title=current_title,
                content=content,
                chapter_number=len(chapters) + 1,
                word_count=count_words(content),
                preview=_chapter_preview(content),
            )
        )
        current_title = None
        current_lines = []

    for line in lines:
        stripped = line.strip()
        if CHAPTER_HEADING_RE.match(stripped):
            flush()
            current_title = _clean_heading(stripped)
            current_lines = []
            continue
        if current_title is None:
            preface_lines.append(line)
        else:
            current_lines.append(line)
    flush()

    if not chapters:
        content = text.strip()
        chapters = [
            ParsedChapter(
                title="正文",
                content=content,
                chapter_number=1,
                word_count=count_words(content),
                preview=_chapter_preview(content),
            )
        ]

    description = _chapter_preview("\n".join(preface_lines).strip(), 160) or None
    total_word_count = sum(chapter.word_count for chapter in chapters)
    return ParsedNovelImport(
        title=title,
        description=description,
        word_count=total_word_count,
        chapters=chapters,
        metadata={
            "filename": filename,
            "parser": "heading",
            "chapter_count": len(chapters),
            "word_count": total_word_count,
        },
    )
