import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set, Any, Tuple
import aioredis
from datetime import datetime
from app.core.config import settings

# 配置日誌
logger = logging.getLogger(__name__)

# Redis連接配置
REDIS_URL = settings.REDIS_URL or "redis://localhost:6379/0"

# Redis鍵前綴
KEY_PREFIX = "ws:"
ROOM_CONNECTIONS_KEY = f"{KEY_PREFIX}room_connections:"  # 聊天室連接映射
USER_CONNECTIONS_KEY = f"{KEY_PREFIX}user_connections:"  # 用戶連接映射
MESSAGE_RATE_KEY = f"{KEY_PREFIX}message_rate:"         # 訊息速率限制
STATS_KEY = f"{KEY_PREFIX}stats"                        # 統計資訊
HEARTBEAT_KEY = f"{KEY_PREFIX}heartbeat:"               # 心跳時間戳

# 全域Redis連接池
redis_pool = None

async def get_redis_pool():
    """獲取Redis連接池"""
    global redis_pool
    if redis_pool is None:
        try:
            redis_pool = await aioredis.create_redis_pool(
                REDIS_URL,
                minsize=5,
                maxsize=20,
                encoding="utf-8"
            )
            logger.info(f"已連接到Redis: {REDIS_URL}")
        except Exception as e:
            logger.error(f"連接Redis失敗: {str(e)}")
            redis_pool = None
    return redis_pool

async def close_redis_pool():
    """關閉Redis連接池"""
    global redis_pool
    if redis_pool is not None:
        redis_pool.close()
        await redis_pool.wait_closed()
        redis_pool = None
        logger.info("已關閉Redis連接池")

