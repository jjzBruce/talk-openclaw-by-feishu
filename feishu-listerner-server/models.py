import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_database(self):
        """初始化数据库表"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incoming_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    message_id TEXT NOT NULL UNIQUE,
                    sender_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    content TEXT,
                    message_type TEXT DEFAULT 'text',
                    attachments TEXT,
                    processed BOOLEAN DEFAULT 0,
                    response_sent BOOLEAN DEFAULT 0,
                    raw_data TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS outgoing_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    recipient_id TEXT NOT NULL,
                    content TEXT,
                    message_type TEXT DEFAULT 'text',
                    attachments TEXT,
                    status TEXT DEFAULT 'pending',
                    sent_at DATETIME
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_incoming_message_id 
                ON incoming_messages(message_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_incoming_processed 
                ON incoming_messages(processed)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_outgoing_status 
                ON outgoing_messages(status)
            """)

            conn.commit()
            logger.info("数据库初始化完成")

    def add_incoming_message(self, message_id: str, sender_id: str, chat_id: str,
                            content: str, message_type: str = 'text',
                            attachments: Optional[Dict] = None,
                            raw_data: Optional[str] = None) -> int:
        """添加接收到的消息"""
        with self.get_connection() as conn:
            try:
                cursor = conn.execute("""
                    INSERT INTO incoming_messages 
                    (message_id, sender_id, chat_id, content, message_type, attachments, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    message_id,
                    sender_id,
                    chat_id,
                    content,
                    message_type,
                    json.dumps(attachments) if attachments else None,
                    raw_data
                ))
                conn.commit()
                logger.info(f"添加接收消息: {message_id}")
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                logger.warning(f"消息已存在: {message_id}")
                return -1

    def get_unprocessed_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取未处理的消息"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM incoming_messages 
                WHERE processed = 0 
                ORDER BY timestamp ASC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_message_processed(self, message_id: int) -> bool:
        """标记消息为已处理"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE incoming_messages 
                SET processed = 1 
                WHERE id = ?
            """, (message_id,))
            conn.commit()
            affected = cursor.rowcount
            logger.info(f"标记消息已处理: {message_id}")
            return affected > 0

    def add_outgoing_message(self, recipient_id: str, content: str,
                            message_type: str = 'text',
                            attachments: Optional[Dict] = None) -> int:
        """添加待发送的回复消息"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO outgoing_messages 
                (recipient_id, content, message_type, attachments, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (
                recipient_id,
                content,
                message_type,
                json.dumps(attachments) if attachments else None
            ))
            conn.commit()
            logger.info(f"添加待发送消息: {cursor.lastrowid}")
            return cursor.lastrowid

    def get_outgoing_messages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取待发送的回复消息"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM outgoing_messages 
                WHERE status = 'pending' 
                ORDER BY timestamp ASC 
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_outgoing_sent(self, message_id: int) -> bool:
        """标记回复为已发送"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE outgoing_messages 
                SET status = 'sent', sent_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (message_id,))
            conn.commit()
            affected = cursor.rowcount
            logger.info(f"标记消息已发送: {message_id}")
            return affected > 0

    def get_message_by_id(self, message_id: int, table: str = 'incoming') -> Optional[Dict[str, Any]]:
        """根据ID获取消息"""
        with self.get_connection() as conn:
            cursor = conn.execute(f"""
                SELECT * FROM {table}_messages 
                WHERE id = ?
            """, (message_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def cleanup_old_messages(self, days: int = 30) -> int:
        """清理旧消息"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                DELETE FROM incoming_messages 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                AND processed = 1 AND response_sent = 1
            """, (days,))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"清理了 {deleted} 条旧消息")
            return deleted