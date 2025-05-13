import asyncio
import time
import logging
from typing import Dict, List, Set, Optional, Any
import threading
from fastapi import WebSocket
from datetime import datetime
import json

from .config import settings

# 配置日誌
logger = logging.getLogger(__name__)

class WebSocketStatsCollector:
    """WebSocket統計資訊收集器"""
    def __init__(self):
        self._lock = threading.RLock()
        self.total_connections = 0
        self.active_connections = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.errors = 0
        self.connection_rate = 0  # 每秒新連接數
        self.message_rate = 0     # 每秒訊息數
        
        # 時間窗口統計（1分鐘）
        self.connection_times: List[float] = []  # 最近連接時間戳
        self.message_times: List[float] = []     # 最近訊息時間戳
        self.window_size = 60  # 60秒窗口
        
        # 啟動後台任務更新速率
        self._update_task = None
        self._is_running = False
    
    def start(self):
        """啟動統計收集器"""
        if not self._is_running:
            self._is_running = True
            self._update_task = asyncio.create_task(self._update_rates())
            logger.info("WebSocket統計收集器已啟動")
    
    async def stop(self):
        """停止統計收集器"""
        if self._is_running:
            self._is_running = False
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            logger.info("WebSocket統計收集器已停止")
    
    async def _update_rates(self):
        """更新速率統計"""
        try:
            while self._is_running:
                await asyncio.sleep(1)
                self._cleanup_old_data()
                self._calculate_rates()
        except asyncio.CancelledError:
            logger.info("WebSocket統計更新任務已取消")
        except Exception as e:
            logger.error(f"WebSocket統計更新任務出錯: {str(e)}")
    
    def _cleanup_old_data(self):
        """清理過期數據"""
        current_time = time.time()
        with self._lock:
            self.connection_times = [t for t in self.connection_times if current_time - t <= self.window_size]
            self.message_times = [t for t in self.message_times if current_time - t <= self.window_size]
    
    def _calculate_rates(self):
        """計算速率"""
        with self._lock:
            self.connection_rate = len(self.connection_times) / self.window_size
            self.message_rate = len(self.message_times) / self.window_size
    
    def record_connection(self):
        """記錄新連接"""
        with self._lock:
            self.total_connections += 1
            self.active_connections += 1
            self.connection_times.append(time.time())
    
    def record_disconnection(self):
        """記錄斷開連接"""
        with self._lock:
            self.active_connections = max(0, self.active_connections - 1)
    
    def record_message_sent(self):
        """記錄發送訊息"""
        with self._lock:
            self.messages_sent += 1
            self.message_times.append(time.time())
    
    def record_message_received(self):
        """記錄接收訊息"""
        with self._lock:
            self.messages_received += 1
            self.message_times.append(time.time())
    
    def record_error(self):
        """記錄錯誤"""
        with self._lock:
            self.errors += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取統計資訊"""
        with self._lock:
            return {
                "total_connections": self.total_connections,
                "active_connections": self.active_connections,
                "messages_sent": self.messages_sent,
                "messages_received": self.messages_received,
                "errors": self.errors,
                "connection_rate": round(self.connection_rate, 2),
                "message_rate": round(self.message_rate, 2),
                "timestamp": datetime.now().isoformat()
            }


class GlobalWebSocketManager:
    """全域WebSocket連接管理器"""
    def __init__(self):
        # 從配置中讀取全域連接限制
        self.MAX_GLOBAL_CONNECTIONS = settings.WS_MAX_GLOBAL_CONNECTIONS
        self.MAX_CONNECTIONS_PER_USER = settings.WS_MAX_CONNECTIONS_PER_USER
        self.MAX_CONNECTIONS_PER_ROOM = settings.WS_MAX_CONNECTIONS_PER_ROOM
        
        # 連接追蹤
        self.user_connections: Dict[int, Set[WebSocket]] = {}  # 用戶ID -> WebSocket集合
        self.room_connections: Dict[int, Dict[int, WebSocket]] = {}  # 聊天室ID -> {用戶ID -> WebSocket}
        
        # 從配置中讀取速率限制
        self.user_message_rates: Dict[int, List[float]] = {}  # 用戶ID -> 訊息時間戳列表
        self.MESSAGE_RATE_LIMIT = settings.WS_MESSAGE_RATE_LIMIT
        self.RATE_LIMIT_WINDOW = settings.WS_RATE_LIMIT_WINDOW
        
        # 統計資訊
        self.stats = WebSocketStatsCollector()
        self.stats.start()
        
        logger.info(f"全域WebSocket管理器已初始化，連接限制：全域={self.MAX_GLOBAL_CONNECTIONS}，每用戶={self.MAX_CONNECTIONS_PER_USER}，每聊天室={self.MAX_CONNECTIONS_PER_ROOM}，訊息速率={self.MESSAGE_RATE_LIMIT}/{self.RATE_LIMIT_WINDOW}秒")
    
    async def shutdown(self):
        """關閉管理器"""
        await self.stats.stop()
        # 關閉所有連接
        for user_id, connections in self.user_connections.items():
            for websocket in connections:
                try:
                    await websocket.close(code=1001)  # 伺服器關閉
                except Exception as e:
                    logger.error(f"關閉用戶 {user_id} 的WebSocket連接失敗: {str(e)}")
        
        # 清空連接
        self.user_connections.clear()
        self.room_connections.clear()
        logger.info("全域WebSocket管理器已關閉")
    
    def can_connect(self, user_id: int, room_id: int) -> bool:
        """檢查是否允許新連接"""
        # 檢查全域連接數
        total_connections = sum(len(connections) for connections in self.user_connections.values())
        if total_connections >= self.MAX_GLOBAL_CONNECTIONS:
            logger.warning(f"全域連接數已達上限 ({total_connections}/{self.MAX_GLOBAL_CONNECTIONS})")
            return False
        
        # 檢查用戶連接數
        user_connection_count = len(self.user_connections.get(user_id, set()))
        if user_connection_count >= self.MAX_CONNECTIONS_PER_USER:
            logger.warning(f"用戶 {user_id} 的連接數已達上限 ({user_connection_count}/{self.MAX_CONNECTIONS_PER_USER})")
            return False
        
        # 檢查聊天室連接數
        room_connection_count = len(self.room_connections.get(room_id, {}))
        if room_connection_count >= self.MAX_CONNECTIONS_PER_ROOM:
            logger.warning(f"聊天室 {room_id} 的連接數已達上限 ({room_connection_count}/{self.MAX_CONNECTIONS_PER_ROOM})")
            return False
        
        return True
    
    def register_connection(self, websocket: WebSocket, user_id: int, room_id: int):
        """註冊新連接"""
        # 初始化用戶連接集合
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        
        # 添加連接到用戶集合
        self.user_connections[user_id].add(websocket)
        
        # 初始化聊天室連接字典
        if room_id not in self.room_connections:
            self.room_connections[room_id] = {}
        
        # 添加連接到聊天室字典
        self.room_connections[room_id][user_id] = websocket
        
        # 記錄統計資訊
        self.stats.record_connection()
        
        logger.info(f"用戶 {user_id} 註冊了到聊天室 {room_id} 的新連接")
    
    def unregister_connection(self, user_id: int, room_id: int):
        """註銷連接"""
        # 從用戶連接集合中移除
        if user_id in self.user_connections:
            # 嘗試找到並移除特定的連接
            if room_id in self.room_connections and user_id in self.room_connections[room_id]:
                websocket = self.room_connections[room_id][user_id]
                if websocket in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(websocket)
            
            # 如果用戶沒有更多連接，刪除用戶條目
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # 從聊天室連接字典中移除
        if room_id in self.room_connections and user_id in self.room_connections[room_id]:
            del self.room_connections[room_id][user_id]
            
            # 如果聊天室沒有更多連接，刪除聊天室條目
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
        
        # 記錄統計資訊
        self.stats.record_disconnection()
        
        logger.info(f"用戶 {user_id} 註銷了到聊天室 {room_id} 的連接")
    
    def check_message_rate_limit(self, user_id: int) -> bool:
        """檢查用戶訊息速率是否超限"""
        current_time = time.time()
        
        # 初始化用戶訊息計數
        if user_id not in self.user_message_rates:
            self.user_message_rates[user_id] = []
        
        # 清理過期的訊息時間戳
        self.user_message_rates[user_id] = [
            ts for ts in self.user_message_rates[user_id]
            if current_time - ts < self.RATE_LIMIT_WINDOW
        ]
        
        # 檢查當前窗口內的訊息數量
        if len(self.user_message_rates[user_id]) >= self.MESSAGE_RATE_LIMIT:
            logger.warning(f"用戶 {user_id} 的訊息速率超限")
            return False
        
        # 記錄本次訊息
        self.user_message_rates[user_id].append(current_time)
        return True
    
    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """向特定用戶發送訊息"""
        if user_id not in self.user_connections:
            return False
        
        # 獲取用戶的所有連接
        connections = self.user_connections[user_id]
        if not connections:
            return False
        
        # 轉換消息為JSON字符串
        message_str = json.dumps(message)
        
        # 選擇用戶的第一個連接發送消息
        websocket = next(iter(connections))
        try:
            await websocket.send_text(message_str)
            self.stats.record_message_sent()
            return True
        except Exception as e:
            logger.error(f"向用戶 {user_id} 發送訊息失敗: {str(e)}")
            self.stats.record_error()
            return False
    
    async def broadcast_to_room(self, room_id: int, message: Dict[str, Any], exclude_user_id: Optional[int] = None):
        """向聊天室廣播訊息"""
        if room_id not in self.room_connections:
            return 0
        
        sent_count = 0
        # 獲取聊天室內的所有用戶
        users = list(self.room_connections[room_id].keys())
        
        # 轉換消息為JSON字符串
        message_str = json.dumps(message)
        
        # 向每個用戶發送消息
        for user_id in users:
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
            
            websocket = self.room_connections[room_id].get(user_id)
            if websocket:
                try:
                    await websocket.send_text(message_str)
                    sent_count += 1
                    self.stats.record_message_sent()
                except Exception as e:
                    logger.error(f"向用戶 {user_id} 發送聊天室 {room_id} 的廣播訊息失敗: {str(e)}")
                    self.stats.record_error()
                    # 可能需要從連接池中移除
                    self.unregister_connection(user_id, room_id)
        
        return sent_count
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取WebSocket管理器統計資訊"""
        stats = self.stats.get_stats()
        stats.update({
            "user_connections": len(self.user_connections),
            "room_connections": len(self.room_connections),
            "rate_limited_users": sum(1 for user_id, timestamps in self.user_message_rates.items() 
                                 if len(timestamps) >= self.MESSAGE_RATE_LIMIT)
        })
        return stats

# 全域WebSocket管理器實例
ws_manager = GlobalWebSocketManager()

# 提供一個關閉管理器的協程函數
async def shutdown_ws_manager():
    """關閉全域WebSocket管理器"""
    await ws_manager.shutdown() 