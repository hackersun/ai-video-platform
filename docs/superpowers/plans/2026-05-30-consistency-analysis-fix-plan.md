# 视频生成一致性保障 - 深入分析与修复计划

> **日期**: 2026-05-30
> **目标**: 确保小说→章节→剧本→分镜→镜头→视频全链路的一致性

---

## 一、问题分析

### 1.1 当前一致性机制

```
Novel → Chapter → Script → Storyboard → Shot → Video
    ↓           ↓           ↓          ↓        ↓
StoryBible ← (引用)      Character ← (资产) → Asset(锁定版本)
    ↓
StateMachine ← (状态追踪)
```

**已有机制**：
- PromptComposer: 统一prompt注入项目风格、Story Bible规则
- ConsistencyContext: 构建镜头实体上下文
- StoryStateMachine: 按章节追踪实体状态变化

### 1.2 一致性缺口矩阵

| 生成环节 | 角色一致性 | 场景一致性 | 道具一致性 | 风格一致性 | 声音一致性 |
|---------|-----------|-----------|-----------|-----------|-----------|
| 剧本生成 | ❌ 未注入 | ❌ 未注入 | ❌ 未注入 | ⚠️ 部分 | N/A |
| 分镜生成 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | N/A |
| 参考图 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | N/A |
| 镜头生成 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | N/A |
| 视频生成 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 | ⚠️ 可选 |
| TTS配音 | N/A | N/A | N/A | N/A | ❌ 未关联 |

---

## 二、根本原因

### 2.1 Shot.entity_refs未强制填充

```python
# 当前问题：shot.extra_data.entity_refs 可能为空
shot.extra_data = {
    "entity_refs": {
        "characters": [],  # 可能为空
        "scenes": [],
        "props": [],
        "events": []
    }
}
```

**影响**：视频生成时无法获取角色/场景/道具上下文

### 2.2 资产版本未锁定注入

```python
# 当前问题：Asset.is_locked 未被强制使用
asset = {
    "id": "xxx",
    "is_locked": True,  # 已锁定但未注入prompt
    "version": 3
}
```

**影响**：不同视频生成可能使用不同版本的资产

### 2.3 TTS音色未与Story Bible关联

```python
# 当前问题：Character.voice 独立于 Story Bible
character = {
    "name": "张三",
    "voice": "音色A",  # 可能与Story Bible中的设定不一致
}
story_bible = {
    "character_rules": [{
        "name": "张三",
        "voice": "音色B"  # 与上方不一致
    }]
}
```

---

## 三、修复计划

### 阶段一：Shot实体绑定强制化

#### Task 1: 强制填充Shot.entity_refs

**文件**:
- Modify: `backend/app/api/v1/endpoints/storyboards.py`
- Modify: `backend/app/services/consistency_context.py`

**实现**:
```python
# 在生成分镜/镜头时自动填充entity_refs
async def auto_fill_shot_entity_refs(
    db: AsyncSession,
    shot: Shot,
    novel_id: str,
    chapter_id: Optional[str] = None
) -> Shot:
    """自动填充镜头的实体引用"""
    # 1. 加载或抽取实体
    entities = await load_or_extract_story_entities(...)

    # 2. 根据镜头内容匹配实体
    shot_text = f"{shot.prompt} {shot.dialogue} {shot.visual_description}"
    matched = match_entities_to_text(entities, shot_text)

    # 3. 更新shot.extra_data.entity_refs
    extra_data = shot.extra_data or {}
    extra_data["entity_refs"] = {
        "characters": [e.id for e in matched["characters"]],
        "scenes": [e.id for e in matched["scenes"]],
        "props": [e.id for e in matched["props"]],
        "events": [e.id for e in matched["events"]],
    }
    shot.extra_data = extra_data

    return shot
```

**验证**:
- 每个生成的Shot都有非空的entity_refs
- entity_refs中的ID指向真实存在的StoryEntity

---

#### Task 2: 在所有生成端点强制调用entity_refs填充

**文件**:
- Modify: `backend/app/api/v1/endpoints/storyboards.py`
- Modify: `backend/app/api/v1/endpoints/shots.py`
- Modify: `backend/app/api/v1/endpoints/video.py`

