# 视频生成流程重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor video generation page with novel association, auto-generate character avatars, and add shot reference image generation.

**Architecture:** Three independent frontend/backend modifications. All image generation uses existing `/images/generate` endpoint (Volcano Seedream). Association data stored in `VideoJob.extra_data` JSON field.

**Tech Stack:** Next.js 14, FastAPI, SQLAlchemy, Volcano Engine, SQLite/PostgreSQL

---

## File Map

| Subsystem | Modify |
|-----------|--------|
| Video Page Refactor | `frontend/src/app/video-generation/page.tsx`, `backend/app/api/v1/endpoints/video.py` |
| Character Avatar | `frontend/src/app/characters/page.tsx`, `backend/app/api/v1/endpoints/characters.py` |
| Shot Reference Images | `backend/app/models/shot.py`, `backend/init_db.py`, `backend/app/api/v1/endpoints/shots.py`, `backend/app/api/v1/endpoints/storyboards.py`, `frontend/src/app/storyboards/page.tsx`, `frontend/src/app/shots/page.tsx`, `frontend/src/lib/api-client.ts` |

---

## Part 1: 视频生成页面重构 (小说关联)

### Task 1: 读取现有视频生成页面

**Files:**
- Read: `frontend/src/app/video-generation/page.tsx`
- Read: `frontend/src/lib/api-client.ts` (novels/scripts/storyboards sections)
- Read: `backend/app/api/v1/endpoints/video.py`

- [ ] **Step 1: Read video generation page**

Read all three files completely. Understand the current cascade logic (script→storyboard→shot) and how the API client fetches data.

- [ ] **Step 2: Read API client novels/scripts methods**

Check if `getNovels()` and `getScripts(novelId?)` methods exist. If not, note what needs to be added.

### Task 2: 后端 - 视频任务增加关联信息存储

**Files:**
- Modify: `backend/app/api/v1/endpoints/video.py`

- [ ] **Step 1: Read video.py completely**

Focus on the `POST /video/generate` endpoint and the job list endpoint.

- [ ] **Step 2: Check existing VideoGenerateRequest fields**

Read `video.py` and find the `VideoGenerateRequest` model definition. The model **already has** `script_id`, `storyboard_id`, `shot_id` fields. Only add `novel_id`:

```python
class VideoGenerateRequest(BaseModel):
    # ... existing fields: script_id, storyboard_id, shot_id are already here ...
    novel_id: Optional[str] = None  # ← Only add this field
```

- [ ] **Step 3: Update POST /video/generate endpoint to fetch titles**

⚠️ **Important:** Read the existing endpoint first. It may already store IDs in `extra_data` (lines ~218-222). You need to **replace or extend** that block to also fetch titles, since the frontend history list (Task 3 Step 6) reads `job.extra_data.novel_title` etc.

Replace the existing `extra_data` assignment with this code that fetches all titles:

```python
extra_data = request.extra_data or {}
if request.novel_id:
    # Fetch novel title
    novel = await db.get(Novel, request.novel_id)
    extra_data["novel_id"] = request.novel_id
    extra_data["novel_title"] = novel.title if novel else None
if request.script_id:
    script = await db.get(Script, request.script_id)
    extra_data["script_id"] = request.script_id
    extra_data["script_title"] = script.title if script else None
if request.storyboard_id:
    storyboard = await db.get(Storyboard, request.storyboard_id)
    extra_data["storyboard_id"] = request.storyboard_id
    extra_data["storyboard_title"] = storyboard.title if storyboard else None
if request.shot_id:
    shot = await db.get(Shot, request.shot_id)
    extra_data["shot_id"] = request.shot_id
    extra_data["shot_number"] = shot.shot_number if shot else None
```

- [ ] **Step 4: Update GET /video/jobs to return association info**

Update the `VideoJobResponse` model to include the association fields:

```python
class VideoJobResponse(BaseModel):
    # ... existing fields ...
    novel_id: Optional[str] = None       # ← Add
    novel_title: Optional[str] = None    # ← Add
    script_id: Optional[str] = None      # ← Add (if not already present)
    script_title: Optional[str] = None    # ← Add
    storyboard_id: Optional[str] = None   # ← Add
    storyboard_title: Optional[str] = None # ← Add
    shot_id: Optional[str] = None         # ← Add
    shot_number: Optional[int] = None     # ← Add
```

