"""
聊天室管理模組

負責聊天室成員關係管理和消息分發，不處理WebSocket連接本身
"""

import asyncio
import logging
from typing import Dict, Set, List, Optional, Any
from datetime import datetime

from .main_ws_manager import websocket_manager

logger = logging.getLogger(__name__)

class ChatRoomManager:
    """
    聊天室管理器 - 專門負責聊天室成員關係和消息分發
    
    負責維護聊天室成員關係，並協調WebSocketManager
    將消息分發給聊天室成員。
    """
    
    def __init__(self):
        # 聊天室成員: {room_id: set(user_id)}
        self.room_members: Dict[int, Set[int]] = {}
        # 用戶加入的聊天室: {user_id: set(room_id)}
        self.user_rooms: Dict[int, Set[int]] = {}
        # 聊天室統計
        self.room_message_counts: Dict[int, int] = {}
        # 聊天室最大成員數限制
        self.max_members_per_room = 1000
        
        logger.info(f"聊天室管理器已初始化，每個聊天室最大成員數: {self.max_members_per_room}")
    
    def room_exists(self, room_id: int) -> bool:
        """
        檢查聊天室是否存在
        
        Args:
            room_id: 聊天室ID
            
        Returns:
            bool: 聊天室是否存在
        """
        return room_id in self.room_members

    def get_room_member_count(self, room_id: int) -> int:
        """
        獲取聊天室成員總數
        
        Args:
            room_id: 聊天室ID
            
        Returns:
            int: 聊天室成員總數
        """
        if not self.room_exists(room_id):
            return 0
        return len(self.room_members[room_id])

    def get_room_online_count(self, room_id: int) -> int:
        """
        獲取聊天室在線成員數
        
        Args:
            room_id: 聊天室ID
            
        Returns:
            int: 聊天室在線成員數
        """
        if not self.room_exists(room_id):
            return 0
        
        # 獲取聊天室所有成員
        all_members = self.room_members[room_id]
        
        # 檢查每個成員是否在線
        online_count = 0
        for user_id in all_members:
            if websocket_manager.is_user_connected(user_id):
                online_count += 1
        
        return online_count

    def get_room_members(self, room_id: int) -> List[int]:
        """
        獲取聊天室所有成員ID
        
        Args:
            room_id: 聊天室ID
            
        Returns:
            List[int]: 成員ID列表
        """
        if not self.room_exists(room_id):
            return []
        return list(self.room_members[room_id])

    def get_room_online_members(self, room_id: int) -> List[int]:
        """
        獲取聊天室在線成員ID
        
        Args:
            room_id: 聊天室ID
            
        Returns:
            List[int]: 在線成員ID列表
        """
        if not self.room_exists(room_id):
            return []
        
        # 獲取聊天室所有成員
        all_members = self.room_members[room_id]
        
        # 過濾出在線成員
        online_members = []
        for user_id in all_members:
            if websocket_manager.is_user_connected(user_id):
                online_members.append(user_id)
        
        return online_members

    def add_user_to_room(self, user_id: int, room_id: int) -> bool:
        """
        將用戶添加到聊天室
        
        Args:
            user_id: 用戶ID
            room_id: 聊天室ID
            
        Returns:
            bool: 是否成功添加
        """
        # 檢查聊天室成員數是否超過限制
        if room_id in self.room_members and len(self.room_members[room_id]) >= self.max_members_per_room:
            logger.warning(f"聊天室 {room_id} 成員數已達上限 ({self.max_members_per_room})")
            return False
        
        # 初始化聊天室成員集合
        if room_id not in self.room_members:
            self.room_members[room_id] = set()
        
        # 初始化用戶聊天室集合
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = set()
        
        # 添加關聯關係
        self.room_members[room_id].add(user_id)
        self.user_rooms[user_id].add(room_id)
        
        logger.info(f"用戶 {user_id} 已加入聊天室 {room_id}, 當前成員數: {len(self.room_members[room_id])}")
        return True

    def remove_user_from_room(self, user_id: int, room_id: int) -> bool:
        """
        從聊天室移除用戶
        
        Args:
            user_id: 用戶ID
            room_id: 聊天室ID
            
        Returns:
            bool: 是否成功移除
        """
        # 檢查聊天室和用戶是否存在
        if room_id not in self.room_members or user_id not in self.room_members[room_id]:
            return False
        
        # 移除關聯關係
        self.room_members[room_id].remove(user_id)
        
        # 如果聊天室沒有成員，刪除聊天室
        if not self.room_members[room_id]:
            del self.room_members[room_id]
            if room_id in self.room_message_counts:
                del self.room_message_counts[room_id]
        
        # 更新用戶的聊天室集合
        if user_id in self.user_rooms:
            self.user_rooms[user_id].discard(room_id)
            # 如果用戶沒有加入任何聊天室，刪除用戶條目
            if not self.user_rooms[user_id]:
                del self.user_rooms[user_id]
        
        logger.info(f"用戶 {user_id} 已離開聊天室 {room_id}")
        return True

    def sync_user_rooms(self, user_id: int, room_ids: List[int]) -> None:
        """
        同步用戶的聊天室列表
        
        Args:
            user_id: 用戶ID
            room_ids: 聊天室ID列表
        """
        # 獲取用戶當前的聊天室列表
        current_rooms = self.get_user_rooms(user_id)
        
        # 需要添加的聊天室
        rooms_to_add = [room_id for room_id in room_ids if room_id not in current_rooms]
        
        # 需要移除的聊天室
        rooms_to_remove = [room_id for room_id in current_rooms if room_id not in room_ids]
        
        # 添加新聊天室
        for room_id in rooms_to_add:
            self.add_user_to_room(user_id, room_id)
        
        # 移除舊聊天室
        for room_id in rooms_to_remove:
            self.remove_user_from_room(user_id, room_id)
        
        logger.info(f"已同步用戶 {user_id} 的聊天室列表, 添加: {len(rooms_to_add)}, 移除: {len(rooms_to_remove)}")

    def get_user_rooms(self, user_id: int) -> List[int]:
        """
        獲取用戶加入的所有聊天室ID
        
        Args:
            user_id: 用戶ID
            
        Returns:
            List[int]: 聊天室ID列表
        """
        if user_id not in self.user_rooms:
            return []
        return list(self.user_rooms[user_id])

    def is_user_in_room(self, user_id: int, room_id: int) -> bool:
        """
        檢查用戶是否在聊天室中
        
        Args:
            user_id: 用戶ID
            room_id: 聊天室ID
            
        Returns:
            bool: 用戶是否在聊天室中
        """
        if room_id not in self.room_members:
            return False
        return user_id in self.room_members[room_id]

    async def broadcast_to_room(self, message: Dict[str, Any], room_id: int, exclude_user_id: Optional[int] = None) -> int:
        """
        向聊天室廣播消息
        
        Args:
            message: 消息
            room_id: 聊天室ID
            exclude_user_id: 要排除的用戶ID
            
        Returns:
            int: 成功發送的消息數
        """
        if not self.room_exists(room_id):
            logger.warning(f"嘗試向不存在的聊天室 {room_id} 廣播消息")
            return 0
        
        # 獲取聊天室成員
        room_members = self.get_room_members(room_id)
        
        # 排除指定用戶
        if exclude_user_id is not None and exclude_user_id in room_members:
            room_members.remove(exclude_user_id)
        
        # 如果沒有成員，直接返回
        if not room_members:
            return 0
        
        # 發送計數
        sent_count = 0
        
        # 向每個成員發送消息
        for user_id in room_members:
            try:
                # 只向在線用戶發送
                if websocket_manager.is_user_connected(user_id):
                    success = await websocket_manager.send_to_user(user_id, message)
                    if success:
                        sent_count += 1
            except Exception as e:
                logger.error(f"向用戶 {user_id} 發送聊天室消息失敗: {str(e)}")
        
        # 更新消息計數
        self.room_message_counts[room_id] = self.room_message_counts.get(room_id, 0) + 1
        
        logger.debug(f"向聊天室 {room_id} 廣播消息, 成功發送 {sent_count}/{len(room_members)} 條")
        return sent_count

    def get_active_rooms(self) -> List[int]:
        """
        獲取所有活躍的聊天室ID
        
        Returns:
            List[int]: 聊天室ID列表
        """
        return list(self.room_members.keys())

    def get_stats(self) -> Dict[str, Any]:
        """
        獲取聊天室管理器的統計信息
        
        Returns:
            Dict[str, Any]: 統計信息
        """
        active_rooms = self.get_active_rooms()
        
        # 計算在線用戶數
        online_users_by_room = {}
        for room_id in active_rooms:
            online_users_by_room[room_id] = self.get_room_online_count(room_id)
        
        stats = {
            "active_rooms": len(active_rooms),
            "total_room_users": sum(len(members) for members in self.room_members.values()),
            "total_unique_users": len(self.user_rooms),
            "room_details": {
                str(room_id): {
                    "total_members": len(self.room_members[room_id]),
                    "online_members": online_users_by_room.get(room_id, 0),
                    "messages": self.room_message_counts.get(room_id, 0)
                } for room_id in active_rooms
            }
        }
        return stats

# 創建全局實例
chat_room_manager = ChatRoomManager() 