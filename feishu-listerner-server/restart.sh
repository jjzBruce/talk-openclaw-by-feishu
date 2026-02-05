#!/bin/bash

# 飞书沟通服务重启脚本

echo "正在重启飞书沟通服务..."

# 先停止服务
./stop.sh

# 等待2秒
sleep 2

# 再启动服务
./start.sh