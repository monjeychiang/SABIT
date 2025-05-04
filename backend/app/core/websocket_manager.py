import asyncio
import time
import logging
from typing import Dict, List, Set, Optional, Any
import threading
from fastapi import WebSocket
from datetime import datetime
import json

from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

class WebSocketStatsCollector:
    """WebSocket统计信息收集器"""
    def __init__(self):
        self._lock = threading.RLock()
        self.total_connections = 0
        self.active_connections = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.errors = 0
        self.connection_rate = 0  # 每秒新连接数
        self.message_rate = 0     # 每秒消息数
        
        # 时间窗口统计（1分钟）
        self.connection_times: List[float] = []  # 最近连接时间戳
        self.message_times: List[float] = []     # 最近消息时间戳
        self.window_size = 60  # 60秒窗口
        
        # 启动后台任务更新速率
        self._update_task = None
        self._is_running = False
    
    def start(self):
        """启动统计收集器"""
        if not self._is_running:
            self._is_running = True
            self._update_task = asyncio.create_task(self._update_rates())
            logger.info("WebSocket统计收集器已启动")
    
    async def stop(self):
        """停止统计收集器"""
        if self._is_running:
            self._is_running = False
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            logger.info("WebSocket统计收集器已停止")
    
    async def _update_rates(self):
        """更新速率统计"""
        try:
            while self._is_running:
                await asyncio.sleep(1)
                self._cleanup_old_data()
                self._calculate_rates()
        except asyncio.CancelledError:
            logger.info("WebSocket统计更新任务已取消")
        except Exception as e:
            logger.error(f"WebSocket统计更新任务出错: {str(e)}")
    
    def _cleanup_old_data(self):
        """清理过期数据"""
        current_time = time.time()
        with self._lock:
            self.connection_times = [t for t in self.connection_times if current_time - t <= self.window_size]
            self.message_times = [t for t in self.message_times if current_time - t <= self.window_size]
    
    def _calculate_rates(self):
        """计算速率"""
        with self._lock:
            self.connection_rate = len(self.connection_times) / self.window_size
            self.message_rate = len(self.message_times) / self.window_size
    
    def record_connection(self):
        """记录新连接"""
        with self._lock:
            self.total_connections += 1
            self.active_connections += 1
            self.connection_times.append(time.time())
    
    def record_disconnection(self):
        """记录断开连接"""
        with self._lock:
            self.active_connections = max(0, self.active_connections - 1)
    
    def record_message_sent(self):
        """记录发送消息"""
        with self._lock:
            self.messages_sent += 1
            self.message_times.append(time.time())
    
    def record_message_received(self):
        """记录接收消息"""
        with self._lock:
            self.messages_received += 1
            self.message_times.append(time.time())
    
    def record_error(self):
        """记录错误"""
        with self._lock:
            self.errors += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
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
    """全局WebSocket连接管理器"""
    def __init__(self):
        # 从配置中读取全局连接限制
        self.MAX_GLOBAL_CONNECTIONS = settings.WS_MAX_GLOBAL_CONNECTIONS
        self.MAX_CONNECTIONS_PER_USER = settings.WS_MAX_CONNECTIONS_PER_USER
        self.MAX_CONNECTIONS_PER_ROOM = settings.WS_MAX_CONNECTIONS_PER_ROOM
        
        # 连接追踪
        self.user_connections: Dict[int, Set[WebSocket]] = {}  # 用户ID -> WebSocket集合
        self.room_connections: Dict[int, Dict[int, WebSocket]] = {}  # 聊天室ID -> {用户ID -> WebSocket}
        
        # 从配置中读取速率限制
        self.user_message_rates: Dict[int, List[float]] = {}  # 用户ID -> 消息时间戳列表
        self.MESSAGE_RATE_LIMIT = settings.WS_MESSAGE_RATE_LIMIT
        self.RATE_LIMIT_WINDOW = settings.WS_RATE_LIMIT_WINDOW
        
        # 统计信息
        self.stats = WebSocketStatsCollector()
        self.stats.start()
        
        logger.info(f"全局WebSocket管理器已初始化，连接限制：全局={self.MAX_GLOBAL_CONNECTIONS}，每用户={self.MAX_CONNECTIONS_PER_USER}，每聊天室={self.MAX_CONNECTIONS_PER_ROOM}，消息速率={self.MESSAGE_RATE_LIMIT}/{self.RATE_LIMIT_WINDOW}秒")
    
    async def shutdown(self):
        """关闭管理器"""
        await self.stats.stop()
        # 关闭所有连接
        for user_id, connections in self.user_connections.items():
            for websocket in connections:
                try:
                    await websocket.close(code=1001)  # 服务器关闭
                except Exception as e:
                    logger.error(f"关闭用户 {user_id} 的WebSocket连接失败: {str(e)}")
        
        # 清空连接
        self.user_connections.clear()
        self.room_connections.clear()
        logger.info("全局WebSocket管理器已关闭")
    
    def can_connect(self, user_id: int, room_id: int) -> bool:
        """检查是否允许新连接"""
        # 检查全局连接数
        total_connections = sum(len(connections) for connections in self.user_connections.values())
        if total_connections >= self.MAX_GLOBAL_CONNECTIONS:
            logger.warning(f"全局连接数已达上限 ({total_connections}/{self.MAX_GLOBAL_CONNECTIONS})")
            return False
        
        # 检查用户连接数
        user_connection_count = len(self.user_connections.get(user_id, set()))
        if user_connection_count >= self.MAX_CONNECTIONS_PER_USER:
            logger.warning(f"用户 {user_id} 的连接数已达上限 ({user_connection_count}/{self.MAX_CONNECTIONS_PER_USER})")
            return False
        
        # 检查聊天室连接数
        room_connection_count = len(self.room_connections.get(room_id, {}))
        if room_connection_count >= self.MAX_CONNECTIONS_PER_ROOM:
            logger.warning(f"聊天室 {room_id} 的连接数已达上限 ({room_connection_count}/{self.MAX_CONNECTIONS_PER_ROOM})")
            return False
        
        return True
    
    def register_connection(self, websocket: WebSocket, user_id: int, room_id: int):
        """注册新连接"""
        # 初始化用户连接集合
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        
        # 添加连接到用户集合
        self.user_connections[user_id].add(websocket)
        
        # 初始化聊天室连接字典
        if room_id not in self.room_connections:
            self.room_connections[room_id] = {}
        
        # 添加连接到聊天室字典
        self.room_connections[room_id][user_id] = websocket
        
        # 记录统计信息
        self.stats.record_connection()
        
        logger.info(f"用户 {user_id} 注册了到聊天室 {room_id} 的新连接")
    
    def unregister_connection(self, user_id: int, room_id: int):
        """注销连接"""
        # 从用户连接集合中移除
        if user_id in self.user_connections:
            # 尝试找到并移除特定的连接
            if room_id in self.room_connections and user_id in self.room_connections[room_id]:
                websocket = self.room_connections[room_id][user_id]
                if websocket in self.user_connections[user_id]:
                    self.user_connections[user_id].remove(websocket)
            
            # 如果用户没有更多连接，删除用户条目
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # 从聊天室连接字典中移除
        if room_id in self.room_connections and user_id in self.room_connections[room_id]:
            del self.room_connections[room_id][user_id]
            
            # 如果聊天室没有更多连接，删除聊天室条目
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
        
        # 记录统计信息
        self.stats.record_disconnection()
        
        logger.info(f"用户 {user_id} 注销了到聊天室 {room_id} 的连接")
    
    def check_message_rate_limit(self, user_id: int) -> bool:
        """检查用户消息速率是否超限"""
        current_time = time.time()
        
        # 初始化用户消息计数
        if user_id not in self.user_message_rates:
            self.user_message_rates[user_id] = []
        
        # 清理过期的消息时间戳
        self.user_message_rates[user_id] = [
            ts for ts in self.user_message_rates[user_id]
            if current_time - ts < self.RATE_LIMIT_WINDOW
        ]
        
        # 检查当前窗口内的消息数量
        if len(self.user_message_rates[user_id]) >= self.MESSAGE_RATE_LIMIT:
            logger.warning(f"用户 {user_id} 的消息速率超限")
            return False
        
        # 添加新消息时间戳
        self.user_message_rates[user_id].append(current_time)
        return True
    
    def record_message_sent(self):
        """记录发送消息"""
        self.stats.record_message_sent()
    
    def record_message_received(self):
        """记录接收消息"""
        self.stats.record_message_received()
    
    def record_error(self):
        """记录错误"""
        self.stats.record_error()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.get_stats()
        
        # 添加额外信息
        stats["user_count"] = len(self.user_connections)
        stats["room_count"] = len(self.room_connections)
        
        return stats


# 创建全局实例
global_ws_manager = GlobalWebSocketManager()


async def shutdown_ws_manager():
    """关闭全局WebSocket管理器"""
    await global_ws_manager.shutdown() 