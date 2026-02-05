#!/bin/bash

# 飞书沟通服务停止脚本

echo "正在停止飞书沟通服务..."

# 查找并停止进程
if pgrep -f "python3 app.py" > /dev/null; then
    pkill -f "python3 app.py"
    sleep 2
    
    # 检查是否停止成功
    if pgrep -f "python3 app.py" > /dev/null; then
        echo "警告: 服务未能正常停止，尝试强制停止..."
        pkill -9 -f "python3 app.py"
        sleep 1
    fi
    
    echo "服务已停止"
else
    echo "服务未运行"
fi