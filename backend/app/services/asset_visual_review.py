"""Deterministic prompt-coverage review for generated asset contracts."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.core.time_utils import utc_now


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _expected_values(contract: Dict[str, Any]) -> List[Dict[str, str]]:
    values: List[Dict[str, str]] = []

    def add(field: str, expected: Any, category: str) -> None:
        for item in _as_list(expected):
            values.append({"field": field, "expected": item, "category": category})

    axes = _as_dict(contract.get("continuity_axes"))
    for field in ("era", "weather", "lighting_direction", "color_palette"):
        add(field, axes.get(field), "continuity_axes")

    layout = _as_dict(contract.get("spatial_layout"))
    for item in layout.get("fixed_elements") or []:
        add("spatial_layout", item, "spatial_layout")
    for item in layout.get("action_zones") or []:
        add("spatial_layout", item, "spatial_layout")

    identity = _as_dict(contract.get("identity"))
    for field in ("age", "appearance", "wardrobe"):
        add(field, identity.get(field), "identity")
    for item in identity.get("signature_items") or []:
        add("signature_items", item, "identity")

    prop_dna = _as_dict(contract.get("prop_dna"))
    for field in ("material", "scale"):
        add(field, prop_dna.get(field), "prop_dna")
    for item in prop_dna.get("fixed_marks") or []:
        add("fixed_marks", item, "prop_dna")

    add("appearance", contract.get("appearance"), "lightweight_contract")
    add("gender_age_hint", contract.get("gender_age_hint"), "lightweight_contract")
    add("entity_name", contract.get("entity_name") or contract.get("name"), "lightweight_contract")

    seen = set()
    deduped = []
    for value in values:
        marker = (value["field"], value["expected"])
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(value)
    return deduped


def review_asset_against_contract(
    contract: Dict[str, Any],
    view_key: str,
    prompt: str,
    provider_result_metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    """Review whether the generated prompt covered exact visual contract values."""
    contract = _as_dict(contract)
    prompt_text = str(prompt or "")
    issues = []
    passed_fields = []

    for item in _expected_values(contract):
        expected = item["expected"]
        if expected in prompt_text:
            passed_fields.append(item)
            continue
        issues.append(
            {
                "field": item["field"],
                "category": item["category"],
                "expected": expected,
                "message": f"提示词缺少契约值：{expected}",
            }
        )

    total = len(passed_fields) + len(issues)
    score = 100 if total == 0 else round((len(passed_fields) / total) * 100)
    status = "passed" if not issues else "needs_retry"
    return {
        "mode": "contract_prompt_coverage",
        "status": status,
        "score": score,
        "contract_id": contract.get("contract_id") or contract.get("id"),
        "view_key": view_key,
        "checked_at": utc_now().isoformat(),
        "provider_result_metadata": provider_result_metadata or {},
        "covered_fields": passed_fields,
        "issues": issues,
        "notes": "确定性提示词覆盖检查；未进行图像像素或多模态相似度判断。",
    }


def _issue_values(issues: Iterable[Dict[str, Any]], field: str) -> List[str]:
    values = []
    for issue in issues:
        if issue.get("field") == field and issue.get("expected"):
            values.append(str(issue["expected"]))
    return list(dict.fromkeys(values))


def retry_prompt_advice(issues: Iterable[Dict[str, Any]], contract: Dict[str, Any]) -> str:
    """Build concise Chinese retry advice from prompt-coverage issues."""
    issue_list = [_as_dict(issue) for issue in issues]
    if not issue_list:
        return ""

    lines = ["重试提示词建议："]
    lighting_values = _issue_values(issue_list, "lighting_direction")
    if lighting_values:
        lines.append(f"必须保持光源方向：{'、'.join(lighting_values)}。")

    layout_values = _issue_values(issue_list, "spatial_layout")
    if layout_values:
        lines.append(f"必须保留空间固定元素：{'、'.join(layout_values)}。")

    for field in (
        "color_palette",
        "era",
        "weather",
        "age",
        "appearance",
        "wardrobe",
        "signature_items",
        "material",
        "scale",
        "fixed_marks",
        "gender_age_hint",
        "entity_name",
    ):
        values = _issue_values(issue_list, field)
        if values:
            lines.append(f"必须补充{field}：{'、'.join(values)}。")

    return "\n".join(lines)
