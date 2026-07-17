"""Chapter-owned evidence contracts for deterministic entity extraction."""

from __future__ import annotations

import hashlib
from typing import Any


def attach_chapter_evidence_contracts(
    entities: list[dict[str, Any]], *, content: str, chapter_id: str,
) -> None:
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    for entity in entities:
        evidence = str(entity.get("evidence_span") or entity.get("evidence") or entity.get("name") or "")
        start = content.find(evidence)
        if start < 0 or not evidence:
            continue
        entity["attributes"] = {**(entity.get("attributes") or {}), "evidence_contract": {
            "status": "verified", "chapter_id": chapter_id,
            "source_span": [start, start + len(evidence)], "content_hash": content_hash,
            "source_excerpt": content[start:start + len(evidence)],
            "parser_version": "deterministic-extraction-v2",
        }}
