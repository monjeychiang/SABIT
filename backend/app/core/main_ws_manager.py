"""
WebSocket連接管理模組

負責管理WebSocket連接的生命週期，但不處理業務邏輯
"""

import asyncio
from typing import Dict, Any, List, Optional, Set
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """WebSocket連接管理器 - 僅負責WebSocket連接的生命週期管理"""
    
    def __init__(self):
        # 存儲活躍的WebSocket連接: {user_id: websocket}
        self.active_connections: Dict[int, WebSocket] = {}
        # 統計信息
        self.stats = {
            "total_connections_handled": 0,
            "messages_sent": 0,
            "messages_failed": 0
        }

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """
        建立WebSocket連接
        
        Args:
            user_id: 用戶ID
            websocket: WebSocket對象
        """
        await websocket.accept()
        # 如果用戶已有連接，關閉舊連接
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
                logger.debug(f"[WebSocket] 關閉用戶 {user_id} 的舊連接")
            except Exception as e:
                logger.error(f"[WebSocket] 關閉舊連接失敗: {str(e)}")
        
        # 存儲新連接
        self.active_connections[user_id] = websocket
        self.stats["total_connections_handled"] += 1
        logger.info(f"[WebSocket] 用戶 {user_id} 已連接，當前活躍連接數: {len(self.active_connections)}")

    def disconnect(self, user_id: int) -> None:
        """
        斷開用戶的WebSocket連接（不關閉連接，僅從管理器中移除）
        
        Args:
            user_id: 用戶ID
        """
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"[WebSocket] 用戶 {user_id} 已從連接管理器移除，當前活躍連接數: {len(self.active_connections)}")

    async def close_connection(self, user_id: int) -> bool:
        """
        主動關閉用戶的WebSocket連接
        
        Args:
            user_id: 用戶ID
        
        Returns:
            bool: 是否成功關閉
        """
        if user_id not in self.active_connections:
            return False
            
        try:
            await self.active_connections[user_id].close()
            self.disconnect(user_id)
            return True
        except Exception as e:
            logger.error(f"[WebSocket] 關閉用戶 {user_id} 的連接失敗: {str(e)}")
            # 即使發生錯誤，也從管理器中移除
            self.disconnect(user_id)
            return False

    async def send_to_user(self, user_id: int, message: Dict[str, Any]) -> bool:
        """
        向特定用戶發送消息
        
        Args:
            user_id: 用戶ID
            message: 要發送的消息
            
        Returns:
            bool: 是否成功發送
        """
        if user_id not in self.active_connections:
            logger.warning(f"[WebSocket] 嘗試發送消息到不存在的連接, 用戶ID: {user_id}")
            return False
            
        try:
            await self.active_connections[user_id].send_json(message)
            self.stats["messages_sent"] += 1
            logger.debug(f"[WebSocket] 成功發送消息給用戶 {user_id}: 類型={message.get('type', 'unknown')}")
            return True
        except WebSocketDisconnect:
            logger.debug(f"[WebSocket] 用戶 {user_id} 已斷開連接，無法發送消息")
            self.disconnect(user_id)
            self.stats["messages_failed"] += 1
            raise
        except Exception as e:
            logger.error(f"[WebSocket] 向用戶 {user_id} 發送消息失敗: {str(e)}")
            self.disconnect(user_id)
            self.stats["messages_failed"] += 1
            return False

    async def broadcast(self, message: Dict[str, Any], exclude_user_ids: Optional[List[int]] = None) -> int:
        """
        向所有連接的用戶廣播消息
        
        Args:
            message: 要廣播的消息
            exclude_user_ids: 要排除的用戶ID列表
            
        Returns:
            int: 成功發送的消息數
        """
        if exclude_user_ids is None:
            exclude_user_ids = []
            
        logger.debug(f"[WebSocket] 廣播消息給所有用戶: 類型={message.get('type', 'unknown')}, 活躍連接數={len(self.active_connections)}")
        
        sent_count = 0
        user_ids = list(self.active_connections.keys())
        
        for user_id in user_ids:
            if user_id in exclude_user_ids:
                continue
                
            try:
                success = await self.send_to_user(user_id, message)
                if success:
                    sent_count += 1
            except WebSocketDisconnect:
                pass  # 已在 send_to_user 中處理
                
        return sent_count

    def is_user_connected(self, user_id: int) -> bool:
        """
        檢查用戶是否連接
        
        Args:
            user_id: 用戶ID
            
        Returns:
            bool: 用戶是否已連接
        """
        return user_id in self.active_connections

    def get_connected_users(self) -> List[int]:
        """
        獲取所有已連接的用戶ID列表
        
        Returns:
            List[int]: 已連接的用戶ID列表
        """
        return list(self.active_connections.keys())

    def get_connection_count(self) -> int:
        """
        獲取當前活躍連接數
        
        Returns:
            int: 活躍連接數
        """
        return len(self.active_connections)

    def get_stats(self) -> Dict[str, Any]:
        """
        獲取連接管理器的統計信息
        
        Returns:
            Dict[str, Any]: 統計信息
        """
        stats = self.stats.copy()
        stats["active_connections"] = len(self.active_connections)
        return stats

# 創建全局實例
websocket_manager = WebSocketManager()

# 兼容性別名，讓舊代碼仍然可以導入 main_ws_manager
main_ws_manager = websocket_manager 