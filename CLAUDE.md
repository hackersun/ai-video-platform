# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI视频平台 is an AI-powered animation/comic video generation platform supporting character consistency management, intelligent storyboard generation, and video synthesis.

## Tech Stack

- **Frontend**: Next.js 14 + React 18 + TypeScript + Tailwind CSS + Radix UI
- **Backend**: FastAPI (Python) with async SQLAlchemy
- **Database**: SQLite (local dev), PostgreSQL (production)
- **AI Services**: Volcano Engine (豆包), Alibaba Qianlian (千问/DashScope), OpenAI
- **Storage**: MinIO (S3-compatible), Neo4j (graph), Milvus (vectors)

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

# Lint
npm run lint
```

### End-to-End Tests
```bash
# Run Playwright e2e tests
cd e2e && npx playwright test
```

### Docker (Production)
```bash
docker-compose up -d
```

## Architecture

### Production Pipeline (Core Workflow)

The platform follows a linear production pipeline:

```
Novel → Chapter → Script → Storyboard → Shots → TTS/Synthesis → Video
```

Each stage generates outputs consumed by the next:
- **Novel**: Imported source material with chapters
- **Script**: Screenplay/screenwriting for each chapter
- **Storyboard**: Visual shots planned with descriptions and prompts
- **Shots**: Individual video clip definitions with references to TTS audio
- **TTS**: Text-to-speech generation for character dialogue
- **Synthesis**: Combines video + audio into final clips
- **Video**: Final rendering via Volcano Engine

### Async Job Pattern

Long-running operations use job polling:
1. `POST /api/v1/{resource}/generate` → returns `{ task_id }` immediately
2. Client polls `GET /api/v1/{resource}/status/{task_id}` until completion
3. On success, response includes `output_url` or `result` field
4. Jobs are tracked in corresponding `_job` tables

### Backend Structure
```
backend/
├── main.py                    # FastAPI entry point
├── init_db.py                 # Database table initialization
├── init_llm_config.py          # LLM provider/model seed data
├── app/
│   ├── api/v1/
│   │   ├── router.py          # Route aggregation
│   │   └── endpoints/         # API endpoints (~30 modules)
│   │       ├── auth.py             # User authentication
│   │       ├── characters.py      # Character management
│   │       ├── novels.py          # Novel import/management
│   │       ├── chapters.py       # Chapter management
│   │       ├── scripts.py        # Screenplay management
│   │       ├── storyboards.py    # Storyboard management
│   │       ├── shots.py          # Shot management
│   │       ├── story_bible.py    # Character consistency ("故事圣经")
│   │       ├── workflow.py        # Orchestrated pipeline workflows
│   │       ├── video.py          # Video generation (火山引擎)
│   │       ├── tts.py           # Text-to-speech synthesis
│   │       ├── synthesis.py      # Audio/video composition
│   │       ├── images.py        # Image generation
│   │       ├── media.py         # Unified media generation API
│   │       ├── subtitles.py     # Subtitle track management
│   │       ├── llm_config.py    # LLM provider configuration
│   │       ├── dashboard.py      # Dashboard statistics
│   │       ├── production_control.py  # Production state machine
│   │       └── ...
│   ├── core/
│   │   ├── database.py          # SQLAlchemy async (SQLite/PostgreSQL)
│   │   ├── security.py         # JWT auth utilities
│   │   ├── model_registry.py   # Dynamic model loading
│   │   └── ...
│   ├── models/                 # SQLAlchemy ORM models
│   │   └── *_job.py           # Job tracking tables (video, tts, synthesis)
│   └── services/               # External API integrations
│       ├── volcano_service.py     # Volcano Engine (视频/图像/TTS)
│       ├── openai_service.py      # OpenAI/DashScope integration
│       ├── storyboard_template_service.py  # AI storyboard generation
│       └── story_state_machine.py  # Production workflow state
```

### Frontend Structure
```
frontend/src/
├── app/                    # Next.js App Router pages
│   ├── page.tsx             # Landing page
│   ├── login/, register/   # Auth pages
│   ├── dashboard/           # Statistics overview
│   ├── novels/              # Novel management
│   ├── scripts/            # Script editor
│   ├── storyboards/         # Storyboard view
│   ├── video-generation/    # Video generation
│   ├── producer/            # Production pipeline UI
│   ├── llm-config/         # LLM provider settings
│   └── settings/           # User preferences
├── components/
│   ├── ui/                  # Radix UI components (Dialog, Dropdown, Tooltip)
│   └── layout/              # Navigation, main layout
└── lib/
    └── api-client.ts       # API client singleton with typed methods
```

### Video Generation (Volcano Engine)
Uses official `volcenginesdkarkruntime` SDK:
- Model: `doubao-seedance-1-5-pro-251215`
- Duration: 4/8/10 seconds
- Resolution: 480p/720p/1080p
- Supports image-to-video via `image_url` parameter

### LLM Configuration Architecture
- **LLMProvider**: Cloud provider (火山引擎, 阿里百炼, 千问)
- **LLMModel**: Specific models per provider (豆包Seed-1.8, qwen-plus, etc.)
- **LLMConfig**: User's API key + custom parameters per model
- Built-in providers/models seeded via `init_llm_config.py`
- Models dynamically loaded via `model_registry.py`

### Frontend API Client
`frontend/src/lib/api-client.ts`:
- Singleton `apiClient` with typed methods per feature
- Base URL: `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'`
- Token stored in `localStorage` under `auth_token` key

## Key API Patterns

### Authentication
JWT-based auth via `get_current_user_id()` dependency. Some endpoints accept `user_id` parameter.

### Database
- Default: SQLite `ai_video.db` (local dev)
- Production: PostgreSQL via `DATABASE_URL` env var
- Tables auto-created via `init_db.py`

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
