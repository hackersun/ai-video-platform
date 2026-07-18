"""Public Prompt Profile facade for legacy and model-aware callers."""

from app.features.prompt_profiles.domain import (
    PromptRouteQuery,
    PromptSelection,
    prompt_entry_evidence,
    render_prompt,
)
from app.features.prompt_profiles.evaluation import (
    build_evaluation_evidence,
    record_prompt_evaluation,
)
from app.features.prompt_profiles.repository import (
    effective_legacy_prompt_skill_payloads,
    latest_versions_for_skills,
    legacy_prompt_skill_payload,
    render_legacy_prompt_skill,
    rendered_legacy_prompt_skill_entry,
)
from app.features.prompt_profiles.routing import (
    resolve_prompt_entries,
    routing_specificity,
    safe_routing_metadata,
    select_prompt_profile,
    select_prompt_profile_version,
)
from app.features.prompt_profiles.versioning import (
    apply_version_to_legacy_skill,
    canonical_prompt_values_checksum,
    canonical_prompt_version_checksum,
    disable_legacy_prompt_profile,
    edit_legacy_prompt_profile,
    edit_prompt_profile,
    ensure_legacy_prompt_profile,
    legacy_prompt_version_values,
    publish_legacy_prompt_profile,
    publish_prompt_profile_version,
    retire_legacy_prompt_profile,
)

__all__ = [
    "PromptRouteQuery", "PromptSelection", "apply_version_to_legacy_skill",
    "build_evaluation_evidence",
    "canonical_prompt_values_checksum", "canonical_prompt_version_checksum",
    "disable_legacy_prompt_profile",
    "edit_legacy_prompt_profile", "edit_prompt_profile",
    "effective_legacy_prompt_skill_payloads", "ensure_legacy_prompt_profile",
    "latest_versions_for_skills", "legacy_prompt_skill_payload",
    "legacy_prompt_version_values",
    "prompt_entry_evidence", "publish_legacy_prompt_profile",
    "publish_prompt_profile_version",
    "record_prompt_evaluation",
    "retire_legacy_prompt_profile",
    "render_legacy_prompt_skill", "rendered_legacy_prompt_skill_entry",
    "render_prompt", "resolve_prompt_entries", "routing_specificity",
    "select_prompt_profile",
    "safe_routing_metadata", "select_prompt_profile_version",
]
