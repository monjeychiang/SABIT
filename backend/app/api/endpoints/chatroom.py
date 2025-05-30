import logging
import json
from typing import List, Dict, Any, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta

from ...db.database import get_db
from ...db.models.chatroom import ChatRoom, ChatRoomMessage, ChatRoomMember
from ...db.models.user import User
from ...schemas.chatroom import (
    ChatRoomCreate, ChatRoomUpdate, ChatRoomResponse, ChatRoomDetailResponse,
    ChatRoomMemberCreate, ChatRoomMessageResponse,
    WebSocketMessage, UserBasic, ChatRoomMemberDB
)
from ...core.security import get_current_user, verify_token_ws
from ...api.endpoints.admin import get_current_admin_user
from ...core.main_ws_manager import main_ws_manager

# 設置聊天室訊息數量上限
MAX_MESSAGES_PER_ROOM = 1000  # 每個聊天室最多保留1000條訊息
DELETE_MESSAGES_COUNT = 500   # 超過上限時刪除最舊的500條訊息

# 設置日誌記錄器
logger = logging.getLogger(__name__)

# 創建路由器
router = APIRouter()

# 輔助函數：廣播消息到聊天室
async def broadcast_to_room(room_id: int, message: dict, exclude_user_id: Optional[int] = None):
    """
    廣播消息到聊天室的所有用戶
    
    Args:
        room_id: 聊天室ID
        message: 要發送的消息
        exclude_user_id: 要排除的用戶ID（不向該用戶發送）
    """
    try:
        # 從數據庫獲取聊天室成員
        db = next(get_db())
        members = db.query(ChatRoomMember).filter(
            ChatRoomMember.room_id == room_id
        ).all()
        
        user_ids = [member.user_id for member in members if member.user_id != exclude_user_id]
        
        if not user_ids:
            logger.warning(f"[ChatroomAPI] 聊天室 {room_id} 沒有可接收消息的成員")
            return
            
        # 使用主WebSocket廣播消息
        for user_id in user_ids:
            try:
                await main_ws_manager.send_to_user(user_id, message)
                logger.debug(f"[ChatroomAPI] 通過主WebSocket發送消息給用戶 {user_id}")
            except Exception as e:
                logger.error(f"[ChatroomAPI] 向用戶 {user_id} 發送消息失敗: {str(e)}")
        
        logger.debug(f"[ChatroomAPI] 廣播消息到聊天室 {room_id} 完成")
        
    except Exception as e:
        logger.error(f"[ChatroomAPI] 廣播消息到聊天室時出錯: {str(e)}")

# API端點：獲取WebSocket連接統計信息
@router.get("/stats", response_model=Dict[str, Any])
async def get_websocket_stats(current_user: User = Depends(get_current_user)):
    """獲取WebSocket連接的統計信息（僅限管理員）"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有管理員可以查看WebSocket統計信息"
        )
    return main_ws_manager.get_stats()

# 聊天室API路由
@router.post("/rooms", response_model=ChatRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    chat_room: ChatRoomCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    創建新的聊天室
    
    - 僅限管理員創建官方聊天室
    - 普通用戶可以創建非官方聊天室
    """
    # 檢查權限
    if chat_room.is_official and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="僅限管理員創建官方聊天室"
        )
    
    try:
        # 創建聊天室
        new_room = ChatRoom(
            name=chat_room.name,
            description=chat_room.description,
            is_public=chat_room.is_public,
            is_official=chat_room.is_official if current_user.is_admin else False,
            created_by=current_user.id
        )
        
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        
        # 創建者自動成為聊天室管理員成員
        member = ChatRoomMember(
            room_id=new_room.id,
            user_id=current_user.id,
            is_admin=True
        )
        
        db.add(member)
        db.commit()
        
        # 構建響應
        result = ChatRoomResponse.from_orm(new_room)
        result.member_count = 1
        result.is_member = True
        result.is_admin = True
        result.creator = None if not new_room.creator else UserBasic.from_orm(new_room.creator)
        
        return result
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"創建聊天室失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建聊天室失敗"
        )

