"""
線上用戶狀態管理模組

該模組提供了用戶線上狀態的管理功能，包括：
1. 追蹤用戶的線上/離線狀態
2. 提供用戶在線狀態查詢功能
3. 自動清理斷開連接的WebSocket
4. 提供線上用戶統計功能
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

# 配置日誌
logger = logging.getLogger(__name__)

class OnlineStatusManager:
    """線上狀態管理器 - 負責管理用戶的線上狀態"""
    
    def __init__(self):
        # 存儲活躍的WebSocket連接: {user_id: websocket}
        self.active_connections: Dict[int, WebSocket] = {}
        # 用戶狀態記錄: {user_id: {online: bool, last_active: datetime, ...}}
        self.user_status: Dict[int, Dict[str, Any]] = {}
        # 用戶最後活躍時間
        self.last_active: Dict[int, datetime] = {}
        # 心跳超時時間（秒）- 延長為10分鐘
        self.heartbeat_timeout = 600  # 10分鐘
        # 清理任務
        self._cleanup_task = None
        # 統計資訊
        self.stats = {
            "total_connections": 0,
            "messages_sent": 0,
            "messages_failed": 0,
            "cleanup_count": 0
        }
        # 是否停用自動清理
        self.disable_auto_cleanup = False
    
    async def start(self):
        """啟動狀態管理器和定期清理任務"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("線上狀態管理器已啟動")
    
    async def shutdown(self):
        """關閉狀態管理器和清理任務"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 關閉所有連接
        for user_id in list(self.active_connections.keys()):
            try:
                await self.active_connections[user_id].close()
            except:
                pass
        self.active_connections.clear()
        logger.info("線上狀態管理器已關閉")
    
    async def _cleanup_loop(self):
        """定期檢查並清理不活躍的連接"""
        while True:
            try:
                # 如果設定了停用自動清理，則跳過
                if not self.disable_auto_cleanup:
                    await self._cleanup_inactive_connections()
                # 每分鐘檢查一次，但不一定執行清理
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"線上狀態清理任務出錯: {str(e)}")
                await asyncio.sleep(60)  # 出錯後等待1分鐘再試
    
    async def _cleanup_inactive_connections(self):
        """清理不活躍的連接"""
        current_time = datetime.now()
        inactive_users = []
        
        # 檢查所有用戶的最後活躍時間
        for user_id, last_active in list(self.last_active.items()):
            if (current_time - last_active).total_seconds() > self.heartbeat_timeout:
                inactive_users.append(user_id)
        
        # 清理不活躍的連接
        for user_id in inactive_users:
            logger.info(f"清理不活躍用戶: {user_id}, 超時未活動")
            await self.disconnect_user(user_id)
        
        if inactive_users:
            self.stats["cleanup_count"] += len(inactive_users)
            logger.info(f"清理了 {len(inactive_users)} 個不活躍連接")
    
    async def connect_user(self, websocket: WebSocket, user_id: int, already_accepted: bool = False):
        """用戶WebSocket連接處理"""
        # 只有當連接尚未被接受時才接受它
        if not already_accepted:
            try:
                await websocket.accept()
            except RuntimeError as e:
                # 如果出現運行時錯誤（例如連接已經被接受），記錄警告但繼續處理
                if "websocket.accept" in str(e):
                    logger.warning(f"WebSocket 可能已經被接受: {str(e)}")
                else:
                    # 如果是其他運行時錯誤，則重新引發
                    raise
        
        # 如果用戶已有連接，先關閉舊連接
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except:
                pass
        
        # 記錄新連接
        self.active_connections[user_id] = websocket
        self.last_active[user_id] = datetime.now()
        self.stats["total_connections"] += 1
        
        # 更新用戶狀態
        self.user_status[user_id] = {
            "online": True,
            "last_active": datetime.now().isoformat(),
            "connection_time": datetime.now().isoformat()
        }
        
        # 生成連接ID，用於日誌追蹤
        connection_id = f"online_status_{user_id}_{id(websocket)}"
        
        logger.info(f"[OnlineStatus] WebSocket連接已建立: 用戶ID={user_id}, 連接ID={connection_id}, 當前連接總數={len(self.active_connections)}")
    
    async def disconnect_user(self, user_id: int):
        """斷開用戶連接並更新狀態"""
        # 如果用戶線上，關閉WebSocket連接
        websocket = None
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await self.active_connections[user_id].close()
            except:
                pass
            del self.active_connections[user_id]
        
        # 更新用戶狀態
        if user_id in self.user_status:
            self.user_status[user_id]["online"] = False
            self.user_status[user_id]["last_disconnect"] = datetime.now().isoformat()
        
        # 清理最後活躍時間記錄
        if user_id in self.last_active:
            del self.last_active[user_id]
        
        # 生成連接ID，用於日誌追蹤
        connection_id = f"online_status_{user_id}_{id(websocket)}" if websocket else "unknown"
        
        logger.info(f"[OnlineStatus] WebSocket連接已斷開: 用戶ID={user_id}, 連接ID={connection_id}, 當前連接總數={len(self.active_connections)}")
    
    def update_user_active_time(self, user_id: int):
        """更新用戶的最後活躍時間"""
        if user_id in self.active_connections:
            self.last_active[user_id] = datetime.now()
            if user_id in self.user_status:
                self.user_status[user_id]["last_active"] = datetime.now().isoformat()
    
    async def send_personal_message(self, message: Dict[str, Any], user_id: int):
        """向特定用戶發送私人訊息"""
        if user_id not in self.active_connections:
            return False
            
        try:
            await self.active_connections[user_id].send_json(message)
            self.update_user_active_time(user_id)  # 更新活躍時間
            self.stats["messages_sent"] += 1
            return True
        except Exception as e:
            logger.error(f"向用戶 {user_id} 發送私人訊息失敗: {str(e)}")
            self.stats["messages_failed"] += 1
            # 發送失敗可能是連接已斷開，嘗試斷開連接
            await self.disconnect_user(user_id)
            return False
    
    def is_user_online(self, user_id: int) -> bool:
        """檢查用戶是否線上"""
        return user_id in self.active_connections
    
    def get_total_online_users(self) -> int:
        """獲取總線上用戶數量"""
        return len(self.active_connections)
    
    def get_all_online_users(self) -> List[int]:
        """獲取所有線上用戶的 ID 列表"""
        return list(self.active_connections.keys())
    
    def get_user_status(self, user_id: int) -> Dict[str, Any]:
        """獲取用戶的狀態資訊
        
        Args:
            user_id: 用戶 ID
            
        Returns:
            包含用戶狀態資訊的字典，如果用戶不存在則返回空字典
        """
        return self.user_status.get(user_id, {})
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取線上狀態管理器的統計資訊"""
        stats = self.stats.copy()
        stats.update({
            "current_connections": len(self.active_connections),
        })
        return stats

    def disable_auto_cleanup_feature(self, disable: bool = True):
        """
        啟用或禁用自動清理功能
        
        Args:
            disable: 是否禁用自動清理功能，默認為True（禁用）
        """
        self.disable_auto_cleanup = disable
        logger.info(f"自動清理功能已{'禁用' if disable else '啟用'}")
        return self.disable_auto_cleanup

# 創建全域實例
online_status_manager = OnlineStatusManager() 