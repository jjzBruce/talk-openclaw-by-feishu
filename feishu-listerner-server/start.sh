#!/bin/bash

# 飞书沟通服务启动脚本

# 检查.env文件是否存在
if [ ! -f .env ]; then
    echo "错误: .env 文件不存在，请先创建配置文件"
    echo "可以复制 .env.example 文件并修改配置项"
    exit 1
fi

# 加载环境变量
export $(cat .env | grep -v '^#' | xargs)

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

# 检查依赖
if ! python3 -c "import flask" 2>/dev/null; then
    echo "正在安装依赖..."
    pip3 install -r requirements.txt
fi

# 检查端口是否被占用
PORT=${PORT:-3000}
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "警告: 端口 $PORT 已被占用"
    echo "正在尝试停止旧进程..."
    pkill -f "python3 app.py"
    sleep 2
fi

# 启动服务
echo "正在启动飞书沟通服务..."
echo "端口: $PORT"
echo "日志文件: app.log"

nohup python3 app.py > app.log 2>&1 &

sleep 2

# 检查服务是否启动成功
if pgrep -f "python3 app.py" > /dev/null; then
    echo "服务启动成功!"
    echo "PID: $(pgrep -f 'python3 app.py')"
    echo "健康检查: curl http://localhost:$PORT/health"
else
    echo "服务启动失败，请查看日志: tail -f app.log"
    exit 1
fi