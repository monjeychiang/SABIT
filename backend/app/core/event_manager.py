import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
import asyncio
from datetime import datetime
import uuid
from sqlalchemy.orm import Session

from ..schemas.event import EventBase, EventType, TradeEvent, PriceAlertEvent, SystemEvent, UserActionEvent
from ..schemas.notification import NotificationCreate, NotificationType
from ..api.endpoints.notifications import create_and_broadcast_notification
from ..core.main_ws_manager import main_ws_manager

# 設置日誌記錄
logger = logging.getLogger(__name__)

# 系統事件類型列表 - 這些事件生成的通知不存入數據庫，只通過WebSocket發送
SYSTEM_EVENT_TYPES = [
    EventType.LOGIN_SUCCESS,
    EventType.SYSTEM_ALERT,
    EventType.PRICE_ALERT,
    EventType.ACCOUNT_UPDATE
]

# 事件通知模板配置
EVENT_TEMPLATES = {
    # 交易事件模板
    EventType.TRADE_COMPLETED: {
        "title": "交易已完成",
        "message": "您的交易 #{trade_id} 已成功完成。交易金額: {trade_amount}，交易時間: {trade_time}",
        "notification_type": NotificationType.SUCCESS
    },
    EventType.TRADE_CREATED: {
        "title": "新交易已創建",
        "message": "您創建了一筆新交易 #{trade_id}。交易金額: {trade_amount}，交易狀態: {trade_status}",
        "notification_type": NotificationType.INFO
    },
    EventType.TRADE_CANCELLED: {
        "title": "交易已取消",
        "message": "您的交易 #{trade_id} 已被取消。交易金額: {trade_amount}，取消原因: {cancel_reason}",
        "notification_type": NotificationType.WARNING
    },
    
    # 價格提醒事件模板
    EventType.PRICE_ALERT: {
        "title": "價格提醒",
        "message": "您關注的資產 {asset_name} 當前價格 {current_price} 已{condition}您設置的提醒價格 {target_price}",
        "notification_type": NotificationType.INFO
    },
    
    # 系統提醒事件模板
    EventType.SYSTEM_ALERT: {
        "title": "系統提醒",
        "message": "系統{component}出現{severity}情況：{message}",
        "notification_type": NotificationType.WARNING
    },
    
    # 帳戶更新事件模板
    EventType.ACCOUNT_UPDATE: {
        "title": "帳戶更新通知",
        "message": "您的帳戶已更新：{update_message}",
        "notification_type": NotificationType.INFO
    },
    
    # 登入成功事件模板
    EventType.LOGIN_SUCCESS: {
        "title": "登入安全提醒",
        "message": "您已於 {login_time} 使用 {device_name} ({browser}) 登入系統。IP: {ip_address}。如非本人操作，請立即修改密碼。",
        "notification_type": NotificationType.INFO
    }
}

