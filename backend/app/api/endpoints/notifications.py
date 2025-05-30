from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Any, List, Optional, Dict
from datetime import datetime
import logging
import asyncio
from sqlalchemy.sql import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ...db.database import get_db
from ...db.models import User, Notification, NotificationType
from ...schemas.notification import NotificationCreate, NotificationResponse, NotificationUpdate, PaginatedNotifications
from ...core.security import get_current_user, verify_token
from ...api.endpoints.admin import get_current_admin_user
from ...core.main_ws_manager import main_ws_manager

# 設置日誌記錄
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", response_model=PaginatedNotifications)
async def get_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    notification_type: Optional[NotificationType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取當前用戶的通知列表（包括全局通知和用戶特定通知）
    
    此端點返回登入用戶的所有可見通知，包括：
    1. 專門發送給該用戶的個人通知
    2. 發送給所有用戶的全局通知
    
    支援按頁進行分頁並可根據通知類型進行過濾。
    返回的通知按時間降序排列，最新的通知排在前面。
    
    參數:
        page: 請求的頁碼（從1開始）
        per_page: 每頁返回的通知數量（最大100條）
        notification_type: 可選的通知類型過濾器
        
    返回:
        一個包含通知列表和分頁資訊的物件
    """
    skip = (page - 1) * per_page
    
    # 構建基本查詢
    query = db.query(Notification).filter(
        or_(
            Notification.user_id == current_user.id,
            Notification.is_global == True
        )
    )
    
    # 如果指定了通知類型，添加過濾條件
    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)
    
    # 按創建時間降序排序
    query = query.order_by(Notification.created_at.desc())
    
    total = query.count()
    notifications = query.offset(skip).limit(per_page).all()
    
    return {
        "items": notifications,
        "total": total,
        "page": page,
        "per_page": per_page
    }

@router.post("", response_model=List[NotificationResponse], status_code=status.HTTP_201_CREATED)
async def create_notification(
    notification: NotificationCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    創建通知（僅限管理員）
    
    允許管理員建立新的通知訊息，並支援多種發送模式：
    - 可以創建全局通知（發送給所有用戶）
    - 可以發送給特定用戶列表
    - 可以指定通知類型（如系統通知、警告等）
    
    此端點同時支援WebSocket即時推送，連接的用戶將實時收到通知。
    
    參數:
        notification: 包含通知內容、類型和接收者資訊的物件
    
    權限要求:
        僅限管理員使用
        
    返回:
        創建的通知列表
    """
    if not notification.is_global and not notification.user_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必須指定用戶ID列表或設置為全局通知"
        )
    
    # 使用創建並廣播函數
    created_notifications = await create_and_broadcast_notification(notification, db)
    return created_notifications

@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    將通知標記為已讀
    
    允許用戶將特定通知標記為已讀狀態，以便在通知列表中區分已讀和未讀通知。
    用戶只能標記自己的通知或發送給所有人的全局通知。
    
    參數:
        notification_id: 要標記為已讀的通知ID
    
    返回:
        更新後的通知物件
        
    錯誤:
        404: 通知不存在或不屬於當前用戶
    """
    notification = db.query(Notification).filter(
        and_(
            Notification.id == notification_id,
            or_(
                Notification.user_id == current_user.id,
                Notification.is_global == True
            )
        )
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知不存在或不屬於當前用戶"
        )
    
    notification.read = True
    db.commit()
    db.refresh(notification)
    
    return notification

@router.get("/missed", response_model=PaginatedNotifications)
async def get_missed_notifications(
    since: Optional[datetime] = Query(None, description="獲取此時間之後的通知"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    notification_type: Optional[NotificationType] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    獲取用戶在離線期間錯過的通知
    
    此端點專門用於檢索用戶在未登入系統期間發送的通知。
    可以通過since參數指定開始時間，只返回該時間之後的通知。
    支援分頁和按通知類型過濾，預設每頁返回較多通知（50條）。
    
    參數:
        since: 可選的時間點，僅返回此時間之後的通知
        page: 頁碼，從1開始
        per_page: 每頁返回的通知數量，默認50條
        notification_type: 可選的通知類型過濾
        
    返回:
        包含通知列表和分頁資訊的物件
    """
    skip = (page - 1) * per_page
    
    # 構建基本查詢 - 獲取用戶特定通知和全局通知
    query = db.query(Notification).filter(
        or_(
            Notification.user_id == current_user.id,
            Notification.is_global == True
        )
    )
    
    # 如果提供了時間範圍，添加時間過濾條件
    if since:
        query = query.filter(Notification.created_at >= since)
    
    # 如果指定了通知類型，添加類型過濾條件
    if notification_type:
        query = query.filter(Notification.notification_type == notification_type)
    
    # 按創建時間降序排序
    query = query.order_by(Notification.created_at.desc())
    
    total = query.count()
    notifications = query.offset(skip).limit(per_page).all()
    
    # 記錄請求信息
    logger.info(f"用戶 {current_user.username} 獲取錯過的通知，開始時間: {since}，共找到 {total} 條")
    
    return {
        "items": notifications,
        "total": total,
        "page": page,
        "per_page": per_page
    }