**实现**:
```python
# 在分镜生成后自动填充所有镜头的entity_refs
@router.post("/storyboards/{storyboard_id}/fill-entity-refs")
async def fill_storyboard_shot_entity_refs(
    storyboard_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id)
):
    """填充分镜下所有镜头的实体引用"""
    shots = await db.execute(
        select(Shot).where(Shot.storyboard_id == storyboard_id)
    )
    for shot in shots.scalars():
        await auto_fill_shot_entity_refs(db, shot, shot.novel_id)

    await db.commit()
    return {"status": "success", "count": len(shots.scalars().all())}
```

---

### 阶段二：资产版本锁定注入

#### Task 3: 创建Asset引用锁定机制

**文件**:
- Create: `backend/app/services/asset_lock_service.py`
- Modify: `backend/app/models/shot.py`

**实现**:
```python
class AssetLockService:
    """资产锁定服务"""

    async def lock_shot_assets(
        db: AsyncSession,
        shot: Shot,
        force: bool = False
    ) -> Dict[str, str]:
        """锁定镜头引用的所有资产版本"""
        locked_assets = {}

        entity_refs = shot.extra_data.get("entity_refs", {})
        for entity_type in ["characters", "scenes", "props"]:
            for entity_id in entity_refs.get(entity_type, []):
                # 获取该实体最新锁定的资产
                asset = await self.get_entity_locked_asset(
                    db, entity_type, entity_id
                )
                if asset:
                    locked_assets[f"{entity_type}_{entity_id}"] = asset.id

        # 保存到shot.extra_data.locked_assets
        shot.extra_data["locked_assets"] = locked_assets
        return locked_assets

    async def get_locked_asset_prompts(
        db: AsyncSession,
        shot: Shot
    ) -> List[str]:
        """获取锁定资产的prompt片段"""
        locked = shot.extra_data.get("locked_assets", {})
        prompts = []

        for key, asset_id in locked.items():
            asset = await db.execute(
                select(Asset).where(Asset.id == asset_id)
            ).scalar_one_or_none()

            if asset:
                entity_type, entity_id = key.split("_", 1)
                prompts.append(
                    f"{entity_type}: {asset.name}, "
                    f"外观: {asset.description or asset.asset_type}"
                )

        return prompts
```

---

#### Task 4: 在视频生成时注入锁定资产

**文件**:
- Modify: `backend/app/services/prompt_composer.py`
- Modify: `backend/app/api/v1/endpoints/video.py`

**实现**:
```python
def compose_video_prompt_with_locked_assets(
    *,
    base_prompt: str,
    shot: Shot,
    locked_assets: List[Dict]
) -> str:
    """组合包含锁定资产引用的视频prompt"""
    sections = [base_prompt]

    # 添加锁定资产约束
    if locked_assets:
        sections.append("【锁定资产一致性约束】")
        for asset in locked_assets:
            sections.append(
                f"- {asset['type']} {asset['name']}: "
                f"严格保持外观与资产{asset['asset_id']}一致"
            )

    sections.append(
        "【硬约束】同一角色不要更换发型、脸型、服装；"
        "同一场景不要更换空间结构、光照、天气；"
        "同一道具不要改变外观状态。"
    )

    return "\n".join(sections)
```

---

### 阶段三：TTS音色一致性

#### Task 5: 统一角色音色配置到Story Bible

**文件**:
- Modify: `backend/app/models/story_bible.py`
- Modify: `backend/app/api/v1/endpoints/tts.py`

**实现**:
```python
# StoryBible.character_rules 扩展音色字段
class CharacterRule(BaseModel):
    name: str
    voice: Optional[str] = None  # 音色配置
    voice_model: Optional[str] = None  # TTS模型
    voice_speed: Optional[float] = 1.0  # 语速

async def get_character_voice_from_story_bible(
    db: AsyncSession,
    character_name: str,
    story_bible_id: str
) -> Optional[Dict[str, Any]]:
    """从Story Bible获取角色音色配置"""
    story_bible = await get_story_bible(story_bible_id)
    character_rules = story_bible.character_rules or []

    for rule in character_rules:
        if rule.get("name") == character_name:
            return {
                "voice": rule.get("voice"),
                "voice_model": rule.get("voice_model"),
                "voice_speed": rule.get("voice_speed", 1.0)
            }

    return None
```

---