class EventManager:
    """事件管理器 - 處理系統事件並轉換為通知"""
    
    def __init__(self):
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self._initialize_default_handlers()
        
    def _initialize_default_handlers(self):
        """初始化默認事件處理器"""
        # 為系統事件類型註冊直接WebSocket處理器
        for event_type in SYSTEM_EVENT_TYPES:
            self.register_handler(event_type, self._system_event_to_websocket_handler)
            
        # 為其他事件類型註冊默認處理器（存入數據庫）
        for event_type in EventType:
            if event_type not in SYSTEM_EVENT_TYPES:
                self.register_handler(event_type, self._default_event_to_notification_handler)
    
    def register_handler(self, event_type: EventType, handler: Callable):
        """註冊事件處理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.info(f"已為事件類型 {event_type} 註冊處理器: {handler.__name__}")
    
    async def process_event(self, event: EventBase, db: Session):
        """處理事件"""
        logger.info(f"處理事件: 類型={event.event_type}, 優先級={event.priority}, 來源={event.source}")
        
        # 檢查是否有針對此事件類型的處理器
        if event.event_type in self.event_handlers:
            for handler in self.event_handlers[event.event_type]:
                try:
                    # 異步執行處理器
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event, db)
                    else:
                        # 如果不是協程函數，在執行緒池中執行
                        handler(event, db)
                except Exception as e:
                    logger.error(f"事件處理器執行失敗: {str(e)}")
        else:
            logger.warning(f"沒有找到事件類型 {event.event_type} 的處理器")
    
    async def _default_event_to_notification_handler(self, event: EventBase, db: Session):
        """默認的事件轉通知處理器 - 存入數據庫並通過WebSocket發送"""
        try:
            # 獲取事件類型對應的通知模板
            if event.event_type not in EVENT_TEMPLATES:
                logger.warning(f"沒有找到事件類型 {event.event_type} 的通知模板")
                return
                
            template = EVENT_TEMPLATES[event.event_type]
            
            # 提取通知所需的變量
            template_variables = self._extract_template_variables(event)
            
            # 確定通知接收者
            is_global = False
            user_ids = None
            
            # 根據事件類型確定通知發送範圍
            if isinstance(event, SystemEvent) and event.is_global:
                is_global = True
            elif hasattr(event, 'user_ids') and event.user_ids:
                user_ids = event.user_ids
            
            # 創建通知請求
            notification_create = NotificationCreate(
                title=template["title"],
                message=template["message"],
                notification_type=template["notification_type"],
                is_global=is_global,
                user_ids=user_ids,
                template_variables=template_variables
            )
            
            # 創建並廣播通知
            created_notifications = await create_and_broadcast_notification(notification_create, db)
            logger.info(f"已從事件 {event.event_type} 創建 {len(created_notifications)} 條通知")
            
        except Exception as e:
            logger.error(f"將事件轉換為通知時出錯: {str(e)}")
            
    async def _system_event_to_websocket_handler(self, event: EventBase, db: Session):
        """系統事件直接通過WebSocket發送，不存入數據庫"""
        try:
            # 獲取事件類型對應的通知模板
            if event.event_type not in EVENT_TEMPLATES:
                logger.warning(f"沒有找到事件類型 {event.event_type} 的通知模板")
                return
                
            template = EVENT_TEMPLATES[event.event_type]
            
            # 提取通知所需的變量
            template_variables = self._extract_template_variables(event)
            
            # 處理模板變量替換
            title = template["title"]
            message = template["message"]
            notification_type = template["notification_type"]
            
            for key, value in template_variables.items():
                placeholder = "{" + key + "}"
                title = title.replace(placeholder, str(value))
                message = message.replace(placeholder, str(value))
            
            # 生成唯一ID
            notification_id = f"sys_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
            
            # 創建通知對象
            notification_data = {
                "id": notification_id,
                "title": title,
                "message": message,
                "notification_type": notification_type.value,
                "is_read": False,
                "created_at": datetime.now().isoformat(),
                "is_global": False,
                "source": "system"  # 標記來源為系統事件
            }
            
            # 創建標準格式的消息
            message = {
                "type": "notification",
                "payload": notification_data,
                "notification": notification_data
            }
            
            # 確定發送範圍
            if isinstance(event, SystemEvent) and event.is_global:
                # 廣播給所有用戶
                logger.info(f"廣播系統事件通知: {title}")
                await main_ws_manager.broadcast(message)
            elif hasattr(event, 'user_ids') and event.user_ids:
                # 發送給指定用戶
                for user_id in event.user_ids:
                    notification_data["user_id"] = user_id  # 添加用戶ID
                    
                    # 重新打包消息，確保每個用戶收到包含自己ID的通知
                    user_message = {
                        "type": "notification",
                        "payload": notification_data,
                        "notification": notification_data
                    }
                    
                    logger.info(f"發送系統事件通知給用戶 {user_id}: {title}")
                    await main_ws_manager.send_to_user(user_id, user_message)
            
            logger.info(f"已通過WebSocket發送系統事件 {event.event_type} 的通知")
            
        except Exception as e:
            logger.error(f"通過WebSocket發送系統事件通知時出錯: {str(e)}")
    
    def _extract_template_variables(self, event: EventBase) -> Dict[str, Any]:
        """從事件中提取通知模板所需的變量"""
        variables = {}
        
        # 基本事件數據
        variables.update(event.data)
        
        # 添加通用時間變量
        variables["event_time"] = event.created_at.strftime("%Y-%m-%d %H:%M:%S")
        
        # 根據事件類型添加特定變量
        if isinstance(event, TradeEvent) and event.trade_id:
            variables["trade_id"] = event.trade_id
            variables["trade_amount"] = event.trade_amount
            variables["trade_status"] = event.trade_status
            variables["trade_time"] = event.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
        elif isinstance(event, PriceAlertEvent):
            variables["asset_id"] = event.asset_id
            variables["target_price"] = event.target_price
            variables["current_price"] = event.current_price
            variables["condition"] = "高於" if event.condition == "above" else "低於"
            
        elif isinstance(event, SystemEvent):
            variables["severity"] = event.severity
            variables["component"] = event.component
            variables["is_action_required"] = "需要" if event.action_required else "不需要"
        
        elif isinstance(event, UserActionEvent) and event.event_type == EventType.LOGIN_SUCCESS:
            variables["login_time"] = event.created_at.strftime("%Y-%m-%d %H:%M:%S")
            variables["action_type"] = event.action_type
            
            # 設備資訊處理
            if event.device_info:
                # 優先使用display_name，如果有的話
                if "display_name" in event.device_info:
                    variables["device_name"] = event.device_info.get("display_name")
                else:
                    # 回退到name
                    variables["device_name"] = event.device_info.get("name", "未知設備")
                
                # 瀏覽器資訊
                variables["browser"] = event.device_info.get("browser", "未知瀏覽器")
            else:
                variables["device_name"] = "未知設備"
                variables["browser"] = "未知瀏覽器"
            
            # 正確處理IP地址
            variables["ip_address"] = event.ip_address or "未知IP"
            
        return variables

# 創建全局事件管理器實例
event_manager = EventManager() 