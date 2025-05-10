import logging
import json
from typing import List, Dict, Any, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from ...db.database import get_db
from ...db.models.chatroom import ChatRoom, ChatRoomMessage, ChatRoomMember
from ...db.models.user import User
from ...schemas.chatroom import (
    ChatRoomCreate, ChatRoomUpdate, ChatRoomResponse, ChatRoomDetailResponse,
    ChatRoomMemberCreate, ChatRoomMessageCreate, ChatRoomMessageResponse,
    WebSocketMessage, UserBasic, ChatRoomMemberDB
)
from ...core.security import get_current_user, verify_token_ws
from ...api.endpoints.admin import get_current_admin_user

# 设置日志记录器
logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter()

# WebSocket连接管理器
class ConnectionManager:
    def __init__(self):
        # 存储活跃的WebSocket连接: {user_id: websocket}
        self.active_connections: Dict[int, WebSocket] = {}
        # 用户加入的聊天室: {user_id: set(room_id)}
        self.user_rooms: Dict[int, Set[int]] = {}
        # 聊天室成员: {room_id: set(user_id)}
        self.room_members: Dict[int, Set[int]] = {}
        # 用户状态记录
        self.user_status: Dict[int, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: int):
        """用户连接 WebSocket"""
        await websocket.accept()
        
        # 存储WebSocket连接
        self.active_connections[user_id] = websocket
        
        # 初始化用户状态
        if user_id not in self.user_status:
            self.user_status[user_id] = {"online": True}
            
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        
        # 生成连接ID，用于日志追踪
        connection_id = f"chatroom_{user_id}_{id(websocket)}"
        
        logger.info(f"[Chatroom] WebSocket连接已建立: 用户ID={user_id}, 连接ID={connection_id}, 当前连接总数={len(self.active_connections)}")
        
        # 通知其他用户该用户上线
        await self.broadcast_user_status_change(user_id, True)
    
    def disconnect(self, user_id: int):
        """断开用户的WebSocket连接"""
        websocket = None
        if user_id in self.active_connections:
            # 保存websocket引用以生成连接ID
            websocket = self.active_connections[user_id]
            del self.active_connections[user_id]
                
            # 更新用户状态
            if user_id in self.user_status:
                self.user_status[user_id]["online"] = False
            
            # 生成连接ID，用于日志追踪
            connection_id = f"chatroom_{user_id}_{id(websocket)}" if websocket else "unknown"
            
            logger.info(f"[Chatroom] WebSocket连接已断开: 用户ID={user_id}, 连接ID={connection_id}, 当前连接总数={len(self.active_connections)}")
    
    async def broadcast_user_status_change(self, user_id: int, is_online: bool):
        """广播用户状态变化"""
        # 获取用户加入的所有聊天室
        user_room_ids = self.user_rooms.get(user_id, set())
        
        # 向用户所在的每个聊天室广播状态变化
        for room_id in user_room_ids:
            message = {
                "type": "user_status",
                "room_id": room_id,
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": datetime.now().isoformat()
            }
            await self.broadcast_to_room(message, room_id, exclude_user_id=user_id)
    
    def add_user_to_room(self, user_id: int, room_id: int):
        """将用户添加到聊天室"""
        # 添加到用户-聊天室映射
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        self.user_rooms[user_id].add(room_id)
        
        # 添加到聊天室-用户映射
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        self.room_members[room_id].add(user_id)
        
        logger.info(f"用户 {user_id} 加入聊天室 {room_id}, 该聊天室现有成员 {len(self.room_members.get(room_id, set()))}")
    
    def remove_user_from_room(self, user_id: int, room_id: int):
        """将用户从聊天室移除"""
        # 从用户-聊天室映射中移除
        if user_id in self.user_rooms and room_id in self.user_rooms[user_id]:
            self.user_rooms[user_id].remove(room_id)
        
        # 从聊天室-用户映射中移除
        if room_id in self.room_members and user_id in self.room_members[room_id]:
            self.room_members[room_id].remove(user_id)
            
        logger.info(f"用户 {user_id} 离开聊天室 {room_id}, 该聊天室剩余成员 {len(self.room_members.get(room_id, set()))}")
    
    async def broadcast_to_room(self, message: Dict[str, Any], room_id: int, exclude_user_id: Optional[int] = None):
        """向聊天室的所有在线成员广播消息"""
        if room_id not in self.room_members:
            return
            
        for user_id in self.room_members[room_id]:
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
                
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].send_json(message)
                except Exception as e:
                    logger.error(f"向用户 {user_id} 广播消息失败: {str(e)}")
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: int):
        """向特定用户发送消息"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"向用户 {user_id} 发送消息失败: {str(e)}")
            
    def get_room_users(self, room_id: int) -> List[int]:
        """获取聊天室的所有用户ID"""
        return list(self.room_members.get(room_id, set()))
        
    def get_user_rooms(self, user_id: int) -> List[int]:
        """获取用户加入的所有聊天室ID"""
        return list(self.user_rooms.get(user_id, set()))
        
    def get_room_connections_count(self, room_id: int) -> int:
        """获取聊天室的在线用户数量"""
        if room_id not in self.room_members:
            return 0
            
        # 计算既在房间成员列表又有活跃连接的用户数
        online_count = sum(1 for user_id in self.room_members[room_id] if user_id in self.active_connections)
        return online_count
    
    def is_user_in_room(self, user_id: int, room_id: int) -> bool:
        """检查用户是否在指定聊天室中"""
        return user_id in self.user_rooms and room_id in self.user_rooms[user_id]
    
    def sync_db_rooms(self, user_id: int, room_ids: List[int]):
        """与数据库同步用户的聊天室"""
        # 创建一个新的房间集合
        new_rooms = set(room_ids)
        
        # 初始化用户的房间集合(如果不存在)
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        
        # 获取当前用户的房间
        current_rooms = self.user_rooms[user_id]
        
        # 添加新房间
        for room_id in new_rooms:
            if room_id not in current_rooms:
                self.add_user_to_room(user_id, room_id)
        
        # 移除旧房间
        rooms_to_remove = current_rooms - new_rooms
        for room_id in rooms_to_remove:
            self.remove_user_from_room(user_id, room_id)

# 创建连接管理器实例
manager = ConnectionManager()

# 聊天室API路由
@router.post("/rooms", response_model=ChatRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    chat_room: ChatRoomCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    创建新的聊天室
    
    - 仅限管理员创建官方聊天室
    - 普通用户可以创建非官方聊天室
    """
    # 检查权限
    if chat_room.is_official and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅限管理员创建官方聊天室"
        )
    
    try:
        # 创建聊天室
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
        
        # 创建者自动成为聊天室管理员成员
        member = ChatRoomMember(
            room_id=new_room.id,
            user_id=current_user.id,
            is_admin=True
        )
        
        db.add(member)
        db.commit()
        
        # 构建响应
        result = ChatRoomResponse.from_orm(new_room)
        result.member_count = 1
        result.is_member = True
        result.is_admin = True
        result.creator = None if not new_room.creator else UserBasic.from_orm(new_room.creator)
        
        return result
        
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"创建聊天室失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建聊天室失败"
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
            
            # 添加在线用户数
            room_response.online_users = manager.get_room_connections_count(room.id)
            
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
            
        # 添加在线用户数
        result.online_users = manager.get_room_connections_count(room_id)
        
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
        result.online_users = manager.get_room_connections_count(room_id)
        
        # 通知所有连接的用户
        update_message = {
            "type": "room_updated",
            "room_id": room_id,
            "content": f"聊天室信息已更新",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        await manager.broadcast_to_room(update_message, room_id)
        
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
            "type": "join",
            "room_id": room_id,
            "user_id": current_user.id,
            "username": current_user.username,
            "avatar_url": current_user.avatar_url,
            "content": f"{current_user.username} 加入了聊天室",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        # 注意：这里不等待广播完成，因为这是HTTP端点
        await manager.broadcast_to_room(room_message, room_id)
        
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
            "type": "leave",
            "room_id": room_id,
            "user_id": current_user.id,
            "username": current_user.username,
            "content": f"{current_user.username} 离开了聊天室",
            "timestamp": datetime.now().isoformat()
        }
        
        # 异步广播
        await manager.broadcast_to_room(room_message, room_id)
        
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
        await manager.broadcast_to_room(room_message, room_id)
        
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

