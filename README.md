# 飞书 OpenClaw 智能对话集成系统

> 一个完整的飞书机器人与本地 AI Agent 的双向通信解决方案，实现飞书用户与本地部署的 AI 系统进行智能对话。

---

## 目录

- [1. 项目背景](#1-项目背景)
- [2. 快速开始](#2-快速开始)
- [3. 系统架构](#3-系统架构)
- [4. 技术架构](#4-技术架构)
- [5. 功能需求](#5-功能需求)
- [6. 数据库设计](#6-数据库设计)
- [7. API 接口文档](#7-api-接口文档)
- [8. 配置说明](#8-配置说明)
- [9. 服务管理](#9-服务管理)
- [10. 故障排查](#10-故障排查)
- [11. 部署与运维](#11-部署与运维)
- [12. 扩展方向](#12-扩展方向)
- [13. 附录](#13-附录)

---

## 1. 项目背景

本方案实现了一个完整的飞书机器人与本地 AI Agent 的双向通信集成，让飞书用户可以通过对话的方式与本地部署的 AI 系统进行交互。

**为什么需要这个方案？**

1. **企业内网环境**：本地 AI 系统通常部署在内网，无法直接被外部访问
2. **飞书作为入口**：企业普遍使用飞书作为沟通工具，需要将 AI 能力集成到飞书中
3. **云中转方案**：通过公网服务器作为中转，实现飞书与本地系统的通信
4. **智能对话**：利用 OpenClaw 的 Agent 能力，提供上下文感知的智能回复

### 核心特性

- 🌐 **云中转架构**：通过公网服务器中转，解决内网访问问题
- 🤖 **智能对话**：集成 OpenClaw Agent，支持上下文感知的智能回复
- 🔄 **双线程处理**：消息获取和处理并行执行，提高效率
- 💬 **直接回复**：本地服务直接调用飞书 API，无需经过公网服务器
- 📊 **完整管理**：提供启动、停止、重启、状态检查等完整管理功能

---

## 2. 快速开始

### 2.1 前置要求

#### 系统要求
- **公网服务器**: Ubuntu 20.04+，1核2G以上
- **本地服务器**: Ubuntu 20.04+，4核8G以上（运行 OpenClaw）
- **Python 版本**: 3.8+

#### 必要软件
```bash
# 公网服务器
sudo apt update
sudo apt install python3 python3-pip nginx

# 本地服务器
sudo apt update
sudo apt install python3 python3-pip python3-venv nodejs npm
```

### 2.2 步骤1：部署飞书应用

1. **创建飞书应用**
   - 访问 [飞书开放平台](https://open.feishu.cn/)
   - 创建企业自建应用
   - 获取 `App ID` 和 `App Secret`

2. **配置事件订阅**
   - 进入应用管理 → 事件订阅
   - 添加订阅事件：`im.message.receive_v1`
   - 配置回调URL：`http://your-public-ip:3000/webhook`
   - 设置验证令牌

3. **获取必要信息**
   ```
   App ID: cli_xxxxx
   App Secret: xxxxx
   Verification Token: xxxxx
   ```

### 2.3 步骤2：部署公网服务 (feishu-listerner-server)

```bash
# 1. 上传代码到公网服务器
scp -r feishu-listerner-server user@your-public-ip:/home/user/

# 2. SSH 登录公网服务器
ssh user@your-public-ip

# 3. 进入目录
cd /home/user/feishu-listerner-server

# 4. 创建环境变量
cp .env.example .env
vim .env

# 配置内容：
# FEISHU_VERIFICATION_TOKEN=你的验证令牌
# VERIFICATION_CODE=你的内部验证码
# PORT=3000
# DB_PATH=./feishu_messages.db
# LOG_LEVEL=INFO

# 5. 安装依赖
pip3 install -r requirements.txt

# 6. 启动服务
chmod +x *.sh
./start.sh

# 7. 验证服务
curl http://localhost:3000/health
```

**Nginx 反向代理（推荐）**：

> 注意：以下 Nginx 配置仅在需要 HTTPS 访问时使用。如果只需要 HTTP 访问，可以跳过此步骤。

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.4 步骤3：部署本地 OpenClaw

```bash
# 1. 安装 OpenClaw
npm install -g @openclaw/cli

# 2. 初始化 OpenClaw
openclaw setup

# 3. 启动 Gateway
openclaw gateway start

# 4. 验证 Gateway
curl http://127.0.0.1:18789/health

# 5. 配置 Agent（如果还没有）
openclaw agent create secretary-agent

# 6. 启用 OpenAI Chat Completions 端点
openclaw config set gateway.http.endpoints.chatCompletions.enabled true

# 7. 获取 Gateway Token
openclaw config get gateway.auth.token

# 8. 重启 Gateway 使配置生效
openclaw gateway restart
```

### 2.5 步骤4：部署本地回复服务 (feishu-resp-server)

```bash
# 1. 进入目录
cd feishu-resp-server

# 2. 初始化环境（创建虚拟环境）
chmod +x *.sh
./setup.sh

# 3. 配置环境变量
vim .env

# 配置内容：
# FEISHU_LISTENER_URL=http://your-public-ip:3000
# VERIFICATION_CODE=你的内部验证码
# FEISHU_APP_ID=cli_xxxxx
# FEISHU_APP_SECRET=xxxxx
# OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
# OPENCLAW_GATEWAY_TOKEN=你的Gateway Token
# OPENCLAW_AGENT_ID=secretary-agent
# OPENCLAW_ENABLED=true
# CHECK_INTERVAL=3
# LOCAL_DB_PATH=./feishu_local_messages.db

# 4. 启动服务
./start.sh

# 5. 查看状态
./status.sh
```

### 2.6 步骤5：端到端测试

1. **在飞书中发送消息**
   ```
   你好
   ```

2. **查看公网服务日志**
   ```bash
   ssh user@your-public-ip
   cd /home/user/feishu-listerner-server
   tail -f app.log
   ```

3. **查看本地服务日志**
   ```bash
   tail -f logs/service.log
   ```

4. **检查 OpenClaw Gateway**
   ```bash
   openclaw gateway status
   ```

5. **验证 Agent 对话**
   ```bash
   # 测试 OpenClaw API
   curl -X POST http://127.0.0.1:18789/v1/chat/completions \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "openclaw:secretary-agent",
       "messages": [{"role": "user", "content": "你好"}]
     }'
   ```

---

## 3. 系统架构

```
┌─────────────┐
│  飞书用户    │
└──────┬──────┘
       │
       │ HTTP/HTTPS
       ↓
┌─────────────────────────────────────┐
│  公网服务器 (feishu-listerner)      │
│  - 接收飞书回调                     │
│  - 存储消息到数据库                 │
│  - 提供 API 查询接口               │
└──────┬──────────────────────────────┘
       │ HTTP API
       ↓
┌─────────────────────────────────────┐
│  本地服务 (feishu-resp-server)      │
│  - 线程1: 从公网服务获取消息         │
│  - 线程2: 处理消息并调用 AI Agent    │
│  - 直接回复飞书用户                 │
└──────┬──────────────────────────────┘
       │ HTTP API
       ↓
┌─────────────────────────────────────┐
│  OpenClaw Gateway                  │
│  - OpenAI 兼容 API                │
│  - Agent 会话管理                  │
│  - 消息路由                        │
└──────┬──────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────┐
│  OpenClaw Agent (secretary-agent)   │
│  - 智能对话处理                    │
│  - 上下文记忆                      │
│  - 工具调用                        │
└─────────────────────────────────────┘
```

---

## 4. 技术架构

### 4.1 整体架构设计

系统采用 **云中转架构**，由两部分组成：

1. **公网监听服务 (feishu-listerner-server)**
   - 部署在公网服务器，可被飞书平台访问
   - 接收飞书平台的事件回调
   - 存储消息到本地数据库
   - 提供 API 接口供本地服务查询

2. **本地回复服务 (feishu-resp-server)**
   - 部署在内网服务器，运行 OpenClaw
   - 从公网服务获取未处理消息
   - 调用 OpenClaw Agent 生成智能回复
   - 直接通过飞书 API 回复用户

### 4.2 技术栈选型

#### 后端服务
- **Python 3.x**：主要开发语言
- **Flask**：Web 框架（公网服务）
- **SQLite**：轻量级数据库
- **Threading**：多线程处理
- **Requests**：HTTP 客户端

#### AI 集成
- **OpenClaw**：本地 AI Agent 平台
- **OpenAI 兼容 API**：标准化接口
- **Secretary Agent**：智能对话 Agent

#### 部署架构
- **云服务器**：中转服务（公网可访问）
- **本地服务器**：AI 系统和 OpenClaw（内网）

### 4.3 双线程架构

**线程1 - 消息获取线程**
- 定期从公网服务获取未处理消息
- 保存到本地数据库
- 标记远程消息为已处理
- 间隔：1秒

**线程2 - 消息处理线程**
- 从本地数据库按 FIFO 顺序获取消息
- 调用 OpenClaw Agent 生成回复
- 直接发送回复给飞书用户
- 持续运行

### 4.4 消息流程

```
1. 用户发送消息到飞书
   ↓
2. 飞书服务器回调公网服务
   ↓
3. 公网服务接收并存储消息
   ↓
4. 本地服务获取消息（线程1）
   ↓
5. 本地服务处理消息（线程2）
   ↓
6. 调用 OpenClaw Agent
   ↓
7. Agent 生成智能回复
   ↓
8. 本地服务直接回复飞书用户
```

### 4.5 数据流

```
飞书 → 公网服务器 → 本地数据库 → Agent 处理 → 飞书 API → 用户
         ↑                                                            ↓
         └────────────────────────── 验证码验证 ←─────────────────────┘
```

---

## 5. 功能需求

### 5.1 消息接收功能

- **事件订阅**: 订阅飞书平台的 `im.message.receive_v1` 事件
- **回调配置**: 配置回调URL为 `http://[server]:3000/webhook`，支持飞书的验证挑战机制
- **消息验证**: 验证来自飞书的回调请求，确保安全性
- **唯一标识获取**: 从飞书消息中提取以下唯一标识信息
  - `message_id`: 消息唯一ID
  - `sender_id`: 发送者唯一ID (user_id 或 union_id)
  - `chat_id`: 聊天会话唯一ID
- **数据存储**: 将接收到的消息存储到 SQLite 数据库
  - 消息ID、发送者ID、聊天ID、消息内容
  - 消息处理状态跟踪（已处理/未处理）

### 5.2 消息处理功能

- **未处理消息查询**: 提供 API 接口供本地 OpenClaw 查询未处理的消息
- **消息状态管理**: 标记消息为已处理状态
- **安全认证**: 通过验证码保护内部 API 接口

### 5.3 消息回复功能

- **回复存储**: 将待发送的回复消息存储到数据库
- **待发送队列**: 提供 API 接口查询待发送的回复消息
- **发送状态跟踪**: 标记消息为已发送状态

### 5.4 会话管理功能

- 使用 `sender_id` 作为会话标识
- OpenClaw 自动维护对话上下文
- 支持多用户并发对话
- 每个用户独立的会话历史

### 5.5 消息格式处理

- **多类型消息支持**: 飞书消息可能是文本、富文本、图片、文件等多种类型，需要解析并存储消息类型
- **富媒体消息处理**:
  - 解析消息类型字段 (message_type)，区分文本、图片、富文本等
  - 对于附件类消息，提取并存储附件URL或ID到attachments字段
  - 保存原始消息结构，以便后续处理不同类型的回复
- **消息内容存储**:
  - 主要内容仍存储在content字段
  - 附件和多媒体信息存储在单独的字段中
  - 保留消息的元数据信息（如消息类型、附件列表等）

---

## 6. 数据库设计

### 6.1 数据库选型

系统使用 **SQLite** 作为数据库，原因：
- 轻量级，无需额外安装数据库服务
- 文件存储，便于备份和迁移
- 对于消息队列场景，性能足够
- 支持事务，保证数据一致性

### 6.2 incoming_messages 表（接收消息表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| timestamp | DATETIME | 接收时间 |
| message_id | TEXT | 飞书消息ID |
| sender_id | TEXT | 发送者ID |
| chat_id | TEXT | 聊天会话ID |
| content | TEXT | 消息内容 |
| message_type | TEXT | 消息类型（text/image/rich_text/file等） |
| attachments | TEXT | 附件信息（JSON格式） |
| processed | BOOLEAN | 是否已处理 |
| response_sent | BOOLEAN | 是否已回复 |
| raw_data | TEXT | 原始消息数据 |

### 6.3 outgoing_messages 表（发送消息表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| timestamp | DATETIME | 创建时间 |
| recipient_id | TEXT | 接收者ID |
| content | TEXT | 消息内容 |
| message_type | TEXT | 消息类型 |
| attachments | TEXT | 附件信息（JSON格式） |
| status | TEXT | 发送状态 |
| sent_at | DATETIME | 发送时间 |

### 6.4 索引建议

```sql
-- 提高未处理消息查询性能
CREATE INDEX idx_incoming_processed ON incoming_messages(processed);
CREATE INDEX idx_incoming_timestamp ON incoming_messages(timestamp);

-- 提高待发送消息查询性能
CREATE INDEX idx_outgoing_status ON outgoing_messages(status);
CREATE INDEX idx_outgoing_timestamp ON outgoing_messages(timestamp);

-- 提高消息去重性能
CREATE INDEX idx_incoming_message_id ON incoming_messages(message_id);
```

### 6.5 数据库维护

```bash
# 清理旧消息（公网服务）
sqlite3 feishu_messages.db "DELETE FROM incoming_messages WHERE processed = 1 AND timestamp < datetime('now', '-30 days');"

# 清理旧消息（本地）
sqlite3 feishu_local_messages.db "DELETE FROM incoming_messages WHERE processed = 1 AND timestamp < datetime('now', '-30 days');"

# 优化数据库
sqlite3 *.db "VACUUM;"

# 重建索引
sqlite3 feishu_local_messages.db "REINDEX;"
```

---

## 7. API 接口文档

所有内部API接口都需要在请求头中添加验证码：

```
X-Verification-Code: your_verification_code
```

### 7.1 飞书回调接口

#### GET/POST /webhook

**说明**: 飞书事件回调入口，支持验证挑战和消息接收

**验证挑战（GET）**:
```json
{
  "challenge": "xxxx",
  "token": "xxxx",
  "type": "url_verification"
}
```

**消息事件（POST）**:
```json
{
  "header": {
    "event_id": "xxxx",
    "event_type": "im.message.receive_v1",
    "create_time": "1234567890",
    "tenant_key": "xxxx",
    "app_id": "xxxx"
  },
  "event": {
    "message": {
      "message_id": "om_xxx",
      "chat_id": "oc_xxx",
      "chat_type": "p2p",
      "create_time": "1234567890",
      "content": "{\"text\":\"你好\"}",
      "message_type": "text",
      "sender": {
        "sender_id": {
          "open_id": "ou_xxx",
          "union_id": "on_xxx",
          "user_id": "xxxx"
        },
        "sender_type": "user"
      }
    }
  }
}
```

### 7.2 消息管理接口

#### GET /api/messages/unprocessed

**说明**: 获取未处理的飞书消息

**参数**:
- `limit`: 返回数量，默认100

**返回示例**:
```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "id": 1,
      "message_id": "om_xxx",
      "sender_id": "ou_xxx",
      "chat_id": "oc_xxx",
      "content": "消息内容",
      "message_type": "text",
      "processed": 0
    }
  ]
}
```

#### POST /api/messages/{message_id}/mark-processed

**说明**: 标记消息为已处理

**参数**:
- `message_id`: 消息ID

**返回**:
```json
{
  "code": 0,
  "msg": "success"
}
```

#### GET /api/messages/outgoing

**说明**: 获取待发送的回复消息

**参数**:
- `limit`: 返回数量，默认100

**返回示例**:
```json
{
  "code": 0,
  "msg": "success",
  "data": [
    {
      "id": 1,
      "recipient_id": "ou_xxx",
      "content": "回复内容",
      "message_type": "text",
      "status": "pending"
    }
  ]
}
```

#### POST /api/messages/outgoing/{message_id}/mark-sent

**说明**: 标记回复为已发送

**参数**:
- `message_id`: 消息ID

**返回**:
```json
{
  "code": 0,
  "msg": "success"
}
```

#### POST /api/messages/reply

**说明**: 添加新的回复消息到发送队列

**请求头**:
```
Content-Type: application/json
X-Verification-Code: your_verification_code
```

**请求体**:
```json
{
  "recipient_id": "ou_xxx",
  "content": "回复内容",
  "message_type": "text"
}
```

**返回**:
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "id": 1
  }
}
```

### 7.3 系统接口

#### GET /health

**说明**: 服务健康检查

**返回**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-05T10:30:00Z"
}
```

---

## 8. 配置说明

### 8.1 公网服务配置

#### 环境变量

| 参数 | 说明 | 示例 |
|------|------|------|
| FEISHU_VERIFICATION_TOKEN | 飞书验证令牌 | `your_token_here` |
| VERIFICATION_CODE | 内部验证码 | `your_code_here` |
| PORT | 服务端口 | `3000` |
| DB_PATH | 数据库路径 | `./feishu_messages.db` |
| LOG_LEVEL | 日志级别 | `INFO` |

#### .env.example
```env
# 飞书验证令牌（从飞书开发者后台获取）
FEISHU_VERIFICATION_TOKEN=your_token_here

# 内部验证码（用于保护API接口，自定义）
VERIFICATION_CODE=your_code_here

# 服务端口
PORT=3000

# 数据库路径
DB_PATH=./feishu_messages.db

# 日志级别
LOG_LEVEL=INFO
```

### 8.2 本地服务配置

#### 环境变量

| 参数 | 说明 | 默认值 |
|------|------|--------|
| FEISHU_LISTENER_URL | 公网服务地址 | `http://your-public-ip:3000` |
| VERIFICATION_CODE | 内部验证码 | - |
| CHECK_INTERVAL | 消息检查间隔（秒） | `3` |
| LOCAL_DB_PATH | 本地数据库路径 | `./feishu_local_messages.db` |
| FEISHU_APP_ID | 飞书应用ID | `cli_xxxxx` |
| FEISHU_APP_SECRET | 飞书应用密钥 | `xxxxx` |
| OPENCLAW_GATEWAY_URL | Gateway 地址 | `http://127.0.0.1:18789` |
| OPENCLAW_GATEWAY_TOKEN | Gateway 认证令牌 | - |
| OPENCLAW_AGENT_ID | Agent ID | `secretary-agent` |
| OPENCLAW_ENABLED | 是否启用 OpenClaw | `true` |

#### .env.example
```env
# 公网服务地址
FEISHU_LISTENER_URL=http://your-public-ip:3000

# 内部验证码（与公网服务一致）
VERIFICATION_CODE=your_code_here

# 消息检查间隔（秒）
CHECK_INTERVAL=3

# 本地数据库路径
LOCAL_DB_PATH=./feishu_local_messages.db

# 飞书应用配置
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# OpenClaw Gateway 配置
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=your_gateway_token_here
OPENCLAW_AGENT_ID=secretary-agent
OPENCLAW_ENABLED=true
```

### 8.3 飞书平台配置

#### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 `App ID` 和 `App Secret`

#### 2. 配置事件订阅

1. 在应用管理中进入"事件订阅"
2. 添加订阅事件：`im.message.receive_v1`
3. 配置回调URL：`http://your-server:3000/webhook`
4. 填写验证令牌（与 `.env` 中的 `FEISHU_VERIFICATION_TOKEN` 一致）
5. 点击"验证"按钮

#### 3. 发布应用

将应用发布到需要使用的群组或个人

---

## 9. 服务管理

### 9.1 公网服务管理

```bash
cd /home/user/feishu-listerner-server

# 启动
./start.sh

# 停止
./stop.sh

# 重启
./restart.sh

# 查看状态
./status.sh

# 查看日志
tail -f app.log
```

### 9.2 本地服务管理

```bash
cd feishu-resp-server

# 启动
./start.sh

# 停止
./stop.sh

# 重启
./restart.sh

# 查看状态
./status.sh

# 查看日志
tail -f logs/service.log
```

### 9.3 OpenClaw Gateway 管理

```bash
# 启动
openclaw gateway start

# 停止
openclaw gateway stop

# 重启
openclaw gateway restart

# 查看状态
openclaw gateway status

# 查看日志
openclaw gateway logs
```

### 9.4 日志查看和分析

#### 公网服务日志
```bash
tail -f /path/to/feishu-listerner-server/app.log
```

关键信息：
- `收到飞书事件` - 飞书回调正常
- `成功存储消息` - 消息存储成功
- `token验证失败` - 验证令牌错误

#### 本地服务日志
```bash
tail -f logs/service.log
```

关键信息：
- `从阿里服务获取到 X 条消息` - 消息获取正常
- `调用 OpenClaw agent` - AI 调用正常
- `OpenClaw 返回回复` - 回复生成成功
- `消息发送成功` - 飞书发送成功

#### OpenClaw Gateway 日志
```bash
openclaw gateway logs
```

关键信息：
- Gateway 启动状态
- Agent 调用日志
- 错误信息

---

## 10. 故障排查

### 10.1 常见问题及解决方案

#### 1. 服务无法启动

**症状**: `./start.sh` 报错

**解决**:
```bash
# 检查虚拟环境
ls -la venv/

# 重新初始化
rm -rf venv
./setup.sh

# 查看详细错误
tail -f logs/service.log
```

#### 2. OpenClaw 调用失败 (405错误)

**症状**: `405 Client Error: Method Not Allowed`

**原因**: OpenAI Chat Completions 端点未启用

**解决**:
```bash
# 启用端点
openclaw config set gateway.http.endpoints.chatCompletions.enabled true

# 重启 Gateway
openclaw gateway restart

# 验证
curl -X POST http://127.0.0.1:18789/v1/chat/completions
```

#### 3. 飞书消息接收不到

**检查清单**:
- [ ] 飞书应用是否已发布
- [ ] 回调URL是否正确
- [ ] 验证令牌是否匹配
- [ ] 公网服务是否运行
- [ ] 防火墙是否开放3000端口

#### 4. 本地服务获取不到消息

**检查清单**:
- [ ] FEISHU_LISTENER_URL 是否正确
- [ ] VERIFICATION_CODE 是否匹配
- [ ] 公网服务是否正常运行
- [ ] 网络是否通畅

#### 5. OpenClaw 返回空回复

**检查清单**:
- [ ] Gateway Token 是否正确
- [ ] Agent ID 是否存在
- [ ] Gateway 是否正常运行
- [ ] Chat Completions 端点是否启用

### 10.2 日志分析

#### 日志管理
- **日志文件自动轮转**：100MB
- **保留策略**：保留最近3个日志文件
- **定期归档旧日志**

#### 日志轮转策略
- 按大小轮转: 当日志文件达到指定大小（如100MB）时创建新文件
- 按时间轮转: 每天或每周创建新的日志文件
- 保留策略: 保留最近N个日志文件，自动删除旧文件

#### 敏感信息保护
- 日志中不应记录验证令牌、验证码等敏感信息
- 对消息内容进行适当脱敏处理
- 避免记录完整的用户ID或其他隐私信息

#### 日志级别控制
支持不同级别的日志输出（DEBUG/INFO/WARNING/ERROR）

### 10.3 性能优化

#### 1. 数据库优化
```bash
# 定期清理旧消息
sqlite3 feishu_local_messages.db "DELETE FROM incoming_messages WHERE processed = 1 AND timestamp < datetime('now', '-30 days');"

# 重建索引
sqlite3 feishu_local_messages.db "VACUUM;"
```

#### 2. 日志管理
- 日志文件自动轮转（100MB）
- 保留最近3个日志文件
- 定期归档旧日志

#### 3. 网络优化
- 使用 CDN 加速飞书 API
- 配置合理的超时时间
- 实现重试机制

### 10.4 异常场景测试

#### 网络中断测试
- 模拟网络连接中断，验证服务的重连机制
- 测试在长时间断网恢复后的数据同步能力

#### 飞书回调失败测试
- 模拟飞书服务器回调超时或失败的情况
- 验证服务是否能正确处理和记录回调失败的事件
- 测试重复回调的去重处理机制

#### 数据库连接失败测试
- 模拟数据库连接失败，验证服务的容错机制
- 测试数据库连接恢复后的自动重连功能
- 验证在数据库不可用期间的消息缓存或排队机制

#### 高并发压力测试
- 模拟大量并发消息同时到达的场景
- 测试服务在高负载下的稳定性和响应时间

#### 异常输入测试
- 输入异常或恶意构造的数据，验证输入验证机制
- 测试边界条件和非法参数的处理

---

## 11. 部署与运维

### 11.1 部署方式

#### 方式一：直接部署

```bash
# 上传代码到服务器
scp -r feishu-openclaw user@server:/path/to/

# SSH登录服务器
ssh user@server

# 进入目录
cd /path/to/feishu-openclaw

# 配置环境变量
cp .env.example .env
vim .env

# 启动服务
chmod +x *.sh
./start.sh
```

#### 方式二：使用 PM2（推荐）

```bash
# 安装 PM2
npm install -g pm2

# 启动服务
pm2 start app.py --name feishu-openclaw

# 查看状态
pm2 status

# 查看日志
pm2 logs feishu-openclaw

# 停止服务
pm2 stop feishu-openclaw

# 重启服务
pm2 restart feishu-openclaw

# 设置开机自启
pm2 startup
pm2 save
```

#### 方式三：使用 Systemd

创建服务文件 `/etc/systemd/system/feishu-openclaw.service`：

```ini
[Unit]
Description=Feishu OpenClaw Service
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/feishu-openclaw
Environment="PATH=/usr/bin"
ExecStart=/usr/bin/python3 /path/to/feishu-openclaw/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable feishu-openclaw
sudo systemctl start feishu-openclaw
sudo systemctl status feishu-openclaw
```

### 11.2 日常维护

#### 每日检查
```bash
# 查看服务状态
./status.sh

# 查看日志
tail -n 100 logs/service.log
```

#### 每周维护
```bash
# 优化数据库
sqlite3 feishu_local_messages.db "VACUUM;"

# 清理旧日志
rm -rf logs/*.log.*
```

#### 每月备份
```bash
# 备份数据库
cp feishu_local_messages.db backup/feishu_local_messages_$(date +%Y%m%d).db
```

### 11.3 升级流程

1. **停止服务**
   ```bash
   ./stop.sh
   ```

2. **备份数据**
   ```bash
   cp feishu_local_messages.db backup/
   ```

3. **更新代码**
   ```bash
   git pull
   ```

4. **更新依赖**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt --upgrade
   ```

5. **启动服务**
   ```bash
   ./start.sh
   ```

6. **验证功能**
   ```bash
   ./status.sh
   ```

### 11.4 安全建议

1. **敏感信息保护**
   - 不要将 `.env` 文件提交到版本控制
   - 使用强密码作为验证码
   - 定期更换 Token

2. **网络安全**
   - 使用 HTTPS 协议
   - 配置防火墙规则
   - 限制访问 IP

3. **访问控制**
   - 使用强密码
   - 定期审计访问日志
   - 实施最小权限原则

4. **数据安全**
   - 定期备份数据库
   - 加密敏感配置信息
   - 使用安全的数据库连接

### 11.5 监控与告警

#### 服务状态监控

```bash
# 公网服务
cd feishu-listerner-server
./status.sh

# 本地服务
cd feishu-resp-server
./status.sh

# OpenClaw Gateway
openclaw gateway status
```

#### 性能监控

- 监控服务响应时间
- 监控资源占用情况
- 监控消息处理速度
- 监控错误率

#### 告警配置

建议配置以下告警：
- 服务停止告警
- 消息积压告警
- 错误率过高告警
- 资源占用过高告警

---

## 12. 扩展方向

### 12.1 多 Agent 支持

- 根据消息类型路由到不同 Agent
- 支持并发处理多个会话
- Agent 间协作

### 12.2 富媒体消息

- 支持图片、文件处理
- 语音消息识别
- 视频消息处理

### 12.3 消息队列升级

- 使用 Redis 替代 SQLite
- 实现消息持久化
- 支持分布式部署

### 12.4 监控系统

- 集成 Prometheus 监控
- 配置告警规则
- 实时性能监控

### 12.5 多机器人支持

支持多个飞书机器人的同时接入，实现不同机器人消息的独立处理。

> 详细需求请查看 [TODO.md](TODO.md)

---

## 13. 附录

### 13.2 环境变量清单

#### 公网服务环境变量
```env
FEISHU_VERIFICATION_TOKEN=your_token_here
VERIFICATION_CODE=your_code_here
PORT=3000
DB_PATH=./feishu_messages.db
LOG_LEVEL=INFO
```

#### 本地服务环境变量
```env
FEISHU_LISTENER_URL=http://your-public-ip:3000
VERIFICATION_CODE=your_code_here
CHECK_INTERVAL=3
LOCAL_DB_PATH=./feishu_local_messages.db
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_GATEWAY_TOKEN=your_gateway_token_here
OPENCLAW_AGENT_ID=secretary-agent
OPENCLAW_ENABLED=true
```

### 13.3 测试方案

#### 健康检查测试
```bash
curl http://localhost:3000/health
```

#### API接口测试
```bash
# 测试未处理消息接口
curl -H "X-Verification-Code: [your_verification_code]" \
  http://[server]:3000/api/messages/unprocessed

# 测试回复消息接口
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-Verification-Code: [your_verification_code]" \
  -d '{"recipient_id":"[recipient]","content":"test message"}' \
  http://[server]:3000/api/messages/reply
```

#### 飞书回调测试
使用飞书开发者后台的"验证URL"功能进行测试

#### 端口连通性测试
```bash
netstat -tlnp | grep :3000
# 或
ss -tlnp | grep :3000
```

### 13.4 编码与国际化

- **字符编码**: 数据库、API接口和消息内容均采用UTF-8编码
- **中文支持**: 确保中文及其他多字节字符的正确存储和传输
- **数据库编码**: SQLite数据库使用UTF-8编码存储消息内容
- **API响应编码**: 所有API接口响应均使用UTF-8编码

### 13.5 常见问题 FAQ

**Q: 为什么需要公网服务器？**

A: 本地 AI 系统通常部署在内网，无法被外部直接访问。通过公网服务器作为中转，可以实现飞书与本地系统的通信。

**Q: 为什么使用双线程架构？**

A: 消息获取和处理并行执行，可以提高整体效率，避免相互阻塞。

**Q: OpenClaw 调用失败会怎样？**

A: 系统会返回包含错误信息的提示，帮助快速定位问题，不会导致服务崩溃。

**Q: 如何实现多 Agent 支持？**

A: 修改 `OPENCLAW_AGENT_ID` 配置即可切换不同的 Agent。

### 13.6 相关资源

- [飞书开放平台](https://open.feishu.cn/)
- [OpenClaw 官方文档](https://docs.openclaw.ai/)
- [Flask 官方文档](https://flask.palletsprojects.com/)
- [Python 官方文档](https://docs.python.org/)

### 13.7 许可证

MIT License