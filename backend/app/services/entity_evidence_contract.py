"""Chapter-owned evidence contracts for deterministic entity extraction."""

from __future__ import annotations

import hashlib
from typing import Any


def build_chapter_evidence_contract(
    *, evidence: str, content: str, chapter_id: str,
) -> dict[str, Any] | None:
    evidence = str(evidence or "")
    start = content.find(evidence)
    if start < 0 or not evidence:
        return None
    return {
        "status": "verified", "chapter_id": chapter_id,
        "source_span": [start, start + len(evidence)],
        "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "source_excerpt": content[start:start + len(evidence)],
        "parser_version": "deterministic-extraction-v2",
    }


def attach_chapter_evidence_contracts(
    entities: list[dict[str, Any]], *, content: str, chapter_id: str,
) -> None:
    for entity in entities:
        evidence = str(entity.get("evidence_span") or entity.get("evidence") or entity.get("name") or "")
        contract = build_chapter_evidence_contract(
            evidence=evidence, content=content, chapter_id=chapter_id,
        )
        if contract is None:
            continue
        entity["attributes"] = {**(entity.get("attributes") or {}), "evidence_contract": contract}
