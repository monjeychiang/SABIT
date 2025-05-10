from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Any, List, Optional, Dict
from datetime import datetime
import logging
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketDisconnect
from fastapi.security import OAuth2PasswordRequestForm
from jose import jwt, JWTError
from sqlalchemy.sql import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ...db.database import get_db
from ...db.models import User, Notification, NotificationType
from ...schemas.notification import NotificationCreate, NotificationResponse, NotificationUpdate, PaginatedNotifications
from ...core.security import get_current_user, verify_token
from ...api.endpoints.admin import get_current_admin_user

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

# ============== 新增代碼：WebSocket通知推送功能 ==============

# 通知WebSocket連接管理器
class NotificationConnectionManager:
    def __init__(self):
        # 用戶ID -> WebSocket連接列表 的映射
        self.user_connections: Dict[int, List[WebSocket]] = {}
        # WebSocket -> 用戶ID 的映射
        self.connection_user: Dict[WebSocket, int] = {}
        # 廣播計數器和日誌記錄
        self.broadcast_counts: Dict[int, int] = {}
        self.last_log_time: Dict[int, datetime] = {}
        self.log_interval = 600  # 每10分鐘記錄一次日誌
        self.active_connections_count = 0

    async def connect(self, websocket: WebSocket, user_id: int) -> str:
        """
        建立WebSocket連接，並將連接與用戶關聯
        
        接受新的WebSocket連接請求，將其與用戶ID關聯，並初始化相關記錄。
        
        參數:
            websocket: 要建立的WebSocket連接
            user_id: 要關聯的用戶ID
            
        返回:
            生成的客戶端ID（用於日誌記錄和追蹤）
            
        異常:
            可能引發WebSocket連接相關的異常
        """
        try:
            await websocket.accept()
            
            # 初始化用戶的連接列表和計數器
            if user_id not in self.user_connections:
                self.user_connections[user_id] = []
                self.broadcast_counts[user_id] = 0
                self.last_log_time[user_id] = datetime.now()
            
            # 添加新連接到用戶的連接列表
            self.user_connections[user_id].append(websocket)
            self.connection_user[websocket] = user_id
            self.active_connections_count += 1
            
            # 生成客戶端ID（方便日誌記錄）
            client_id = f"notification_{user_id}_{id(websocket)}"
            logger.info(f"[Notification] WebSocket连接已建立: 用户ID={user_id}, 连接ID={client_id}, 当前连接总数={self.active_connections_count}")
            return client_id
            
        except Exception as e:
            logger.error(f"建立通知WebSocket連接失敗: {str(e)}")
            raise

    def disconnect(self, websocket: WebSocket) -> None:
        """
        關閉WebSocket連接
        
        斷開指定的WebSocket連接，清理相關資源和記錄。
        如果用戶沒有其他活躍連接，將清理該用戶的所有相關數據。
        
        參數:
            websocket: 要斷開的WebSocket連接
        """
        try:
            if websocket in self.connection_user:
                user_id = self.connection_user[websocket]
                
                # 生成连接ID用于日志
                connection_id = f"notification_{user_id}_{id(websocket)}"
                
                # 從用戶連接列表中移除
                if user_id in self.user_connections and websocket in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(websocket)
                    
                    # 如果用戶沒有活躍連接了，清理相關記錄
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
                        if user_id in self.broadcast_counts:
                            del self.broadcast_counts[user_id]
                        if user_id in self.last_log_time:
                            del self.last_log_time[user_id]
                
                # 從映射表中移除
                del self.connection_user[websocket]
                self.active_connections_count -= 1
                
                # 記錄連接關閉信息
                logger.info(f"[Notification] WebSocket连接已断开: 用户ID={user_id}, 连接ID={connection_id}, 当前连接总数={self.active_connections_count}")
            
        except ValueError:
            logger.warning("嘗試移除不存在的通知WebSocket連接")
        except Exception as e:
            logger.error(f"關閉通知WebSocket連接時出錯: {str(e)}")

    async def broadcast_to_user(self, user_id: int, message: Dict[str, Any]) -> None:
        """
        向指定用戶廣播通知消息
        
        將消息發送給特定用戶的所有活躍WebSocket連接。
        包含智能日誌記錄，避免過多日誌，只在特定間隔或事件記錄。
        自動清理已斷開的連接。
        
        參數:
            user_id: 目標用戶ID
            message: 要發送的消息內容（JSON可序列化的字典）
        """
        if user_id not in self.user_connections:
            return
        
        # 更新廣播計數和記錄日誌
        self.broadcast_counts[user_id] = self.broadcast_counts.get(user_id, 0) + 1
        current_time = datetime.now()
        last_time = self.last_log_time.get(user_id, datetime.now())
        time_diff = (current_time - last_time).total_seconds()
        
        # 僅在以下情況記錄日誌: 首次廣播、達到記錄間隔或廣播達到1000次
        should_log = (self.broadcast_counts[user_id] == 1 or 
                      time_diff >= self.log_interval or 
                      self.broadcast_counts[user_id] % 1000 == 0)
        
        if should_log and self.user_connections.get(user_id, []):
            logger.info(f"向用戶 {user_id} 廣播通知消息 (連接數: {len(self.user_connections[user_id])}, 已廣播: {self.broadcast_counts[user_id]}次)")
            self.last_log_time[user_id] = current_time
            
        # 向用戶所有連接廣播消息
        disconnected = []
        for connection in self.user_connections.get(user_id, []):
            try:
                await connection.send_json(message)
            except Exception as e:
                # 避免大量連接錯誤日誌，僅記錄非連接相關錯誤
                if "connection" not in str(e).lower():
                    logger.error(f"向用戶 {user_id} 廣播通知消息時出錯: {str(e)}")
                disconnected.append(connection)
        
        # 清理斷開的連接
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_global(self, message: Dict[str, Any]) -> None:
        """
        向所有連接的用戶廣播全局通知
        
        將消息發送給所有當前連接的用戶。
        使用列表複製避免在迭代過程中修改字典。
        
        參數:
            message: 要廣播的消息內容（JSON可序列化的字典）
        """
        logger.info(f"廣播全局通知消息，當前活躍用戶數: {len(self.user_connections)}")
        
        # 為每個連接的用戶廣播消息
        for user_id in list(self.user_connections.keys()):  # 使用列表複製避免迭代時修改
            await self.broadcast_to_user(user_id, message)

    def get_connected_users_count(self) -> int:
        """
        獲取當前連接的用戶數量
        
        返回:
            目前有WebSocket連接的不同用戶數量
        """
        return len(self.user_connections)

    def get_total_connections_count(self) -> int:
        """
        獲取當前總連接數
        
        返回:
            系統中所有WebSocket連接的總數
        """
        return self.active_connections_count

