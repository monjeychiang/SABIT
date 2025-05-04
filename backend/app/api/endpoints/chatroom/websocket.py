import asyncio
import json
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
import time
import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from ....db.database import get_db
from ....db.models.user import User
from ....db.models.chatroom import ChatRoom, ChatRoomMember as ChatRoomUser, ChatRoomMessage as ChatMessage
from ....schemas.chatroom import ChatRoomCreate, ChatRoomResponse, ChatMessageCreate
from ....core.security import verify_token_ws as get_current_user_ws
from ....core.websocket_manager import global_ws_manager
from ....core.config import settings

# 配置日志
logger = logging.getLogger(__name__)

# 定义路由器
router = APIRouter()

# WebSocket连接处理
@router.websocket("/ws/{room_id}/{token}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    try:
        # 验证用户
        current_user = await get_current_user_ws(token, db)
        if not current_user:
            await websocket.close(code=1008)  # 策略违例
            return
        
        # 验证聊天室
        chatroom = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not chatroom:
            await websocket.close(code=1003)  # 未找到聊天室
            return
        
        # 检查用户是否已加入聊天室
        is_member = False
        for member in chatroom.members:
            if member.user_id == current_user.id:
                is_member = True
                break
        
        if not is_member:
            await websocket.close(code=1003)  # 未授权
            return
        
        # 检查全局连接限制
        if not global_ws_manager.can_connect(current_user.id, room_id):
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "连接数超过限制，请稍后再试",
                "timestamp": datetime.now().isoformat()
            })
            await websocket.close(code=1008)  # 策略违例
            return
        
        # 接受连接
        await websocket.accept()
        logger.info(f"用户 {current_user.username} (ID: {current_user.id}) 连接到聊天室 {room_id}")
        
        # 注册到全局连接管理器
        global_ws_manager.register_connection(websocket, current_user.id, room_id)
        
        # 通知聊天室其他用户
        join_message = {
            "type": "system",
            "message": f"用户 {current_user.username} 已加入聊天室",
            "user": {
                "id": current_user.id,
                "username": current_user.username
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 使用广播发送加入消息
        await broadcast_to_room(
            room_id, 
            join_message, 
            exclude_user_id=None  # 包括自己
        )
        
        try:
            # 消息接收循环
            while True:
                data = await websocket.receive_text()
                global_ws_manager.record_message_received()
                
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "message")
                    
                    # 处理心跳响应
                    if message_type == "pong":
                        continue
                    
                    # 检查消息速率限制
                    if message_type == "message" and not global_ws_manager.check_message_rate_limit(current_user.id):
                        await websocket.send_json({
                            "type": "error",
                            "message": "消息发送过于频繁，请稍后再试",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    
                    # 处理消息类型
                    if message_type == "message":
                        # 处理聊天消息
                        content = message_data.get("content", "").strip()
                        if not content:
                            continue
                        
                        # 创建消息记录
                        new_message = ChatMessage(
                            room_id=room_id,
                            user_id=current_user.id,
                            content=content,
                            created_at=datetime.now()
                        )
                        db.add(new_message)
                        db.commit()
                        db.refresh(new_message)
                        
                        # 广播消息
                        message_to_send = {
                            "type": "message",
                            "id": new_message.id,
                            "content": new_message.content,
                            "user": {
                                "id": current_user.id,
                                "username": current_user.username
                            },
                            "timestamp": new_message.created_at.isoformat()
                        }
                        
                        await broadcast_to_room(room_id, message_to_send)
                        
                    elif message_type == "typing":
                        # 处理正在输入状态
                        typing_message = {
                            "type": "typing",
                            "user": {
                                "id": current_user.id,
                                "username": current_user.username
                            },
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        # 广播正在输入状态（排除自己）
                        await broadcast_to_room(room_id, typing_message, exclude_user_id=current_user.id)
                    
                    elif message_type == "ping":
                        # 客户端主动发送的心跳检查
                        await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})
                    
                except json.JSONDecodeError:
                    logger.error(f"用户 {current_user.id} 发送了无效的JSON消息: {data}")
                    continue
                except Exception as e:
                    logger.error(f"处理用户 {current_user.id} 的消息时出错: {str(e)}")
                    global_ws_manager.record_error()
                    continue
                
        except WebSocketDisconnect:
            # 用户断开连接
            logger.info(f"用户 {current_user.username} (ID: {current_user.id}) 断开了与聊天室 {room_id} 的连接")
            
            # 从全局管理器注销连接
            global_ws_manager.unregister_connection(current_user.id, room_id)
            
            # 通知其他用户
            leave_message = {
                "type": "system",
                "message": f"用户 {current_user.username} 已离开聊天室",
                "user": {
                    "id": current_user.id,
                    "username": current_user.username
                },
                "timestamp": datetime.now().isoformat()
            }
            
            await broadcast_to_room(room_id, leave_message)
            
    except Exception as e:
        logger.error(f"WebSocket处理出错: {str(e)}")
        global_ws_manager.record_error()
        try:
            await websocket.close(code=1011)  # 内部错误
        except:
            pass

# 辅助函数：广播消息到聊天室
async def broadcast_to_room(room_id: int, message: dict, exclude_user_id: Optional[int] = None):
    """
    广播消息到聊天室的所有连接
    
    Args:
        room_id: 聊天室ID
        message: 要发送的消息
        exclude_user_id: 要排除的用户ID（不向该用户发送）
    """
    if room_id not in global_ws_manager.room_connections:
        return
    
    disconnected_users = []
    
    for user_id, websocket in global_ws_manager.room_connections[room_id].items():
        if exclude_user_id is not None and user_id == exclude_user_id:
            continue
        
        try:
            await websocket.send_json(message)
            global_ws_manager.record_message_sent()
        except Exception as e:
            logger.error(f"向用户 {user_id} 广播消息失败: {str(e)}")
            disconnected_users.append(user_id)
            global_ws_manager.record_error()
    
    # 清理断开连接的用户
    for user_id in disconnected_users:
        global_ws_manager.unregister_connection(user_id, room_id)


# API端点：获取WebSocket连接统计信息
@router.get("/stats", response_model=Dict[str, Any])
async def get_websocket_stats(current_user: User = Depends(get_current_user_ws)):
    """获取WebSocket连接的统计信息（仅限管理员）"""
    return global_ws_manager.get_stats() 