#### Task 6: TTS生成时强制注入Story Bible音色

**文件**:
- Modify: `backend/app/api/v1/endpoints/tts.py`

**实现**:
```python
@router.post("/tts/generate")
async def generate_tts(request: TTSGenerateRequest):
    """生成TTS，强制使用Story Bible音色"""
    # 1. 如果有story_bible_id，查询音色配置
    voice_config = None
    if request.story_bible_id:
        voice_config = await get_character_voice_from_story_bible(
            db, request.character_name, request.story_bible_id
        )

    # 2. 使用Story Bible音色或用户选择
    effective_voice = (
        voice_config.get("voice")
        if voice_config and voice_config.get("voice")
        else request.voice_model
    )
    effective_speed = (
        voice_config.get("voice_speed")
        if voice_config and voice_config.get("voice_speed")
        else request.speed
    )

    # 3. 生成TTS
    ...
```

---

### 阶段四：一致性质量检查

#### Task 7: 创建ConsistencyChecker服务

**文件**:
- Create: `backend/app/services/consistency_checker.py`

**实现**:
```python
class ConsistencyChecker:
    """一致性检查器"""

    async def check_shot_consistency(
        self,
        shot: Shot,
        story_bible: StoryBible,
        asset: Optional[Asset] = None
    ) -> ConsistencyReport:
        """检查镜头一致性"""
        issues = []

        # 1. 检查角色外观是否与Story Bible一致
        character_refs = shot.extra_data.get("entity_refs", {}).get("characters", [])
        for char_ref in character_refs:
            char = await self.get_character(char_ref)
            bible_char = self.find_in_story_bible(story_bible, char.name)

            if bible_char and char.appearance != bible_char.get("appearance"):
                issues.append(ConsistencyIssue(
                    type="character_appearance_drift",
                    severity="warning",
                    entity=char.name,
                    expected=bible_char.get("appearance"),
                    actual=char.appearance
                ))

        # 2. 检查是否使用锁定资产
        locked_assets = shot.extra_data.get("locked_assets", {})
        if not locked_assets and shot.image_url:
            issues.append(ConsistencyIssue(
                type="unlocked_asset_reference",
                severity="warning",
                message="镜头使用了参考图但未锁定资产版本"
            ))

        # 3. 检查TTS音色是否与Story Bible一致
        tts_job = await self.get_tts_job(shot.tts_job_id)
        if tts_job:
            bible_voice = self.get_story_bible_voice(story_bible, tts_job.character_name)
            if bible_voice and tts_job.voice != bible_voice:
                issues.append(ConsistencyIssue(
                    type="tts_voice_drift",
                    severity="error",
                    entity=tts_job.character_name,
                    expected=bible_voice,
                    actual=tts_job.voice
                ))

        return ConsistencyReport(shot_id=shot.id, issues=issues)

    async def check_batch_consistency(
        self,
        storyboard_id: str
    ) -> BatchConsistencyReport:
        """批量检查分镜一致性"""
        shots = await self.get_storyboard_shots(storyboard_id)
        reports = []

        for shot in shots:
            report = await self.check_shot_consistency(shot, ...)
            reports.append(report)

        return BatchConsistencyReport(
            storyboard_id=storyboard_id,
            total_shots=len(shots),
            consistent_count=sum(1 for r in reports if not r.has_blocking_issues),
            issues_by_type=self.group_by_type(reports)
        )
```

---

#### Task 8: 一致性检查API端点

**文件**:
- Create: `backend/app/api/v1/endpoints/consistency.py`

**实现**:
```python
@router.get("/consistency/shot/{shot_id}")
async def check_shot_consistency(
    shot_id: str,
    db: AsyncSession = Depends(get_db)
) -> ConsistencyReport:
    """检查镜头一致性"""

@router.get("/consistency/storyboard/{storyboard_id}")
async def check_storyboard_consistency(
    storyboard_id: str
) -> BatchConsistencyReport:
    """批量检查分镜一致性"""

@router.post("/consistency/shot/{shot_id}/fix")
async def auto_fix_shot_consistency(
    shot_id: str,
    fix_level: str = "auto"  # auto, manual
) -> Dict:
    """自动修复一致性问题"""
```

---

### 阶段五：Chain of Consistency保障

#### Task 9: Story Bible变更传播机制

