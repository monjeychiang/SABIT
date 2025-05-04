from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class ChatSessionBase(BaseModel):
    """聊天会话基本数据模型"""
    title: str


class ChatSessionCreate(ChatSessionBase):
    """创建聊天会话的请求数据模型"""
    title: str = "新对话"


class ChatSessionUpdate(ChatSessionBase):
    """更新聊天会话的请求数据模型"""
    pass


class ChatSessionResponse(ChatSessionBase):
    """聊天会话的响应数据模型"""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class ChatMessageBase(BaseModel):
    """聊天消息基本数据模型"""
    content: str
    role: str


class ChatMessageCreate(ChatMessageBase):
    """创建聊天消息的请求数据模型"""
    pass


class ChatMessageResponse(ChatMessageBase):
    """聊天消息的响应数据模型"""
    id: int
    session_id: int
    created_at: datetime

    class Config:
        orm_mode = True


class ChatRequest(BaseModel):
    """发送聊天消息的请求数据模型"""
    session_id: int
    message: str


class ChatHistoryResponse(BaseModel):
    """聊天历史记录的响应数据模型"""
    messages: List[ChatMessageResponse]
    
    class Config:
        orm_mode = True


class ChatSessionWithMessages(ChatSessionResponse):
    """带有消息列表的聊天会话响应数据模型"""
    messages: List[ChatMessageResponse] = []
    
    class Config:
        orm_mode = True


class PaginatedChatSessions(BaseModel):
    """分页的聊天会话列表"""
    items: List[ChatSessionResponse]
    total: int
    page: int
    per_page: int 