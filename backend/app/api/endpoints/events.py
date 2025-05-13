from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from typing import Any, Dict, List

from ...db.database import get_db
from ...db.models.user import User
from ...core.security import get_current_user
from ...api.endpoints.admin import get_current_admin_user
from ...schemas.event import EventBase, EventType, TradeEvent, PriceAlertEvent, SystemEvent, UserActionEvent
from ...core.event_manager import event_manager

# 設置日誌記錄
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/process", status_code=status.HTTP_202_ACCEPTED)
async def process_event(
    event: EventBase,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)  # 只允許管理員直接提交事件
) -> Dict[str, Any]:
    """
    處理系統事件（僅限管理員）
    
    此端點允許提交各種系統事件，事件管理器將處理這些事件並生成相應的通知。
    
    參數:
        event: 要處理的事件數據
        
    返回:
        包含處理結果的響應
    """
    try:
        logger.info(f"接收到事件提交: 類型={event.event_type}, 來源={event.source}")
        
        # 傳遞事件給事件管理器處理
        await event_manager.process_event(event, db)
        
        return {
            "status": "accepted",
            "message": f"事件 {event.event_type} 已接受處理",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"處理事件時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理事件時出錯: {str(e)}"
        )

@router.post("/trade", status_code=status.HTTP_202_ACCEPTED)
async def process_trade_event(
    event: TradeEvent,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # 允許普通用戶提交交易事件
) -> Dict[str, Any]:
    """
    處理交易相關事件
    
    此端點用於處理交易完成、創建或取消等事件，並向相關用戶發送通知。
    
    參數:
        event: 交易事件詳情
        
    返回:
        處理結果
    """
    try:
        # 檢查用戶權限（只能提交與自己相關的交易事件）
        if not current_user.is_admin and current_user.id not in event.user_ids:
            logger.warning(f"用戶 {current_user.id} 嘗試提交與自己無關的交易事件")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能提交與自己相關的交易事件"
            )
            
        logger.info(f"接收到交易事件: 類型={event.event_type}, 交易ID={event.trade_id}")
        
        # 傳遞事件給事件管理器處理
        await event_manager.process_event(event, db)
        
        return {
            "status": "accepted",
            "message": f"交易事件 {event.event_type} 已接受處理",
            "trade_id": event.trade_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"處理交易事件時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理交易事件時出錯: {str(e)}"
        )

@router.post("/price-alert", status_code=status.HTTP_202_ACCEPTED)
async def process_price_alert(
    event: PriceAlertEvent,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    處理價格提醒事件
    
    當資產價格達到用戶設定的目標價格時，提交此事件以通知相關用戶。
    
    參數:
        event: 價格提醒事件詳情
        
    返回:
        處理結果
    """
    try:
        # 檢查權限
        if not current_user.is_admin and current_user.id not in event.user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="只能提交與自己相關的價格提醒事件"
            )
            
        logger.info(f"接收到價格提醒事件: 資產ID={event.asset_id}, 目標價格={event.target_price}, 當前價格={event.current_price}")
        
        # 傳遞事件給事件管理器處理
        await event_manager.process_event(event, db)
        
        return {
            "status": "accepted",
            "message": "價格提醒事件已接受處理",
            "asset_id": event.asset_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"處理價格提醒事件時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理價格提醒事件時出錯: {str(e)}"
        )

@router.post("/system", status_code=status.HTTP_202_ACCEPTED)
async def process_system_event(
    event: SystemEvent,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)  # 只允許管理員提交系統事件
) -> Dict[str, Any]:
    """
    處理系統事件
    
    用於系統警報、維護通知等系統級事件的處理，通常會向所有用戶或特定用戶組發送通知。
    
    參數:
        event: 系統事件詳情
        
    返回:
        處理結果
    """
    try:
        logger.info(f"接收到系統事件: 嚴重程度={event.severity}, 組件={event.component}")
        
        # 傳遞事件給事件管理器處理
        await event_manager.process_event(event, db)
        
        return {
            "status": "accepted",
            "message": "系統事件已接受處理",
            "component": event.component,
            "severity": event.severity,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"處理系統事件時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理系統事件時出錯: {str(e)}"
        )

@router.post("/login-success", status_code=status.HTTP_202_ACCEPTED)
async def process_login_success(
    event: UserActionEvent,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    處理登入成功事件
    
    當用戶成功登入系統時，發送此事件以記錄登入活動並通知用戶。
    包含登入時間、位置、IP地址和設備信息等。
    
    參數:
        event: 登入事件詳情
        
    返回:
        處理結果
    """
    try:
        # 檢查事件是否是登入成功事件
        if event.event_type != EventType.LOGIN_SUCCESS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="提交的事件類型不是登入成功事件"
            )
            
        # 確保事件只包含當前用戶的ID（安全措施）
        if current_user.id not in event.user_ids:
            event.user_ids = [current_user.id]
            
        # 設置默認的操作類型（如果未提供）
        if not hasattr(event, 'action_type') or not event.action_type:
            event.action_type = "login"
            
        logger.info(f"接收到登入成功事件: 用戶ID={current_user.id}, IP={event.ip_address}, 設備={event.device_info}")
        
        # 傳遞事件給事件管理器處理
        await event_manager.process_event(event, db)
        
        return {
            "status": "accepted",
            "message": "登入成功事件已接受處理",
            "user_id": current_user.id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"處理登入成功事件時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"處理登入成功事件時出錯: {str(e)}"
        ) 