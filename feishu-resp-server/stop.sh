#!/bin/bash

# 飞书回复服务停止脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "正在停止飞书回复服务..."

if [ -f feishu_resp_server.pid ]; then
    PID=$(cat feishu_resp_server.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        # 等待进程结束
        for i in {1..10}; do
            if ! ps -p $PID > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # 强制终止（如果需要）
        if ps -p $PID > /dev/null 2>&1; then
            kill -9 $PID
        fi
        
        rm -f feishu_resp_server.pid
        echo "服务已停止"
    else
        echo "服务未运行"
        rm -f feishu_resp_server.pid
    fi
else
    # 尝试通过进程名查找并终止
    PIDS=$(pgrep -f "feishu_resp_server.py")
    if [ ! -z "$PIDS" ]; then
        kill $PIDS
        echo "服务已停止 (通过进程名终止)"
    else
        echo "服务未运行"
    fi
fi