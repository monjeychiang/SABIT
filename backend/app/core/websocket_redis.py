import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set, Any, Tuple
import aioredis
from datetime import datetime
from app.core.config import settings

# 配置日志
logger = logging.getLogger(__name__)

# Redis连接配置
REDIS_URL = settings.REDIS_URL or "redis://localhost:6379/0"

# Redis键前缀
KEY_PREFIX = "ws:"
ROOM_CONNECTIONS_KEY = f"{KEY_PREFIX}room_connections:"  # 聊天室连接映射
USER_CONNECTIONS_KEY = f"{KEY_PREFIX}user_connections:"  # 用户连接映射
MESSAGE_RATE_KEY = f"{KEY_PREFIX}message_rate:"         # 消息速率限制
STATS_KEY = f"{KEY_PREFIX}stats"                        # 统计信息
HEARTBEAT_KEY = f"{KEY_PREFIX}heartbeat:"               # 心跳时间戳

# 全局Redis连接池
redis_pool = None

async def get_redis_pool():
    """获取Redis连接池"""
    global redis_pool
    if redis_pool is None:
        try:
            redis_pool = await aioredis.create_redis_pool(
                REDIS_URL,
                minsize=5,
                maxsize=20,
                encoding="utf-8"
            )
            logger.info(f"已连接到Redis: {REDIS_URL}")
        except Exception as e:
            logger.error(f"连接Redis失败: {str(e)}")
            redis_pool = None
    return redis_pool

async def close_redis_pool():
    """关闭Redis连接池"""
    global redis_pool
    if redis_pool is not None:
        redis_pool.close()
        await redis_pool.wait_closed()
        redis_pool = None
        logger.info("已关闭Redis连接池")

