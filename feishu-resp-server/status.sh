#!/bin/bash

# 飞书回复服务状态检查脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查进程状态
if [ -f feishu_resp_server.pid ]; then
    PID=$(cat feishu_resp_server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "✓ 服务运行中"
        echo "  PID: $PID"
        echo "  启动时间: $(ps -p $PID -o lstart=)"
        echo "  CPU: $(ps -p $PID -o %cpu=)%"
        echo "  内存: $(ps -p $PID -o %mem=)%"
    else
        echo "✗ 服务未运行 (PID文件存在但进程不存在)"
        rm -f feishu_resp_server.pid
    fi
else
    PIDS=$(pgrep -f "feishu_resp_server.py")
    if [ ! -z "$PIDS" ]; then
        echo "✓ 服务运行中 (PID: $PIDS)"
    else
        echo "✗ 服务未运行"
    fi
fi

# 显示配置
echo ""
echo "配置信息:"
if [ -f .env ]; then
    if [ -d "venv" ]; then
        source venv/bin/activate
        python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(f\"  飞书监听地址: {os.getenv('FEISHU_LISTENER_URL', 'N/A')}\"); print(f\"  OpenClaw: {'启用' if os.getenv('OPENCLAW_ENABLED', 'false').lower() in ('true', '1', 'yes') else '禁用'}\"); print(f\"  Agent ID: {os.getenv('OPENCLAW_AGENT_ID', 'N/A')}\")" 2>/dev/null || echo "  无法读取配置"
    else
        echo "  虚拟环境不存在，无法读取配置"
    fi
else
    echo "  .env 文件不存在"
fi

# 显示最近的日志
echo ""
echo "最近日志 (最后10行):"
if [ -f logs/service.log ]; then
    tail -n 10 logs/service.log
else
    echo "  日志文件不存在"
fi