@router.get("/rooms", response_model=List[ChatRoomResponse])
async def list_chat_rooms(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """获取可加入的聊天室列表"""
    try:
        # 查询所有公开的聊天室和用户是成员的私有聊天室
        public_rooms = db.query(ChatRoom).filter(ChatRoom.is_public == True).all()
        
        # 用户参与的私有聊天室
        user_private_rooms = (
            db.query(ChatRoom)
            .join(ChatRoomMember, ChatRoom.id == ChatRoomMember.room_id)
            .filter(
                ChatRoom.is_public == False,
                ChatRoomMember.user_id == current_user.id
            )
            .all()
        )
        
        # 合并结果
        all_rooms = public_rooms + [room for room in user_private_rooms if room not in public_rooms]
        
        # 分页
        paginated_rooms = all_rooms[skip:skip + limit]
        
        # 查询用户所在的聊天室
        user_room_memberships = (
            db.query(ChatRoomMember)
            .filter(ChatRoomMember.user_id == current_user.id)
            .all()
        )
        
        user_room_ids = {membership.room_id for membership in user_room_memberships}
        user_admin_room_ids = {
            membership.room_id 
            for membership in user_room_memberships 
            if membership.is_admin
        }
        
        # 构建响应
        result = []
        for room in paginated_rooms:
            room_response = ChatRoomResponse.from_orm(room)
            room_response.creator = None if not room.creator else UserBasic.from_orm(room.creator)
            room_response.member_count = len(room.members)
            room_response.is_member = room.id in user_room_ids
            room_response.is_admin = room.id in user_admin_room_ids
            
            # 查詢在線用戶數（從數據庫計算）
            online_count = 0
            try:
                # 從主WebSocket管理器獲取在線用戶數
                online_count = await main_ws_manager.get_room_online_users_count(room.id)
            except Exception as e:
                logger.error(f"獲取聊天室 {room.id} 的在線用戶數失敗: {str(e)}")
            
            room_response.online_users = online_count
            
            result.append(room_response)
            
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"获取聊天室列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天室列表失败"
        )

@router.get("/rooms/{room_id}", response_model=ChatRoomDetailResponse)
async def get_chat_room(
    room_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取聊天室详情"""
    try:
        # 查询聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 检查是否是成员或管理员
        is_member = False
        is_admin = False
        
        if current_user.is_admin:
            is_admin = True
            
        # 查询用户在此聊天室中的成员信息
        member = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == current_user.id
            )
            .first()
        )
        
        # 检查是否为成员或管理员
        if member:
            is_member = True
            is_admin = is_admin or member.is_admin
            
        # 如果不是成员且聊天室是私有的，普通用户不能查看详情
        if not is_member and not room.is_public and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限查看此聊天室"
            )
            
        # 获取聊天室成员列表
        members = db.query(ChatRoomMember).filter(ChatRoomMember.room_id == room_id).all()
        
        # 获取最近的消息
        recent_messages = (
            db.query(ChatRoomMessage)
            .filter(ChatRoomMessage.room_id == room_id)
            .order_by(ChatRoomMessage.created_at.desc())
            .limit(50)
            .all()
        )
        recent_messages.reverse()  # 按时间升序排列
        
        # 构建响应
        result = ChatRoomDetailResponse.from_orm(room)
        result.creator = None if not room.creator else UserBasic.from_orm(room.creator)
        result.member_count = len(members)
        result.is_member = is_member
        result.is_admin = is_admin
        
        # 添加成员信息
        result.members = [ChatRoomMemberDB.from_orm(member) for member in members]
        
        # 添加消息信息
        result.latest_messages = []
        for message in recent_messages:
            message_response = ChatRoomMessageResponse.from_orm(message)
            if message.user:
                message_response.user = UserBasic.from_orm(message.user)
            result.latest_messages.append(message_response)
            
        # 查詢在線用戶數（從主WebSocket管理器獲取）
        online_count = 0
        try:
            online_count = await main_ws_manager.get_room_online_users_count(room_id)
        except Exception as e:
            logger.error(f"獲取聊天室 {room_id} 的在線用戶數失敗: {str(e)}")
        
        result.online_users = online_count
        
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"获取聊天室详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天室详情失败"
        )

@router.patch("/rooms/{room_id}", response_model=ChatRoomResponse)
async def update_chat_room(
    room_id: int = Path(..., ge=1),
    chat_room: ChatRoomUpdate = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    更新聊天室信息
    
    - 仅限聊天室创建者或管理员修改
    - 支持修改名称、描述、公开状态等
    - 仅限管理员可以设置官方聊天室状态
    """
    try:
        # 查询聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 检查是否有权限修改(创建者或管理员)
        is_room_admin = False
        member = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == current_user.id,
                ChatRoomMember.is_admin == True
            )
            .first()
        )
        
        if member:
            is_room_admin = True
            
        if room.created_by != current_user.id and not is_room_admin and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限修改此聊天室"
            )
        
        # 更新聊天室信息
        if chat_room:
            if chat_room.name is not None:
                room.name = chat_room.name
                
            if chat_room.description is not None:
                room.description = chat_room.description
                
            if chat_room.is_public is not None:
                room.is_public = chat_room.is_public
                
            # 官方聊天室标记仅管理员可设置
            if hasattr(chat_room, 'is_official') and chat_room.is_official is not None:
                if current_user.is_admin:
                    room.is_official = chat_room.is_official
                elif chat_room.is_official:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="仅限管理员设置官方聊天室标记"
                    )
            
            # 处理其他字段...
            if hasattr(chat_room, 'max_members') and chat_room.max_members is not None:
                room.max_members = chat_room.max_members
                
            if hasattr(chat_room, 'announcement') and chat_room.announcement is not None:
                room.announcement = chat_room.announcement
                
        db.commit()
        db.refresh(room)
        
        # 构建响应
        result = ChatRoomResponse.from_orm(room)
        result.creator = None if not room.creator else UserBasic.from_orm(room.creator)
        result.member_count = len(room.members)
        
        # 当前用户是否为成员
        is_member = db.query(ChatRoomMember).filter(
            ChatRoomMember.room_id == room_id,
            ChatRoomMember.user_id == current_user.id
        ).first() is not None
        
        result.is_member = is_member
        result.is_admin = is_room_admin or current_user.is_admin
        
        # 查詢在線用戶數
        online_count = 0
        try:
            online_count = await main_ws_manager.get_room_online_users_count(room_id)
        except Exception as e:
            logger.error(f"獲取聊天室 {room_id} 的在線用戶數失敗: {str(e)}")
        
        result.online_users = online_count
        
        # 通知所有连接的用户
        update_message = {
            "type": "room_updated",
            "room_id": room_id,
            "content": f"聊天室信息已更新",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        await broadcast_to_room(room_id, update_message)
        
        return result
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"更新聊天室失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新聊天室失败"
        )

