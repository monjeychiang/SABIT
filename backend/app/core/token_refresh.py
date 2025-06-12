"""
令牌刷新優化模組

此模組實現了高效的令牌刷新策略，通過動態閾值計算、
批量處理請求和令牌衰減機制，優化系統在高併發情況下
的刷新令牌處理性能，並增強系統安全性。
"""

import asyncio
import hashlib
import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List, Set

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.db.models.user import User, RefreshToken

# 設置日誌記錄
logger = logging.getLogger(__name__)

class RefreshTokenUsage:
    """
    刷新令牌使用記錄
    
    記錄用戶刷新令牌的使用模式，用於動態調整刷新策略。
    """
    def __init__(self, user_id, token_id, created_at=None):
        self.user_id = user_id
        self.token_id = token_id
        self.created_at = created_at or datetime.now()
        self.decay_factor = 1.0  # 初始無衰減

class UserActivityTracker:
    """
    用戶活躍度追蹤器
    
    記錄和分析用戶活躍模式，用於優化令牌刷新策略。
    使用內存緩存，避免依賴外部服務。
    """
    
    def __init__(self):
        self.activity_data = {}  # {user_id: user_activity_data}
        self.usage_history = {}  # {user_id: [RefreshTokenUsage]}
        self.lock = threading.RLock()
        self.max_history_per_user = 10
        
    def record_activity(self, user_id: int, activity_type: str):
        """記錄用戶活動"""
        with self.lock:
            if user_id not in self.activity_data:
                self.activity_data[user_id] = {
                    "last_active": datetime.now(),
                    "request_count": 0,
                    "refresh_count": 0,
                    "session_start": datetime.now()
                }
            
            user_data = self.activity_data[user_id]
            user_data["last_active"] = datetime.now()
            user_data["request_count"] += 1
            
            if activity_type == "refresh":
                user_data["refresh_count"] += 1
                
    def record_refresh(self, user_id: int, token_id: str):
        """記錄令牌刷新"""
        with self.lock:
            # 添加使用記錄
            usage = RefreshTokenUsage(user_id, token_id)
            
            if user_id not in self.usage_history:
                self.usage_history[user_id] = []
                
            # 限制歷史記錄數量
            history = self.usage_history[user_id]
            if len(history) >= self.max_history_per_user:
                history.pop(0)  # 移除最舊的記錄
                
            history.append(usage)
            
            # 記錄活動
            self.record_activity(user_id, "refresh")
            
    def calculate_refresh_threshold(self, user_id: int) -> int:
        """根據用戶活躍度動態計算刷新閾值"""
        with self.lock:
            if user_id not in self.activity_data:
                return settings.REFRESH_THRESHOLD_SECONDS
                
            user_data = self.activity_data[user_id]
            
            # 計算請求頻率 (每小時)
            now = datetime.now()
            hours_active = max(1, (now - user_data["session_start"]).total_seconds() / 3600)
            req_per_hour = user_data["request_count"] / hours_active
            
            # 根據活躍度計算動態閾值
            base_threshold = settings.REFRESH_THRESHOLD_SECONDS
            
            if req_per_hour > 100:  # 高頻用戶
                return min(base_threshold * 2, 900)  # 最多15分鐘
            elif req_per_hour > 30:  # 中頻用戶
                return base_threshold
            else:  # 低頻用戶
                return max(base_threshold // 2, 120)  # 最少2分鐘
                
    def get_refresh_pattern(self, user_id: int) -> Dict[str, Any]:
        """獲取用戶刷新模式信息"""
        with self.lock:
            if user_id not in self.usage_history or len(self.usage_history[user_id]) < 3:
                return {"pattern": "unknown", "avg_interval": None}
                
            history = self.usage_history[user_id]
            
            # 計算平均刷新間隔
            intervals = []
            for i in range(1, len(history)):
                interval = (history[i].created_at - history[i-1].created_at).total_seconds()
                intervals.append(interval)
                
            avg_interval = sum(intervals) / len(intervals)
            
            # 判斷刷新模式
            if avg_interval < 3600:  # 小於1小時
                pattern = "frequent"
            elif avg_interval < 86400:  # 小於1天
                pattern = "daily"
            else:
                pattern = "infrequent"
                
            return {
                "pattern": pattern,
                "avg_interval": avg_interval,
                "refresh_count": len(history)
            }
            
    def cleanup_old_data(self):
        """清理舊數據"""
        with self.lock:
            now = datetime.now()
            inactive_threshold = now - timedelta(days=7)
            
            # 清理不活躍用戶的數據
            inactive_users = []
            for user_id, data in self.activity_data.items():
                if data["last_active"] < inactive_threshold:
                    inactive_users.append(user_id)
                    
            for user_id in inactive_users:
                if user_id in self.activity_data:
                    del self.activity_data[user_id]
                if user_id in self.usage_history:
                    del self.usage_history[user_id]
                    
            if inactive_users and settings.DEBUG:
                logger.debug(f"已清理 {len(inactive_users)} 個不活躍用戶的活躍度數據")

class TokenRefreshManager:
    """
    令牌刷新管理器
    
    管理令牌刷新過程，實現批量處理、緩存和高效並發控制。
    使用內存緩存和鎖機制，避免依賴外部服務。
    """
    
    def __init__(self):
        self.locks = {}  # {lock_key: lock}
        self.lock_dict_lock = threading.RLock()
        self.result_cache = {}  # {cache_key: result}
        self.batch_queue = asyncio.Queue()
        self.activity_tracker = UserActivityTracker()
        self.batch_processing = False
        self.batch_size = 20
        self.max_wait_ms = 200
        
    def get_user_lock(self, user_id: int) -> threading.RLock:
        """獲取用戶專用的鎖"""
        lock_key = f"refresh_token_lock_{user_id}"
        
        with self.lock_dict_lock:
            if lock_key not in self.locks:
                self.locks[lock_key] = threading.RLock()
                
        return self.locks[lock_key]
        
    def cache_refresh_result(self, user_id: int, refresh_token: str, result: Dict[str, Any]):
        """緩存刷新結果"""
        # 生成多個緩存鍵，提高命中率
        cache_keys = [
            f"refresh_result_{user_id}",  # 用戶ID作為鍵
            f"refresh_result_{hashlib.md5(refresh_token.encode()).hexdigest()[:10]}"  # 令牌指紋作為鍵
        ]
        
        # 添加時間戳
        result_with_timestamp = result.copy()
        result_with_timestamp["timestamp"] = time.time()
        
        # 存儲到緩存
        for key in cache_keys:
            self.result_cache[key] = result_with_timestamp
            
    def get_cached_result(self, user_id: int = None, refresh_token: str = None) -> Optional[Dict[str, Any]]:
        """獲取緩存的刷新結果"""
        cache_keys = []
        
        if user_id:
            cache_keys.append(f"refresh_result_{user_id}")
            
        if refresh_token:
            cache_keys.append(f"refresh_result_{hashlib.md5(refresh_token.encode()).hexdigest()[:10]}")
            
        # 檢查每個可能的緩存鍵
        current_time = time.time()
        for key in cache_keys:
            if key in self.result_cache:
                cached_item = self.result_cache[key]
                # 檢查緩存是否過期 - 45秒有效期
                if current_time - cached_item["timestamp"] < 45:
                    return cached_item
                    
        return None
        
    def clean_expired_cache(self, force=False):
        """清理過期的緩存結果"""
        try:
            # 只有在隨機條件滿足或強制清理時才執行
            if not force and not (time.time() % 10 < 0.5):  # 約5%的概率
                return
                
            current_time = time.time()
            
            # 找出所有過期的令牌
            expired_keys = []
            for k, item in self.result_cache.items():
                if current_time - item.get("timestamp", 0) > 180:  # 3分鐘超時
                    expired_keys.append(k)
                    
            # 刪除過期的令牌
            for k in expired_keys:
                if k in self.result_cache:
                    del self.result_cache[k]
                    
            # 智能緩存大小控制
            if len(self.result_cache) > 1000:
                # 按時間戳排序，刪除最舊的項目
                sorted_items = sorted(
                    [(k, v.get("timestamp", 0)) for k, v in self.result_cache.items()],
                    key=lambda x: x[1]
                )
                
                # 刪除最舊的前1/3
                to_remove = sorted_items[:len(sorted_items)//3]
                for k, _ in to_remove:
                    if k in self.result_cache:
                        del self.result_cache[k]
                        
            if expired_keys and settings.DEBUG:
                logger.debug(f"已清理 {len(expired_keys)} 個過期令牌緩存項")
                
        except Exception as e:
            logger.error(f"清理過期緩存失敗: {str(e)}")
            
    async def start_batch_processing(self):
        """啟動批處理任務"""
        if self.batch_processing:
            return
            
        self.batch_processing = True
        asyncio.create_task(self.process_batch())
        
    async def process_batch(self):
        """處理批次刷新請求"""
        logger.info("令牌批處理任務已啟動")
        
        while self.batch_processing:
            batch = []
            
            try:
                # 獲取第一個請求（阻塞）
                first_request = await self.batch_queue.get()
                batch.append(first_request)
                
                # 在最大等待時間內盡可能多收集請求
                batch_start = time.time()
                while len(batch) < self.batch_size and (time.time() - batch_start) * 1000 < self.max_wait_ms:
                    try:
                        # 非阻塞獲取更多請求
                        request = self.batch_queue.get_nowait()
                        batch.append(request)
                    except asyncio.QueueEmpty:
                        # 短暫等待後再試
                        await asyncio.sleep(0.01)
                
                # 按用戶分組請求
                user_groups = {}
                for req in batch:
                    user_id = req["user_id"]
                    if user_id not in user_groups:
                        user_groups[user_id] = []
                    user_groups[user_id].append(req)
                
                # 批量處理每個用戶的請求
                for user_id, requests in user_groups.items():
                    # 只處理每個用戶的第一個請求，結果共享給該用戶的其他請求
                    first_req = requests[0]
                    try:
                        result = await self.process_user_token_refresh(first_req)
                        
                        # 為該用戶的所有請求設置相同結果
                        for req in requests:
                            self.set_result(req["task_id"], result)
                    except Exception as e:
                        logger.error(f"處理用戶 {user_id} 的刷新請求時發生錯誤: {str(e)}")
                        # 設置錯誤結果
                        error_result = {"error": str(e)}
                        for req in requests:
                            self.set_result(req["task_id"], error_result)
                
                # 標記所有請求為已完成
                for _ in batch:
                    self.batch_queue.task_done()
                    
            except Exception as e:
                logger.error(f"批處理刷新請求時發生錯誤: {str(e)}")
                await asyncio.sleep(0.1)
                
        logger.info("令牌批處理任務已停止")
            
    async def process_user_token_refresh(self, request_data):
        """處理單個用戶的令牌刷新"""
        # 在實際實現中需要處理數據庫會話等
        # 這裡提供簡單示例
        return {}
        
    def set_result(self, task_id, result):
        """設置處理結果"""
        # 實際實現中需要存儲結果
        pass
        
    async def add_request(self, request_data):
        """添加刷新請求到佇列"""
        task_id = str(uuid.uuid4())
        request_data["task_id"] = task_id
        await self.batch_queue.put(request_data)
        return task_id
        
    def calculate_dynamic_refresh_threshold(self, user_id: int) -> int:
        """計算動態刷新閾值"""
        return self.activity_tracker.calculate_refresh_threshold(user_id)
        
    def create_refresh_token_with_decay(
        self,
        db: Session, 
        user_id: int,
        expires_delta: Optional[timedelta] = None,
        device_info: Optional[str] = None
    ) -> Tuple[str, RefreshToken, dict]:
        """創建帶衰減特性的刷新令牌"""
        # 獲取用戶刷新模式
        refresh_pattern = self.activity_tracker.get_refresh_pattern(user_id)
        
        # 計算衰減因子
        decay_factor = 1.0  # 初始無衰減
        
        if refresh_pattern["pattern"] != "unknown":
            if refresh_pattern["pattern"] == "frequent":
                decay_factor = 0.9  # 較小衰減
            elif refresh_pattern["pattern"] == "daily":
                decay_factor = 0.95
            else:  # infrequent
                decay_factor = 0.98
        
        # 創建基本刷新令牌
        token, db_token = create_refresh_token(
            db, user_id, expires_delta, device_info
        )
        
        # 記錄令牌使用情況
        self.activity_tracker.record_refresh(user_id, str(db_token.id))
        
        # 計算下次建議刷新時間
        next_refresh = None
        if expires_delta:
            next_refresh_seconds = int(expires_delta.total_seconds() * decay_factor * 0.8)
            next_refresh = datetime.now() + timedelta(seconds=next_refresh_seconds)
        
        # 返回令牌和衰減信息
        decay_info = {
            "decay_factor": decay_factor,
            "next_refresh_suggested": next_refresh.isoformat() if next_refresh else None,
            "refresh_pattern": refresh_pattern["pattern"]
        }
        
        return token, db_token, decay_info
        
    def cleanup(self):
        """執行定期清理任務"""
        self.clean_expired_cache(force=True)
        self.activity_tracker.cleanup_old_data()

# 全局實例
token_refresh_manager = TokenRefreshManager() 