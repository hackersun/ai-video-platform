# OpenCode 配置与使用指南

> 适用于AI视频平台开发

---

## 一、OpenCode 简介

OpenCode 是一款AI驱动的代码编辑器，集成了：
- 智能代码补全
- 自然语言代码生成
- 内置终端
- Git版本控制
- 调试工具

---

## 二、安装与配置

### 2.1 检查OpenCode安装

```bash
# 检查是否已安装
which opencode

# 查看版本
opencode --version
```

**当前环境**: OpenCode v1.2.20 已安装

### 2.2 启动OpenCode

```bash
# 进入项目目录
cd /Users/admin/workspace/ai-video-platform

# 使用OpenCode打开项目
opencode .
```

### 2.3 推荐插件安装

在OpenCode中按 `Cmd+Shift+P` (Mac) 或 `Ctrl+Shift+P` (Windows)，搜索安装：

| 插件 | 用途 |
|------|------|
| Python | Python语言支持 |
| FastAPI | FastAPI框架支持 |
| Pylance | Python智能提示 |
| Docker | Docker支持 |
| GitLens | Git增强 |
| Prettier | 代码格式化 |
| ESLint | JavaScript/TypeScript检查 |

---

## 三、项目开发流程

### 3.1 打开项目

```bash
cd /Users/admin/workspace/ai-video-platform
opencode .
```

### 3.2 创建新文件

在OpenCode中：
1. 点击左侧文件树
2. 右键选择 "New File"
3. 输入文件路径

或使用快捷键：
- `Cmd+N` (Mac) / `Ctrl+N` (Windows) - 新建文件

### 3.3 使用AI辅助编码

在OpenCode中：
1. 按 `Cmd+I` (Mac) 或 `Ctrl+I` (Windows)
2. 输入自然语言描述
3. AI自动生成代码

**示例**:
```
创建一个FastAPI的用户注册API，包含邮箱验证和密码加密
```

### 3.4 运行代码

在OpenCode内置终端中：

```bash
# 激活虚拟环境
source backend/venv/bin/activate

# 安装依赖
pip install -r backend/requirements.txt

# 启动后端
cd backend
python main.py
```

### 3.5 调试代码

1. 在代码行左侧点击设置断点
2. 按 `F5` 启动调试
3. 使用调试工具栏单步执行

---

## 四、Git操作

### 4.1 在OpenCode中使用Git

1. 点击左侧Git图标
2. 查看修改的文件
3. 输入提交信息
4. 点击提交按钮

### 4.2 命令行Git（在OpenCode终端中）

```bash
# 查看状态
git status

# 添加文件
git add .

# 提交
git commit -m "feat: 添加用户API"

# 推送
git push origin dev

# 创建分支
git checkout -b feature/user-api
```

---

## 五、开发任务清单

### 任务1: 完成用户API

**文件**: `backend/app/api/v1/user.py`

**功能**:
- POST /users - 用户注册
- POST /users/login - 用户登录
- GET /users/me - 获取当前用户
- PUT /users/me - 更新用户信息

**AI提示词**:
```
创建一个FastAPI用户API模块，包含：
1. 用户注册接口（邮箱、用户名、密码）
2. 用户登录接口（JWT token）
3. 获取当前用户信息
4. 更新用户信息
使用依赖注入获取数据库会话
```

### 任务2: 完成小说API

**文件**: `backend/app/api/v1/novel.py`

**功能**:
- CRUD操作
- 分页查询
- 搜索功能

### 任务3: Docker配置

**文件**: `docker/Dockerfile.backend`

**AI提示词**:
```
创建一个Python 3.11的Dockerfile，用于FastAPI应用：
1. 使用官方Python镜像
2. 安装依赖
3. 复制代码
4. 暴露8000端口
5. 使用uvicorn启动
```

---

## 六、常用快捷键

| 快捷键 | 功能 |
|--------|------|
| `Cmd+P` | 快速打开文件 |
| `Cmd+Shift+P` | 命令面板 |
| `Cmd+Shift+F` | 全局搜索 |
| `Cmd+\`` | 打开终端 |
| `Cmd+I` | AI辅助 |
| `F5` | 调试 |
| `F12` | 跳转到定义 |
| `Cmd+/` | 注释切换 |

---

## 七、问题排查

### 问题1: OpenCode无法启动

```bash
# 检查路径
ls -la /usr/local/bin/opencode

# 重新安装
brew reinstall opencode
```

### 问题2: Python环境错误

```bash
# 创建虚拟环境
cd backend
python3.11 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 问题3: Git提交失败

```bash
# 配置Git
 git config user.name "Your Name"
git config user.email "your@email.com"
```

---

## 八、开发规范

### 8.1 代码风格

- 使用Black格式化Python代码
- 使用Prettier格式化前端代码
- 遵循PEP 8规范

### 8.2 提交规范

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式
refactor: 重构
test: 测试
chore: 构建/工具
```

---

## 九、参考资源

- OpenCode文档: https://opencode.ai/docs
- FastAPI文档: https://fastapi.tiangolo.com
- 项目PRD: [飞书文档]

---

**最后更新**: 2026-03-12
**配置人**: AIBoss