@router.post("/rooms/{room_id}/join", status_code=status.HTTP_200_OK)
async def join_chat_room(
    room_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """加入聊天室"""
    try:
        # 查询聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 检查是否已经是成员
        existing_member = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == current_user.id
            )
            .first()
        )
        
        if existing_member:
            return {"message": "您已经是聊天室成员"}
            
        # 检查权限
        if not room.is_public and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="该聊天室是私有的，需要邀请才能加入"
            )
            
        # 添加成员
        new_member = ChatRoomMember(
            room_id=room_id,
            user_id=current_user.id,
            is_admin=False
        )
        
        db.add(new_member)
        
        # 添加系统消息
        system_message = ChatRoomMessage(
            room_id=room_id,
            user_id=None,
            content=f"{current_user.username} 加入了聊天室",
            is_system=True
        )
        
        db.add(system_message)
        db.commit()
        
        # 广播用户加入消息
        room_message = {
            "type": "chat/join",
            "room_id": room_id,
            "user_id": current_user.id,
            "username": current_user.username,
            "avatar_url": current_user.avatar_url,
            "content": f"{current_user.username} 加入了聊天室",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        await broadcast_to_room(room_id, room_message)
        
        return {"message": "已成功加入聊天室"}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"加入聊天室失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="加入聊天室失败"
        )

@router.post("/rooms/{room_id}/leave", status_code=status.HTTP_200_OK)
async def leave_chat_room(
    room_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """离开聊天室"""
    try:
        # 查询聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 检查是否是成员
        member = (
            db.query(ChatRoomMember)
            .filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == current_user.id
            )
            .first()
        )
        
        if not member:
            return {"message": "您不是聊天室成员"}
            
        # 删除成员
        db.delete(member)
        
        # 添加系统消息
        system_message = ChatRoomMessage(
            room_id=room_id,
            user_id=None,
            content=f"{current_user.username} 离开了聊天室",
            is_system=True
        )
        
        db.add(system_message)
        db.commit()
        
        # 广播用户离开消息
        room_message = {
            "type": "chat/leave",
            "room_id": room_id,
            "user_id": current_user.id,
            "username": current_user.username,
            "content": f"{current_user.username} 离开了聊天室",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        await broadcast_to_room(room_id, room_message)
        
        return {"message": "已成功离开聊天室"}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"离开聊天室失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="离开聊天室失败"
        )

@router.delete("/rooms/{room_id}", status_code=status.HTTP_200_OK)
async def delete_chat_room(
    room_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """删除聊天室（仅限创建者或管理员）"""
    try:
        # 查询聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 检查权限
        if room.created_by != current_user.id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限删除此聊天室"
            )
            
        # 删除聊天室
        db.delete(room)
        db.commit()
        
        # 通知所有连接的用户
        room_message = {
            "type": "room_deleted",
            "room_id": room_id,
            "content": f"聊天室已被删除",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        await broadcast_to_room(room_id, room_message)
        
        return {"message": "聊天室已成功删除"}
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"删除聊天室失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除聊天室失败"
        )

