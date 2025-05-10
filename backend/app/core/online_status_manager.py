"""
在线用户状态管理模块

该模块提供了用户在线状态的管理功能，包括：
1. 跟踪用户的在线/离线状态
2. 只向真正在线的用户发送消息
3. 自动清理断开连接的WebSocket
4. 提供在线用户统计和查询功能
"""

import logging
import json
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timedelta
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

# 配置日志
logger = logging.getLogger(__name__)

class OnlineStatusManager:
    """在线状态管理器 - 负责管理用户的在线状态和WebSocket连接"""
    
    def __init__(self):
        # 存储活跃的WebSocket连接: {user_id: websocket}
        self.active_connections: Dict[int, WebSocket] = {}
        # 用户加入的聊天室: {user_id: set(room_id)}
        self.user_rooms: Dict[int, Set[int]] = {}
        # 聊天室成员: {room_id: set(user_id)}
        self.room_members: Dict[int, Set[int]] = {}
        # 用户状态记录: {user_id: {online: bool, last_active: datetime, ...}}
        self.user_status: Dict[int, Dict[str, Any]] = {}
        # 用户最后活跃时间
        self.last_active: Dict[int, datetime] = {}
        # 心跳超时时间（秒）
        self.heartbeat_timeout = 300  # 5分钟
        # 清理任务
        self._cleanup_task = None
        # 统计信息
        self.stats = {
            "total_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "cleanup_count": 0
        }
    
    async def start(self):
        """启动状态管理器和定期清理任务"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("在线状态管理器已启动")
    
    async def shutdown(self):
        """关闭状态管理器和清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有连接
        for user_id in list(self.active_connections.keys()):
            try:
                await self.active_connections[user_id].close()
            except:
                pass
        self.active_connections.clear()
        logger.info("在线状态管理器已关闭")
    
    async def _cleanup_loop(self):
        """定期检查并清理不活跃的连接"""
        while True:
            try:
                await self._cleanup_inactive_connections()
                # 每分钟清理一次
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"在线状态清理任务出错: {str(e)}")
                await asyncio.sleep(60)  # 出错后等待1分钟再试
    
    async def _cleanup_inactive_connections(self):
        """清理不活跃的连接"""
        current_time = datetime.now()
        inactive_users = []
        
        # 检查所有用户的最后活跃时间
        for user_id, last_active in list(self.last_active.items()):
            if (current_time - last_active).total_seconds() > self.heartbeat_timeout:
                inactive_users.append(user_id)
        
        # 清理不活跃的连接
        for user_id in inactive_users:
            logger.info(f"清理不活跃用户: {user_id}, 超时未活动")
            await self.disconnect_user(user_id)
        
        if inactive_users:
            self.stats["cleanup_count"] += len(inactive_users)
            logger.info(f"清理了 {len(inactive_users)} 个不活跃连接")
    
    async def connect_user(self, websocket: WebSocket, user_id: int):
        """用户WebSocket连接处理"""
        # 接受WebSocket连接
        await websocket.accept()
        
        # 如果用户已有连接，先关闭旧连接
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except:
                pass
        
        # 记录新连接
        self.active_connections[user_id] = websocket
        self.last_active[user_id] = datetime.now()
        self.stats["total_connections"] += 1
        
        # 更新用户状态
        self.user_status[user_id] = {
            "online": True,
            "last_active": datetime.now().isoformat(),
            "connection_time": datetime.now().isoformat()
        }
        
        # 生成连接ID，用于日志追踪
        connection_id = f"online_status_{user_id}_{id(websocket)}"
        
        logger.info(f"[OnlineStatus] WebSocket连接已建立: 用户ID={user_id}, 连接ID={connection_id}, 当前连接总数={len(self.active_connections)}")
        
        # 向所有相关聊天室通知用户在线
        await self.broadcast_user_status_change(user_id, True)
    
    async def disconnect_user(self, user_id: int):
        """断开用户连接并更新状态"""
        # 如果用户在线，关闭WebSocket连接
        websocket = None
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await self.active_connections[user_id].close()
            except:
                pass
            del self.active_connections[user_id]
        
        # 更新用户状态
        if user_id in self.user_status:
            self.user_status[user_id]["online"] = False
            self.user_status[user_id]["last_disconnect"] = datetime.now().isoformat()
        
        # 清理最后活跃时间记录
        if user_id in self.last_active:
            del self.last_active[user_id]
        
        # 生成连接ID，用于日志追踪
        connection_id = f"online_status_{user_id}_{id(websocket)}" if websocket else "unknown"
        
        logger.info(f"[OnlineStatus] WebSocket连接已断开: 用户ID={user_id}, 连接ID={connection_id}, 当前连接总数={len(self.active_connections)}")
        
        # 向所有相关聊天室通知用户离线
        await self.broadcast_user_status_change(user_id, False)
    
    def update_user_active_time(self, user_id: int):
        """更新用户的最后活跃时间"""
        if user_id in self.active_connections:
            self.last_active[user_id] = datetime.now()
            if user_id in self.user_status:
                self.user_status[user_id]["last_active"] = datetime.now().isoformat()
    
    def add_user_to_room(self, user_id: int, room_id: int):
        """添加用户到聊天室"""
        # 初始化用户的聊天室集合
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        
        # 将聊天室添加到用户的聊天室集合
        self.user_rooms[user_id].add(room_id)
        
        # 初始化聊天室的用户集合
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        
        # 将用户添加到聊天室的成员集合
        self.room_members[room_id].add(user_id)
        
        logger.info(f"用户 {user_id} 加入聊天室 {room_id}, 该聊天室目前有 {len(self.room_members[room_id])} 个成员")
    
    def remove_user_from_room(self, user_id: int, room_id: int):
        """从聊天室中移除用户"""
        # 从用户的聊天室集合中移除
        if user_id in self.user_rooms and room_id in self.user_rooms[user_id]:
            self.user_rooms[user_id].remove(room_id)
        
        # 从聊天室的成员集合中移除
        if room_id in self.room_members and user_id in self.room_members[room_id]:
            self.room_members[room_id].remove(user_id)
            
        logger.info(f"用户 {user_id} 离开聊天室 {room_id}, 该聊天室剩余 {len(self.room_members.get(room_id, set()))} 个成员")
    
    async def broadcast_to_room(self, message: Dict[str, Any], room_id: int, exclude_user_id: Optional[int] = None):
        """向聊天室的所有在线成员广播消息"""
        if room_id not in self.room_members:
            return
            
        disconnected_users = []  # 记录发送失败的用户，可能是连接已断开
        sent_count = 0
        
        # 遍历聊天室成员
        for user_id in self.room_members[room_id]:
            # 排除指定用户
            if exclude_user_id is not None and user_id == exclude_user_id:
                continue
                
            # 只向在线用户发送消息
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].send_json(message)
                    self.update_user_active_time(user_id)  # 更新活跃时间
                    sent_count += 1
                    self.stats["messages_sent"] += 1
                except Exception as e:
                    logger.error(f"向用户 {user_id} 发送消息失败: {str(e)}")
                    # 将发送失败的用户添加到断开列表
                    disconnected_users.append(user_id)
                    self.stats["messages_failed"] += 1
        
        # 处理断开连接的用户
        for user_id in disconnected_users:
            await self.disconnect_user(user_id)
        
        return sent_count
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: int):
        """向特定用户发送私人消息"""
        if user_id not in self.active_connections:
            return False
            
        try:
            await self.active_connections[user_id].send_json(message)
            self.update_user_active_time(user_id)  # 更新活跃时间
            self.stats["messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"向用户 {user_id} 发送私人消息失败: {str(e)}")
            # 如果发送失败，断开连接
            await self.disconnect_user(user_id)
            self.stats["messages_failed"] += 1
            return False
    
    async def broadcast_user_status_change(self, user_id: int, is_online: bool):
        """向所有相关聊天室广播用户状态变化"""
        # 获取用户所在的所有聊天室
        user_room_ids = self.user_rooms.get(user_id, set())
        
        # 向每个聊天室广播状态变化
        for room_id in user_room_ids:
            status_message = {
                "type": "user_status",
                "room_id": room_id,
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": datetime.now().isoformat()
            }
            
            # 广播到聊天室（不排除自己，让用户自己也收到状态变化通知）
            await self.broadcast_to_room(status_message, room_id)
    
    def is_user_online(self, user_id: int) -> bool:
        """检查用户是否在线"""
        return user_id in self.active_connections
    
    def get_room_online_users(self, room_id: int) -> List[int]:
        """获取聊天室的在线用户ID列表"""
        if room_id not in self.room_members:
            return []
            
        return [user_id for user_id in self.room_members[room_id] 
                if self.is_user_online(user_id)]
    
    def get_room_online_count(self, room_id: int) -> int:
        """获取聊天室的在线用户数量"""
        return len(self.get_room_online_users(room_id))
    
    def get_total_online_users(self) -> int:
        """获取系统总在线用户数"""
        return len(self.active_connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取状态管理器的统计信息"""
        return {
            **self.stats,
            "current_online_users": self.get_total_online_users(),
            "rooms_count": len(self.room_members),
            "current_time": datetime.now().isoformat()
        }
    
    def is_user_in_room(self, user_id: int, room_id: int) -> bool:
        """检查用户是否在指定聊天室中"""
        return (user_id in self.user_rooms and 
                room_id in self.user_rooms[user_id])
    
    def sync_user_rooms(self, user_id: int, room_ids: List[int]):
        """同步用户的聊天室（从数据库）"""
        # 创建房间集合
        new_rooms = set(room_ids)
        
        # 获取当前用户的房间
        current_rooms = self.user_rooms.get(user_id, set())
        
        # 添加新房间
        for room_id in new_rooms:
            if room_id not in current_rooms:
                self.add_user_to_room(user_id, room_id)
        
        # 移除旧房间
        rooms_to_remove = current_rooms - new_rooms
        for room_id in rooms_to_remove:
            self.remove_user_from_room(user_id, room_id)
            
        logger.info(f"同步用户 {user_id} 的聊天室，现在加入了 {len(new_rooms)} 个聊天室")


# 创建全局在线状态管理器实例
online_status_manager = OnlineStatusManager() 