In the endpoint, extract these from `extra_data` when building the response.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/endpoints/video.py
git commit -m "feat(video): store novel/script/storyboard/shot association in video jobs"
```

### Task 3: 前端 - 视频生成页面增加小说选择器

**Files:**
- Modify: `frontend/src/app/video-generation/page.tsx`

- [ ] **Step 1: Add state for novel selection**

```typescript
const [selectedNovel, setSelectedNovel] = useState<string>("");
const [novels, setNovels] = useState<Novel[]>([]);
```

- [ ] **Step 2: Fetch novels on mount**

```typescript
useEffect(() => {
  const fetchData = async () => {
    const data = await apiClient.getNovels();
    setNovels(data);
  };
  fetchData();
}, []);
```

- [ ] **Step 3: Add NovelSelector component in the cascade UI**

Insert above the existing script selector. When novel changes, reset script/storyboard/shot selections:

```tsx
<div className="mb-4">
  <label className="block text-sm font-medium mb-1">选择小说</label>
  <select
    value={selectedNovel}
    onChange={(e) => {
      setSelectedNovel(e.target.value);
      setSelectedScript("");
      setSelectedStoryboard("");
      setSelectedShot("");
    }}
    className="w-full px-3 py-2 border rounded-lg"
  >
    <option value="">-- 选择小说 --</option>
    {novels.map((n) => (
      <option key={n.id} value={n.id}>{n.title}</option>
    ))}
  </select>
</div>
```

- [ ] **Step 4: Filter scripts by selected novel**

⚠️ **Context:** The page currently loads ALL scripts globally (no novel concept exists yet). The script selector uses the full list. You need to **client-side filter** the scripts dropdown by `novel_id` when a novel is selected:

```typescript
// In the JSX where scripts dropdown options are rendered:
const filteredScripts = selectedNovel
  ? scripts.filter((s) => s.novel_id === selectedNovel)
  : scripts;

// Render dropdown with filteredScripts instead of scripts
```

If the backend endpoint `GET /scripts` supports a `novel_id` query param, prefer that instead (more efficient). Otherwise client-side filter is fine for now.

- [ ] **Step 5: Pass association IDs to generateVideo call**

Update the `handleGenerate` function:

```typescript
const result = await apiClient.generateVideo({
  prompt,
  duration,
  resolution,
  image_url: selectedCharacterAvatar,
  model_id: selectedModel?.id,
  novel_id: selectedNovel || undefined,
  script_id: selectedScript || undefined,
  storyboard_id: selectedStoryboard || undefined,
  shot_id: selectedShot || undefined,
});
```

- [ ] **Step 6: Update history list to show association info**

In the history card/row, read from `job.extra_data` and display:

```tsx
{job.extra_data?.novel_title && (
  <span className="text-xs text-muted-foreground">
    {job.extra_data.novel_title}
    {job.extra_data.script_title && ` / ${job.extra_data.script_title}`}
    {job.extra_data.shot_number && ` / 镜头${job.extra_data.shot_number}`}
  </span>
)}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/video-generation/page.tsx
git commit -m "feat(frontend): add novel selector and association display to video generation page"
```

---

## Part 2: 角色形象自动生成

### Task 4: 读取现有角色页面

**Files:**
- Read: `frontend/src/app/characters/page.tsx`
- Read: `backend/app/api/v1/endpoints/characters.py`
- Read: `backend/app/api/v1/endpoints/images.py`

- [ ] **Step 1: Read all three files**

Focus on the create character flow, the extract flow, and how image generation is currently called.

### Task 5: 后端 - extract增加自动生成参数

**Files:**
- Modify: `backend/app/api/v1/endpoints/characters.py`

- [ ] **Step 1: Read characters.py**

Focus on the `extract_characters` endpoint and the image generation service.

- [ ] **Step 2: Add auto_generate_avatar parameter to existing CharacterExtractRequest**

⚠️ **Important:** Do NOT create a new class. Find the existing `CharacterExtractRequest` class definition in `characters.py` (around line 85) and **add one field** to it:

```python
class CharacterExtractRequest(BaseModel):
    # ... keep all existing fields ...
    auto_generate_avatar: bool = True  # ← Add this field to existing class
