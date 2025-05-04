from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from ...db.database import Base
from .base import get_china_time
from datetime import datetime

class ChatSession(Base):
    """
    聊天會話模型
    
    此模型定義了用戶與AI助手之間的聊天會話資料結構，包含會話基本信息
    以及與用戶和消息的關聯關係。
    """
    __tablename__ = "chat_sessions"  # 資料表名稱
    
    id = Column(Integer, primary_key=True, index=True)  # 會話唯一識別符，主鍵
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # 關聯用戶ID
    title = Column(String(100), nullable=False, default="新的对话")  # 會話標題
    created_at = Column(DateTime, default=get_china_time)  # 會話創建時間
    updated_at = Column(DateTime, default=get_china_time, onupdate=get_china_time)  # 會話更新時間
    
    # 關聯關係：所屬用戶
    # 多對一關係，多個聊天會話可以關聯到同一個用戶
    user = relationship("User", back_populates="chat_sessions")
    
    # 關聯關係：會話消息
    # 一對多關係，一個會話可以包含多條消息記錄
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識會話物件
        """
        return f"<ChatSession id={self.id} title={self.title}>"


class ChatMessage(Base):
    """
    聊天消息模型
    
    此模型定義了聊天會話中的消息資料結構，包含消息內容、
    角色(用戶或助手)和相關時間戳記。
    """
    __tablename__ = "chat_messages"  # 資料表名稱
    
    id = Column(Integer, primary_key=True, index=True)  # 消息唯一識別符，主鍵
    session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)  # 關聯會話ID
    role = Column(String(20), nullable=False)  # 消息角色，例如 'user' 或 'assistant'
    content = Column(Text, nullable=False)  # 消息內容，使用Text類型支持長文本
    created_at = Column(DateTime, default=get_china_time)  # 消息創建時間
    
    # 關聯關係：所屬會話
    # 多對一關係，多條消息可以關聯到同一個會話
    session = relationship("ChatSession", back_populates="messages")
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識消息物件
        """
        return f"<ChatMessage id={self.id} role={self.role}>"


class ChatMessageUsage(Base):
    """聊天消息使用统计模型
    
    记录用户每天发送的消息数量，用于限制用户每天的消息发送数量
    新的实现采用每用户一条记录的方式，每天24:00自动重置计数
    """
    __tablename__ = "chat_message_usage"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    message_count = Column(Integer, default=0, comment="当日消息计数")
    last_reset_at = Column(DateTime, default=datetime.now, comment="上次重置时间")
    
    # 关联关系：用户
    user = relationship("User", back_populates="chat_message_usage")
    
    def __repr__(self):
        return f"<ChatMessageUsage(user_id={self.user_id}, message_count={self.message_count}, last_reset_at={self.last_reset_at})>" 