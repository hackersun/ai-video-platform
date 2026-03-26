# 设计文档：视频生成流程重构 + 角色形象自动生成 + 镜头参考图生成

**日期**: 2026-03-26
**状态**: 已批准

---

## 任务一：重构视频生成页面 — 关联小说/剧本/分镜/镜头

### 目标

在视频生成页面增加小说选择器，并在历史记录中展示关联信息。

### 实现方案

#### 1. 页面布局变更

在现有三级级联选择器（剧本 → 分镜 → 镜头）**上方**，增加小说一级选择器：

```
┌─ 视频生成 ───────────────────────────────────────────────────┐
│ [选择小说 ▼] → [选择剧本 ▼] → [选择分镜 ▼] → [选择镜头 ▼]        │
│                                                              │
│   配置区（Prompt / 角色图 / 时长 / 分辨率）  │  预览区 + 历史记录   │
└──────────────────────────────────────────────────────────────┘
```

- 小说选择器加载用户所有小说列表
- 选择小说后，自动过滤出关联的剧本（下拉列表只显示该小说关联的剧本）
- 后续分镜/镜头级联逻辑不变
- 用户也可不选小说，直接选剧本/分镜/镜头（兼容性）

#### 2. 数据存储

`VideoJob` 表通过现有 `extra_data` JSON 字段存储关联信息，无需改表结构：

```json
{
  "novel_id": "uuid",
  "novel_title": "小说名称",
  "script_id": "uuid",
  "script_title": "剧本标题",
  "storyboard_id": "uuid",
  "storyboard_title": "分镜标题",
  "shot_id": "uuid",
  "shot_number": 1
}
```

#### 3. 历史记录展示

视频历史列表每行增加关联信息展示：

```
┌─────────────────────────────────────────────────┐
│ [视频缩略图] 任务ID  prompt...  小说/剧本/镜头号   │
│             状态: succeeded  时长: 5s  2026-03-26│
└─────────────────────────────────────────────────┘
```

通过 JOIN `novels`、`scripts`、`storyboards` 表获取名称。

#### 4. 改动文件

- `frontend/src/app/video-generation/page.tsx` — 增加小说选择器，历史列表增加关联列
- `frontend/src/lib/api-client.ts` — `generateVideo` 增加关联参数传递
- `backend/app/api/v1/endpoints/video.py` — 创建 job 时从 request 接收并存储关联信息
- `backend/app/api/v1/endpoints/novels.py` — 如果需要新增 novels-by-user 列表接口

---

## 任务二：角色形象自动生成

### 目标

创建角色后自动（经用户确认或不确认）生成形象图。

### 实现方案

#### 1. 创建角色时自动触发

- 角色创建表单底部增加勾选框：`☑ 创建后自动生成形象图`（默认勾选）
- 用户提交创建请求 → 后端创建角色记录 → 返回角色ID
- 前端如果勾选了自动生成：立即调用 `POST /images/generate`
- 图像生成完成后：更新角色 `avatar` 字段 → 刷新角色详情显示新头像

#### 2. 创建后手动触发（已有逻辑增强）

- 点击「AI生成头像」按钮 → 调用图像生成 API → 完成后弹出轻量 toast 提示「形象图已生成」
- 刷新角色卡片/详情中的头像显示

#### 3. AI 提取角色后自动生成

- 调用 `POST /characters/extract` 时，增加参数 `auto_generate_avatar: bool = True`
- 后端 `characters.py` extract 逻辑：提取完成后，遍历每个新创建的角色，调用图像生成服务
- 前端提取结果弹窗中，每个角色卡片显示形象图生成状态（pending → generating → succeeded/failed）
- 用户可在弹窗中看到每个角色的生成进度

#### 4. 改动文件

- `frontend/src/app/characters/page.tsx` — 创建表单增加勾选框，extract 弹窗增加生成状态显示
- `backend/app/api/v1/endpoints/characters.py` — extract 端点增加自动生成逻辑
- `backend/app/api/v1/endpoints/images.py` — 确保图像生成服务可被 characters 模块调用
- `frontend/src/lib/api-client.ts` — 如需新增接口方法

---

## 任务三：分镜/镜头参考图生成

### 目标

为每个镜头生成参考图，支持单镜头和批量生成。

### 实现方案

#### 1. 数据模型变更

`Shot` 模型增加两个字段：

```python
image_url = Column(Text)      # 参考图 URL
image_status = Column(String(20), default="pending")  # pending / generating / succeeded / failed
image_asset_id = Column(String(36), ForeignKey("assets.id"), nullable=True)  # 关联资产库记录
```

#### 2. 单镜头生成

在镜头详情编辑器中，「视觉描述」区域下方增加「生成参考图」按钮：

```
┌─ 镜头详情编辑器 ────────────────────────────────────────┐
│ 视觉描述: [    textarea    ]                            │
│ Camera: [    ] Emotion: [    ] Lighting: [    ]        │
│                                                          │
│              [🎨 生成参考图]  [⏳ 生成中...]              │
│              [生成的参考图预览]                            │
└──────────────────────────────────────────────────────────┘
```

- 点击后调用 `POST /images/generate`，prompt 使用 `visual_description` + `shot.prompt`
- 轮询图像任务状态，状态更新到 `shot.image_status`
- 生成成功后：
  - `shot.image_url` = 图像 URL
  - 同时在 `assets` 表创建一条记录（category=`scene`，`url`=图像URL），`shot.image_asset_id` = 资产ID
- 显示参考图缩略图预览

#### 3. 批量生成

在分镜列表页和镜头列表页增加「批量生成参考图」按钮：

- 用户勾选多个镜头（复选框）
- 点击按钮 → 批量调用图像生成 API
- 显示进度面板：每个镜头一行，显示 shot_number、visual_description、状态
- 轮询所有任务，完成后更新 shot 记录
- 失败时显示失败原因

#### 4. 改动文件

- `backend/app/models/shot.py` — 增加 `image_url`、`image_status`、`image_asset_id` 字段
- `backend/init_db.py` — 如果需要添加新字段到已有数据库（ALTER TABLE）
- `backend/app/api/v1/endpoints/shots.py` — 增加 `shots/{id}/generate-image` 端点
- `backend/app/api/v1/endpoints/storyboards.py` — 增加 `storyboards/{id}/shots/generate-images` 批量端点
- `frontend/src/app/storyboards/page.tsx` — 镜头编辑器增加生成按钮和预览
- `frontend/src/app/shots/page.tsx` — 增加批量生成 UI 和进度面板
- `frontend/src/lib/api-client.ts` — 增加 `generateShotImage`、`generateShotsImages` 方法

---

## 总结

三个任务相互独立但都属于「视频生成完整流程」的一部分：

1. **视频生成页面** — 建立 novel→script→storyboard→shot 的完整关联链，并在历史中可追溯
2. **角色形象自动生成** — 减少用户手动操作，创建/提取角色后自动生成形象
3. **镜头参考图生成** — 为每个镜头提供 AI 生成的视觉参考，提升分镜制作效率

所有图像生成统一使用现有的 `/images/generate` 接口（豆包 Seedream 模型）。