```

- [ ] **Step 3: After creating each character, auto-generate avatar if enabled**

Find where extracted characters are created. After the loop that creates characters, if `auto_generate_avatar` is True, call the image generation service for each character.

Build avatar prompt from character fields:
```python
def build_avatar_prompt(char: Character) -> str:
    """Construct an image generation prompt from character data."""
    parts = []
    if char.name:
        parts.append(f"character: {char.name}")
    if char.appearance:
        parts.append(f"appearance: {char.appearance}")
    if char.personality:
        parts.append(f"personality: {char.personality}")
    parts.append("anime style, high quality, portrait")
    return ", ".join(parts)
```

Then for each character:
```python
if request.auto_generate_avatar:
    from app.services.volcano_service import VolcanoService
    volcano = VolcanoService()
    for char in created_characters:
        try:
            prompt = build_avatar_prompt(char)
            result = await volcano.generate_image(prompt=prompt)
            image_url = result.get("image_url")
            if image_url:
                char.avatar = image_url
                db.add(char)
                await db.commit()
        except Exception:
            # Don't fail the whole extract if one avatar fails
            pass
```

Note: Image generation is synchronous here (waiting for result). This is acceptable for extract flows with few characters. If characters > 5, consider making it async (background task).

For simplicity, do this synchronously by calling the image generation API and waiting for completion:

```python
if request.auto_generate_avatar:
    from app.services.volcano_service import VolcanoService
    volcano = VolcanoService()
    for char in created_characters:
        try:
            # Build avatar generation prompt from character appearance
            prompt = build_avatar_prompt(char)
            result = await volcano.generate_image(prompt=prompt)
            char.avatar = result.get("image_url")
            db.add(char)
            await db.commit()
        except Exception as e:
            # Don't fail the whole extract if one avatar fails
            pass
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/endpoints/characters.py
git commit -m "feat(backend): auto-generate character avatars on extract"
```

### Task 6: 前端 - 创建角色时自动生成 + UI增强

**Files:**
- Modify: `frontend/src/app/characters/page.tsx`

- [ ] **Step 1: Read characters page completely**

Focus on the create form, the create modal, and the extract modal.

- [ ] **Step 2: Add auto-generate checkbox to create form**

In the character create/edit form (inside the modal), add before the submit button:

```tsx
<div className="flex items-center gap-2 mb-4">
  <input
    type="checkbox"
    id="autoGenerateAvatar"
    checked={autoGenerateAvatar}
    onChange={(e) => setAutoGenerateAvatar(e.target.checked)}
    className="w-4 h-4"
  />
  <label htmlFor="autoGenerateAvatar" className="text-sm">
    创建后自动生成形象图
  </label>
</div>
```

- [ ] **Step 3: Add state for auto-generate**

```typescript
const [autoGenerateAvatar, setAutoGenerateAvatar] = useState(true);
```

- [ ] **Step 4: Update handleCreateCharacter**

⚠️ **Important UX:** Close the modal immediately after creation, so the generating state is visible on the character card in the list (avatar area shows spinner). Don't keep the modal open — the user can see progress from the list view.

```typescript
const handleCreate = async () => {
  const char = await apiClient.createCharacter(formData);
  setCharacters([...characters, char]);
  setShowCreateModal(false);  // Close modal immediately

  if (autoGenerateAvatar) {
    setGeneratingAvatarId(char.id);  // Spinner shows on card in list
    try {
      const result = await apiClient.generateCharacterAvatar(char.id, {
        prompt: buildAvatarPrompt(char),
      });
      pollAvatarStatus(char.id, result.task_id);
    } catch (err) {
      console.error("Avatar generation failed:", err);
      setGeneratingAvatarId(null);
    }
  }
};

const pollAvatarStatus = async (charId: string, taskId: string) => {
  const maxAttempts = 30;
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const status = await apiClient.getImageJobStatus(taskId);
    if (status.status === "succeeded") {
      const avatarUrl = status.image_url;
      await apiClient.updateCharacter(charId, { avatar: avatarUrl });
      setCharacters(prev => prev.map(c => c.id === charId ? { ...c, avatar: avatarUrl } : c));
      setGeneratingAvatarId(null);
      return;
    }
    if (status.status === "failed") {
      setGeneratingAvatarId(null);
      return;
    }
  }
  setGeneratingAvatarId(null);
};
```

- [ ] **Step 5: Show generating state on character card**

In the character list item, when `generatingAvatarId === char.id`, show a spinner/badge on the avatar area.

- [ ] **Step 6: Enhance extract modal to show avatar generation status**

After extract completes, show a list of extracted characters. For each, show avatar status (pending/generating/succeeded). Poll all avatar generation statuses.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/characters/page.tsx
git commit -m "feat(frontend): auto-generate character avatars on create and extract"
```