@router.get("/rooms/{room_id}/members", response_model=List[ChatRoomMemberDB])
async def get_room_members(
    room_id: int = Path(..., ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取聊天室成员列表"""
    try:
        # 查询聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 检查是否有权限查看（是公开聊天室或用户是成员）
        is_member = False
        if current_user.is_admin:
            is_member = True
        else:
            # 查询用户是否是成员
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
                
        # 如果不是公开聊天室且用户不是成员，则拒绝访问
        if not room.is_public and not is_member and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您没有权限查看此聊天室成员"
            )
            
        # 获取聊天室成员列表
        members = (
            db.query(ChatRoomMember)
            .filter(ChatRoomMember.room_id == room_id)
            .all()
        )
        
        # 构建响应
        result = []
        for member in members:
            member_data = ChatRoomMemberDB.from_orm(member)
            if member.user:
                member_data.user = UserBasic.from_orm(member.user)
            result.append(member_data)
            
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"获取聊天室成员失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取聊天室成员失败"
        )

@router.get("/messages/{room_id}", response_model=List[ChatRoomMessageResponse])
async def get_chat_messages(
    room_id: int = Path(..., ge=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    獲取聊天室的歷史消息
    
    返回指定聊天室的消息列表，原本支持分頁，現在返回所有消息
    
    參數:
        room_id: 聊天室ID
        skip: 已棄用 (保留參數但不使用)
        limit: 已棄用 (保留參數但不使用)
        
    返回:
        聊天消息列表
    """
    try:
        # 查詢聊天室
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="聊天室不存在"
            )
            
        # 檢查用户是否有權限查看消息
        # 公開聊天室或者用户是聊天室成員可以查看消息
        is_member = db.query(ChatRoomMember).filter(
            ChatRoomMember.room_id == room_id,
            ChatRoomMember.user_id == current_user.id
        ).first() is not None
        
        if not room.is_public and not is_member and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="您沒有權限查看此聊天室的消息"
            )
            
        # 檢查並清理超過上限的訊息
        await cleanup_messages(room_id, db)
            
        # 查詢消息，按時間順序返回，過濾掉系統消息
        # 移除 limit 和 offset，返回所有消息
        messages = db.query(ChatRoomMessage).filter(
            ChatRoomMessage.room_id == room_id,
            ChatRoomMessage.is_system == False  # 過濾掉系統消息
        ).order_by(
            ChatRoomMessage.created_at.asc()
        ).all()
        
        # 構建響應
        result = []
        for message in messages:
            message_response = ChatRoomMessageResponse.from_orm(message)
            if message.user:
                message_response.user = UserBasic.from_orm(message.user)
            result.append(message_response)
            
        # 更新用户最後讀取時間
        if is_member:
            member = db.query(ChatRoomMember).filter(
                ChatRoomMember.room_id == room_id,
                ChatRoomMember.user_id == current_user.id
            ).first()
            
            member.last_read_at = datetime.now()
            db.commit()
            
        return result
        
    except SQLAlchemyError as e:
        logger.error(f"獲取聊天室消息失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取聊天室消息失敗"
        )

# 檢查並刪除多餘的聊天室訊息
async def cleanup_messages(room_id: int, db: Session):
    """
    檢查聊天室訊息數量，如果超過上限則刪除最舊的訊息
    
    參數:
        room_id: 聊天室ID
        db: 資料庫會話
    """
    try:
        # 獲取聊天室訊息總數
        message_count = db.query(ChatRoomMessage).filter(
            ChatRoomMessage.room_id == room_id
        ).count()
        
        # 如果訊息數量超過上限，刪除最舊的訊息
        if message_count > MAX_MESSAGES_PER_ROOM:
            # 獲取要刪除的訊息ID
            messages_to_delete = db.query(ChatRoomMessage).filter(
                ChatRoomMessage.room_id == room_id
            ).order_by(
                ChatRoomMessage.created_at.asc()
            ).limit(DELETE_MESSAGES_COUNT).all()
            
            message_ids = [message.id for message in messages_to_delete]
            
            # 刪除這些訊息
            if message_ids:
                db.query(ChatRoomMessage).filter(
                    ChatRoomMessage.id.in_(message_ids)
                ).delete(synchronize_session=False)
                db.commit()
                logger.info(f"已從聊天室 {room_id} 刪除 {len(message_ids)} 條最舊訊息，目前共有 {message_count - len(message_ids)} 條訊息")
    except Exception as e:
        logger.error(f"清理聊天室訊息時出錯: {str(e)}")
        # 不拋出異常，讓主要功能繼續執行