class RedisWebSocketManager:
    """基于Redis的WebSocket连接管理器"""
    
    def __init__(self, node_id: str):
        """
        初始化Redis WebSocket管理器
        
        Args:
            node_id: 当前节点的唯一标识符
        """
        self.node_id = node_id
        self.redis = None
        self.pubsub = None
        self.is_running = False
        self.background_tasks = set()
        
        # 本地连接缓存
        self.local_connections = {}  # {room_id: {user_id: websocket}}
        
        # 用户消息速率限制
        self.MESSAGE_RATE_LIMIT = 10  # 每分钟最大消息数
        self.RATE_LIMIT_WINDOW = 60   # 速率限制窗口（秒）
        
        # 节点信息(主机名、IP等)
        self.node_info = {"id": node_id, "started_at": datetime.now().isoformat()}
    
    async def initialize(self):
        """初始化Redis连接"""
        self.redis = await get_redis_pool()
        if not self.redis:
            logger.error("无法初始化Redis连接，将使用本地状态")
            return False
        
        # 订阅Redis频道用于节点间通信
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(f"{KEY_PREFIX}broadcast")
        
        # 启动消息监听任务
        listen_task = asyncio.create_task(self.listen_for_messages())
        self.background_tasks.add(listen_task)
        listen_task.add_done_callback(self.background_tasks.discard)
        
        # 启动心跳任务
        heartbeat_task = asyncio.create_task(self.send_heartbeat())
        self.background_tasks.add(heartbeat_task)
        heartbeat_task.add_done_callback(self.background_tasks.discard)
        
        self.is_running = True
        logger.info(f"Redis WebSocket管理器已初始化，节点ID: {self.node_id}")
        
        # 注册节点信息
        await self.redis.hset(f"{KEY_PREFIX}nodes", self.node_id, json.dumps(self.node_info))
        await self.redis.expire(f"{KEY_PREFIX}nodes", 3600)  # 1小时过期
        
        return True
    
    async def shutdown(self):
        """关闭所有连接和任务"""
        self.is_running = False
        
        # 取消所有后台任务
        for task in self.background_tasks:
            task.cancel()
        
        # 等待任务完成
        pending = [t for t in self.background_tasks if not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        
        # 清除Redis中的节点信息
        if self.redis:
            await self.redis.hdel(f"{KEY_PREFIX}nodes", self.node_id)
            
            # 取消订阅
            if self.pubsub:
                await self.pubsub.unsubscribe(f"{KEY_PREFIX}broadcast")
        
        logger.info(f"Redis WebSocket管理器已关闭，节点ID: {self.node_id}")
    
    async def register_connection(self, room_id: int, user_id: int, websocket):
        """注册新WebSocket连接"""
        # 存储本地连接引用
        if room_id not in self.local_connections:
            self.local_connections[room_id] = {}
        self.local_connections[room_id][user_id] = websocket
        
        # 更新Redis中的连接映射
        if self.redis:
            connection_info = {
                "node_id": self.node_id,
                "user_id": user_id,
                "connected_at": time.time()
            }
            
            # 添加用户到房间连接列表
            await self.redis.hset(
                f"{ROOM_CONNECTIONS_KEY}{room_id}",
                user_id,
                json.dumps(connection_info)
            )
            
            # 添加房间到用户连接列表
            await self.redis.sadd(f"{USER_CONNECTIONS_KEY}{user_id}", room_id)
            
            # 设置过期时间（1天）
            await self.redis.expire(f"{ROOM_CONNECTIONS_KEY}{room_id}", 86400)
            await self.redis.expire(f"{USER_CONNECTIONS_KEY}{user_id}", 86400)
            
            # 更新统计信息
            await self.redis.hincrby(STATS_KEY, "total_connections", 1)
            await self.redis.hincrby(STATS_KEY, "active_connections", 1)
            
            # 发布用户加入消息
            join_event = {
                "type": "join",
                "room_id": room_id,
                "user_id": user_id,
                "node_id": self.node_id,
                "timestamp": time.time()
            }
            await self.redis.publish(f"{KEY_PREFIX}broadcast", json.dumps(join_event))
            
            logger.info(f"用户 {user_id} 加入聊天室 {room_id}，节点 {self.node_id}")
    
    async def unregister_connection(self, room_id: int, user_id: int):
        """注销WebSocket连接"""
        # 从本地连接缓存中移除
        if room_id in self.local_connections and user_id in self.local_connections[room_id]:
            del self.local_connections[room_id][user_id]
            if not self.local_connections[room_id]:
                del self.local_connections[room_id]
        
        # 从Redis中移除连接映射
        if self.redis:
            # 移除用户从房间连接列表
            await self.redis.hdel(f"{ROOM_CONNECTIONS_KEY}{room_id}", user_id)
            
            # 移除房间从用户连接列表
            await self.redis.srem(f"{USER_CONNECTIONS_KEY}{user_id}", room_id)
            
            # 更新统计信息
            await self.redis.hincrby(STATS_KEY, "active_connections", -1)
            
            # 发布用户离开消息
            leave_event = {
                "type": "leave",
                "room_id": room_id,
                "user_id": user_id,
                "node_id": self.node_id,
                "timestamp": time.time()
            }
            await self.redis.publish(f"{KEY_PREFIX}broadcast", json.dumps(leave_event))
            
            logger.info(f"用户 {user_id} 离开聊天室 {room_id}，节点 {self.node_id}")
    
    async def check_message_rate_limit(self, user_id: int) -> bool:
        """检查用户消息速率是否超限"""
        current_time = time.time()
        
        if not self.redis:
            # 如果没有Redis，使用本地速率限制
            return True
        
        rate_key = f"{MESSAGE_RATE_KEY}{user_id}"
        
        # 获取用户最近消息时间戳
        timestamps = await self.redis.zrangebyscore(
            rate_key,
            current_time - self.RATE_LIMIT_WINDOW,
            current_time
        )
        
        # 检查消息数量是否超限
        if len(timestamps) >= self.MESSAGE_RATE_LIMIT:
            logger.warning(f"用户 {user_id} 消息速率超限: {len(timestamps)}/{self.MESSAGE_RATE_LIMIT}")
            return False
        
        # 添加新消息时间戳
        await self.redis.zadd(rate_key, current_time, f"{current_time}:{int(current_time * 1000) % 1000}")
        await self.redis.expire(rate_key, self.RATE_LIMIT_WINDOW * 2)  # 设置过期时间
        
        # 清理过期的消息时间戳
        await self.redis.zremrangebyscore(
            rate_key, 
            0, 
            current_time - self.RATE_LIMIT_WINDOW
        )
        
        return True
    
    async def broadcast_message(self, room_id: int, message: dict, exclude_user_id: Optional[int] = None):
        """广播消息到聊天室"""
        if not self.redis:
            # 如果没有Redis，只能广播到本地连接
            await self._broadcast_to_local(room_id, message, exclude_user_id)
            return
        
        # 构建广播事件
        broadcast_event = {
            "type": "broadcast",
            "room_id": room_id,
            "message": message,
            "exclude_user_id": exclude_user_id,
            "source_node_id": self.node_id,
            "timestamp": time.time()
        }
        
        # 发布广播事件
        await self.redis.publish(f"{KEY_PREFIX}broadcast", json.dumps(broadcast_event))
        
        # 在本地广播
        await self._broadcast_to_local(room_id, message, exclude_user_id)
        
        # 更新统计信息
        await self.redis.hincrby(STATS_KEY, "messages_sent", 1)
    
    async def _broadcast_to_local(self, room_id: int, message: dict, exclude_user_id: Optional[int] = None):
        """广播消息到本地连接"""
        if room_id not in self.local_connections:
            return
        
        disconnected_users = []
        for user_id, websocket in self.local_connections[room_id].items():
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
            
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"向用户 {user_id} 发送消息失败: {str(e)}")
                disconnected_users.append(user_id)
        
        # 处理断开的连接
        for user_id in disconnected_users:
            await self.unregister_connection(room_id, user_id)
    
    async def listen_for_messages(self):
        """监听Redis广播消息"""
        if not self.pubsub:
            return
        
        try:
            while self.is_running:
                message = await self.pubsub.get_message(timeout=1.0)
                if message and message["type"] == "message":
                    data = message["data"]
                    try:
                        event = json.loads(data)
                        await self._handle_event(event)
                    except json.JSONDecodeError:
                        logger.error(f"解析Redis消息失败: {data}")
                    except Exception as e:
                        logger.error(f"处理Redis消息时出错: {str(e)}")
                
                await asyncio.sleep(0.1)  # 避免CPU占用过高
        except asyncio.CancelledError:
            logger.info("Redis消息监听任务已取消")
        except Exception as e:
            logger.error(f"Redis消息监听任务出错: {str(e)}")
    
    async def _handle_event(self, event: Dict[str, Any]):
        """处理广播事件"""
        event_type = event.get("type")
        source_node_id = event.get("source_node_id")
        
        # 忽略来自本节点的事件
        if source_node_id == self.node_id:
            return
        
        if event_type == "broadcast":
            # 广播消息事件
            room_id = event.get("room_id")
            message = event.get("message")
            exclude_user_id = event.get("exclude_user_id")
            
            if room_id and message:
                await self._broadcast_to_local(room_id, message, exclude_user_id)
        
        elif event_type in ("join", "leave"):
            # 用户加入/离开事件，这里可以处理跨节点的在线状态更新
            pass
    
    async def send_heartbeat(self):
        """定期发送心跳到Redis"""
        if not self.redis:
            return
        
        try:
            while self.is_running:
                # 更新节点心跳
                current_time = time.time()
                heartbeat_data = {
                    "timestamp": current_time,
                    "connections": sum(len(users) for users in self.local_connections.values()),
                    "rooms": len(self.local_connections)
                }
                
                await self.redis.hset(
                    f"{HEARTBEAT_KEY}{self.node_id}",
                    "data",
                    json.dumps(heartbeat_data)
                )
                await self.redis.expire(f"{HEARTBEAT_KEY}{self.node_id}", 60)  # 60秒过期
                
                # 更新节点信息
                self.node_info["last_heartbeat"] = current_time
                self.node_info["connections"] = heartbeat_data["connections"]
                await self.redis.hset(
                    f"{KEY_PREFIX}nodes",
                    self.node_id,
                    json.dumps(self.node_info)
                )
                
                await asyncio.sleep(10)  # 每10秒发送一次心跳
        except asyncio.CancelledError:
            logger.info("Redis心跳任务已取消")
        except Exception as e:
            logger.error(f"Redis心跳任务出错: {str(e)}")
    
    async def get_room_users(self, room_id: int) -> List[int]:
        """获取聊天室中所有用户的ID"""
        if not self.redis:
            # 如果没有Redis，返回本地用户
            return list(self.local_connections.get(room_id, {}).keys())
        
        # 从Redis获取房间所有用户
        users = await self.redis.hkeys(f"{ROOM_CONNECTIONS_KEY}{room_id}")
        return [int(user_id) for user_id in users]
    
    async def get_user_rooms(self, user_id: int) -> List[int]:
        """获取用户加入的所有聊天室ID"""
        if not self.redis:
            # 如果没有Redis，返回本地房间
            return [room_id for room_id, users in self.local_connections.items() if user_id in users]
        
        # 从Redis获取用户所有房间
        rooms = await self.redis.smembers(f"{USER_CONNECTIONS_KEY}{user_id}")
        return [int(room_id) for room_id in rooms]
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取WebSocket连接统计信息"""
        stats = {
            "node_id": self.node_id,
            "local_connections": sum(len(users) for users in self.local_connections.values()),
            "local_rooms": len(self.local_connections),
            "timestamp": datetime.now().isoformat()
        }
        
        if self.redis:
            # 从Redis获取全局统计信息
            redis_stats = await self.redis.hgetall(STATS_KEY)
            for key, value in redis_stats.items():
                try:
                    stats[f"global_{key}"] = int(value)
                except (ValueError, TypeError):
                    stats[f"global_{key}"] = value
            
            # 获取活跃节点列表
            nodes = await self.redis.hgetall(f"{KEY_PREFIX}nodes")
            active_nodes = []
            for node_id, node_data in nodes.items():
                try:
                    node_info = json.loads(node_data)
                    active_nodes.append(node_info)
                except json.JSONDecodeError:
                    pass
            
            stats["active_nodes"] = active_nodes
            stats["node_count"] = len(active_nodes)
        
        return stats


# 全局Redis WebSocket管理器实例
redis_ws_manager = None

async def init_redis_ws_manager(node_id: str):
    """初始化Redis WebSocket管理器"""
    global redis_ws_manager
    if redis_ws_manager is None:
        redis_ws_manager = RedisWebSocketManager(node_id)
        await redis_ws_manager.initialize()
    return redis_ws_manager

async def shutdown_redis_ws_manager():
    """关闭Redis WebSocket管理器"""
    global redis_ws_manager
    if redis_ws_manager:
        await redis_ws_manager.shutdown()
        redis_ws_manager = None
    await close_redis_pool() 