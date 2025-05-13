from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
from enum import Enum
from datetime import datetime

class EventType(str, Enum):
    TRADE_COMPLETED = "trade_completed"  # 交易完成
    TRADE_CREATED = "trade_created"      # 交易創建
    TRADE_CANCELLED = "trade_cancelled"  # 交易取消
    PRICE_ALERT = "price_alert"          # 價格提醒
    SYSTEM_ALERT = "system_alert"        # 系統提醒
    USER_ACTION = "user_action"          # 用戶動作
    ACCOUNT_UPDATE = "account_update"    # 帳戶更新
    LOGIN_SUCCESS = "login_success"      # 登入成功
    
class EventPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EventBase(BaseModel):
    """事件基本模型"""
    event_type: EventType
    created_at: datetime = Field(default_factory=datetime.now)
    priority: EventPriority = Field(default=EventPriority.MEDIUM)
    source: str = Field(..., description="事件來源")
    data: Dict[str, Any] = Field(..., description="事件數據")
    
class TradeEvent(EventBase):
    """交易相關事件"""
    event_type: EventType = Field(..., description="交易事件類型")
    data: Dict[str, Any] = Field(..., description="交易數據")
    user_ids: List[int] = Field(..., description="相關用戶ID列表")
    
    # 交易特有字段
    trade_id: Optional[int] = Field(None, description="交易ID")
    trade_amount: Optional[float] = Field(None, description="交易金額")
    trade_status: Optional[str] = Field(None, description="交易狀態")
    
class PriceAlertEvent(EventBase):
    """價格提醒事件"""
    event_type: Literal[EventType.PRICE_ALERT] = EventType.PRICE_ALERT
    user_ids: List[int] = Field(..., description="設置提醒的用戶ID列表")
    
    # 價格提醒特有字段
    asset_id: int = Field(..., description="資產ID")
    target_price: float = Field(..., description="目標價格")
    current_price: float = Field(..., description="當前價格")
    condition: str = Field(..., description="條件 (高於/低於)")
    
class SystemEvent(EventBase):
    """系統事件"""
    event_type: Literal[EventType.SYSTEM_ALERT] = EventType.SYSTEM_ALERT
    is_global: bool = Field(default=True, description="是否全局事件")
    user_ids: Optional[List[int]] = Field(None, description="相關用戶ID列表（非全局事件時使用）")
    
    # 系統事件特有字段
    severity: str = Field(..., description="嚴重程度")
    component: str = Field(..., description="相關系統組件")
    action_required: bool = Field(default=False, description="是否需要操作")

class UserActionEvent(EventBase):
    """用戶動作事件"""
    event_type: EventType = Field(default=EventType.USER_ACTION, description="用戶動作事件類型")
    user_ids: List[int] = Field(..., description="相關用戶ID列表")
    
    # 用戶動作特有字段
    action_type: str = Field(..., description="動作類型")
    device_info: Optional[Dict[str, Any]] = Field(None, description="設備信息")
    location: Optional[str] = Field(None, description="位置信息")
    ip_address: Optional[str] = Field(None, description="IP地址") 