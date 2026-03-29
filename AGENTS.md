# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

AI视频平台 is an AI-powered animation/comic video generation platform supporting character consistency management, intelligent storyboard generation, and video synthesis.

## Tech Stack

- **Frontend**: Next.js 14 + React 18 + TypeScript + Tailwind CSS
- **Backend**: FastAPI (Python) with async SQLAlchemy
- **Database**: SQLite (local dev), PostgreSQL (production)
- **AI Services**: Volcano Engine (豆包), Alibaba Qianlian (千问/DashScope)

## Development Commands

### Backend (FastAPI)
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Initialize database tables
python init_db.py

# Initialize LLM providers and models
python init_llm_config.py

# Run development server
uvicorn main:app --reload --port 8000

# Access API docs at http://localhost:8000/docs
```

### Frontend (Next.js)
```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

### Docker (Production)
```bash
docker-compose up -d
```

## Architecture

### Backend Structure
```
backend/
├── main.py                 # FastAPI entry point
├── init_db.py              # Database table initialization
├── init_llm_config.py       # LLM provider/model seed data
├── app/
│   ├── api/v1/
│   │   ├── router.py       # API route aggregation
│   │   └── endpoints/       # Individual API endpoints
│   │       ├── auth.py         # User authentication
│   │       ├── characters.py    # Character management
│   │       ├── novels.py        # Novel management
│   │       ├── scripts.py       # Script/screenplay management
│   │       ├── chapters.py      # Chapter management
│   │       ├── storyboards.py   # Storyboard management
│   │       ├── shots.py         # Shot management
│   │       ├── video.py         # Video generation (火山引擎)
│   │       ├── llm_config.py    # LLM provider configuration
│   │       ├── qwen.py          # Alibaba Qianlian API
│   │       └── dashboard.py      # Dashboard statistics
│   ├── core/
│   │   ├── database.py      # SQLAlchemy async setup (SQLite)
│   │   ├── security.py      # JWT auth utilities
│   │   ├── volcano_config.py # Volcano Engine model configs
│   │   └── qwen_config.py   # Qianlian/Qwen model configs
│   ├── models/              # SQLAlchemy ORM models
│   │   ├── character.py     # Character model
│   │   ├── llm_config.py    # LLMProvider, LLMModel, LLMConfig, LLMUsageLog
│   │   └── video_job.py    # Video generation job tracking
│   └── services/            # External API integrations
│       ├── volcano_service.py    # Volcano Engine (图像/视频/TTS)
│       ├── dashscope_service.py  # Alibaba DashScope
│       └── qianlian_service.py   # Alibaba Qianlian
```

### Frontend Structure
```
frontend/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── page.tsx           # Landing page
│   │   ├── dashboard/         # Dashboard
│   │   ├── novels/            # Novel management
│   │   ├── characters/        # Character management
│   │   ├── scripts/           # Script editor
│   │   ├── storyboards/        # Storyboard view
│   │   ├── video-generation/   # Video generation
│   │   ├── llm-config/        # LLM configuration
│   │   └── settings/          # Settings
│   ├── components/
│   │   ├── ui/                # Radix UI components
│   │   └── layout/            # Layout components (top-navigation, main-layout)
│   └── lib/
│       ├── api-client.ts      # API client singleton
│       └── utils.ts           # Utility functions
```

### Video Generation Workflow
1. User submits prompt → `POST /api/v1/video/generate`
2. Backend creates `VideoJob` record in SQLite
3. Calls Volcano Engine ARK API (`doubao-seedance-1-5-pro-251215`)
4. Returns `task_id` for polling
5. Client polls `GET /api/v1/video/status/{task_id}`
6. On completion, video URL stored in `VideoJob`

### LLM Configuration Architecture
- **LLMProvider**: Cloud provider (火山引擎, 阿里百炼, 千问)
- **LLMModel**: Specific models per provider (豆包Seed-1.8, qwen-plus, etc.)
- **LLMConfig**: User's API key + custom parameters per model
- Built-in providers/models seeded via `init_llm_config.py`

### Database
- Default: SQLite `ai_video.db` (for local development)
- Production: PostgreSQL via `DATABASE_URL` env var
- Tables auto-created via `init_db.py`

## Key API Patterns

### Authentication
JWT-based auth via `get_current_user_id()` dependency. Some endpoints require `user_id` parameter.

### Video Generation (Volcano Engine)
Uses official `volcenginesdkarkruntime` SDK:
- Model: `doubao-seedance-1-5-pro-251215`
- Duration: 4/8/10 seconds
- Resolution: 480p/720p/1080p
- Supports image-to-video with `image_url` parameter

### Frontend API Client
Located at `frontend/src/lib/api-client.ts`:
- Singleton `apiClient` instance
- Methods for all major features: characters, novels, scripts, video, LLM config
- Base URL: `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'`

## Service Ports
| Service | Port |
|---------|------|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Neo4j | 7474/7687 |
| Milvus | 19530 |
| MinIO | 9000/9001 |

## Environment Variables (Production)
```bash
OPENAI_API_KEY=
VOLCENGINE_API_KEY=
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
MINIO_ENDPOINT=
NEO4J_URI=
MILVUS_HOST=
```
