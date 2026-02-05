#!/bin/bash

# 飞书回复服务重启脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "正在重启飞书回复服务..."

./stop.sh
sleep 2
./start.sh