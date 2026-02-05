#!/bin/bash

# 虚拟环境初始化脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "  飞书回复服务 - 虚拟环境初始化"
echo "======================================"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python 3"
    exit 1
fi

echo "Python 版本: $(python3 --version)"

# 检查虚拟环境是否已存在
if [ -d "venv" ]; then
    echo "警告: 虚拟环境已存在"
    read -p "是否删除并重新创建? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "删除现有虚拟环境..."
        rm -rf venv
    else
        echo "使用现有虚拟环境"
        exit 0
    fi
fi

# 创建虚拟环境
echo "创建虚拟环境..."
python3 -m venv venv

if [ $? -ne 0 ]; then
    echo "错误: 创建虚拟环境失败"
    echo "请确保已安装 python3-venv: sudo apt install python3-venv"
    exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate

# 升级 pip
echo "升级 pip..."
pip install --upgrade pip

# 安装依赖
echo "安装依赖..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    if [ $? -eq 0 ]; then
        echo "依赖安装成功"
    else
        echo "错误: 依赖安装失败"
        exit 1
    fi
else
    echo "警告: requirements.txt 不存在"
fi

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo ""
    echo "======================================"
    echo "配置文件初始化"
    echo "======================================"
    if [ -f ".env.example" ]; then
        echo "从 .env.example 创建 .env 文件..."
        cp .env.example .env
        echo "已创建 .env 文件"
        echo ""
        echo "请编辑 .env 文件配置必要参数:"
        echo "  vim .env"
        echo ""
        echo "主要配置项:"
        echo "  FEISHU_LISTENER_URL - 飞书监听服务地址"
        echo "  VERIFICATION_CODE - 验证码"
        echo "  FEISHU_APP_ID - 飞书应用 ID"
        echo "  FEISHU_APP_SECRET - 飞书应用密钥"
        echo "  OPENCLAW_GATEWAY_TOKEN - OpenClaw Gateway Token"
    else
        echo "错误: .env.example 不存在"
        exit 1
    fi
fi

# 创建日志目录
mkdir -p logs

echo ""
echo "======================================"
echo "初始化完成!"
echo "======================================"
echo ""
echo "使用方法:"
echo "  激活虚拟环境: source venv/bin/activate"
echo "  启动服务:     ./start.sh"
echo "  停止服务:     ./stop.sh"
echo "  查看状态:     ./status.sh"
echo "  查看日志:     tail -f logs/service.log"
echo ""