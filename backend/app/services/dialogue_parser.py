"""Shared parsing rules for character-labelled dialogue."""

import re
from typing import Dict, List, Optional


def extract_character_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    patterns = [
        r"([^\s：:]+)说[：:]",
        r"([^\s：:]+)道[：:]",
        r"([^\s：:]+)回答[：:]",
        r"([^\s：:]+)[：:]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def parse_dialogue(dialogue: str) -> List[Dict[str, str]]:
    if not dialogue:
        return []
    segments = []
    for raw_line in dialogue.strip().split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([^:：]+?)[:：]\s*(.+)$", line)
        segments.append({
            "character": match.group(1).strip() if match else "",
            "text": match.group(2).strip() if match else line,
        })
    return segments
