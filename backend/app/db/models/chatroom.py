from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from ...db.database import Base
from .base import get_china_time


class ChatRoom(Base):
    """
    聊天室模型
    
    此模型定义了聊天室的数据结构，包含聊天室基本信息和与用户、消息的关联关系。
    """
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_public = Column(Boolean, default=True, nullable=False)
    is_official = Column(Boolean, default=False, nullable=False)
    max_members = Column(Integer, default=0, nullable=False)  # 0表示不限制成员数量
    announcement = Column(String(500), nullable=True)  # 聊天室公告
    created_at = Column(DateTime, default=get_china_time)
    updated_at = Column(DateTime, default=get_china_time, onupdate=get_china_time)
    
    # 关联关系：创建者
    creator = relationship("User", foreign_keys=[created_by], backref="created_rooms")
    
    # 关联关系：聊天室消息
    messages = relationship("ChatRoomMessage", back_populates="room", cascade="all, delete-orphan")
    
    # 关联关系：聊天室成员
    members = relationship("ChatRoomMember", back_populates="room", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatRoom id={self.id} name={self.name}>"


class ChatRoomMessage(Base):
    """
    聊天室消息模型
    
    此模型定义了聊天室中的消息数据结构，包含消息内容、发送者和时间戳。
    """
    __tablename__ = "chat_room_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=get_china_time)
    
    # 关联关系：所属聊天室
    room = relationship("ChatRoom", back_populates="messages")
    
    # 关联关系：发送者
    user = relationship("User", foreign_keys=[user_id], backref="chat_room_messages")
    
    def __repr__(self):
        return f"<ChatRoomMessage id={self.id} room_id={self.room_id}>"


class ChatRoomMember(Base):
    """
    聊天室成员模型
    
    此模型定义了用户与聊天室的关系，包含用户在聊天室中的角色和状态。
    """
    __tablename__ = "chat_room_members"
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    joined_at = Column(DateTime, default=get_china_time)
    last_read_at = Column(DateTime, default=get_china_time)
    
    # 关联关系：聊天室
    room = relationship("ChatRoom", back_populates="members")
    
    # 关联关系：用户
    user = relationship("User", backref="chat_room_memberships")
    
    def __repr__(self):
        return f"<ChatRoomMember room_id={self.room_id} user_id={self.user_id}>" 