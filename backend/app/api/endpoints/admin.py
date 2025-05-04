from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import Any, List, Optional, Dict
from datetime import datetime
from sqlalchemy import or_
from pydantic import BaseModel
from ...db.database import get_db
from ...db.models import User, Notification, UserTag
from ...schemas.user import UserResponse, UserUpdate, UserTagUpdate
from ...core.security import get_current_user
import logging

# 配置日志
logger = logging.getLogger(__name__)

# 創建路由器
router = APIRouter()

# 獲取當前管理員用戶
def get_current_admin_user(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> User:
    """
    驗證當前用戶是否是管理員
    
    檢查當前登入用戶是否具有管理員權限，若不是則拒絕訪問。
    此函數用於保護僅限管理員訪問的端點。
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="您沒有管理員權限",
        )
    return current_user

class PaginatedUsers(BaseModel):
    items: List[UserResponse]
    total: int
    page: int
    per_page: int
    
class UserAdminUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    
class UserStatusUpdate(BaseModel):
    is_active: bool
    
class UserAdminStatusUpdate(BaseModel):
    is_admin: bool

@router.get("/users", response_model=PaginatedUsers)
async def get_all_users(
    db: Session = Depends(get_db),
    page: int = 1, 
    per_page: int = 10,
    search: Optional[str] = None,
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    獲取所有用戶（管理員權限），支援分頁和搜索
    
    此端點返回系統中的用戶列表，可透過分頁參數控制返回數量，
    並支援按用戶名和電子郵件進行模糊搜索。
    
    參數:
        page: 頁碼，從1開始
        per_page: 每頁顯示的記錄數量
        search: 搜索關鍵字，用於過濾用戶名和電子郵件
        
    返回:
        分頁後的用戶列表及分頁資訊
    """
    # 計算分頁偏移量
    skip = (page - 1) * per_page
    
    # 構建查詢
    query = db.query(User)
    
    # 如果有搜索關鍵字，添加過濾條件
    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    # 獲取總數
    total = query.count()
    
    # 獲取當前頁數據
    users = query.offset(skip).limit(per_page).all()
    
    return {
        "items": users,
        "total": total,
        "page": page,
        "per_page": per_page
    }

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    通過ID獲取用戶資訊（管理員權限）
    
    根據用戶ID查詢並返回特定用戶的詳細資訊。
    若指定ID的用戶不存在，將返回404錯誤。
    
    參數:
        user_id: 要查詢的用戶ID
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserAdminUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    更新用戶資訊（管理員權限）
    
    允許管理員修改指定用戶的基本資訊、啟用狀態和管理員權限。
    包含特殊限制以防止禁用或移除管理員權限。
    
    參數:
        user_id: 要更新的用戶ID
        user_update: 包含需要更新的用戶屬性
        
    安全限制:
        - 不能禁用具有管理員標籤或管理員權限的用戶
        - 不能移除管理員用戶的管理員權限
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查是否試圖禁用管理員用戶
    if (user.user_tag == UserTag.ADMIN or user.is_admin) and user_update.is_active is not None and not user_update.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用管理員用戶"
        )
    
    # 檢查是否試圖移除管理員的管理員權限
    if (user.user_tag == UserTag.ADMIN or user.is_admin) and user_update.is_admin is not None and not user_update.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除管理員用戶的管理員權限"
        )
    
    # 更新用戶資訊
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
    if user_update.is_admin is not None:
        user.is_admin = user_update.is_admin
    
    db.commit()
    db.refresh(user)
    
    return user

@router.put("/users/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    update: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    更新用戶狀態（啟用/禁用）
    
    提供專門用於啟用或禁用用戶帳戶的端點。
    此操作有安全限制，禁止禁用當前登入的管理員或其他管理員用戶。
    
    參數:
        user_id: 要更新狀態的用戶ID
        update: 包含is_active布爾值的物件
        
    安全限制:
        - 不能禁用當前登入的管理員
        - 不能禁用任何具有管理員標籤或管理員權限的用戶
    """
    # 不能禁用自己
    if user_id == current_admin.id and not update.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用當前登入的管理員帳號"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 不允許禁用任何管理員用戶
    if (user.user_tag == UserTag.ADMIN or user.is_admin) and not update.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能禁用管理員用戶"
        )
    
    # 設置活躍狀態
    user.is_active = update.is_active
    db.commit()
    db.refresh(user)
    
    return user

@router.put("/users/{user_id}/admin", response_model=UserResponse)
async def update_user_admin_status(
    user_id: int,
    update: UserAdminStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    更新用戶管理員狀態
    
    提供專門用於授予或撤銷用戶管理員權限的端點。
    管理員不能撤銷自己的管理員權限，以防止意外失去系統訪問權。
    
    參數:
        user_id: 要更新管理員狀態的用戶ID
        update: 包含is_admin布爾值的物件
        
    安全限制:
        - 管理員不能取消自己的管理員權限
    """
    # 不能取消自己的管理員權限
    if user_id == current_admin.id and not update.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能取消自己的管理員權限"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 設置管理員狀態
    user.is_admin = update.is_admin
    db.commit()
    db.refresh(user)
    
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    刪除用戶（管理員權限）
    
    永久刪除系統中的用戶帳戶及其相關資料。
    為安全起見，管理員不能刪除自己的帳戶。
    
    參數:
        user_id: 要刪除的用戶ID
        
    安全限制:
        - 管理員不能刪除自己的帳戶
        
    返回:
        操作成功時返回204 No Content狀態碼，不包含任何內容
    """
    # 不能刪除自己
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能刪除自己"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    db.delete(user)
    db.commit()
    
    # 使用204狀態碼時不返回任何內容 


@router.put("/users/{user_id}/tag", response_model=UserResponse)
async def update_user_tag(
    user_id: int,
    tag_update: UserTagUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    更新用戶標籤（僅限管理員）
    
    允許管理員更改用戶的標籤分類，用於特殊權限或分組管理。
    有特殊邏輯處理管理員標籤，確保權限一致性。
    
    參數:
        user_id: 要更新標籤的用戶ID
        tag_update: 包含新user_tag值的物件
        
    特殊邏輯:
        - 不能從管理員用戶移除管理員標籤
        - 設置管理員標籤時會自動授予管理員權限(is_admin=True)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查是否試圖移除管理員的管理員標籤
    if (user.user_tag == UserTag.ADMIN or user.is_admin) and tag_update.user_tag != UserTag.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能移除管理員用戶的管理員權限"
        )
    
    # 更新用戶標籤
    user.user_tag = tag_update.user_tag
    
    # 如果標籤是ADMIN，同時設置is_admin為True
    if tag_update.user_tag == UserTag.ADMIN:
        user.is_admin = True
    # 如果標籤不是ADMIN，但用戶是管理員，則保持管理員權限
    # 如果需要移除管理員權限，應使用專門的管理員權限端點
    
    db.commit()
    db.refresh(user)
    
    return user

# 獲取通知統計資訊的端點
@router.get("/notifications/stats", response_model=dict)
async def get_notifications_stats(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    獲取通知統計資訊，包括總數量和全局通知數量
    
    提供系統通知相關的統計指標，幫助管理員了解通知系統的使用情況。
    返回通知總數量以及其中的全局通知數量。
    
    返回:
        包含total和global計數的字典
    """
    # 查詢所有通知數量
    total_notifications = db.query(Notification).count()
    
    # 查詢全局通知數量
    global_notifications = db.query(Notification).filter(Notification.is_global == True).count()
    
    return {
        "total": total_notifications,
        "global": global_notifications
    } 