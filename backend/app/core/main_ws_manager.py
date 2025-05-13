import asyncio
from typing import Dict, Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class MainWSManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(message)
                logger.debug(f"[MainWS] 成功發送消息到用戶 {user_id}: 類型={message.get('type')}")
            except Exception as e:
                logger.error(f"[MainWS] 向用戶 {user_id} 發送消息失敗: {str(e)}")
                self.disconnect(user_id)
        else:
            logger.warning(f"[MainWS] 嘗試發送消息到不存在的連接, 用戶ID: {user_id}")

    async def broadcast(self, message: Dict[str, Any]):
        logger.debug(f"[MainWS] 廣播消息給所有用戶: 類型={message.get('type')}, 活動連接數={len(self.active_connections)}")
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)

main_ws_manager = MainWSManager() 