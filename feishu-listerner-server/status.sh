#!/bin/bash

# 飞书沟通服务状态检查脚本

# 检查进程状态
if pgrep -f "python3 app.py" > /dev/null; then
    PID=$(pgrep -f "python3 app.py")
    echo "✓ 服务运行中"
    echo "  PID: $PID"
    echo "  启动时间: $(ps -p $PID -o lstart=)"
    
    # 检查端口
    PORT=$(grep -E "^PORT=" .env 2>/dev/null | cut -d'=' -f2)
    PORT=${PORT:-3000}
    
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "  端口: $PORT ✓"
    else
        echo "  端口: $PORT ✗ (未监听)"
    fi
    
    # 检查健康状态
    echo ""
    echo "健康检查:"
    if command -v curl &> /dev/null; then
        curl -s http://localhost:$PORT/health | python3 -m json.tool 2>/dev/null || echo "  健康检查失败"
    else
        echo "  未安装 curl，无法检查健康状态"
    fi
    
else
    echo "✗ 服务未运行"
fi

# 显示最近的日志
echo ""
echo "最近日志 (最后10行):"
if [ -f app.log ]; then
    tail -n 10 app.log
else
    echo "  日志文件不存在"
fi