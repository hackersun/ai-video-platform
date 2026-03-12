# AI视频平台 - 动画漫剧生成系统

## 项目概述

基于AI技术的动画漫剧生成平台，支持角色一致性管理、智能分镜生成、视频合成等功能。

## 技术架构

- **前端**: Next.js 14 + React 18 + TypeScript
- **后端**: FastAPI + Python 3.11
- **数据库**: PostgreSQL + Redis + Milvus + Neo4j
- **AI服务**: 火山引擎 + OpenAI + ElevenLabs
- **部署**: Docker + Docker Compose

## 项目结构

```
ai-video-platform/
├── frontend/          # Next.js前端
├── backend/           # FastAPI后端
├── ai-service/        # AI服务层
├── docker/            # Docker配置
├── docs/              # 文档
└── scripts/           # 脚本工具
```

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/hackersun/ai-video-platform.git
cd ai-video-platform

# 启动服务
docker-compose up -d

# 访问
# 前端: http://localhost:3000
# 后端API: http://localhost:8000
# API文档: http://localhost:8000/docs
```

## 开发指南

见 [docs/DEVELOPMENT.md](./docs/DEVELOPMENT.md)

## 许可证

MIT
