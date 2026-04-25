#!/bin/bash
# VFX-Agent 启动脚本
# 同时启动 backend (FastAPI) 和 frontend (Vite)

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查 .env 文件
check_env() {
    if [ ! -f "$BACKEND_DIR/.env" ]; then
        log_warn "backend/.env 不存在，正在从 .env.example 创建..."
        if [ -f "$BACKEND_DIR/.env.example" ]; then
            cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
            log_success "已创建 backend/.env"
            log_warn "请编辑 backend/.env 配置你的 API keys 后重新启动"
        else
            log_error "backend/.env.example 不存在"
            exit 1
        fi
    fi
}

# 检查依赖
check_deps() {
    log_info "检查依赖..."
    
    # Backend: Python + pip packages
    if ! command -v python &> /dev/null; then
        log_error "Python 未安装"
        exit 1
    fi
    
    if [ ! -d "$BACKEND_DIR/.venv" ] && [ ! -f "$BACKEND_DIR/requirements.txt" ]; then
        log_warn "Backend 依赖未安装，正在安装..."
        cd "$BACKEND_DIR"
        pip install -r requirements.txt
        log_success "Backend 依赖安装完成"
    fi
    
    # Frontend: npm install
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        log_warn "Frontend 依赖未安装，正在安装..."
        cd "$FRONTEND_DIR"
        npm install
        log_success "Frontend 依赖安装完成"
    fi
    
    # Playwright browsers
    if ! python -c "from playwright.sync_api import sync_playwright; print('ok')" 2>/dev/null; then
        log_warn "Playwright 浏览器未安装，正在安装..."
        cd "$BACKEND_DIR"
        playwright install chromium
        log_success "Playwright 浏览器安装完成"
    fi
}

# PID 文件路径
BACKEND_PID_FILE="$PROJECT_ROOT/.backend.pid"
FRONTEND_PID_FILE="$PROJECT_ROOT/.frontend.pid"

# 启动 backend
start_backend() {
    log_info "启动 Backend (FastAPI)..."
    cd "$BACKEND_DIR"
    
    # 使用 nohup 在后台运行
    nohup uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload > "$PROJECT_ROOT/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$BACKEND_PID_FILE"
    
    # 等待服务启动
    sleep 2
    if curl -s http://localhost:8000/health > /dev/null; then
        log_success "Backend 启动成功 (PID: $BACKEND_PID)"
        log_info "Backend URL: http://localhost:8000"
    else
        log_error "Backend 启动失败，请查看 backend.log"
        exit 1
    fi
}

# 启动 frontend
start_frontend() {
    log_info "启动 Frontend (Vite)..."
    cd "$FRONTEND_DIR"
    
    # 使用 nohup 在后台运行
    nohup npm run dev > "$PROJECT_ROOT/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$FRONTEND_PID_FILE"
    
    # 等待服务启动
    sleep 3
    if curl -s http://localhost:5173 > /dev/null; then
        log_success "Frontend 启动成功 (PID: $FRONTEND_PID)"
        log_info "Frontend URL: http://localhost:5173"
    else
        log_warn "Frontend 可能仍在启动中，请稍候查看 frontend.log"
    fi
}

# 停止服务
stop_services() {
    log_info "停止服务..."
    
    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 $BACKEND_PID 2>/dev/null; then
            kill $BACKEND_PID
            log_success "Backend 已停止"
        fi
        rm -f "$BACKEND_PID_FILE"
    fi
    
    if [ -f "$FRONTEND_PID_FILE" ]; then
        FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            kill $FRONTEND_PID
            log_success "Frontend 已停止"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi
    
    # 清理可能残留的进程
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    
    log_success "所有服务已停止"
}

# 显示状态
show_status() {
    echo ""
    log_info "=== VFX-Agent 服务状态 ==="
    echo ""
    
    # Backend status
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "  Backend:  ${GREEN}运行中${NC}  http://localhost:8000"
    else
        echo -e "  Backend:  ${RED}未运行${NC}"
    fi
    
    # Frontend status
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo -e "  Frontend: ${GREEN}运行中${NC}  http://localhost:5173"
    else
        echo -e "  Frontend: ${RED}未运行${NC}"
    fi
    
    echo ""
    
    # PID info
    if [ -f "$BACKEND_PID_FILE" ]; then
        echo "  Backend PID: $(cat $BACKEND_PID_FILE)"
    fi
    if [ -f "$FRONTEND_PID_FILE" ]; then
        echo "  Frontend PID: $(cat $FRONTEND_PID_FILE)"
    fi
    
    echo ""
    echo "  日志文件:"
    echo "    backend.log  - Backend 输出"
    echo "    frontend.log - Frontend 输出"
    echo ""
}

# 显示帮助
show_help() {
    echo "VFX-Agent 启动脚本"
    echo ""
    echo "用法:"
    echo "  ./start.sh [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动 backend 和 frontend (默认)"
    echo "  stop      停止所有服务"
    echo "  status    显示服务状态"
    echo "  restart   重启所有服务"
    echo "  logs      显示日志 (tail -f)"
    echo "  help      显示此帮助"
    echo ""
    echo "示例:"
    echo "  ./start.sh          # 启动服务"
    echo "  ./start.sh start    # 启动服务"
    echo "  ./start.sh stop     # 停止服务"
    echo "  ./start.sh status   # 查看状态"
    echo "  ./start.sh logs     # 查看实时日志"
    echo ""
}

# 显示日志
show_logs() {
    log_info "显示实时日志 (Ctrl+C 退出)..."
    tail -f "$PROJECT_ROOT/backend.log" "$PROJECT_ROOT/frontend.log"
}

# 主逻辑
case "${1:-start}" in
    start)
        check_env
        check_deps
        start_backend
        start_frontend
        show_status
        ;;
    stop)
        stop_services
        ;;
    status)
        show_status
        ;;
    restart)
        stop_services
        sleep 1
        check_env
        check_deps
        start_backend
        start_frontend
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "未知命令: $1"
        show_help
        exit 1
        ;;
esac