**文件**:
- Modify: `backend/app/services/story_state_machine.py`
- Modify: `backend/app/api/v1/endpoints/story_bible.py`

**实现**:
```python
async def propagate_story_bible_change(
    db: AsyncSession,
    story_bible_id: str,
    change_type: str,  # "character_update", "scene_update", etc.
    affected_entity_id: str
):
    """将Story Bible变更传播到相关镜头"""
    # 1. 查找使用该实体的所有镜头
    shots = await db.execute(
        select(Shot).where(
            Shot.extra_data.contains({"entity_refs": {"characters": [affected_entity_id]}})
        )
    )

    # 2. 标记这些镜头需要审查
    for shot in shots:
        shot.extra_data = shot.extra_data or {}
        shot.extra_data["needs_review"] = True
        shot.extra_data["review_reason"] = f"Story Bible {change_type} changed"
        shot.consistency_status = "stale"

    await db.commit()

    # 3. 通知用户
    return {
        "affected_shots": len(shots.scalars().all()),
        "action": "marked_for_review"
    }
```

---

#### Task 10: 批量重新生成一致性prompt

**文件**:
- Modify: `backend/app/services/prompt_composer.py`
- Modify: `backend/app/api/v1/endpoints/shots.py`

**实现**:
```python
@router.post("/shots/batch-rebuild-prompts")
async def batch_rebuild_consistency_prompts(
    storyboard_id: str,
    use_locked_assets: bool = True
):
    """批量重新构建镜头的连贯性prompt"""
    shots = await get_storyboard_shots(storyboard_id)
    rebuilt = []

    for shot in shots:
        # 1. 重新填充entity_refs
        shot = await auto_fill_shot_entity_refs(db, shot, ...)

        # 2. 锁定资产
        if use_locked_assets:
            locked = await lock_shot_assets(db, shot)

        # 3. 重新构建prompt
        new_prompt = await rebuild_shot_prompt(db, shot)

        shot.prompt = new_prompt
        shot.consistency_status = "rebuilt"
        rebuilt.append(shot.id)

    await db.commit()
    return {"rebuilt_count": len(rebuilt)}
```

---

## 四、验证标准

### 4.1 功能验证

- [ ] 每个Shot都有非空的entity_refs
- [ ] 视频生成时使用锁定资产
- [ ] TTS使用Story Bible音色配置
- [ ] 一致性检查能发现drift问题
- [ ] Story Bible变更后标记相关镜头

### 4.2 端到端验证

```
1. 创建小说 → 导入章节
2. 生成Story Bible（含角色外观描述）
3. 生成剧本 → 生成分镜
4. 检查所有Shot都有entity_refs
5. 生成视频 → 检查prompt包含锁定资产引用
6. 生成TTS → 检查使用Story Bible音色
7. 修改Story Bible → 检查相关镜头被标记
8. 运行一致性检查 → 应无blocking问题
```

---

## 五、优先级

| Task | 优先级 | 工作量 | 风险 |
|------|--------|--------|------|
| Task 1: 强制填充entity_refs | 🔴 P0 | 低 | 低 |
| Task 2: 端点调用entity_refs填充 | 🔴 P0 | 低 | 低 |
| Task 3: AssetLockService | 🔴 P0 | 中 | 中 |
| Task 4: 视频prompt注入锁定资产 | 🔴 P0 | 中 | 低 |
| Task 5: Story Bible音色配置 | 🟡 P1 | 中 | 低 |
| Task 6: TTS注入音色 | 🟡 P1 | 低 | 低 |
| Task 7: ConsistencyChecker | 🟡 P1 | 中 | 中 |
| Task 8: 一致性检查API | 🟡 P1 | 低 | 低 |
| Task 9: 变更传播机制 | 🟢 P2 | 中 | 中 |
| Task 10: 批量重新生成 | 🟢 P2 | 中 | 中 |

---

## 六、技术债务清理

### 6.1 清理项

1. 移除Shot.prompt的手动编辑入口，强制通过PromptComposer生成
2. 统一Character.voice和StoryBible.character_rules.voice
3. 移除DEV_MODE下的一致性跳过逻辑

### 6.2 新增验证

1. 单元测试：entity_refs自动填充
2. 单元测试：锁定资产注入
3. E2E测试：完整链路一致性验证