# WebSocket路由
@router.websocket("/ws/user/{token}")
async def websocket_endpoint(
    websocket: WebSocket, 
    token: str,
    db: Session = Depends(get_db)
):
    """WebSocket连接处理 - 每用户一个连接"""
    # 验证Token
    user = await verify_token_ws(token, db)
    if not user:
            await websocket.close(code=1008)  # Policy Violation
            return
    
    # 接受WebSocket连接
    try:
        # 建立WebSocket连接
        await manager.connect(websocket, user.id)
        
        # 从数据库获取用户加入的聊天室
        user_rooms = (
            db.query(ChatRoomMember.room_id)
            .filter(ChatRoomMember.user_id == user.id)
            .all()
        )
        room_ids = [room[0] for room in user_rooms]
        
        # 同步数据库中的聊天室到连接管理器
        manager.sync_db_rooms(user.id, room_ids)
        
        # 告诉当前用户已成功连接，并发送初始信息
        welcome_message = {
            "type": "connected",
            "user_id": user.id,
            "content": f"您已连接到聊天系统",
            "room_ids": room_ids,
            "timestamp": datetime.now().isoformat()
        }
        
        await manager.send_personal_message(welcome_message, user.id)
        
        # 接收消息循环
        while True:
            try:
                # 接收消息
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # 验证消息格式
                if "type" not in message_data:
                    continue
                
                # 处理心跳消息 - 不需要room_id
                if message_data["type"] == "ping":
                    logger.debug(f"收到用户 {user.id} 的ping消息")
                    pong_message = {
                        "type": "pong"
                    }
                    await websocket.send_json(pong_message)
                    continue
                
                # 其他消息需要包含room_id
                if "room_id" not in message_data:
                    continue
                    
                room_id = int(message_data["room_id"])
                
                # 检查用户是否有权在此聊天室发消息
                if not manager.is_user_in_room(user.id, room_id):
                    # 查询数据库确认用户是否是聊天室成员
                    member = (
                        db.query(ChatRoomMember)
                        .filter(
                            ChatRoomMember.room_id == room_id,
                            ChatRoomMember.user_id == user.id
                        )
                        .first()
                    )
                    
                    if not member:
                        # 用户不是此聊天室成员，发送错误消息
                        error_message = {
                            "type": "error",
                            "room_id": room_id,
                            "content": "您不是此聊天室成员，无法发送消息",
                            "timestamp": datetime.now().isoformat()
                        }
                        await manager.send_personal_message(error_message, user.id)
                        continue
                    else:
                        # 用户是成员但未在manager中注册，添加用户到房间
                        manager.add_user_to_room(user.id, room_id)
                    
                # 处理不同类型的消息
                if message_data["type"] == "message":
                    # 处理聊天消息
                    if "content" not in message_data or not message_data["content"].strip():
                        continue
                        
                    # 创建消息记录
                    new_message = ChatRoomMessage(
                        room_id=room_id,
                        user_id=user.id,
                        content=message_data["content"],
                        is_system=False
                    )
                    
                    db.add(new_message)
                    db.commit()
                    db.refresh(new_message)
                    
                    # 获取房间信息
                    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
                    if not room:
                        continue
                    
                    # 更新用户最后阅读时间
                    member = (
                        db.query(ChatRoomMember)
                        .filter(
                            ChatRoomMember.room_id == room_id,
                            ChatRoomMember.user_id == user.id
                        )
                        .first()
                    )
                    if member:
                        member.last_read_at = datetime.now()
                        db.commit()
                    
                    # 广播消息
                    broadcast_message = {
                        "type": "message",
                        "message_id": new_message.id,
                        "room_id": room_id,
                        "user_id": user.id,
                        "username": user.username,
                        "avatar_url": user.avatar_url,
                        "content": new_message.content,
                        "timestamp": new_message.created_at.isoformat()
                    }
                    
                    await manager.broadcast_to_room(broadcast_message, room_id)
                    
                elif message_data["type"] == "typing":
                    # 处理正在输入状态
                    typing_message = {
                        "type": "typing",
                        "room_id": room_id,
                        "user_id": user.id,
                        "username": user.username,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await manager.broadcast_to_room(typing_message, room_id, exclude_user_id=user.id)
                
                elif message_data["type"] == "join_room":
                    # 用户请求加入聊天室
                    # 检查用户是否有权限加入
                    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
                    if not room:
                        error_message = {
                            "type": "error",
                            "content": "聊天室不存在",
                            "timestamp": datetime.now().isoformat()
                        }
                        await manager.send_personal_message(error_message, user.id)
                        continue
                    
                    # 检查是否公开聊天室或用户是管理员
                    if not room.is_public and not user.is_admin:
                        error_message = {
                            "type": "error",
                            "room_id": room_id,
                            "content": "该聊天室是私有的，需要邀请才能加入",
                            "timestamp": datetime.now().isoformat()
                        }
                        await manager.send_personal_message(error_message, user.id)
                        continue
                    
                    # 检查是否已经是成员
                    existing_member = (
                        db.query(ChatRoomMember)
                        .filter(
                            ChatRoomMember.room_id == room_id,
                            ChatRoomMember.user_id == user.id
                        )
                        .first()
                    )
                    
                    if not existing_member:
                        # 添加成员
                        new_member = ChatRoomMember(
                            room_id=room_id,
                            user_id=user.id,
                            is_admin=False
                        )
                        
                        db.add(new_member)
                        
                        # 添加系统消息
                        system_message = ChatRoomMessage(
                            room_id=room_id,
                            user_id=None,
                            content=f"{user.username} 加入了聊天室",
                            is_system=True
                        )
                        
                        db.add(system_message)
                        db.commit()
                    
                    # 更新连接管理器
                    manager.add_user_to_room(user.id, room_id)
                    
                    # 通知聊天室所有成员
                    join_message = {
                        "type": "join",
                        "room_id": room_id,
                        "user_id": user.id,
                        "username": user.username,
                        "avatar_url": user.avatar_url,
                        "content": f"{user.username} 加入了聊天室",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await manager.broadcast_to_room(join_message, room_id)
                    
                elif message_data["type"] == "leave_room":
                    # 用户请求离开聊天室
                    # 检查用户是否在该聊天室
                    member = (
                        db.query(ChatRoomMember)
                        .filter(
                            ChatRoomMember.room_id == room_id,
                            ChatRoomMember.user_id == user.id
                        )
                        .first()
                    )
                    
                    if member:
                        # 从数据库移除
                        db.delete(member)
                        
                        # 添加系统消息
                        system_message = ChatRoomMessage(
                            room_id=room_id,
                            user_id=None,
                            content=f"{user.username} 离开了聊天室",
                            is_system=True
                        )
                        
                        db.add(system_message)
                        db.commit()
                        
                        # 更新连接管理器
                        manager.remove_user_from_room(user.id, room_id)
                        
                        # 通知聊天室所有成员
                        leave_message = {
                            "type": "leave",
                            "room_id": room_id,
                            "user_id": user.id,
                            "username": user.username,
                            "content": f"{user.username} 离开了聊天室",
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        await manager.broadcast_to_room(leave_message, room_id)
                    
            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                # 忽略无效的JSON
                continue
            except Exception as e:
                logger.error(f"处理WebSocket消息失败: {str(e)}")
                break
                
    except WebSocketDisconnect:
        # 处理连接断开
        manager.disconnect(user.id)
        
        # 通知所有相关聊天室的其他用户
        await manager.broadcast_user_status_change(user.id, False)
        
    except Exception as e:
        logger.error(f"WebSocket处理失败: {str(e)}")
        manager.disconnect(user.id) 