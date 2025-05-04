from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from ..db.models.base import NotificationType

class NotificationBase(BaseModel):
    title: str = Field(..., title="通知标题", description="通知的标题，不超过100字符")
    message: str = Field(..., title="通知内容", description="通知的详细内容")
    notification_type: NotificationType = Field(NotificationType.INFO, title="通知类型", description="通知的类型，影响前端显示样式")

class NotificationCreate(NotificationBase):
    is_global: bool = Field(False, title="是否全局通知", description="如果为True，则发送给所有用户")
    user_ids: Optional[List[int]] = Field(None, title="用户ID列表", description="要发送通知的特定用户ID列表，如果is_global为True则忽略")

class NotificationUpdate(BaseModel):
    read: bool = Field(..., title="是否已读", description="设置通知为已读或未读")

class NotificationResponse(NotificationBase):
    id: int
    user_id: Optional[int] = None
    is_global: bool
    read: bool
    created_at: datetime
    
    class Config:
        orm_mode = True

class PaginatedNotifications(BaseModel):
    items: List[NotificationResponse]
    total: int
    page: int
    per_page: int
    
# 通知設置相關模型
class NotificationSettingsBase(BaseModel):
    email_notifications: bool = Field(True, title="電子郵件通知", description="是否啟用電子郵件通知")
    trade_notifications: bool = Field(True, title="交易通知", description="是否啟用交易通知")
    system_notifications: bool = Field(True, title="系統通知", description="是否啟用系統通知")
    desktop_notifications: bool = Field(True, title="桌面通知", description="是否啟用桌面通知")
    sound_notifications: bool = Field(True, title="聲音通知", description="是否啟用聲音通知")
    notification_preferences: Dict[str, bool] = Field(
        default_factory=lambda: {
            "info": True,
            "success": True,
            "warning": True,
            "error": True,
            "system": True
        },
        title="通知類型偏好",
        description="每種通知類型的偏好設置"
    )

class NotificationSettingsCreate(NotificationSettingsBase):
    pass

class NotificationSettingsUpdate(NotificationSettingsBase):
    pass

class NotificationSettingsResponse(NotificationSettingsBase):
    id: int
    user_id: int
    updated_at: datetime
    
    class Config:
        orm_mode = True 