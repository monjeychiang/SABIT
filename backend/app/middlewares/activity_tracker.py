from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from datetime import datetime
import time
from typing import Dict, List
import asyncio
import logging

logger = logging.getLogger(__name__)

# 用户活跃状态存储
class ActiveSessionStore:
    def __init__(self, expiration_seconds=300):  # 默认5分钟无活动视为离线
        self.user_sessions: Dict[int, datetime] = {}
        self.expiration_seconds = expiration_seconds
        self.cleanup_task = None
    
    def update_user_activity(self, user_id: int):
        """更新用户活跃时间"""
        if user_id:
            self.user_sessions[user_id] = datetime.now()
    
    def is_user_active(self, user_id: int) -> bool:
        """检查用户是否处于活跃状态"""
        if user_id not in self.user_sessions:
            return False
        
        last_active = self.user_sessions[user_id]
        seconds_since_active = (datetime.now() - last_active).total_seconds()
        return seconds_since_active < self.expiration_seconds
    
    def get_active_users_count(self) -> int:
        """获取活跃用户数量"""
        now = datetime.now()
        active_count = 0
        
        for last_active in self.user_sessions.values():
            if (now - last_active).total_seconds() < self.expiration_seconds:
                active_count += 1
        
        return active_count
    
    def get_all_active_users(self) -> List[int]:
        """获取所有活跃用户ID"""
        now = datetime.now()
        active_users = []
        
        for user_id, last_active in self.user_sessions.items():
            if (now - last_active).total_seconds() < self.expiration_seconds:
                active_users.append(user_id)
        
        return active_users
    
    def get_user_last_active(self, user_id: int) -> datetime:
        """获取用户最后活跃时间"""
        return self.user_sessions.get(user_id)
    
    async def start_cleanup_task(self):
        """启动定期清理任务"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())
            logger.info("Started activity tracker cleanup task")
    
    async def stop_cleanup_task(self):
        """停止清理任务"""
        if self.cleanup_task is not None:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
            self.cleanup_task = None
            logger.info("Stopped activity tracker cleanup task")
    
    async def _cleanup_expired_sessions(self):
        """定期清理过期会话"""
        try:
            while True:
                await asyncio.sleep(60)  # 每分钟清理一次
                now = datetime.now()
                expired_users = []
                
                for user_id, last_active in list(self.user_sessions.items()):
                    if (now - last_active).total_seconds() > self.expiration_seconds * 2:
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    del self.user_sessions[user_id]
                
                if expired_users:
                    logger.debug(f"Cleaned up {len(expired_users)} expired sessions")
        except asyncio.CancelledError:
            logger.info("Activity tracker cleanup task cancelled")
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}")
            self.cleanup_task = None


# 创建全局活跃会话存储
active_session_store = ActiveSessionStore()

# 活跃跟踪中间件
class ActivityTrackerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 尝试从认证头获取用户信息
        from ..core.security import verify_token, JWTError
        from ..db.database import get_db
        from ..db.models.user import User
        
        user_id = None
        # 尝试从Authorization头获取token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("bearer "):
            token = auth_header.replace("bearer ", "", 1)
            try:
                # 验证token并获取用户名
                payload = verify_token(token)
                username = payload.get("sub")
                if username:
                    # 获取数据库连接
                    db = next(get_db())
                    try:
                        # 查找用户
                        user = db.query(User).filter(User.username == username).first()
                        if user:
                            # 设置用户到请求状态
                            request.state.user = user
                            user_id = user.id
                            # 更新用户活跃状态
                            active_session_store.update_user_activity(user_id)
                    finally:
                        # 确保数据库连接被释放
                        db.close()
            except (JWTError, Exception) as e:
                logger.warning(f"Token verification failed: {str(e)}")
                # 继续处理请求，只是不更新活跃状态
        
        # 处理请求
        response = await call_next(request)
        
        # 记录请求处理时间
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        return response 