# 廣播新通知給用戶
async def broadcast_notification(notification: Notification, db: Session) -> None:
    """
    廣播新通知給用戶
    將新創建的通知通過主WebSocket發送給相關用戶。
    """
    try:
        # 檢查消息中是否有未替換的模板變量
        message_text = notification.message
        if "{" in message_text and "}" in message_text:
            logger.warning(f"檢測到通知消息中可能包含未替換的模板變量: {message_text}")
        
        notification_data = {
            "id": notification.id,
            "title": notification.title,
            "message": notification.message,
            "is_global": notification.is_global,
            "is_read": notification.read,
            "notification_type": notification.notification_type.value,
            "created_at": notification.created_at.isoformat(),
            "user_id": notification.user_id
        }
        
        # 創建標準格式的消息，使用payload和notification兩個字段都包含通知數據
        # 這樣前端無論使用哪個字段都能獲取到通知
        message = {
            "type": "notification",
            "payload": notification_data,
            "notification": notification_data  # 保留notification字段以兼容舊代碼
        }
        
        # 根據通知類型選擇廣播方式
        if notification.is_global:
            logger.info(f"開始廣播全局通知: ID={notification.id}, 標題={notification.title}")
            # 使用主WebSocket管理器廣播全局通知
            await main_ws_manager.broadcast(message)
            logger.info(f"通過主WebSocket管理器成功廣播全局通知，ID: {notification.id}")
        elif notification.user_id:
            logger.info(f"開始廣播用戶特定通知: ID={notification.id}, 用戶ID={notification.user_id}")
            # 使用主WebSocket管理器發送給特定用戶
            await main_ws_manager.send_to_user(notification.user_id, message)
            logger.info(f"通過主WebSocket管理器成功發送通知給用戶 {notification.user_id}，通知ID: {notification.id}")
    except Exception as e:
        logger.error(f"廣播通知時出錯: {str(e)}")

# 創建並廣播通知
async def create_and_broadcast_notification(
    notification_data: NotificationCreate,
    db: Session
) -> List[Notification]:
    """
    創建並廣播通知
    
    在資料庫中創建新通知，並立即廣播給相關用戶。
    支援創建全局通知或發送給特定用戶的通知。
    
    參數:
        notification_data: 通知創建請求數據
        db: 資料庫會話
        
    返回:
        創建的通知物件列表
        
    異常:
        如果創建過程中出錯，會回滾事務並重新拋出異常
    """
    created_notifications = []
    
    try:
        # 處理模板變量
        message = notification_data.message
        title = notification_data.title
        
        # 檢查消息中是否有未替換的模板變量
        if "{" in message and "}" in message:
            # 如果存在template_variables字段，則進行替換
            template_variables = getattr(notification_data, 'template_variables', None)
            if template_variables and isinstance(template_variables, dict):
                logger.info(f"嘗試使用變量替換模板: {template_variables}")
                try:
                    # 替換消息中的變量
                    for key, value in template_variables.items():
                        placeholder = "{" + key + "}"
                        message = message.replace(placeholder, str(value))
                    
                    # 替換標題中的變量
                    for key, value in template_variables.items():
                        placeholder = "{" + key + "}"
                        title = title.replace(placeholder, str(value))
                    
                    logger.info("模板變量替換完成")
                except Exception as e:
                    logger.error(f"替換模板變量時出錯: {str(e)}")
            else:
                logger.warning(f"檢測到未替換的模板變量，但未提供template_variables: {message}")
        
        if notification_data.is_global:
            # 創建全局通知
            db_notification = Notification(
                title=title,
                message=message,
                is_global=True,
                read=False,
                notification_type=notification_data.notification_type
            )
            db.add(db_notification)
            db.commit()
            db.refresh(db_notification)
            created_notifications.append(db_notification)
            
            # 廣播全局通知
            await broadcast_notification(db_notification, db)
            
        elif notification_data.user_ids:
            # 發送給特定用戶
            for user_id in notification_data.user_ids:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    db_notification = Notification(
                        title=title,
                        message=message,
                        is_global=False,
                        user_id=user_id,
                        read=False,
                        notification_type=notification_data.notification_type
                    )
                    db.add(db_notification)
                    created_notifications.append(db_notification)
            
            db.commit()
            
            # 廣播用戶特定通知
            for notification in created_notifications:
                db.refresh(notification)
                await broadcast_notification(notification, db)
    except Exception as e:
        logger.error(f"創建和廣播通知時出錯: {str(e)}")
        db.rollback()
        raise
        
    return created_notifications

@router.delete("/all", status_code=status.HTTP_200_OK)
async def delete_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    刪除當前用戶的所有通知
    
    為當前登入用戶刪除系統中所有可見的通知，包括：
    1. 專門發送給該用戶的個人通知
    2. 所有全局通知
    
    此操作不可撤銷，刪除後無法恢復。
    
    返回:
        包含操作結果和已刪除通知數量的狀態訊息
        
    錯誤:
        500: 刪除過程中出現伺服器錯誤
    """
    try:
        # 找到該用戶的所有通知（包括針對該用戶的通知和全局通知）
        notifications = db.query(Notification).filter(
            or_(
                Notification.user_id == current_user.id,
                Notification.is_global == True
            )
        ).all()
        
        # 記錄刪除操作
        logger.info(f"用戶 {current_user.username}(ID:{current_user.id}) 請求刪除所有通知，共 {len(notifications)} 條")
        
        # 刪除這些通知
        for notification in notifications:
            db.delete(notification)
        
        # 提交事務
        db.commit()
        
        # 返回成功響應
        return {
            "status": "success", 
            "message": f"已成功刪除 {len(notifications)} 條通知",
            "deleted_count": len(notifications)
        }
        
    except Exception as e:
        # 如果發生錯誤，回滾事務
        db.rollback()
        logger.error(f"刪除用戶 {current_user.username} 的通知時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刪除通知時出錯: {str(e)}"
        ) 