### Task 7: API Client - 确保相关方法存在

**Files:**
- Modify: `frontend/src/lib/api-client.ts`

- [ ] **Step 1: Check existing methods**

Ensure these methods exist (or add them):
- `generateCharacterAvatar(characterId, params)` → calls `POST /images/generate` with character context
- `getImageJobStatus(taskId)` → calls `GET /images/status/{taskId}`

If they don't exist, add them:

```typescript
async generateCharacterAvatar(characterId: string, params: { prompt: string }) {
  const res = await this.fetchWithAuth("/images/generate", {
    method: "POST",
    body: JSON.stringify({
      prompt: params.prompt,
      model: "doubao-seedream-3-0",
      extra_data: { character_id: characterId }
    }),
  });
  return res;
}

async getImageJobStatus(taskId: string) {
  const res = await this.fetchWithAuth(`/images/status/${taskId}`);
  return res;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api-client.ts
git commit -m "feat(api): add image generation methods for character avatars"
```

---

## Part 3: 镜头参考图生成

### Task 8: 数据库 - Shot模型增加字段

**Files:**
- Modify: `backend/app/models/shot.py`
- Modify: `backend/init_db.py`

- [ ] **Step 1: Add fields to Shot model**

Add three new columns to the `Shot` class:

```python
# 参考图
image_url = Column(Text, nullable=True)       # 参考图 URL
image_status = Column(String(20), default="pending")  # pending/generating/succeeded/failed
image_asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
```

- [ ] **Step 2: Read init_db.py to understand migration approach**

If `init_db.py` uses `Base.metadata.create_all()` (SQLite dev), the new columns will be auto-created on next startup. For existing databases, we need an ALTER TABLE. Add a migration section:

```python
# Migration: Add shot image fields
def migrate_add_shot_image_fields():
    """Add image_url, image_status, image_asset_id to shots table."""
    from sqlalchemy import text
    conn = engine.connect()

    # Check if column exists first
    try:
        conn.execute(text("SELECT image_url FROM shots LIMIT 1"))
    except Exception:
        conn.execute(text("ALTER TABLE shots ADD COLUMN image_url TEXT"))
        conn.execute(text("ALTER TABLE shots ADD COLUMN image_status VARCHAR(20) DEFAULT 'pending'"))
        conn.execute(text("ALTER TABLE shots ADD COLUMN image_asset_id VARCHAR(36)"))
        conn.commit()
    conn.close()
```

Call this migration function after table creation.

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/shot.py backend/init_db.py
git commit -m "feat(db): add image_url, image_status, image_asset_id to Shot model"
```

### Task 9: 后端 - Shots端点增加生成参考图接口

**Files:**
- Modify: `backend/app/api/v1/endpoints/shots.py`
- Read: `backend/app/api/v1/endpoints/images.py` (for image generation service reference)

- [ ] **Step 1: Read shots.py completely**

Focus on the existing endpoints and how the image generation service is used.

- [ ] **Step 2: Create shared image poll service module**

⚠️ **Critical fix:** Background tasks CANNOT share the request's `db` session — it gets closed when the HTTP response is sent, causing `DetachedInstanceError`. You must create a separate session inside the background task.

Create a new file:

**Create:** `backend/app/services/image_poll_service.py`

```python
"""Background image generation polling service."""
import asyncio
from app.core.database import async_session_maker
from app.models.shot import Shot
from app.models.asset import Asset


