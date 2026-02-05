import os
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional

from flask import Flask, request, jsonify
from werkzeug.exceptions import BadRequest, Unauthorized

from models import DatabaseManager

# 配置日志
def setup_logging():
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置
FEISHU_VERIFICATION_TOKEN = os.getenv('FEISHU_VERIFICATION_TOKEN', '')
VERIFICATION_CODE = os.getenv('VERIFICATION_CODE', '')
PORT = int(os.getenv('PORT', 3000))
DB_PATH = os.getenv('DB_PATH', './feishu_messages.db')

# 初始化数据库
db = DatabaseManager(DB_PATH)


def verify_request():
    """验证内部API请求"""
    code = request.headers.get('X-Verification-Code')
    if not code or code != VERIFICATION_CODE:
        logger.warning("未授权的API访问")
        raise Unauthorized("Invalid verification code")


def parse_message_content(message_data: Dict[str, Any]) -> tuple:
    """
    解析飞书消息内容
    返回: (content, message_type, attachments)
    """
    content_type = message_data.get('msg_type', 'text')
    content_raw = message_data.get('content', '{}')
    
    # content可能是字符串格式的JSON，需要解析
    if isinstance(content_raw, str):
        try:
            content = json.loads(content_raw)
        except:
            content = {}
    else:
        content = content_raw
    
    message_type = content_type
    text_content = ""
    attachments = None
    
    if content_type == 'text':
        text_content = content.get('text', '')
    elif content_type == 'post':
        # 富文本消息
        post_content = content.get('post', {})
        zh_cn = post_content.get('zh_cn', [])
        text_blocks = []
        for item in zh_cn:
            if item.get('tag') == 'text':
                text_blocks.append(item.get('text', ''))
            elif item.get('tag') == 'a':
                text_blocks.append(item.get('text', ''))
        text_content = '\n'.join(text_blocks)
    elif content_type == 'image':
        image_key = content.get('image_key', '')
        text_content = f"[图片: {image_key}]"
        attachments = {'type': 'image', 'image_key': image_key}
    elif content_type == 'file':
        file_key = content.get('file_key', '')
        file_name = content.get('file_name', 'unknown')
        text_content = f"[文件: {file_name}]"
        attachments = {'type': 'file', 'file_key': file_key, 'file_name': file_name}
    elif content_type == 'audio':
        file_key = content.get('file_key', '')
        text_content = f"[音频]"
        attachments = {'type': 'audio', 'file_key': file_key}
    elif content_type == 'media':
        file_key = content.get('file_key', '')
        text_content = f"[媒体]"
        attachments = {'type': 'media', 'file_key': file_key}
    elif content_type == 'sticker':
        file_key = content.get('file_key', '')
        text_content = f"[表情]"
        attachments = {'type': 'sticker', 'file_key': file_key}
    else:
        text_content = json.dumps(content, ensure_ascii=False)
    
    return text_content, message_type, attachments


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'feishu-openclaw'
    })


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """飞书事件回调接口"""
    
    # 验证挑战（飞书URL验证）
    if request.method == 'GET':
        challenge = request.args.get('challenge')
        token = request.args.get('token')
        
        if token == FEISHU_VERIFICATION_TOKEN and challenge:
            logger.info("飞书URL验证成功")
            return jsonify({'challenge': challenge})
        else:
            logger.warning("飞书URL验证失败")
            raise Unauthorized("Invalid token")
    
    # 处理POST事件
    if request.method == 'POST':
        try:
            data = request.get_json()
            logger.info(f"收到飞书事件: {json.dumps(data, ensure_ascii=False)[:200]}")
            
            # 验证token（支持schema 2.0新格式）
            schema = data.get('schema', '1.0')
            if schema == '2.0':
                # 新格式：token在header中
                token = data.get('header', {}).get('token')
                event_type = data.get('header', {}).get('event_type')
                event = data.get('event', {})
            else:
                # 旧格式：token在根节点
                token = data.get('token')
                event_type = data.get('type')
                event = data.get('event', {})
            
            if token != FEISHU_VERIFICATION_TOKEN:
                logger.warning(f"飞书事件token验证失败: {token}")
                return jsonify({'code': 1, 'msg': 'Unauthorized'}), 401
            
            # 检查是否为消息接收事件
            if event_type == 'url_verification':
                # URL验证
                challenge = data.get('challenge')
                return jsonify({'challenge': challenge})
            
            if event_type == 'im.message.receive_v1':
                message = event.get('message', {})
                sender_info = event.get('sender', {})
                
                # 提取消息信息
                message_id = message.get('message_id', '')
                
                # 正确提取 sender_id
                # 飞书消息回调中的 sender_id 结构：
                # "sender_id": {"open_id": "ou_xxx", "union_id": "on_xxx", "user_id": "xxxx"}
                # 优先使用 open_id（应用内用户ID），其次使用 union_id（跨应用用户ID）
                # 不使用 user_id（租户内ID），因为它在多租户环境中不唯一
                sender_data = sender_info.get('sender_id', {})
                sender_id = sender_data.get('open_id', '')
                
                # 如果没有 open_id，尝试使用 union_id
                if not sender_id:
                    sender_id = sender_data.get('union_id', '')
                
                chat_id = message.get('chat_id', '')
                
                if not message_id:
                    logger.warning(f"消息信息不完整: {json.dumps(message)}")
                    return jsonify({'code': 0, 'msg': 'OK'})
                
                # 如果sender_id为空，记录警告但不使用chat_id作为备选
                if not sender_id:
                    logger.error(f"未找到有效的sender_id（open_id或union_id），chat_id={chat_id}")
                    logger.error(f"完整sender_info: {json.dumps(sender_info)}")
                    # 继续处理，但不会发送回复
                    return jsonify({'code': 0, 'msg': 'OK'})
                
                # 解析消息内容
                content, message_type, attachments = parse_message_content(message)
                
                # 存储到数据库
                db.add_incoming_message(
                    message_id=message_id,
                    sender_id=sender_id,
                    chat_id=chat_id,
                    content=content,
                    message_type=message_type,
                    attachments=attachments,
                    raw_data=json.dumps(message, ensure_ascii=False)
                )
                
                logger.info(f"成功存储消息: {message_id} from {sender_id}")
                return jsonify({'code': 0, 'msg': 'success'})
            
            return jsonify({'code': 0, 'msg': 'OK'})
            
        except Exception as e:
            logger.error(f"处理飞书事件失败: {str(e)}", exc_info=True)
            return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/messages/unprocessed', methods=['GET'])
