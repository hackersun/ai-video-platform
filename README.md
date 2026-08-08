# AI视频平台 - 动画漫剧生成系统

## 项目概述

基于 AI 技术的动画漫剧生产平台，支持小说与章节管理、实体和参考资产、剧本分镜、视频与语音生成、字幕和成片合成。仓库仍处于商业化治理阶段，正式发布状态以[商业版本发布门禁](./docs/release/commercial-release-gates.md)为准。

## 技术架构

- **前端**: Next.js 14 + React 18 + TypeScript
- **后端**: FastAPI + Python 3.11
- **数据库**: SQLite（本地）+ PostgreSQL（目标生产）
- **AI服务**: 通过模型中心配置的文本、图像、视频和语音供应商
- **媒体**: 本地开发存储 + 可配置对象存储

## 项目结构

```
ai-video-platform/
├── frontend/          # Next.js 前端与浏览器验收
├── backend/           # FastAPI 后端与后端测试
├── docs/              # 架构、产品、安全、运维和发布文档
├── e2e/               # 旧版独立端到端验收工程
├── scripts/           # 跨前后端开发和验收脚本
└── tools/             # 不依赖业务运行时的仓库治理工具
```

完整职责和迁移目标见[仓库目录规范](./docs/architecture/repository-layout.md)。

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/hackersun/ai-video-platform.git
cd ai-video-platform

# 安装前端依赖
npm ci
npm --prefix frontend ci

# 终端 1：启动后端
cd backend
python3 -m pip install -r requirements.txt
python3 init_db.py
uvicorn main:app --reload --port 8000

# 终端 2：启动前端
cd frontend
npm run dev
```

本地地址：前端 `http://localhost:3000`，后端文档 `http://localhost:8000/docs`。当前 `docker-compose.yml` 尚未通过生产发布门禁，不作为可信生产启动方式。

## 本地验收

```bash
# 快速验收：前端类型检查、构建和 smoke E2E
npm run verify:quick

# 后端测试
npm run verify:backend

# 前端类型检查 + 构建
npm run verify:frontend

# 端到端测试（需先启动前端服务）
npm run verify:e2e
```

## 开发指南

开发前请阅读：

- [仓库目录规范](./docs/architecture/repository-layout.md)
- [AI 持续开发与代码健康治理规范](./docs/architecture/ai-development-governance.md)
- [模块分类与依赖边界](./docs/architecture/module-boundaries.md)
- [分支与版本发布规范](./docs/release/branching-strategy.md)
- [商业安全基线](./docs/security/commercial-security-baseline.md)
- [商用就绪路线图](./docs/product/commercial-readiness-roadmap.md)

## 许可证

仓库尚未提交可验证的 `LICENSE` 文件。正式开源或闭源商业发布前，必须完成依赖许可证盘点并统一仓库、产品页面和合同中的版权声明。