async def poll_and_update_shot_image(shot_id: str, task_id: str, user_id: str):
    """Background polling: creates its own DB session. Call with asyncio.create_task()."""
    import uuid
    from app.services.volcano_service import VolcanoService

    volcano = VolcanoService()
    max_attempts = 60  # 2 min max

    for _ in range(max_attempts):
        await asyncio.sleep(2)
        try:
            status_result = await volcano.get_image_status(task_id)
            status = status_result.get("status")

            if status == "succeeded":
                image_url = status_result.get("image_url")

                # Create independent session for background work
                async with async_session_maker() as session:
                    # Update shot
                    shot = await session.get(Shot, shot_id)
                    if shot:
                        shot.image_url = image_url
                        shot.image_status = "succeeded"

                        # Create asset
                        asset = Asset(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            category="scene",
                            name=f"镜头{shot.shot_number}参考图",
                            asset_type="image",
                            url=image_url,
                            extra_data={"shot_id": shot_id},
                        )
                        session.add(asset)
                        shot.image_asset_id = asset.id
                        await session.commit()
                return

            elif status == "failed":
                async with async_session_maker() as session:
                    shot = await session.get(Shot, shot_id)
                    if shot:
                        shot.image_status = "failed"
                        await session.commit()
                return

        except Exception:
            continue