class RedisWebSocketManager:
    """基於Redis的WebSocket連接管理器"""
    
    def __init__(self, node_id: str):
        """
        初始化Redis WebSocket管理器
        
        Args:
            node_id: 當前節點的唯一標識符
        """
        self.node_id = node_id
        self.redis = None
        self.pubsub = None
        self.is_running = False
        self.background_tasks = set()
        
        # 本地連接緩存
        self.local_connections = {}  # {room_id: {user_id: websocket}}
        
        # 用戶訊息速率限制
        self.MESSAGE_RATE_LIMIT = 10  # 每分鐘最大訊息數
        self.RATE_LIMIT_WINDOW = 60   # 速率限制窗口（秒）
        
        # 節點資訊(主機名、IP等)
        self.node_info = {"id": node_id, "started_at": datetime.now().isoformat()}
    
    async def initialize(self):
        """初始化Redis連接"""
        self.redis = await get_redis_pool()
        if not self.redis:
            logger.error("無法初始化Redis連接，將使用本地狀態")
            return False
        
        # 訂閱Redis頻道用於節點間通信
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(f"{KEY_PREFIX}broadcast")
        
        # 啟動訊息監聽任務
        listen_task = asyncio.create_task(self.listen_for_messages())
        self.background_tasks.add(listen_task)
        listen_task.add_done_callback(self.background_tasks.discard)
        
        # 啟動心跳任務
        heartbeat_task = asyncio.create_task(self.send_heartbeat())
        self.background_tasks.add(heartbeat_task)
        heartbeat_task.add_done_callback(self.background_tasks.discard)
        
        self.is_running = True
        logger.info(f"Redis WebSocket管理器已初始化，節點ID: {self.node_id}")
        
        # 註冊節點資訊
        await self.redis.hset(f"{KEY_PREFIX}nodes", self.node_id, json.dumps(self.node_info))
        await self.redis.expire(f"{KEY_PREFIX}nodes", 3600)  # 1小時過期
        
        return True
    
    async def shutdown(self):
        """關閉所有連接和任務"""
        self.is_running = False
        
        # 取消所有後台任務
        for task in self.background_tasks:
            task.cancel()
        
        # 等待任務完成
        pending = [t for t in self.background_tasks if not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        
        # 清除Redis中的節點資訊
        if self.redis:
            await self.redis.hdel(f"{KEY_PREFIX}nodes", self.node_id)
            
            # 取消訂閱
            if self.pubsub:
                await self.pubsub.unsubscribe(f"{KEY_PREFIX}broadcast")
        
        logger.info(f"Redis WebSocket管理器已關閉，節點ID: {self.node_id}")
    
    async def register_connection(self, room_id: int, user_id: int, websocket):
        """註冊新WebSocket連接"""
        # 儲存本地連接引用
        if room_id not in self.local_connections:
            self.local_connections[room_id] = {}
        self.local_connections[room_id][user_id] = websocket
        
        # 更新Redis中的連接映射
        if self.redis:
            connection_info = {
                "node_id": self.node_id,
                "user_id": user_id,
                "connected_at": time.time()
            }
            
            # 添加用戶到房間連接列表
            await self.redis.hset(
                f"{ROOM_CONNECTIONS_KEY}{room_id}",
                user_id,
                json.dumps(connection_info)
            )
            
            # 添加房間到用戶連接列表
            await self.redis.sadd(f"{USER_CONNECTIONS_KEY}{user_id}", room_id)
            
            # 設置過期時間（1天）
            await self.redis.expire(f"{ROOM_CONNECTIONS_KEY}{room_id}", 86400)
            await self.redis.expire(f"{USER_CONNECTIONS_KEY}{user_id}", 86400)
            
            # 更新統計資訊
            await self.redis.hincrby(STATS_KEY, "total_connections", 1)
            await self.redis.hincrby(STATS_KEY, "active_connections", 1)
            
            # 發布用戶加入訊息
            join_event = {
                "type": "join",
                "room_id": room_id,
                "user_id": user_id,
                "node_id": self.node_id,
                "timestamp": time.time()
            }
            await self.redis.publish(f"{KEY_PREFIX}broadcast", json.dumps(join_event))
            
            logger.info(f"用戶 {user_id} 加入聊天室 {room_id}，節點 {self.node_id}")
    
    async def unregister_connection(self, room_id: int, user_id: int):
        """註銷WebSocket連接"""
        # 從本地連接緩存中移除
        if room_id in self.local_connections and user_id in self.local_connections[room_id]:
            del self.local_connections[room_id][user_id]
            if not self.local_connections[room_id]:
                del self.local_connections[room_id]
        
        # 從Redis中移除連接映射
        if self.redis:
            # 移除用戶從房間連接列表
            await self.redis.hdel(f"{ROOM_CONNECTIONS_KEY}{room_id}", user_id)
            
            # 移除房間從用戶連接列表
            await self.redis.srem(f"{USER_CONNECTIONS_KEY}{user_id}", room_id)
            
            # 更新統計資訊
            await self.redis.hincrby(STATS_KEY, "active_connections", -1)
            
            # 發布用戶離開訊息
            leave_event = {
                "type": "leave",
                "room_id": room_id,
                "user_id": user_id,
                "node_id": self.node_id,
                "timestamp": time.time()
            }
            await self.redis.publish(f"{KEY_PREFIX}broadcast", json.dumps(leave_event))
            
            logger.info(f"用戶 {user_id} 離開聊天室 {room_id}，節點 {self.node_id}")
    
    async def check_message_rate_limit(self, user_id: int) -> bool:
        """檢查用戶訊息速率是否超限"""
        if not self.redis:
            return True  # 沒有Redis時不做速率限制
        
        current_time = time.time()
        rate_key = f"{MESSAGE_RATE_KEY}{user_id}"
        
        # 獲取用戶最近的訊息時間戳
        timestamps = await self.redis.zrangebyscore(
            rate_key,
            current_time - self.RATE_LIMIT_WINDOW,
            current_time
        )
        
        # 如果訊息數量超過限制，則拒絕
        if len(timestamps) >= self.MESSAGE_RATE_LIMIT:
            logger.warning(f"用戶 {user_id} 訊息速率超限: {len(timestamps)}/{self.MESSAGE_RATE_LIMIT}")
            return False
        
        # 記錄本次訊息時間戳
        await self.redis.zadd(rate_key, current_time, str(current_time))
        
        # 設置過期時間，避免佔用過多記憶體
        await self.redis.expire(rate_key, self.RATE_LIMIT_WINDOW * 2)
        
        return True
    
    async def broadcast_message(self, room_id: int, message: dict, exclude_user_id: Optional[int] = None):
        """向聊天室廣播訊息（分佈式）"""
        # 消息類型標記為"message"，用於區分系統事件
        message["_meta"] = {
            "type": "message",
            "room_id": room_id,
            "sender_id": message.get("user_id"),
            "timestamp": time.time(),
            "node_id": self.node_id
        }
        
        # 更新統計資訊
        if self.redis:
            await self.redis.hincrby(STATS_KEY, "messages_sent", 1)
            
            # 通過Redis發布廣播訊息
            broadcast_data = {
                "type": "broadcast",
                "room_id": room_id,
                "message": message,
                "exclude_user_id": exclude_user_id,
                "node_id": self.node_id,
                "timestamp": time.time()
            }
            await self.redis.publish(f"{KEY_PREFIX}broadcast", json.dumps(broadcast_data))
        
        # 本節點直接廣播
        await self._broadcast_to_local(room_id, message, exclude_user_id)
    
    async def _broadcast_to_local(self, room_id: int, message: dict, exclude_user_id: Optional[int] = None):
        """向本地連接的用戶廣播訊息"""
        if room_id not in self.local_connections:
            return
        
        # 轉換為JSON字串
        message_str = json.dumps(message)
        sent_count = 0
        
        # 向房間中的每個用戶發送訊息
        for user_id, websocket in list(self.local_connections[room_id].items()):
            # 跳過被排除的用戶
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
                
            try:
                await websocket.send_text(message_str)
                sent_count += 1
            except Exception as e:
                logger.error(f"向用戶 {user_id} 發送訊息失敗: {str(e)}")
                # 連接可能已斷開，移除連接
                await self.unregister_connection(room_id, user_id)
        
        logger.debug(f"在節點 {self.node_id} 的聊天室 {room_id} 中向 {sent_count} 個用戶發送了訊息")
    
    async def listen_for_messages(self):
        """監聽來自其他節點的訊息"""
        if not self.pubsub:
            return
            
        try:
            while self.is_running:
                message = await self.pubsub.get_message(timeout=1)
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        # 處理來自其他節點的事件
                        if data.get('node_id') != self.node_id:
                            await self._handle_event(data)
                    except json.JSONDecodeError:
                        logger.error(f"解析Redis訊息失敗: {message['data']}")
                    except Exception as e:
                        logger.error(f"處理Redis訊息時出錯: {str(e)}")
                
                await asyncio.sleep(0.01)  # 小睡一下，避免CPU使用率過高
        except asyncio.CancelledError:
            logger.info("Redis訊息監聽任務已取消")
        except Exception as e:
            logger.error(f"Redis訊息監聽任務異常: {str(e)}")
    
    async def _handle_event(self, event: Dict[str, Any]):
        """處理來自其他節點的事件"""
        event_type = event.get('type')
        
        if event_type == 'broadcast':
            # 廣播訊息事件
            room_id = event.get('room_id')
            message = event.get('message')
            exclude_user_id = event.get('exclude_user_id')
            
            if room_id and message:
                await self._broadcast_to_local(room_id, message, exclude_user_id)
                
        elif event_type in ['join', 'leave']:
            # 用戶加入/離開事件 - 可以通知本地連接的用戶
            room_id = event.get('room_id')
            user_id = event.get('user_id')
            
            if room_id in self.local_connections:
                status_message = {
                    "type": "user_status",
                    "user_id": user_id,
                    "status": "online" if event_type == "join" else "offline",
                    "timestamp": event.get('timestamp', time.time())
                }
                await self._broadcast_to_local(room_id, status_message)
    
    async def send_heartbeat(self):
        """定期發送心跳以維持節點活躍狀態"""
        try:
            while self.is_running and self.redis:
                current_time = time.time()
                
                # 更新節點心跳時間
                await self.redis.hset(
                    HEARTBEAT_KEY,
                    self.node_id,
                    current_time
                )
                
                # 設置過期時間
                await self.redis.expire(HEARTBEAT_KEY, 300)  # 5分鐘
                
                # 更新節點資訊
                self.node_info["last_heartbeat"] = current_time
                self.node_info["connections"] = sum(len(users) for users in self.local_connections.values())
                await self.redis.hset(
                    f"{KEY_PREFIX}nodes",
                    self.node_id,
                    json.dumps(self.node_info)
                )
                
                # 清理過期節點（超過2分鐘未發送心跳）
                all_heartbeats = await self.redis.hgetall(HEARTBEAT_KEY)
                for node, timestamp in all_heartbeats.items():
                    try:
                        if float(timestamp) < current_time - 120:  # 2分鐘超時
                            logger.warning(f"節點 {node} 心跳超時，可能已離線")
                            # 可以在這裡處理節點離線後的清理工作
                    except (ValueError, TypeError):
                        pass
                
                # 每30秒發送一次心跳
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            logger.info("心跳任務已取消")
        except Exception as e:
            logger.error(f"心跳任務異常: {str(e)}")
    
    async def get_room_users(self, room_id: int) -> List[int]:
        """獲取聊天室中的所有用戶ID"""
        if not self.redis:
            return list(self.local_connections.get(room_id, {}).keys())
            
        # 從Redis獲取聊天室用戶列表
        users = await self.redis.hkeys(f"{ROOM_CONNECTIONS_KEY}{room_id}")
        return [int(user_id) for user_id in users]
    
    async def get_user_rooms(self, user_id: int) -> List[int]:
        """獲取用戶加入的所有聊天室ID"""
        if not self.redis:
            return [room_id for room_id, users in self.local_connections.items() if user_id in users]
            
        # 從Redis獲取用戶聊天室列表
        rooms = await self.redis.smembers(f"{USER_CONNECTIONS_KEY}{user_id}")
        return [int(room_id) for room_id in rooms]
    
    async def get_stats(self) -> Dict[str, Any]:
        """獲取WebSocket統計資訊"""
        stats = {
            "node_id": self.node_id,
            "local_connections": sum(len(users) for users in self.local_connections.items()),
            "local_rooms": len(self.local_connections),
            "timestamp": datetime.now().isoformat()
        }
        
        if self.redis:
            # 從Redis獲取全域統計資訊
            redis_stats = await self.redis.hgetall(STATS_KEY)
            if redis_stats:
                for key, value in redis_stats.items():
                    try:
                        stats[f"global_{key}"] = int(value)
                    except (TypeError, ValueError):
                        stats[f"global_{key}"] = value
            
            # 獲取活躍節點數
            active_nodes = await self.redis.hlen(HEARTBEAT_KEY)
            stats["active_nodes"] = active_nodes
            
            # 獲取所有聊天室數
            all_room_keys = await self.redis.keys(f"{ROOM_CONNECTIONS_KEY}*")
            stats["total_rooms"] = len(all_room_keys)
            
            # 獲取所有用戶數
            all_user_keys = await self.redis.keys(f"{USER_CONNECTIONS_KEY}*")
            stats["total_users"] = len(all_user_keys)
        
        return stats

# 全域Redis WebSocket管理器實例
redis_ws_manager = None

async def init_redis_ws_manager(node_id: str):
    """初始化Redis WebSocket管理器"""
    global redis_ws_manager
    redis_ws_manager = RedisWebSocketManager(node_id)
    success = await redis_ws_manager.initialize()
    return redis_ws_manager if success else None

async def shutdown_redis_ws_manager():
    """關閉Redis WebSocket管理器"""
    global redis_ws_manager
    if redis_ws_manager:
        await redis_ws_manager.shutdown()
        redis_ws_manager = None
    await close_redis_pool() 