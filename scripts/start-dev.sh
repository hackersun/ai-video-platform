#!/bin/bash
# AI视频平台开发环境一键启动脚本
# 确保不影响现有小龙虾环境

set -e

echo "🎬 AI视频平台开发环境启动脚本"
echo "================================"
echo ""

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 检查Docker
step "1. 检查Docker环境..."
if ! command -v docker &> /dev/null; then
    error "Docker未安装，请先安装Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

info "Docker版本: $(docker --version | cut -d' ' -f3 | tr -d ',')"
info "Docker Compose版本: $(docker-compose --version | cut -d' ' -f3 | tr -d ',')"

# 检查是否在正确的目录
step "2. 检查项目结构..."
if [ ! -f "docker-compose.yml" ]; then
    error "未找到docker-compose.yml，请在项目根目录运行此脚本"
    exit 1
fi

info "项目根目录: $PROJECT_ROOT"

# 创建必要目录
step "3. 创建数据目录..."
mkdir -p data/postgres data/redis data/milvus data/neo4j data/minio
mkdir -p models storage/logs storage/uploads
mkdir -p frontend/node_modules backend/__pycache__
info "✓ 数据目录已创建"

# 检查.env文件
step "4. 检查环境变量配置..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        warn ".env文件不存在，从模板创建..."
        cp .env.example .env
        info "✓ 已创建.env文件，请根据需要编辑配置"
    else
        warn ".env.example也不存在，创建默认配置..."
        cat > .env << 'EOF'
# AI视频平台开发环境配置

# 数据库配置
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/aivideo
REDIS_URL=redis://redis:6379/0

# Milvus配置
MILVUS_HOST=milvus
MILVUS_PORT=19530

# Neo4j配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# MinIO配置
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# JWT配置
JWT_SECRET=dev-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# 环境配置
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# 前端配置
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws

# AI服务配置（免费模型优先）
# 使用Edge TTS（完全免费）
TTS_PROVIDER=edge
# 使用本地Stable Diffusion
IMAGE_PROVIDER=local
# 使用本地Stable Video Diffusion
VIDEO_PROVIDER=local

# Celery配置
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2
EOF
        info "✓ 已创建默认.env文件"
    fi
else
    info "✓ .env文件已存在"
fi

# 检查端口占用
step "5. 检查端口占用..."
PORTS=("3000" "8000" "5432" "6379" "9000" "9001" "7474" "7687" "19530" "5555")
PORT_IN_USE=false

for port in "${PORTS[@]}"; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        warn "端口 $port 已被占用"
        PORT_IN_USE=true
    fi
done

if [ "$PORT_IN_USE" = true ]; then
    warn "部分端口已被占用，可能会导致服务启动失败"
    read -p "是否继续? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        info "已取消启动"
        exit 0
    fi
fi

# 构建并启动服务
step "6. 构建Docker镜像..."
docker-compose build --parallel 2>&1 | tee logs/build.log || {
    error "构建失败，请检查日志: logs/build.log"
    exit 1
}
info "✓ Docker镜像构建完成"

step "7. 启动服务..."
docker-compose up -d 2>&1 | tee logs/startup.log || {
    error "启动失败，请检查日志: logs/startup.log"
    exit 1
}

# 等待服务就绪
step "8. 等待服务就绪..."
sleep 5

# 检查服务状态
step "9. 检查服务状态..."
echo ""
docker-compose ps

echo ""
echo "================================"
echo ""

# 检查关键服务
SERVICES_OK=true

info "检查关键服务..."

# 检查PostgreSQL
if docker-compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
    info "  ✓ PostgreSQL 运行正常"
else
    warn "  ✗ PostgreSQL 可能未就绪"
    SERVICES_OK=false
fi

# 检查Redis
if docker-compose exec -T redis redis-cli ping >/dev/null 2>&1; then
    info "  ✓ Redis 运行正常"
else
    warn "  ✗ Redis 可能未就绪"
    SERVICES_OK=false
fi

# 检查后端API
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    info "  ✓ 后端API 运行正常"
else
    warn "  ✗ 后端API 可能未就绪（首次启动需要更长时间）"
    SERVICES_OK=false
fi

echo ""
echo "================================"
echo ""

if [ "$SERVICES_OK" = true ]; then
    echo -e "${GREEN}🎉 所有服务启动成功！${NC}"
else
    echo -e "${YELLOW}⚠️  部分服务可能未就绪，请等待几分钟后重试${NC}"
fi

echo ""
echo "📍 服务访问地址："
echo "   前端界面:     http://localhost:3000"
echo "   后端API:      http://localhost:8000"
echo "   API文档:      http://localhost:8000/docs"
echo "   Flower监控:   http://localhost:5555"
echo "   MinIO控制台:  http://localhost:9001"
echo "   Neo4j浏览器:  http://localhost:7474"
echo ""
echo "📝 常用命令："
echo "   查看日志:     docker-compose logs -f [service]"
echo "   停止服务:     docker-compose down"
echo "   重启服务:     docker-compose restart [service]"
echo "   进入容器:     docker-compose exec [service] bash"
echo ""
echo "💡 提示："
echo "   - 首次启动可能需要下载镜像，请耐心等待"
echo "   - 如果服务未就绪，请等待1-2分钟后刷新页面"
echo "   - 查看详细日志: tail -f logs/startup.log"
echo ""