# 创建通知连接管理器实例
notification_manager = NotificationConnectionManager()

# 廣播新通知給用戶
async def broadcast_notification(notification: Notification, db: Session) -> None:
    """
    廣播新通知給用戶
    
    將新創建的通知通過WebSocket實時推送給相關用戶。
    根據通知類型（全局或用戶特定）決定推送方式。
    
    參數:
        notification: 要廣播的通知物件
        db: 資料庫會話
    """
    try:
        # 轉換通知模型為可序列化字典
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
        
        message = {
            "type": "notification",
            "notification": notification_data
        }
        
        # 根據通知類型決定廣播方式
        if notification.is_global:
            # 全局通知廣播給所有連接的用戶
            await notification_manager.broadcast_global(message)
        elif notification.user_id:
            # 用戶特定通知只廣播給目標用戶
            await notification_manager.broadcast_to_user(notification.user_id, message)
    
    except Exception as e:
        logger.error(f"廣播通知時出錯: {str(e)}")

# 修改創建通知函數以添加即時廣播功能
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
        if notification_data.is_global:
            # 創建全局通知
            db_notification = Notification(
                title=notification_data.title,
                message=notification_data.message,
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
                        title=notification_data.title,
                        message=notification_data.message,
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

# WebSocket通知訂閱端點
@router.websocket("/ws")
async def websocket_notifications(websocket: WebSocket):
    """
    通知WebSocket连接
    
    客户端通过此WebSocket连接接收实时通知
    """
    # 注意：不要在这里调用websocket.accept()，因为在notification_manager.connect()中已经调用了
    user_id = None
    connection_id = None
    
    try:
        # 获取查询参数中的token
        token = websocket.query_params.get("token")
        
        if not token:
            # 注意：未接受连接前不能发送消息，所以这里我们先接受连接再发送错误
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "未提供认证令牌"
            })
            await websocket.close(code=1008)
            return
        
        # 验证token
        try:
            # 使用现有验证函数验证token
            payload = verify_token(token)
            if not payload or "sub" not in payload:
                await websocket.accept()
                await websocket.send_json({
                    "type": "error",
                    "message": "无效的认证令牌"
                })
                await websocket.close(code=1008)
                return
                
            username = payload.get("sub")
            
            # 获取用户信息
            db = next(get_db())
            try:
                user = db.query(User).filter(User.username == username).first()
                
                if not user:
                    await websocket.accept()
                    await websocket.send_json({
                        "type": "error",
                        "message": "用户不存在"
                    })
                    await websocket.close(code=1008)
                    return
                    
                user_id = user.id
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"WebSocket认证失败: {str(e)}")
            await websocket.accept()
            await websocket.send_json({
                "type": "error",
                "message": "认证失败"
            })
            await websocket.close(code=1008)
            return
        
        # 建立连接（内部会调用websocket.accept()）
        connection_id = await notification_manager.connect(websocket, user_id)
        
        # 发送欢迎消息
        await websocket.send_json({
            "type": "connected",
            "message": "已连接到通知系统",
            "connection_id": connection_id
        })
        
        # 接收消息
        while True:
            try:
                # 接收消息
                data = await websocket.receive_json()
                
                # 如果是ping消息，立即回复pong
                if "type" in data and data["type"] == "ping":
                    logger.debug(f"收到客户端ping消息，立即响应pong")
                    await websocket.send_json({"type": "pong"})
                    continue
                    
                # 处理其他类型的消息
                message_type = data.get("type")
                
                if message_type == "heartbeat_ack":
                    # 旧版心跳机制，兼容保留，不做处理
                    logger.debug(f"收到客户端心跳确认")
                    continue
                
                # 如果是其他未识别的消息类型，记录但不处理
                logger.debug(f"收到未知类型的消息: {message_type}")
                    
            except WebSocketDisconnect:
                logger.info(f"通知WebSocket客户端主动断开连接: {connection_id}")
                break
                
            except json.JSONDecodeError:
                logger.warning(f"接收到无效的JSON消息: {connection_id}")
                continue
                
            except Exception as e:
                logger.error(f"处理通知WebSocket消息时出错: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"通知WebSocket处理时发生异常: {str(e)}")
        
    finally:
        # 关闭连接
        if connection_id:
            notification_manager.disconnect(websocket)
            logger.info(f"通知WebSocket连接已关闭，用户ID: {user_id}，当前连接总数: {notification_manager.get_total_connections_count()}")
            logger.info(f"通知WebSocket连接已清理: {connection_id}")

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