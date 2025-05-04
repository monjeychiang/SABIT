import os
import platform
import socket
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
import logging

from ...db.database import get_db
from ...db.models import User, get_china_time
from ...core.security import get_current_admin_user

router = APIRouter()
logger = logging.getLogger(__name__)

# 記錄伺服器啟動時間
START_TIME = datetime.now()

# 简单的内存速率限制器
class RateLimiter:
    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit  # 时间窗口内允许的最大请求数
        self.window_seconds = window_seconds  # 时间窗口大小（秒）
        self.client_requests: Dict[str, list] = {}  # 记录客户端请求历史
    
    def is_rate_limited(self, client_ip: str) -> Tuple[bool, int]:
        """
        检查客户端是否达到速率限制
        返回 (是否受限, 剩余秒数)
        """
        current_time = time.time()
        
        # 如果是新客户端，初始化记录
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = []
        
        # 清理过期的请求记录
        self.client_requests[client_ip] = [
            req_time for req_time in self.client_requests[client_ip]
            if current_time - req_time < self.window_seconds
        ]
        
        # 检查是否超过限制
        if len(self.client_requests[client_ip]) >= self.requests_limit:
            oldest_request = min(self.client_requests[client_ip])
            time_to_reset = int(self.window_seconds - (current_time - oldest_request))
            return True, max(0, time_to_reset)
        
        # 记录本次请求
        self.client_requests[client_ip].append(current_time)
        return False, 0

# 创建速率限制器实例
system_ping_rate_limiter = RateLimiter(requests_limit=20, window_seconds=60)  # 每分钟限制20次，允许完成一次15秒的网络测试

@router.get("/status")
async def get_server_status(
    current_admin: User = Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """
    獲取伺服器狀態資訊，包括CPU、記憶體使用情況等
    
    此端點提供系統運行狀態的完整概覽，包含：
    - 系統基本資訊（作業系統、版本、處理器等）
    - 資源使用情況（CPU、記憶體、磁碟空間）
    - 時間資訊（伺服器時間、運行時間）
    
    僅限管理員用戶訪問。
    """
    # 伺服器運行時間
    uptime = datetime.now() - START_TIME
    
    # 系統資訊
    system_info = {
        "system": platform.system(),
        "version": platform.version(),
        "processor": platform.processor(),
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
    }
    
    # 資源使用情況
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    resources = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory": {
            "total": memory.total / (1024 ** 3),  # GB
            "used": memory.used / (1024 ** 3),    # GB
            "percent": memory.percent
        },
        "disk": {
            "total": disk.total / (1024 ** 3),    # GB
            "used": disk.used / (1024 ** 3),      # GB
            "percent": disk.percent
        }
    }
    
    # 伺服器時間資訊
    time_info = {
        "server_time": get_china_time().strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": {
            "days": uptime.days,
            "hours": uptime.seconds // 3600,
            "minutes": (uptime.seconds % 3600) // 60,
            "seconds": uptime.seconds % 60
        },
        "start_time": START_TIME.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    logger.info(f"Server status checked by admin: {current_admin.username}")
    
    return {
        "status": "running",
        "system": system_info,
        "resources": resources,
        "time": time_info
    }

@router.get("/ping")
async def ping(request: Request) -> Dict[str, Any]:
    """
    简单的Ping端点，用于测量API延迟
    
    此端点返回当前服务器时间戳，客户端可以用来计算往返延迟。
    """
    # 获取客户端IP地址
    client_ip = request.client.host if request.client else "unknown"
    
    # 检查是否超过速率限制（系统ping限制稍宽松）
    is_limited, reset_time = system_ping_rate_limiter.is_rate_limited(client_ip)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time} seconds.",
            headers={"Retry-After": str(reset_time)}
        )
    
    # 返回最小化的响应以减少处理时间
    return {
        "timestamp": int(time.time() * 1000)  # 毫秒时间戳
    }

@router.get("/users-login-history")
async def get_users_login_history(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    獲取用戶登入歷史記錄，包括最近登入時間和IP地址
    
    返回最近登入系統的用戶清單，按照登入時間降序排列。
    每條記錄包含用戶基本資訊以及其最後登入的時間戳和IP地址。
    
    參數:
        limit: 要返回的記錄數量上限，預設為20條
        
    返回:
        包含用戶登入資訊的列表
        
    權限:
        僅限管理員用戶訪問
    """
    try:
        # 獲取有登入記錄的用戶
        users_with_login = db.query(User).filter(
            User.last_login_at.isnot(None)
        ).order_by(desc(User.last_login_at)).limit(limit).all()
        
        users_data = []
        for user in users_with_login:
            users_data.append({
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_active": user.is_active,
                "user_tag": user.user_tag,
                "last_login_at": user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else None,
                "last_login_ip": user.last_login_ip
            })
        
        logger.info(f"Users login history checked by admin: {current_admin.username}")
        
        return users_data
    except Exception as e:
        logger.error(f"Error getting users login history: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="獲取用戶登入歷史失敗"
        ) 

@router.get("/user/{user_id}/login-history")
async def get_user_login_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user),
    limit: int = 20
) -> Dict[str, Any]:
    """
    獲取單一用戶的登入歷史記錄
    
    根據用戶ID返回指定用戶的登入歷史，包括最近登入時間和IP地址。
    如果用戶不存在或沒有登入記錄，將返回適當的錯誤訊息。
    
    參數:
        user_id: 要查詢的用戶ID
        limit: 要返回的記錄數量上限，預設為20條
        
    返回:
        包含用戶基本信息和登入記錄的字典
        
    權限:
        僅限管理員用戶訪問
    """
    try:
        # 檢查用戶是否存在
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"用戶ID {user_id} 不存在"
            )
        
        # 用戶基本資訊
        user_info = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "user_tag": user.user_tag,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None,
            "is_verified": user.is_verified,
            "last_login_at": user.last_login_at.strftime("%Y-%m-%d %H:%M:%S") if user.last_login_at else None,
            "last_login_ip": user.last_login_ip,
            "avatar_url": user.avatar_url,
            "full_name": user.full_name,
            "oauth_provider": user.oauth_provider
        }
        
        # 登入歷史（這裡僅返回當前登入資訊，因為目前數據庫中只存儲了最後一次登入）
        # 在實際應用中，如果有完整的登入歷史表，可以從該表中查詢歷史記錄
        login_history = []
        if user.last_login_at:
            login_history.append({
                "login_time": user.last_login_at.strftime("%Y-%m-%d %H:%M:%S"),
                "login_ip": user.last_login_ip,
                "is_current": True  # 標記為當前登入狀態
            })
        
        logger.info(f"User login history for user_id={user_id} checked by admin: {current_admin.username}")
        
        return {
            "user_info": user_info,
            "login_history": login_history
        }
    except HTTPException:
        # 重新拋出 HTTPException，讓 FastAPI 處理
        raise
    except Exception as e:
        logger.error(f"Error getting login history for user_id={user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取用戶 {user_id} 的登入歷史失敗"
        ) 