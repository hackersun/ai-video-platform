# Skill + Model + Deterministic Validation Pipeline

## Intent lock

Make entity extraction, script generation, storyboard generation, and shot prompt generation execute the selected Skill through the configured text model, while preserving a deterministic, validated fallback and auditable evidence.

## Scope

- Add one provider-neutral stage execution kernel.
- Integrate it into the four series-production text stages.
- Persist sanitized execution evidence beside the existing Skill evidence.
- Preserve current records, API shapes, idempotency, ownership, and deterministic behavior when no usable model is configured.
- Do not perform paid/live provider calls in automated verification.

## Contract

- Skill binding happens before model execution.
- A valid model result is used only after JSON parsing and stage validation.
- Provider, binding, parse, or validation failure selects the deterministic fallback.
- Evidence includes mode, model/binding identifiers, input/output hashes, validation status, and a sanitized fallback reason; never prompts, responses, or secrets.
- Existing callers that supply entity candidates keep working and are recorded as an explicit supplied-candidate mode.

## Batches and verification

1. Add execution-kernel failing tests, then implementation.
   - `pytest -q tests/test_series_stage_model_pipeline.py`
2. Integrate entity extraction and assert model-first/fallback behavior.
   - `pytest -q tests/test_entity_extraction_quality.py tests/test_series_run_skill_routing.py`
3. Integrate script, storyboard, and shot stages with persisted evidence.
   - `pytest -q tests/test_series_run_skill_routing.py tests/test_series_skill_execution.py`
4. Run backend regression slice and frontend type/build checks for evidence rendering.
   - `pytest -q tests/test_series_* tests/test_entity_extraction_*`
   - `npm run build`

## Acceptance criteria

- All four stages use the rendered Skill as the actual model input when a model succeeds.
- Invalid/missing model output never bypasses deterministic validation.
- All fallbacks are visible in stored sanitized evidence with a stable reason code.
- No existing production stage becomes dependent on model availability.
