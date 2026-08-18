# DeepSeek Official Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class, user-isolated DeepSeek API support for the current official V4 Flash and V4 Pro text models.

**Architecture:** Register DeepSeek as a built-in provider and reuse the existing OpenAI-compatible HTTP service through an explicit `deepseek` provider route. Keep provider identity, credentials, catalog entries, connection testing, and default-model bindings independent from OpenAI and Volcano Agent Plan.

**Tech Stack:** FastAPI, async SQLAlchemy, aiohttp, pytest, Next.js model-center UI.

## Global Constraints

- Do not change database schemas or existing provider behavior.
- Keep API keys user-scoped and never expose decrypted credentials to the frontend.
- Only publish `deepseek-v4-flash` and `deepseek-v4-pro`; do not seed retired aliases.
- Use `https://api.deepseek.com` with the existing OpenAI-compatible Chat Completions contract.

---

### Task 1: Provider execution contract

**Files:**
- Modify: `backend/tests/test_text_generation_adapter_compatibility.py`
- Modify: `backend/app/features/model_drivers/text_execution.py`
- Modify: `backend/app/features/model_drivers/adapters/legacy_text.py`

**Interfaces:**
- Consumes: `create_text_generation_service(api_key, provider_name, base_url)`.
- Produces: explicit `deepseek` provider routing to `OpenAIService` and a Chinese connection-success message.

- [ ] Add a failing compatibility case for provider `deepseek`, default base URL normalization, and OpenAI-compatible response extraction.
- [ ] Run the targeted test and confirm it fails because `deepseek` is unsupported.
- [ ] Add the minimal explicit DeepSeek branch and success label.
- [ ] Re-run the targeted test and confirm it passes.

### Task 2: Official provider and model catalog

**Files:**
- Modify: `backend/tests/test_llm_config_catalog.py`
- Create: `backend/app/core/deepseek_catalog.py`
- Modify: `backend/app/api/v1/endpoints/llm_config.py`
- Modify: `backend/init_llm_config.py`

**Interfaces:**
- Produces: `DEEPSEEK_PROVIDER` and `DEEPSEEK_MODEL_SEEDS` containing `deepseek-v4-flash` and `deepseek-v4-pro`.

- [ ] Add failing catalog tests for provider URL, current model IDs, capabilities, and absence of retired aliases.
- [ ] Run the catalog tests and confirm the current catalog does not satisfy them.
- [ ] Add a focused declarative catalog module and consume it from both initialization/catalog paths.
- [ ] Re-run catalog tests and confirm they pass.

### Task 3: Integration verification

**Files:**
- Test: `backend/tests/test_text_generation_adapter_compatibility.py`
- Test: model-center and catalog suites
- Verify: `frontend/`

- [ ] Run targeted backend provider, catalog, binding, and model-center tests.
- [ ] Run backend code-health checks for changed production files.
- [ ] Run frontend build to prove the shared model-center flow remains valid.
- [ ] Review the final diff for credential isolation, retired aliases, and unrelated changes.
