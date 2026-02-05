#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import time
import logging
import signal
import sys
from datetime import datetime
import sqlite3
from typing import Dict, List, Optional
import threading
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# 配置日志
logger = logging.getLogger('feishu_resp_server')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'logs/service.log',
    maxBytes=100*1024*1024,  # 100MB
    backupCount=3
)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

class DirectFeishuSender:
    """
    直接向飞书发送消息的类
    使用飞书官方API直接发送消息
    """
    
    def __init__(self, app_id: str = None, app_secret: str = None):
        """
        初始化发送器
        :param app_id: 飞书应用ID
        :param app_secret: 飞书应用密钥
        """
        self.app_id = app_id or os.environ.get('FEISHU_APP_ID')
        self.app_secret = app_secret or os.environ.get('FEISHU_APP_SECRET')
        self.access_token = None
        self.token_expire_time = 0
    
    def get_access_token(self) -> Optional[str]:
        """
        获取访问令牌
        """
        if self.access_token and datetime.now().timestamp() < self.token_expire_time - 60:
            # 令牌未过期且还有至少60秒有效期
            return self.access_token
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        
        headers = {
            "Content-Type": "application/json; charset=utf-8"
        }
        
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    self.access_token = result.get("tenant_access_token")
                    logger.info("访问令牌获取成功")
                    # 设置过期时间（减去60秒作为缓冲）
                    self.token_expire_time = datetime.now().timestamp() + result.get("expire", 7200) - 60
                    return self.access_token
                else:
                    logger.error(f"获取访问令牌失败: {result}")
                    return None
            else:
                logger.error(f"请求访问令牌失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"获取访问令牌异常: {e}")
            return None
    
    def send_message(self, recipient_id: str, content: str, message_type: str = 'text', receive_id_type: str = 'open_id') -> bool:
        """
        发送消息到飞书
        :param recipient_id: 接收者ID（默认使用 open_id）
        :param content: 消息内容
        :param message_type: 消息类型,默认为text
        :param receive_id_type: 接收者ID类型,默认为open_id（与消息接收时提取的ID类型保持一致）
        :return: 发送是否成功
        """
        access_token = self.get_access_token()
        if not access_token:
            logger.error("无法获取访问令牌,无法发送消息")
            return False
        
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # 构建消息内容
        if message_type == 'text':
            content_json = {
                "text": content
            }
        else:
            content_json = {
                "text": content  # 默认按文本处理
            }
        
        params = {
            "receive_id_type": receive_id_type
        }
        
        data = {
            "receive_id": recipient_id,
            "msg_type": "text",
            "content": json.dumps(content_json)
        }
        
        try:
            response = requests.post(url, headers=headers, params=params, json=data, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == 0:
                    logger.info(f"消息发送成功: {content[:50]}...")
                    return True
                else:
                    logger.error(f"消息发送失败: {result}")
                    return False
            else:
                logger.error(f"消息发送请求失败: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return False


class OpenClawGatewayClient:
    """
    OpenClaw Gateway 客户端
    通过 OpenAI 兼容 API 与 OpenClaw agent 交互
    """
    
    def __init__(self, gateway_url: str, gateway_token: str, agent_id: str):
        """
        初始化客户端
        :param gateway_url: OpenClaw Gateway URL
        :param gateway_token: Gateway 认证令牌
        :param agent_id: Agent ID
        """
        self.gateway_url = gateway_url
        self.gateway_token = gateway_token
        self.agent_id = agent_id
        self.chat_url = f"{gateway_url}/v1/chat/completions"
    
    def chat(self, message: str, user_id: str = None) -> str:
        """
        与 agent 对话
        :param message: 用户消息
        :param user_id: 用户ID（用于会话保持）
        :return: agent 的回复
        """
        headers = {
            'Authorization': f'Bearer {self.gateway_token}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': f'openclaw:{self.agent_id}',
            'messages': [
                {'role': 'user', 'content': message}
            ],
            'stream': False
        }
        
        if user_id:
            data['user'] = user_id
        
        try:
            response = requests.post(self.chat_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
        except requests.exceptions.RequestException as e:
            logger.error(f"调用 OpenClaw Gateway 失败: {e}")
            return None
        except (KeyError, IndexError) as e:
            logger.error(f"解析 OpenClaw 响应失败: {e}")
            logger.error(f"响应内容: {response.text if 'response' in locals() else 'N/A'}")
            return None

class FeishuReplyService:
    """
    飞书回复服务
    用于从公网服务器获取未处理的消息并进行处理和回复
    """
    
    def __init__(self):
        """
        初始化回复服务
        """
        self.running = False
        self.config = self.load_config()
        self.api_base_url = self.config.get('feishuListenerUrl', '')
        self.verification_code = self.config.get('verification_code')
        self.check_interval = self.config.get('check_interval', 3)  # 检查间隔（秒）
        self.local_db_path = self.config.get('local_db_path', './feishu_local_messages.db')
        
        # 初始化本地数据库
        self.init_local_db()
        
        # 初始化直接发送器,传入配置文件中的凭证
        self.direct_sender = DirectFeishuSender(
            app_id=self.config.get('feishu_app_id'),
            app_secret=self.config.get('feishu_app_secret')
        )
        
        # 初始化 OpenClaw Gateway 客户端
        openclaw_config = self.config.get('openclaw', {})
        self.openclaw_enabled = openclaw_config.get('enabled', False)
        if self.openclaw_enabled:
            self.openclaw_client = OpenClawGatewayClient(
                gateway_url=openclaw_config.get('gateway_url', ''),
                gateway_token=openclaw_config.get('gateway_token', ''),
                agent_id=openclaw_config.get('agent_id', 'secretary-agent')
            )
            logger.info(f"OpenClaw Gateway 客户端已初始化，agent_id: {openclaw_config.get('agent_id')}")
        else:
            self.openclaw_client = None
            logger.info("OpenClaw Gateway 未启用")
        
        # 线程相关
        self.fetch_thread = None
        self.process_thread = None
        self.stop_event = threading.Event()
        self.db_lock = threading.Lock()  # 数据库访问锁
    
    def load_config(self) -> Dict:
        """
        加载配置 - 从环境变量和 .env 文件加载
        """
        # 加载 .env 文件
        load_dotenv()
        
        # 基础配置
        config = {
            'feishuListenerUrl': os.getenv('FEISHU_LISTENER_URL', ''),
            'verification_code': os.getenv('VERIFICATION_CODE', ''),
            'local_db_path': os.getenv('LOCAL_DB_PATH', './feishu_local_messages.db'),
            'check_interval': int(os.getenv('CHECK_INTERVAL', '3')),
            'feishu_app_id': os.getenv('FEISHU_APP_ID', ''),
            'feishu_app_secret': os.getenv('FEISHU_APP_SECRET', ''),
        }
        
        # OpenClaw 配置
        openclaw_enabled = os.getenv('OPENCLAW_ENABLED', 'false').lower() in ('true', '1', 'yes')
        config['openclaw'] = {
            'enabled': openclaw_enabled,
            'gateway_url': os.getenv('OPENCLAW_GATEWAY_URL', ''),
            'gateway_token': os.getenv('OPENCLAW_GATEWAY_TOKEN', ''),
            'agent_id': os.getenv('OPENCLAW_AGENT_ID', 'secretary-agent'),
        }
        
        return config
    
    def init_local_db(self):
        """
        初始化本地数据库,用于记录已处理的消息
        """
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        # 创建 incoming_messages 表（从公网服务获取的原始消息）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS incoming_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER UNIQUE,
                message_id TEXT,
                sender_id TEXT,
                chat_id TEXT,
                content TEXT,
                message_type TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed INTEGER DEFAULT 0,
                raw_data TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_incoming_processed 
            ON incoming_messages(processed)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_incoming_timestamp 
            ON incoming_messages(timestamp)
        ''')
        
        # 创建已处理消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                original_content TEXT,
                processed_result TEXT
            )
        ''')
        
        # 创建待回复消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_id TEXT,
                content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                sent INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_incoming_message(self, message: Dict) -> bool:
        """
        保存从公网服务获取的消息到本地数据库
        """
        server_id = message.get('id')
        message_id = message.get('message_id', '')
        sender_id = message.get('sender_id', '')
        chat_id = message.get('chat_id', '')
        content = message.get('content', '')
        message_type = message.get('message_type', 'text')
        
        with self.db_lock:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO incoming_messages 
                    (server_id, message_id, sender_id, chat_id, content, message_type, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    server_id,
                    message_id,
                    sender_id,
                    chat_id,
                    content,
                    message_type,
                    json.dumps(message, ensure_ascii=False)
                ))
                
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"保存消息到本地数据库失败: {e}")
                return False
            finally:
                conn.close()
    
    def get_local_unprocessed_messages(self, limit: int = 10) -> List[Dict]:
        """
        从本地数据库获取未处理的消息
        """
        with self.db_lock:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    SELECT * FROM incoming_messages 
                    WHERE processed = 0 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                messages = [dict(zip(columns, row)) for row in rows]
                
                return messages
            except Exception as e:
                logger.error(f"获取本地未处理消息失败: {e}")
                return []
            finally:
                conn.close()
    
    def mark_local_processed(self, local_id: int) -> bool:
        """
        标记本地消息为已处理
        """
        with self.db_lock:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    UPDATE incoming_messages 
                    SET processed = 1 
                    WHERE id = ?
                ''', (local_id,))
                
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                logger.error(f"标记本地消息已处理失败: {e}")
                return False
            finally:
                conn.close()
    
    def fetch_from_remote(self):
        """
        线程1：从公网服务获取消息并落库
        """
        logger.info("消息获取线程启动")
        
        while self.running and not self.stop_event.is_set():
            try:
                # 从公网服务获取未处理的消息
                remote_messages = self.get_unprocessed_messages()
                
                if remote_messages:
                    logger.info(f"从公网服务获取到 {len(remote_messages)} 条消息")
                    
                    for msg in remote_messages:
                        # 保存到本地数据库
                        if self.save_incoming_message(msg):
                            # 标记公网服务上的消息为已处理
                            server_id = msg.get('id')
                            if server_id and self.mark_message_as_processed(server_id):
                                logger.debug(f"消息 {msg.get('message_id')} 已保存到本地并标记远程为已处理")
                        else:
                            logger.warning(f"消息 {msg.get('message_id')} 保存到本地失败")
                else:
                    logger.debug("没有新消息")
                
            except Exception as e:
                logger.error(f"从远程获取消息时发生错误: {e}")
            
            # 休息1秒
            self.stop_event.wait(1)
        
        logger.info("消息获取线程停止")
    
    def get_unprocessed_messages(self) -> List[Dict]:
        """
        从公网服务器获取未处理的消息
        """
        url = f"{self.api_base_url}/api/messages/unprocessed"
        headers = {
            'X-Verification-Code': self.verification_code
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                # 检查是否是包含data字段的响应格式
                if 'data' in result:
                    return result['data']
                else:
                    return result
            else:
                logger.error(f"获取消息失败: {response.status_code} - {response.text}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {e}")
            return []
    
    def mark_message_as_processed(self, message_id: int) -> bool:
        """
        标记消息为已处理
        """
        url = f"{self.api_base_url}/api/messages/{message_id}/mark-processed"
        headers = {
            'X-Verification-Code': self.verification_code
        }
        
        try:
            response = requests.post(url, headers=headers, timeout=10)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logger.error(f"标记消息为已处理失败: {e}")
            return False
    
    def save_processed_message(self, message_id: str, original_content: str, result: str):
        """
        在本地数据库中保存已处理的消息记录
        """
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO processed_messages 
                (message_id, original_content, processed_result) 
                VALUES (?, ?, ?)
            ''', (message_id, original_content, result))
            
            conn.commit()
        except Exception as e:
            logger.error(f"保存已处理消息记录失败: {e}")
        finally:
            conn.close()
    
    def add_reply_message(self, recipient_id: str, content: str) -> bool:
        """
        添加待回复的消息到本地数据库
        """
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO pending_replies (recipient_id, content) 
                VALUES (?, ?)
            ''', (recipient_id, content))
            
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"添加回复消息失败: {e}")
            return False
        finally:
            conn.close()
    
    def get_pending_replies(self) -> List[Dict]:
        """
        获取待发送的回复消息
        """
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM pending_replies 
            WHERE sent = 0 
            ORDER BY created_at ASC
        ''')
        
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        messages = [dict(zip(columns, row)) for row in rows]
        
        conn.close()
        return messages
    
    def mark_reply_as_sent(self, reply_id: int) -> bool:
        """
        标记回复消息为已发送
        """
        conn = sqlite3.connect(self.local_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE pending_replies 
                SET sent = 1 
                WHERE id = ?
            ''', (reply_id,))
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"标记回复为已发送失败: {e}")
            return False
        finally:
            conn.close()
    
    def send_reply_to_server(self, recipient_id: str, content: str) -> bool:
        """
        直接将回复消息发送到飞书（通过飞书API）
        """
        # 直接发送到飞书,不再回退到服务器
        if self.direct_sender.app_id and self.direct_sender.app_secret:
            success = self.direct_sender.send_message(recipient_id, content)
            if success:
                logger.info(f"回复消息已直接发送到飞书: {content[:50]}...")
            else:
                logger.error(f"直接发送到飞书失败")
            return success
        else:
            logger.error("未配置飞书应用凭证,无法发送消息")
            return False
    
    def send_pending_replies_to_server(self) -> int:
        """
        将本地待发送的回复消息批量发送到公网服务器
        """
        pending_replies = self.get_pending_replies()
        sent_count = 0
        
        for reply in pending_replies:
            reply_id = reply['id']
            recipient_id = reply['recipient_id']
            content = reply['content']
            
            # 发送到服务器
            if self.send_reply_to_server(recipient_id, content):
                # 标记为已发送
                if self.mark_reply_as_sent(reply_id):
                    sent_count += 1
                    logger.info(f"回复消息 {reply_id} 已发送并标记为已发送")
                else:
                    logger.error(f"回复消息 {reply_id} 发送成功但本地标记失败")
            else:
                logger.error(f"回复消息 {reply_id} 发送失败")
        
        return sent_count
    
    def process_single_message(self, message: Dict) -> str:
        """
        处理单条消息 - 调用OpenClaw进行智能回复
        """
        message_id = message.get('message_id', 'unknown')
        sender_id = message.get('sender_id', 'unknown')
        content = message.get('content', '')
        
        logger.info(f"处理消息: ID={message_id}, 发送者={sender_id}, 内容='{content}'")
        
        response_content = None
        error_message = None
        
        # 如果启用了 OpenClaw Gateway，使用它进行智能回复
        if self.openclaw_enabled and self.openclaw_client:
            try:
                logger.info(f"调用 OpenClaw agent: {self.openclaw_client.agent_id}")
                openclaw_message = f"来自飞书的消息: {content}"
                response_content = self.openclaw_client.chat(
                    message=openclaw_message,
                    user_id=sender_id
                )
                
                if response_content:
                    logger.info(f"OpenClaw 返回回复: {response_content[:100]}...")
                else:
                    error_message = "OpenClaw 返回空回复"
                    logger.warning(f"{error_message}")
                    response_content = f"抱歉，AI助手暂时无法回复。已收到您的消息: {content}\n\n错误信息: {error_message}"
            except Exception as e:
                error_message = str(e)
                logger.error(f"调用 OpenClaw 时发生错误: {error_message}")
                response_content = f"抱歉，AI助手暂时无法回复。已收到您的消息: {content}\n\n错误信息: {error_message}"
        else:
            # 未启用 OpenClaw，使用默认回复
            response_content = f"已收到您的消息: {content}。我是一个AI助手，很高兴为您服务！"
        
        # 将回复添加到待发送队列
        self.add_reply_message(sender_id, response_content)
        
        return response_content
    
    def process_local_messages(self):
        """
        线程2：处理本地数据库中的消息
        """
        logger.info("消息处理线程启动")
        
        while self.running and not self.stop_event.is_set():
            try:
                # 从本地数据库获取未处理的消息（FIFO）
                local_messages = self.get_local_unprocessed_messages(limit=1)
                
                if local_messages:
                    msg = local_messages[0]
                    local_id = msg['id']
                    message_id = msg.get('message_id', 'unknown')
                    sender_id = msg.get('sender_id', 'unknown')
                    content = msg.get('content', '')
                    
                    logger.info(f"处理本地消息: ID={message_id}, 发送者={sender_id}, 内容='{content}'")
                    
                    try:
                        # 处理消息
                        result = self.process_single_message(msg)
                        
                        # 保存处理结果到本地
                        original_content = msg.get('content', '')
                        self.save_processed_message(message_id, original_content, result)
                        
                        # 标记本地消息为已处理
                        if self.mark_local_processed(local_id):
                            logger.info(f"本地消息 {message_id} 已标记为已处理")
                        else:
                            logger.error(f"本地消息 {message_id} 标记为已处理失败")
                            
                    except Exception as e:
                        logger.error(f"处理消息时发生错误: {e}")
                else:
                    logger.debug("没有待处理的本地消息")
                
                # 发送待回复的消息到飞书
                sent_count = self.send_pending_replies_to_server()
                if sent_count > 0:
                    logger.info(f"成功发送 {sent_count} 条回复消息到飞书")
                
            except Exception as e:
                logger.error(f"处理本地消息时发生错误: {e}")
            
            # 短暂休息后继续处理
            self.stop_event.wait(0.1)
        
        logger.info("消息处理线程停止")
    
    def start(self):
        """
        启动服务
        """
        self.running = True
        self.stop_event.clear()
        logger.info("飞书回复服务启动")
        
        # 启动消息获取线程
        self.fetch_thread = threading.Thread(target=self.fetch_from_remote, name="FetchThread")
        self.fetch_thread.daemon = True
        self.fetch_thread.start()
        logger.info("消息获取线程已启动")
        
        # 启动消息处理线程
        self.process_thread = threading.Thread(target=self.process_local_messages, name="ProcessThread")
        self.process_thread.daemon = True
        self.process_thread.start()
        logger.info("消息处理线程已启动")
        
        # 等待线程结束
        try:
            while self.running and not self.stop_event.is_set():
                self.stop_event.wait(1)
                
                # 检查线程状态
                if self.fetch_thread and not self.fetch_thread.is_alive():
                    logger.error("消息获取线程异常退出")
                    self.running = False
                    
                if self.process_thread and not self.process_thread.is_alive():
                    logger.error("消息处理线程异常退出")
                    self.running = False
                    
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号")
            self.stop()
        
        logger.info("飞书回复服务已停止")
    
    def stop(self):
        """
        停止服务
        """
        self.running = False
        self.stop_event.set()
        logger.info("正在停止飞书回复服务...")
        
        # 等待线程结束
        if self.fetch_thread and self.fetch_thread.is_alive():
            self.fetch_thread.join(timeout=5)
            if self.fetch_thread.is_alive():
                logger.warning("消息获取线程未正常退出")
        
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=5)
            if self.process_thread.is_alive():
                logger.warning("消息处理线程未正常退出")
        
        logger.info("飞书回复服务已停止")
    
    def restart(self):
        """
        重启服务
        """
        logger.info("正在重启飞书回复服务...")
        self.stop()
        time.sleep(2)
        self.start()


def main():
    """
    主函数,处理命令行参数
    """
    if len(sys.argv) < 2:
        print("用法: python feishu_resp_server.py [start|stop|restart|status]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # 确保日志目录存在
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # 加载 .env 文件
    if not os.path.exists('.env'):
        print("警告: .env 文件不存在，请创建并配置环境变量")
        print("可以从 .env.example 复制模板: cp .env.example .env")
    
    service = FeishuReplyService()
    
    if command == 'start':
        service.start()
    elif command == 'stop':
        service.stop()
        print("服务已停止")
    elif command == 'restart':
        service.restart()
    elif command == 'status':
        # 检查是否有正在运行的进程
        import subprocess
        try:
            result = subprocess.run(['pgrep', '-f', 'feishu_resp_server.py'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("服务正在运行")
            else:
                print("服务未运行")
        except Exception:
            print("无法确定服务状态")
    else:
        print(f"未知命令: {command}")
        print("用法: python feishu_resp_server.py [start|stop|restart|status]")
        sys.exit(1)


if __name__ == "__main__":
    main()