```

- [ ] **Step 3: Add generate-image endpoint to shots.py**

Use the shared service:

```python
@router.post("/shots/{shot_id}/generate-image")
async def generate_shot_image(
    shot_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """为指定镜头生成参考图"""
    shot = await db.get(Shot, shot_id)
    if not shot or shot.user_id != user_id:
        raise HTTPException(status_code=404, detail="镜头不存在")

    # Build prompt (include lighting and color_grading for better results)
    prompt_parts = []
    if shot.visual_description:
        prompt_parts.append(shot.visual_description)
    if shot.prompt:
        prompt_parts.append(shot.prompt)
    if shot.camera_angle:
        prompt_parts.append(f"camera: {shot.camera_angle}")
    if shot.emotion:
        prompt_parts.append(f"emotion: {shot.emotion}")
    if shot.lighting:
        prompt_parts.append(f"lighting: {shot.lighting}")
    prompt = " ".join(prompt_parts) if prompt_parts else shot.visual_description or shot.prompt or "cinematic scene"

    # Call image generation service
    from app.services.volcano_service import VolcanoService
    volcano = VolcanoService()
    result = await volcano.generate_image(prompt=prompt)
    task_id = result.get("task_id")

    # Update shot status
    shot.image_status = "generating"
    await db.commit()

    # Start background poll with user_id — creates own DB session
    asyncio.create_task(poll_and_update_shot_image(shot_id, task_id, user_id))

    return {"shot_id": shot_id, "task_id": task_id, "status": "generating"}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/image_poll_service.py backend/app/api/v1/endpoints/shots.py
git commit -m "feat(shots): add generate-image endpoint with background polling"
```

### Task 10: 后端 - Storyboards端点增加批量生成接口

**Files:**
- Modify: `backend/app/api/v1/endpoints/storyboards.py`

- [ ] **Step 1: Read storyboards.py**

- [ ] **Step 2: Add batch generate images endpoint to storyboards.py**

⚠️ **Same DB session issue as Task 9.** Use the shared `poll_and_update_shot_image` from `image_poll_service.py` (do NOT pass the request's `db` session — the shared function creates its own).

```python
@router.post("/storyboards/{storyboard_id}/shots/generate-images")
async def generate_storyboard_shot_images(
    storyboard_id: str,
    shot_ids: List[str] = Body(...),  # List of shot IDs to generate
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """批量为指定镜头生成参考图"""
    storyboard = await db.get(Storyboard, storyboard_id)
    if not storyboard or storyboard.user_id != user_id:
        raise HTTPException(status_code=404, detail="分镜不存在")

    results = []
    for shot_id in shot_ids:
        shot = await db.get(Shot, shot_id)
        if not shot or shot.storyboard_id != storyboard_id:
            results.append({"shot_id": shot_id, "status": "skipped", "reason": "not found or not in this storyboard"})
            continue

        # Build prompt (include lighting for better results)
        prompt_parts = []
        if shot.visual_description:
            prompt_parts.append(shot.visual_description)
        if shot.prompt:
            prompt_parts.append(shot.prompt)
        if shot.lighting:
            prompt_parts.append(f"lighting: {shot.lighting}")
        prompt = " ".join(prompt_parts) if prompt_parts else shot.visual_description or shot.prompt or "cinematic scene"

        try:
            from app.services.volcano_service import VolcanoService
            volcano = VolcanoService()
            result = await volcano.generate_image(prompt=prompt)
            task_id = result.get("task_id")

            shot.image_status = "generating"
            await db.commit()

            # Use shared background poller — it creates its own DB session
            from app.services.image_poll_service import poll_and_update_shot_image
            asyncio.create_task(poll_and_update_shot_image(shot_id, task_id, user_id))

            results.append({"shot_id": shot_id, "task_id": task_id, "status": "generating"})
        except Exception as e:
            results.append({"shot_id": shot_id, "status": "error", "reason": str(e)})

    return {"storyboard_id": storyboard_id, "results": results}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/endpoints/storyboards.py
git commit -m "feat(storyboards): add batch generate shot images endpoint"
```

### Task 11: 前端 - Storyboards页面增加单镜头生成

**Files:**
- Modify: `frontend/src/app/storyboards/page.tsx`

- [ ] **Step 1: Read storyboards page completely**

Focus on the shot detail editor section.

- [ ] **Step 2: Add image generation state and handler**

```typescript
const [generatingImage, setGeneratingImage] = useState(false);
const [shotImageUrl, setShotImageUrl] = useState<string | null>(null);

const handleGenerateShotImage = async (shotId: string) => {
  setGeneratingImage(true);
  try {
    const result = await apiClient.generateShotImage(shotId);
    // Poll for status
    pollShotImage(shotId, result.task_id);
  } catch (err) {
    console.error("Image generation failed:", err);
    setGeneratingImage(false);
  }
};

const pollShotImage = async (shotId: string, taskId: string) => {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const status = await apiClient.getShotImageStatus(shotId);
    if (status.image_status === "succeeded") {
      setShotImageUrl(status.image_url);
      // Refresh shot data
      const shots = await apiClient.getShotsByStoryboard(selectedStoryboard);
      setShots(shots);
      setGeneratingImage(false);
      return;
    }
    if (status.image_status === "failed") {
      setGeneratingImage(false);
      return;
    }
  }
  setGeneratingImage(false);
};
```

- [ ] **Step 3: Add Generate Reference Image button and preview**

In the shot detail editor, below the visual description textarea:

```tsx
{/* Visual Description */}
<div className="mb-4">
  <label className="block text-sm font-medium mb-1">视觉描述</label>
  <textarea
    value={editingShot.visual_description || ""}
    onChange={(e) => setEditingShot({ ...editingShot, visual_description: e.target.value })}
    className="w-full px-3 py-2 border rounded-lg"
    rows={3}
  />
</div>

{/* Reference Image Section */}
<div className="mb-4">
  <div className="flex items-center justify-between mb-2">
    <label className="text-sm font-medium">参考图</label>
    <button
      onClick={() => handleGenerateShotImage(editingShot.id)}
      disabled={generatingImage || !editingShot.visual_description}
      className="px-3 py-1 text-sm bg-primary text-white rounded-lg disabled:opacity-50"
    >
      {generatingImage ? "生成中..." : "🎨 生成参考图"}
    </button>
  </div>
  {editingShot.image_status === "generating" && (
    <div className="text-sm text-muted-foreground">生成中...</div>
  )}
  {(editingShot.image_url || shotImageUrl) && (
    <img
      src={shotImageUrl || editingShot.image_url}
      alt="Shot reference"
      className="w-full max-h-48 object-cover rounded-lg border"
    />
  )}
</div>
```

- [ ] **Step 4: Add to API client**

In `frontend/src/lib/api-client.ts`, add:

```typescript
async generateShotImage(shotId: string) {
  const res = await this.fetchWithAuth(`/shots/${shotId}/generate-image`, { method: "POST" });
  return res;
}

async getShotImageStatus(shotId: string) {
  // This endpoint should return current shot data including image_status
  const res = await this.fetchWithAuth(`/shots/${shotId}`);
  return res;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/storyboards/page.tsx frontend/src/lib/api-client.ts
git commit -m "feat(frontend): add shot reference image generation to storyboard editor"
```

### Task 12: 前端 - Shots页面增加批量生成

**Files:**
- Modify: `frontend/src/app/shots/page.tsx`

- [ ] **Step 1: Read shots page**

Focus on the grid view and batch operations.

- [ ] **Step 2: Add batch generation state**

```typescript
const [selectedShotIds, setSelectedShotIds] = useState<string[]>([]);
const [batchGenerating, setBatchGenerating] = useState(false);
const [batchProgress, setBatchProgress] = useState<Record<string, string>>({});
```

- [ ] **Step 3: Add batch generate button**

In the header area (near existing stats cards), add:

```tsx
{selectedShotIds.length > 0 && (
  <div className="flex items-center gap-2">
    <span className="text-sm">{selectedShotIds.length} 个镜头已选</span>
    <button
      onClick={handleBatchGenerateImages}
      disabled={batchGenerating}
      className="px-4 py-2 bg-purple-600 text-white rounded-lg disabled:opacity-50"
    >
      {batchGenerating ? "生成中..." : `🎨 批量生成参考图 (${selectedShotIds.length})`}
    </button>
  </div>
)}
```

- [ ] **Step 4: Add batch generate handler**

```typescript
const handleBatchGenerateImages = async () => {
  setBatchGenerating(true);
  const progress: Record<string, string> = {};
  selectedShotIds.forEach(id => { progress[id] = "pending"; });
  setBatchProgress(progress);

  try {
    const results = await apiClient.generateShotsImages(selectedStoryboard!, selectedShotIds);
    // results.results is array of {shot_id, status, task_id}
    for (const r of results.results) {
      if (r.status === "generating") {
        setBatchProgress(prev => ({ ...prev, [r.shot_id]: "generating" }));
        pollBatchShotImage(r.shot_id, r.task_id);
      }
    }
  } catch (err) {
    console.error("Batch generation failed:", err);
    setBatchGenerating(false);
  }
};

const pollBatchShotImage = async (shotId: string, taskId: string) => {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const shot = await apiClient.getShot(shotId);
    if (shot.image_status === "succeeded") {
      setBatchProgress(prev => ({ ...prev, [shotId]: "succeeded" }));
      // Refresh shots list
      const updated = await apiClient.getShotsByStoryboard(selectedStoryboard!);
      setShots(updated);
      // Check if all done
      const values = Object.values({ ...batchProgress, [shotId]: "succeeded" });
      if (!values.includes("generating") && !values.includes("pending")) {
        setBatchGenerating(false);
      }
      return;
    }
    if (shot.image_status === "failed") {
      setBatchProgress(prev => ({ ...prev, [shotId]: "failed" }));
      setBatchGenerating(false);
      return;
    }
  }
};
```

- [ ] **Step 5: Show status badge on shot cards**

In each shot card in the grid, show image status badge:

```tsx
{shot.image_status === "generating" && (
  <span className="absolute top-2 right-2 px-2 py-1 bg-yellow-500 text-white text-xs rounded">
    生成中...
  </span>
)}
{shot.image_status === "succeeded" && shot.image_url && (
  <img
    src={shot.image_url}
    className="absolute inset-0 w-full h-full object-cover opacity-30 rounded-lg"
    alt=""
  />
)}
```

- [ ] **Step 6: Add to API client**

```typescript
async generateShotsImages(storyboardId: string, shotIds: string[]) {
  const res = await this.fetchWithAuth(`/storyboards/${storyboardId}/shots/generate-images`, {
    method: "POST",
    body: JSON.stringify(shotIds),
  });
  return res;
}

async getShot(shotId: string) {
  const res = await this.fetchWithAuth(`/shots/${shotId}`);
  return res;
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/shots/page.tsx frontend/src/lib/api-client.ts
git commit -m "feat(frontend): add batch shot image generation to shots page"
```

---

## Implementation Order

1. **Task 8** (Shot model fields) first — all downstream changes depend on it
2. **Task 4** (Read existing code) — parallel with Task 8
3. **Task 1** (Read existing code) — parallel with Task 8
4. **Task 2** (Video backend) → Task 3 (Video frontend)
5. **Task 5** (Characters backend) → Task 6 (Characters frontend) → Task 7 (API client chars)
6. **Task 9** (Shots image endpoint) → Task 10 (Storyboards batch endpoint) → Task 11 (Storyboards UI) → Task 12 (Shots batch UI)

## Testing

- Manual testing via browser: Each task produces a working UI component
- Backend: `cd backend && python -m pytest test_api.py -v -k "video or character or shot"`
- E2E tests: `cd e2e && npx playwright test`
