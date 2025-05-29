from ...core.online_status_manager import online_status_manager
from fastapi import Depends, HTTPException, status, APIRouter
from typing import List, Dict, Any
from ...core.security import get_current_active_user, get_current_admin_user
from ...db.models import User
from sqlalchemy.orm import Session
from ...db.database import get_db, SessionLocal
from ...schemas.user import UserPublicInfo
import logging

# 创建日志记录器
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/active-users-count")
async def get_active_users_count(current_user: User = Depends(get_current_active_user)):
    """獲取當前活躍用戶數量
    
    該端點返回系統中目前在線的活躍用戶總數。
    只有已認證的用戶才能訪問此資訊。
    """
    return {"active_users": online_status_manager.get_total_online_users()}

# 添加一个新的API端点，允许普通用户访问在線用戶列表的基本信息，但不包含敏感数据
@router.get("/active-users-public")
async def get_active_users_public(current_user: User = Depends(get_current_active_user)):
    """獲取在線用戶基本公開信息（適用於普通用戶）
    
    此端點返回系統中當前活躍用戶的基本公開資訊，如用戶名和頭像。
    只包含已允許公開顯示的資訊，不包含敏感數據如電子郵件。
    所有已認證的用戶均可訪問此端點。
    """
    # 使用with語句和try-finally確保連接被正確釋放回連接池
    db = SessionLocal()
    try:
        # 使用 online_status_manager 替代 active_session_store
        online_user_ids = online_status_manager.get_all_online_users()
        
        if not online_user_ids:
            return {"users": []}
        
        # 獲取活躍用戶詳細資訊
        users = db.query(User).filter(User.id.in_(online_user_ids)).all()
        
        # 構建包含最後活躍時間的用戶資訊，但只包含公開資料
        result = []
        for user in users:
            # 獲取用戶的最後活躍時間
            user_status = online_status_manager.get_user_status(user.id)
            last_active = user_status.get("last_active") if user_status else None
            
            user_dict = {
                "id": user.id,
                "username": user.username,
                "avatar_url": user.avatar_url,
                "last_active": last_active
            }
            result.append(user_dict)
        
        return {"users": result}
    finally:
        # 確保在任何情況下都會關閉連接並釋放回連接池
        db.close()

@router.get("/is-active/{user_id}")
async def check_user_active(
    user_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """檢查用戶是否處於活躍狀態
    
    參數:
        user_id: 要檢查的用戶ID
        
    返回:
        包含用戶活躍狀態和最後活躍時間的詳細資訊
        
    權限:
        - 普通用戶只能查詢自己的狀態
        - 管理員可以查詢任何用戶的狀態
    """
    # 如果不是管理員，只能查詢自己的狀態
    if not current_user.is_admin and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="沒有權限查看其他用戶的狀態"
        )
    
    # 使用 online_status_manager 替代 active_session_store
    is_online = online_status_manager.is_user_online(user_id)
    user_status = online_status_manager.get_user_status(user_id)
    last_active = user_status.get("last_active")
    
    return {
        "user_id": user_id,
        "is_active": is_online,
        "last_active": last_active
    }

@router.get("/active-users", response_model=List[int])
async def get_active_users(current_user: User = Depends(get_current_admin_user)):
    """獲取所有活躍用戶列表（僅限管理員）
    
    返回當前系統中所有活躍用戶的ID列表。
    此端點僅限管理員使用，需要管理員權限。
    """
    # 使用 online_status_manager 替代 active_session_store
    return online_status_manager.get_all_online_users()

@router.get("/active-users-details")
async def get_active_users_details(current_user: User = Depends(get_current_admin_user)):
    """獲取所有活躍用戶的詳細資訊（僅限管理員）
    
    提供系統中所有當前活躍用戶的完整資訊，包括：
    - 用戶ID
    - 用戶名
    - 電子郵件
    - 頭像URL
    - 管理員狀態
    - 最後活躍時間
    
    此端點僅限管理員使用，需要管理員權限。
    """
    # 使用依賴注入獲取資料庫連接，確保連接會被正確關閉
    from sqlalchemy.orm import Session
    from ...db.database import get_db, SessionLocal
    
    # 使用with語句和try-finally確保連接被正確釋放回連接池
    db = SessionLocal()
    try:
        # 使用 online_status_manager 替代 active_session_store
        online_user_ids = online_status_manager.get_all_online_users()
        
        if not online_user_ids:
            return {"users": []}
        
        # 獲取活躍用戶詳細資訊
        users = db.query(User).filter(User.id.in_(online_user_ids)).all()
        
        # 構建包含最後活躍時間的用戶資訊
        result = []
        for user in users:
            user_status = online_status_manager.get_user_status(user.id)
            last_active = user_status.get("last_active")
            
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "is_admin": user.is_admin,
                "last_active": last_active
            }
            result.append(user_dict)
        
        return {"users": result}
    finally:
        # 確保在任何情況下都會關閉連接並釋放回連接池
        db.close()

# 将这个路由移到最后，确保前面的路由能被正确匹配
@router.get("/user-info/{user_id}", response_model=UserPublicInfo)
async def get_user_public_info(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """獲取用戶的公開信息
    
    根據用戶ID返回用戶的基本公開信息，包括用戶名、頭像等。
    任何已登錄用戶都可以訪問此API。
    
    參數:
        user_id: 要查詢的用戶ID
        
    返回:
        包含用戶公開資訊的對象
    """
    logger.info(f"獲取用戶 {user_id} 的公開信息，請求用戶ID: {current_user.id}")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        logger.warning(f"用戶 {user_id} 不存在")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    logger.info(f"成功獲取用戶 {user_id} 的公開信息: {user.username}")
    return user 