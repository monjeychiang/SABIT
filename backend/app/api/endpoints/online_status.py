"""
在线状态管理API端点

提供在線狀態查詢API
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session
from datetime import datetime

from ...db.database import get_db
from ...db.models.user import User
from ...db.models.chatroom import ChatRoom, ChatRoomMember, ChatRoomMessage
from ...core.security import get_current_user
from ...core.online_status_manager import online_status_manager
from ...core.main_ws_manager import websocket_manager

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()

# 获取用户在线状态
@router.get("/users/online", response_model=Dict[str, Any])
async def get_online_users(
    current_user: User = Depends(get_current_user),
    user_ids: List[int] = Query(None),
    db: Session = Depends(get_db)
):
    """获取指定用户列表的在线状态"""
    
    # 如果未提供用户ID列表，則查詢當前用户所在聊天室的所有用户
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
    
    # 获取統計信息
    stats = online_status_manager.get_stats()
    # 添加WebSocket管理器的統計信息
    stats.update(websocket_manager.get_stats())
    
    return stats 

@router.get("/public-stats", response_model=Dict[str, Any])
async def get_public_online_stats(
    current_user: User = Depends(get_current_user),
):
    """获取公开的在线状态统计信息，供所有用户查看"""
    
    # 只返回必要的統計信息：在線用戶總數
    return {
        "total_online": online_status_manager.get_total_online_users()
    } 