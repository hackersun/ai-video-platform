# MiniMax 模型集成设计方案

**日期：** 2026-03-27
**状态：** 已批准

## 1. 概述

为 AI 视频平台新增 MiniMax 服务商支持，覆盖文本生成、图像生成、TTS 语音合成三种模态。遵循现有架构模式，不影响火山引擎、阿里百炼等其他已配置模型。

## 2. API 规范

MiniMax Token Plan 提供了与 OpenAI SDK 兼容的 API，同时也支持 Anthropic SDK 格式。

### 2.1 API 基础地址

根据 API Key 前缀自动判断：

| Key 前缀 | 区域 | Base URL |
|----------|------|----------|
| `sk-api-*` | 中国大陆 | `https://api.minimaxi.com/v1` |
| `sk-cp-*` | 海外 | `https://api.minimax.io/v1` |
| 其他/默认 | 中国大陆 | `https://api.minimaxi.com/v1` |

### 2.2 各模态端点

#### 文本生成
- **端点：** `POST /v1/chat/completions`（OpenAI SDK 兼容）
- **认证：** `Authorization: Bearer {api_key}`
- **模型：** `MiniMax-M2.7`（最新）、`MiniMax-M2`
- **请求体：** OpenAI 标准格式，支持 function calling
- **响应：** OpenAI 标准格式

#### 图像生成
- **端点：** `POST /v1/image_generation`
- **认证：** `Authorization: Bearer {api_key}`
- **模型：** `image-01`
- **同步返回：** 无需轮询，URL 有效期 24 小时
- **尺寸支持：** `1:1`(1024x1024)、`16:9`(1280x720)、`4:3`(1152x864)、`3:2`(1248x832)、`2:3`(832x1248)、`3:4`(864x1152)、`9:16`(720x1280)、`21:9`(1344x576)
- **n：** 1-9 张

#### TTS 语音合成
- **端点：** `POST /v1/t2a_v2`
- **认证：** `Authorization: Bearer {api_key}`
- **模型：** `speech-2.6-hd`（高清）、`speech-2.6-turbo`（快速）
- **同步返回：** 返回 hex 编码音频
- **最大字符：** 10,000
- **voice_id 精选：**

| voice_id | 语言 | 风格 |
|----------|------|------|
| `female-shaonv` | 中文 | 少女 |
| `female-yujie` | 中文 | 御姐 |
| `male-qn-qingse` | 中文 | 清涩少年 |
| `male-qn-jingying` | 中文 | 精英男性 |
| `male-qn-badao` | 中文 | 霸道 |
| `English_expressive_narrator` | 英文 | 表现力叙述 |
| `female-tianmei` | 英文 | 甜美女声 |
| `Japanese_female_qingli` | 日语 | 日语女声 |
| `Korean_female_qingli` | 韩语 | 韩语女声 |
| `audiobook_male_1` | 中/英 | 有声书男声 |

## 3. 架构设计

### 3.1 文件变更

新增：
- `backend/app/core/minimax_config.py` — 配置：provider 信息 + 模型列表 + 辅助函数
- `backend/app/services/minimax_service.py` — 服务：text/image/TTS 统一调用类

修改：
- `backend/app/api/v1/endpoints/llm_config.py` — 新增 `test_minimax_api()` + 路由
- `backend/init_llm_config.py` — 追加 MiniMax provider + 4 个模型种子数据

### 3.2 数据模型映射

| 模型 | model_type | endpoint | api_model_id |
|------|-----------|----------|-------------|
| MiniMax-M2.7 | text-generation | /v1/chat/completions | MiniMax-M2.7 |
| MiniMax-M2 | text-generation | /v1/chat/completions | MiniMax-M2 |
| image-01 | image-generation | /v1/image_generation | image-01 |
| speech-2.6-hd | tts | /v1/t2a_v2 | speech-2.6-hd |

> 注：`model_type: tts` 为字符串值，无需修改数据库表结构。

### 3.3 MiniMaxService 类方法

```python
async def chat_completion(
    self, model: str, messages: List[Dict], temperature: float = 0.7,
    max_tokens: int = 2048, stream: bool = False, **kwargs
) -> Dict[str, Any]

async def generate_image(
    self, prompt: str, model: str = "image-01",
    aspect_ratio: str = "1:1", n: int = 1,
    response_format: str = "url", **kwargs
) -> Dict[str, Any]

async def text_to_speech(
    self, text: str, model: str = "speech-2.6-hd",
    voice_id: str = "female-shaonv", speed: float = 1.0,
    output_dir: str = "audio", **kwargs
) -> Dict[str, Any]
```

## 4. 实现顺序

1. 创建 `minimax_config.py`
2. 创建 `minimax_service.py`
3. 在 `llm_config.py` 添加 `test_minimax_api()` + 路由
4. 在 `init_llm_config.py` 追加种子数据
5. 运行初始化脚本
6. 重启后端服务
7. 连通性测试验证

## 5. 不在本次范围内

- MiniMax 视频生成 API（模型众多，需单独评估）
- MiniMax 音乐生成 API
- MiniMax voice cloning / voice design
- 前端 TTS 页面新增 voice_id 选择器（可后续扩展）
