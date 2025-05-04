"""
在线状态管理API端点

提供WebSocket连接端点和在线状态查询API
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from datetime import datetime

from ...db.database import get_db
from ...db.models.user import User
from ...db.models.chatroom import ChatRoom, ChatRoomMember, ChatRoomMessage
from ...core.security import get_current_user, verify_token_ws
from ...core.online_status_manager import online_status_manager

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()

# WebSocket连接端点 - 用于在线状态更新
@router.websocket("/ws/status/{token}")
async def status_websocket_endpoint(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db)
):
    """WebSocket连接处理 - 用于实时更新用户在线状态"""
    # 验证Token
    user = await verify_token_ws(token, db)
    if not user:
        await websocket.close(code=1008)  # Policy Violation
        return
    
    try:
        # 建立WebSocket连接
        await online_status_manager.connect_user(websocket, user.id)
        
        # 从数据库获取用户加入的聊天室
        user_rooms = (
            db.query(ChatRoomMember.room_id)
            .filter(ChatRoomMember.user_id == user.id)
            .all()
        )
        room_ids = [room[0] for room in user_rooms]
        
        # 同步数据库中的聊天室
        online_status_manager.sync_user_rooms(user.id, room_ids)
        
        # 发送欢迎消息
        welcome_message = {
            "type": "status_connected",
            "user_id": user.id,
            "content": "您已连接到在线状态系统",
            "timestamp": datetime.now().isoformat()
        }
        
        await online_status_manager.send_personal_message(welcome_message, user.id)
        
        # 接收消息循环
        while True:
            try:
                # 接收消息 - 主要用于心跳检测和状态更新
                data = await websocket.receive_text()
                
                # 更新用户活跃时间
                online_status_manager.update_user_active_time(user.id)
                
                # 心跳响应
                await websocket.send_json({"type": "pong"})
                
            except WebSocketDisconnect:
                break
                
    except WebSocketDisconnect:
        # 处理连接断开
        await online_status_manager.disconnect_user(user.id)
        
    except Exception as e:
        logger.error(f"在线状态WebSocket处理失败: {str(e)}")
        try:
            await online_status_manager.disconnect_user(user.id)
        except:
            pass

# 获取聊天室在线用户
@router.get("/rooms/{room_id}/online", response_model=Dict[str, Any])
async def get_room_online_users(
    room_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取特定聊天室的在线用户列表"""
    # 验证聊天室存在
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="聊天室不存在"
        )
    
    # 验证权限 (公开聊天室或用户是成员)
    is_member = False
    member = (
        db.query(ChatRoomMember)
        .filter(
            ChatRoomMember.room_id == room_id,
            ChatRoomMember.user_id == current_user.id
        )
        .first()
    )
    
    if member:
        is_member = True
    
    if not room.is_public and not is_member and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您没有权限查看此聊天室"
        )
    
    # 获取在线用户ID列表
    online_user_ids = online_status_manager.get_room_online_users(room_id)
    
    # 获取用户详细信息
    online_users = []
    if online_user_ids:
        users = (
            db.query(User)
            .filter(User.id.in_(online_user_ids))
            .all()
        )
        
        online_users = [
            {
                "id": user.id,
                "username": user.username,
                "avatar_url": user.avatar_url,
                "last_active": online_status_manager.user_status.get(user.id, {}).get("last_active", None)
            }
            for user in users
        ]
    
    # 构建响应
    return {
        "room_id": room_id,
        "online_count": len(online_users),
        "online_users": online_users
    }

# 获取用户在线状态
@router.get("/users/online", response_model=Dict[str, Any])
async def get_online_users(
    current_user: User = Depends(get_current_user),
    user_ids: List[int] = Query(None),
    db: Session = Depends(get_db)
):
    """获取指定用户列表的在线状态"""
    
    # 如果未提供用户ID列表，则查询当前用户所在聊天室的所有用户
    if not user_ids:
        # 获取当前用户所在的聊天室
        user_rooms = (
            db.query(ChatRoomMember.room_id)
            .filter(ChatRoomMember.user_id == current_user.id)
            .all()
        )
        room_ids = [room[0] for room in user_rooms]
        
        # 获取这些聊天室的所有用户
        if room_ids:
            members = (
                db.query(ChatRoomMember.user_id)
                .filter(ChatRoomMember.room_id.in_(room_ids))
                .distinct()
                .all()
            )
            user_ids = [member[0] for member in members]
        else:
            user_ids = [current_user.id]  # 至少包含当前用户
    
    # 构建在线状态结果
    result = {}
    for user_id in user_ids:
        result[str(user_id)] = online_status_manager.is_user_online(user_id)
    
    # 返回在线状态映射
    return {
        "online_status": result,
        "total_online": online_status_manager.get_total_online_users()
    }

# 获取系统在线状态统计信息 (仅限管理员)
@router.get("/stats", response_model=Dict[str, Any])
async def get_online_stats(
    current_user: User = Depends(get_current_user),
):
    """获取系统在线状态统计信息（仅限管理员）"""
    # 检查是否是管理员
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理员可以访问此接口"
        )
    
    # 获取统计信息
    stats = online_status_manager.get_stats()
    
    return stats 