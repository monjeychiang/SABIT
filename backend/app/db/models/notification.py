from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from ...db.database import Base
from .base import get_china_time, NotificationType

class Notification(Base):
    """
    通知模型
    
    用於存儲系統向用戶發送的各類通知信息，包括系統公告、交易提醒、
    警告信息等。支持個人通知和全局通知，並可按不同類型分類展示。
    
    通知可以設置已讀狀態，方便用戶管理和追蹤未讀信息。每條通知
    都會記錄創建時間，用於時間排序和過期處理。
    """
    __tablename__ = "notifications"  # 資料表名稱
    
    id = Column(Integer, primary_key=True, index=True)  # 通知唯一識別符，主鍵
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # 關聯用戶ID，允許為空（全局通知）
    title = Column(String(100), nullable=False)  # 通知標題，簡短描述通知內容
    message = Column(Text, nullable=False)  # 通知詳細信息，使用Text類型支持長文本
    is_global = Column(Boolean, default=False)  # 是否為全局通知（發送給所有用戶）
    read = Column(Boolean, default=False)  # 是否已讀，用於標記用戶已閱讀的通知
    created_at = Column(DateTime, default=get_china_time)  # 通知創建時間，用於排序和過期處理
    
    # 通知類型，用於前端以不同樣式顯示不同類型的通知
    # 默認為一般信息類型(INFO)
    notification_type = Column(Enum(NotificationType), default=NotificationType.INFO, nullable=False)
    
    # 關聯關係：所屬用戶
    # 多對一關係，多個通知可以關聯到同一個用戶
    # 全局通知的user_id為NULL，不關聯特定用戶
    user = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識通知物件
        """
        return f"<Notification {self.id}: {self.title}>" 