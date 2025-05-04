from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ChatRoomBase(BaseModel):
    """聊天室基本信息模型"""
    name: str = Field(..., min_length=1, max_length=100, description="聊天室名称")
    description: Optional[str] = Field(None, max_length=500, description="聊天室描述")
    is_public: bool = Field(True, description="是否公开聊天室")
    is_official: Optional[bool] = Field(False, description="是否官方聊天室")


class ChatRoomCreate(ChatRoomBase):
    """创建聊天室请求模型"""
    pass


class ChatRoomUpdate(BaseModel):
    """更新聊天室请求模型"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="聊天室名称")
    description: Optional[str] = Field(None, max_length=500, description="聊天室描述")
    is_public: Optional[bool] = Field(None, description="是否公开聊天室")
    is_official: Optional[bool] = Field(None, description="是否官方聊天室")
    max_members: Optional[int] = Field(None, ge=0, description="聊天室最大成员数(0表示不限制)")
    announcement: Optional[str] = Field(None, max_length=500, description="聊天室公告")


class ChatRoomMemberBase(BaseModel):
    """聊天室成员基本信息模型"""
    user_id: int = Field(..., description="用户ID")
    room_id: int = Field(..., description="聊天室ID")
    is_admin: bool = Field(False, description="是否为聊天室管理员")


class ChatRoomMemberCreate(BaseModel):
    """添加聊天室成员请求模型"""
    user_id: int = Field(..., description="用户ID")
    is_admin: bool = Field(False, description="是否为聊天室管理员")


class ChatRoomMemberUpdate(BaseModel):
    """更新聊天室成员请求模型"""
    is_admin: bool = Field(..., description="是否为聊天室管理员")


class ChatRoomMessageBase(BaseModel):
    """聊天室消息基本信息模型"""
    content: str = Field(..., min_length=1, description="消息内容")


class ChatRoomMessageCreate(ChatRoomMessageBase):
    """创建聊天室消息请求模型"""
    pass


class ChatRoomMessageDB(ChatRoomMessageBase):
    """聊天室消息数据库模型"""
    id: int
    room_id: int
    user_id: Optional[int]
    is_system: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserBasic(BaseModel):
    """用户基本信息模型"""
    id: int
    username: str
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class ChatRoomMemberDB(BaseModel):
    """聊天室成员数据库模型"""
    id: int
    room_id: int
    user_id: int
    is_admin: bool = False
    joined_at: datetime
    last_read_at: Optional[datetime] = None
    user: Optional[UserBasic] = None
    
    class Config:
        from_attributes = True


class ChatRoomMessageResponse(ChatRoomMessageDB):
    """聊天室消息响应模型"""
    user: Optional[UserBasic] = None


class ChatRoomDB(ChatRoomBase):
    """聊天室数据库模型"""
    id: int
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChatRoomResponse(ChatRoomDB):
    """聊天室响应模型"""
    creator: Optional[UserBasic] = None
    member_count: int = 0
    is_member: bool = False
    is_admin: bool = False
    online_users: Optional[int] = None


class ChatRoomDetailResponse(ChatRoomResponse):
    """聊天室详情响应模型"""
    members: List[ChatRoomMemberDB] = []
    latest_messages: List[ChatRoomMessageResponse] = []
    max_members: int = 0
    announcement: Optional[str] = None


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""
    type: str = Field(..., description="消息类型: message, join, leave, typing")
    room_id: int = Field(..., description="聊天室ID")
    content: Optional[str] = Field(None, description="消息内容")
    user_id: Optional[int] = Field(None, description="用户ID") 