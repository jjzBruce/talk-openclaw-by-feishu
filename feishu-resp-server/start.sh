#!/bin/bash

# 飞书回复服务启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在"
    echo "请先运行: ./setup.sh"
    exit 1
fi

# 激活虚拟环境
source venv/bin/activate

# 检查配置文件
if [ ! -f .env ]; then
    echo "错误: .env 文件不存在"
    echo "请从 .env.example 复制模板: cp .env.example .env"
    echo "然后编辑 .env 文件配置必要参数"
    exit 1
fi

# 确保日志目录存在
mkdir -p logs

# 检查服务是否已运行
if [ -f feishu_resp_server.pid ]; then
    PID=$(cat feishu_resp_server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "服务已在运行 (PID: $PID)"
        exit 1
    else
        rm -f feishu_resp_server.pid
    fi
fi

# 启动服务
echo "正在启动飞书回复服务..."
nohup python feishu_resp_server.py start > logs/service.log 2>&1 &
PID=$!

# 保存进程ID
echo $PID > feishu_resp_server.pid

# 等待服务启动
sleep 2

if ps -p $PID > /dev/null 2>&1; then
    echo "服务启动成功 (PID: $PID)"
    echo "日志文件: logs/service.log"
    echo "查看日志: tail -f logs/service.log"
else
    echo "服务启动失败，请查看日志: tail -f logs/service.log"
    rm -f feishu_resp_server.pid
    exit 1
fi