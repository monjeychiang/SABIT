from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from ...db.database import Base
from .base import get_china_time

class NotificationSetting(Base):
    """
    通知設置模型
    
    存儲用戶的通知偏好設置，允許用戶自定義接收哪些類型的通知，
    以及通過哪些渠道接收這些通知（電子郵件、桌面通知等）。
    
    每個用戶僅能有一個通知設置記錄，通過與用戶表的一對一關係實現。
    設置項使用布林值標記啟用/禁用狀態，並使用JSON欄位存儲更靈活的配置。
    """
    __tablename__ = "notification_settings"  # 資料表名稱
    
    id = Column(Integer, primary_key=True, index=True)  # 唯一識別符，主鍵
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)  # 關聯用戶ID，唯一約束確保一對一關係
    
    # 是否啟用電子郵件通知
    # 啟用後，系統會發送郵件通知到用戶註冊的電子郵件地址
    email_notifications = Column(Boolean, default=True)
    
    # 是否啟用交易通知
    # 包括訂單成交、持倉變更、止損止盈觸發等交易相關通知
    trade_notifications = Column(Boolean, default=True)
    
    # 是否啟用系統通知
    # 包括系統維護、版本更新、安全提醒等系統相關通知
    system_notifications = Column(Boolean, default=True)
    
    # 是否啟用桌面通知
    # 啟用後，前端網頁將使用瀏覽器的通知API顯示彈出通知
    desktop_notifications = Column(Boolean, default=True)
    
    # 是否啟用聲音通知
    # 啟用後，前端網頁收到新通知時將播放提示音
    sound_notifications = Column(Boolean, default=True)
    
    # 通知設置的詳細偏好配置（JSON格式）
    # 可針對每種通知類型設置不同的接收偏好
    # 使用lambda函數動態生成預設值，所有通知類型默認啟用
    notification_preferences = Column(JSON, default=lambda: {
        "info": True,      # 一般信息通知，如系統公告、提示等
        "success": True,   # 成功信息通知，如操作成功、交易完成等
        "warning": True,   # 警告信息通知，如風險提示、余額不足等
        "error": True,     # 錯誤信息通知，如操作失敗、系統錯誤等
        "system": True     # 系統通知，如維護通知、版本更新等
    })
    
    # 最後更新時間
    # 記錄用戶何時修改過通知設置，自動在更新時更新
    updated_at = Column(DateTime, default=get_china_time, onupdate=get_china_time)
    
    # 關聯關係：所屬用戶
    # 一對一關係，每個通知設置記錄只屬於一個特定用戶
    user = relationship("User", back_populates="notification_settings")
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識通知設置物件
        """
        return f"<NotificationSetting for user_id={self.user_id}>" 