# 豆包语音 TTS V3 接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让现有 `volcano` TTS 配置使用豆包语音控制台的 AppID、Access Token 和 `seed-tts-2.0` 完成真实短文本合成。

**Architecture:** 新建独立供应商适配器，负责 V3 HTTP 请求、事件流解析、音色兼容映射和静态音频落盘；现有 `VolcanoService` 只在识别到 openspeech TTS 端点时委派给新适配器。模型与用户凭据继续使用现有 `LLMModel` / `LLMConfig`，Access Token 加密存储，AppID 与 Resource ID 保存在用户配置参数中，并仅在调用时合并到 TTS endpoint。

**Tech Stack:** Python 3、aiohttp、pytest、SQLAlchemy、SQLite。

## Global Constraints

- 不改变火山方舟文本、图像和视频调用。
- 不向 `backend/app/api/v1/endpoints/tts.py` 追加供应商协议逻辑。
- 不把 Access Token 或 Secret Key 写入源码、测试、计划或 Git diff。
- Secret Key 不参与 V3 Bearer/Access Token 合成，本次不落库。
- 默认资源固定为 `seed-tts-2.0`，验证音色固定为 `zh_female_vv_uranus_bigtts`。
- 真实验证只合成一段短文本，控制调用成本。

---

### Task 1: 锁定 V3 请求与响应契约

**Files:**
- Create: `backend/tests/test_volcano_speech_tts.py`
- Create: `backend/app/services/volcano_speech_tts.py`

**Interfaces:**
- Produces: `is_volcano_speech_tts_endpoint(base_url: str | None) -> bool`
- Produces: `parse_volcano_speech_endpoint(base_url: str) -> VolcanoSpeechEndpoint`
- Produces: `parse_volcano_speech_events(payload: str) -> tuple[list[dict], bytes]`

- [x] **Step 1: Write failing contract tests**

```python
def test_endpoint_parses_app_and_resource_without_token(): ...
def test_concatenated_events_decode_mp3_chunks(): ...
def test_legacy_voice_alias_maps_to_seed_tts_voice(): ...
```

- [x] **Step 2: Run red test**

Run: `cd backend && python3 -m pytest tests/test_volcano_speech_tts.py -q`

Expected: FAIL because `app.services.volcano_speech_tts` does not exist.

- [x] **Step 3: Implement the minimum adapter contract**

Implement an immutable endpoint value object, URL parsing, legacy voice alias mapping, concatenated JSON parsing, V3 request construction, provider-code validation and MP3 persistence under `backend/static/<output_dir>`.

- [x] **Step 4: Run green test**

Run: `cd backend && python3 -m pytest tests/test_volcano_speech_tts.py -q`

Expected: all tests pass.

### Task 2: Connect the compatibility service

**Files:**
- Modify: `backend/app/services/volcano_service.py`
- Test: `backend/tests/test_volcano_speech_tts.py`

**Interfaces:**
- Consumes: `synthesize_volcano_speech_v3(...) -> dict`
- Preserves: `VolcanoService.text_to_speech(...) -> dict`

- [x] **Step 1: Add a failing delegation test**

Verify that an openspeech endpoint delegates to the V3 adapter while an Ark base URL preserves the existing `/audio/speech` path.

- [x] **Step 2: Run red test**

Run: `cd backend && python3 -m pytest tests/test_volcano_speech_tts.py -q`

Expected: the delegation assertion fails.

- [x] **Step 3: Add minimal delegation**

At the start of `VolcanoService.text_to_speech`, detect the endpoint and call the focused adapter with the existing method arguments.

- [x] **Step 4: Run targeted regressions**

Run: `cd backend && python3 -m pytest tests/test_volcano_speech_tts.py test_workflow_routes.py -q -k 'volcano and tts'`

Expected: all selected tests pass.

### Task 3: Persist model configuration and verify live generation

**Files:**
- Runtime data only: configured SQLite database `llm_providers`, `llm_models`, `llm_configs`
- Generated artifact only: `backend/static/audio/previews/*.mp3`

**Interfaces:**
- Consumes: existing encrypted `LLMConfig.set_api_key_encrypted(...)`.
- Produces: one active, tested TTS config for the existing local user.

- [x] **Step 1: Inspect active database and user ownership**

Run a read-only query for the actual database URL, user IDs, existing volcano TTS models and configs. Do not print decrypted keys.

- [x] **Step 2: Upsert the model and encrypted config**

Persist model ID `seed-tts-2.0`, model type `tts`, capability `text-to-speech`, the AppID and Resource ID as user-scoped extra parameters, and the encrypted Access Token. Preserve unrelated rows.

- [x] **Step 3: Call the repository service with the persisted values**

Run one short synthesis through `VolcanoService.text_to_speech`, then verify HTTP/provider success, non-empty MP3, local static path, and `ffprobe` audio metadata.

- [x] **Step 4: Run final verification**

Run targeted pytest, Python compile checks, repository code-health verification if available, and inspect `git diff --check` plus the exact changed files.
