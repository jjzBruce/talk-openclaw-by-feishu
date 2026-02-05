# 快速开始指南

## 首次部署

### 1. 初始化环境

```bash
cd feishu-resp-server
./setup.sh
```

### 2. 配置环境变量

```bash
vim .env
```

必须配置的参数：
- `FEISHU_LISTENER_URL` - 公网服务器地址
- `VERIFICATION_CODE` - 验证码
- `FEISHU_APP_ID` - 飞书应用ID
- `FEISHU_APP_SECRET` - 飞书应用密钥
- `OPENCLAW_GATEWAY_TOKEN` - OpenClaw Gateway Token

### 3. 启动服务

```bash
./start.sh
```

### 4. 检查状态

```bash
./status.sh
```

### 5. 查看日志

```bash
tail -f logs/service.log
```

## 日常操作

### 启动服务
```bash
./start.sh
```

### 停止服务
```bash
./stop.sh
```

### 重启服务
```bash
./restart.sh
```

### 查看状态
```bash
./status.sh
```

### 查看日志
```bash
tail -f logs/service.log
```

## 获取 OpenClaw Gateway Token

```bash
openclaw config get gateway.auth.token
```

## 常见问题

### Q: 虚拟环境不存在？
```bash
./setup.sh
```

### Q: 如何重新初始化？
```bash
rm -rf venv
./setup.sh
```

### Q: 服务启动失败？
```bash
# 查看日志
tail -f logs/service.log

# 检查配置
./status.sh
```

### Q: 如何更新依赖？
```bash
source venv/bin/activate
pip install -r requirements.txt --upgrade
```