def get_unprocessed_messages():
    """获取未处理的飞书消息"""
    verify_request()
    
    try:
        limit = request.args.get('limit', 100, type=int)
        messages = db.get_unprocessed_messages(limit)
        
        # 转换attachments字段
        for msg in messages:
            if msg.get('attachments'):
                try:
                    msg['attachments'] = json.loads(msg['attachments'])
                except:
                    pass
        
        logger.info(f"返回 {len(messages)} 条未处理消息")
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': messages
        })
    except Exception as e:
        logger.error(f"获取未处理消息失败: {str(e)}", exc_info=True)
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/messages/<int:message_id>/mark-processed', methods=['POST'])
def mark_message_processed(message_id):
    """标记消息为已处理"""
    verify_request()
    
    try:
        success = db.mark_message_processed(message_id)
        if success:
            return jsonify({'code': 0, 'msg': 'success'})
        else:
            return jsonify({'code': 1, 'msg': 'message not found'}), 404
    except Exception as e:
        logger.error(f"标记消息失败: {str(e)}", exc_info=True)
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/messages/outgoing', methods=['GET'])
def get_outgoing_messages():
    """获取待发送的回复消息"""
    verify_request()
    
    try:
        limit = request.args.get('limit', 100, type=int)
        messages = db.get_outgoing_messages(limit)
        
        # 转换attachments字段
        for msg in messages:
            if msg.get('attachments'):
                try:
                    msg['attachments'] = json.loads(msg['attachments'])
                except:
                    pass
        
        logger.info(f"返回 {len(messages)} 条待发送消息")
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': messages
        })
    except Exception as e:
        logger.error(f"获取待发送消息失败: {str(e)}", exc_info=True)
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/messages/outgoing/<int:message_id>/mark-sent', methods=['POST'])
def mark_outgoing_sent(message_id):
    """标记回复为已发送"""
    verify_request()
    
    try:
        success = db.mark_outgoing_sent(message_id)
        if success:
            return jsonify({'code': 0, 'msg': 'success'})
        else:
            return jsonify({'code': 1, 'msg': 'message not found'}), 404
    except Exception as e:
        logger.error(f"标记发送失败: {str(e)}", exc_info=True)
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.route('/api/messages/reply', methods=['POST'])
def add_reply():
    """添加新的回复消息到发送队列"""
    verify_request()
    
    try:
        data = request.get_json()
        recipient_id = data.get('recipient_id')
        content = data.get('content')
        message_type = data.get('message_type', 'text')
        attachments = data.get('attachments')
        
        if not recipient_id or not content:
            return jsonify({'code': 1, 'msg': 'recipient_id and content are required'}), 400
        
        message_id = db.add_outgoing_message(
            recipient_id=recipient_id,
            content=content,
            message_type=message_type,
            attachments=attachments
        )
        
        return jsonify({
            'code': 0,
            'msg': 'success',
            'data': {'message_id': message_id}
        })
    except Exception as e:
        logger.error(f"添加回复失败: {str(e)}", exc_info=True)
        return jsonify({'code': 1, 'msg': str(e)}), 500


@app.errorhandler(400)
def bad_request(error):
    return jsonify({'code': 1, 'msg': 'Bad Request'}), 400


@app.errorhandler(401)
def unauthorized(error):
    return jsonify({'code': 1, 'msg': 'Unauthorized'}), 401


@app.errorhandler(404)
def not_found(error):
    return jsonify({'code': 1, 'msg': 'Not Found'}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({'code': 1, 'msg': 'Internal Server Error'}), 500


if __name__ == '__main__':
    logger.info(f"启动飞书沟通服务，端口: {PORT}")
    logger.info(f"数据库路径: {DB_PATH}")
    app.run(host='0.0.0.0', port=PORT, debug=False)