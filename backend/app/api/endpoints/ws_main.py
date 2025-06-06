"""
主WebSocket端點模組

提供整合的WebSocket連接處理，接收並分發消息到相應的處理器
"""
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging
import asyncio
import time
from starlette.websockets import WebSocketDisconnect as StarletteWebSocketDisconnect

from ...db.database import get_db
from ...db.models.chatroom import ChatRoom, ChatRoomMember, ChatRoomMessage
from ...core.security import verify_token_ws
from .chatroom import cleanup_messages
from ...core.main_ws_manager import websocket_manager  # 使用新的WebSocketManager
from ...core.chat_room_manager import chat_room_manager  # 使用新的ChatRoomManager
from ...core.online_status_manager import online_status_manager
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/main")
async def main_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="用戶驗證token"),
    db: Session = Depends(get_db)
):
    """
    單一主WebSocket連線，整合聊天、通知、在線狀態
    所有消息都需帶有 type 欄位
    """
    # 驗證Token
    user = await verify_token_ws(token, db)
    if not user:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "無效token"})
        await websocket.close(code=1008)
        return
    
    # 連接到WebSocketManager
    await websocket_manager.connect(user.id, websocket)
    logger.info(f"[WebSocket] 用戶 {user.id} 已建立WebSocket連線")
    
    # 更新在線狀態
    try:
        await online_status_manager.connect_user(websocket, user.id, already_accepted=True)
        logger.info(f"[WebSocket] 已更新用戶 {user.id} 的在線狀態")
    except Exception as e:
        logger.error(f"[WebSocket] 更新用戶在線狀態失敗: {str(e)}")

    # 初始化用戶的聊天室資料
    db_room_ids = (
        db.query(ChatRoomMember.room_id)
        .filter(ChatRoomMember.user_id == user.id)
        .all()
    )
    room_ids = [room[0] for room in db_room_ids]
    
    # 同步聊天室成員關係
    chat_room_manager.sync_user_rooms(user.id, room_ids)
    logger.debug(f"[WebSocket] 已同步用戶 {user.id} 的聊天室列表: {room_ids}")

    # 發送連線成功訊息
    await websocket.send_json({
        "type": "connected",
        "user_id": user.id,
        "room_ids": room_ids,
        "timestamp": datetime.now().isoformat()
    })

    # 追蹤最後活動時間
    last_activity_time = time.time()

    try:
        while True:
            try:
                data = await websocket.receive_text()
                # 更新最後活動時間
                current_time = time.time()
                time_since_last = current_time - last_activity_time
                last_activity_time = current_time
                
                # 如果超過30秒沒活動，記錄一下（但不斷開連接）
                if time_since_last > 30:
                    pass  # 可以添加DEBUG日誌
                
                message_data = json.loads(data)
                msg_type = message_data.get("type")

                # 處理心跳
                if msg_type == "ping":
                    logger.debug(f"PING - user:{user.id}")
                    # 更新在線狀態管理器中的最後活動時間
                    online_status_manager.update_user_active_time(user.id)
                    await websocket.send_json({
                        "type": "pong", 
                        "timestamp": datetime.now().isoformat()
                    })
                    continue
                elif msg_type == "pong":
                    logger.debug(f"PONG - user:{user.id}")
                    continue

                # 處理聊天訊息
                if msg_type == "chat/message":
                    room_id = int(message_data.get("room_id", 0))
                    content = message_data.get("content", "").strip()
                    logger.debug(f"[WebSocket] 接收到聊天消息: room_id={room_id}, content_length={len(content)}")
                    if not room_id or not content:
                        logger.warning(f"[WebSocket] 無效的聊天消息: room_id={room_id}, content_empty={not content}")
                        continue
                    
                    # 權限檢查
                    member = db.query(ChatRoomMember).filter(
                        ChatRoomMember.room_id == room_id,
                        ChatRoomMember.user_id == user.id
                    ).first()
                    if not member:
                        logger.warning(f"[WebSocket] 用戶 {user.id} 不是聊天室 {room_id} 成員，無法發送訊息")
                        await websocket.send_json({
                            "type": "chat/error",
                            "room_id": room_id,
                            "content": "您不是此聊天室成員，無法發送訊息",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    
                    # 寫入訊息
                    logger.debug(f"[WebSocket] 將用戶 {user.id} 的消息寫入聊天室 {room_id}")
                    new_message = ChatRoomMessage(
                        room_id=room_id,
                        user_id=user.id,
                        content=content,
                        is_system=False
                    )
                    db.add(new_message)
                    db.commit()
                    db.refresh(new_message)
                    await cleanup_messages(room_id, db)
                    
                    # 廣播消息到聊天室
                    broadcast_message = {
                        "type": "chat/message",
                        "message_id": new_message.id,
                        "room_id": room_id,
                        "user_id": user.id,
                        "username": user.username,
                        "avatar_url": user.avatar_url,
                        "content": new_message.content,
                        "timestamp": new_message.created_at.isoformat()
                    }
                    logger.debug(f"[WebSocket] 廣播消息到聊天室 {room_id}: {broadcast_message}")

                    # 使用ChatRoomManager廣播消息
                    sent_count = await chat_room_manager.broadcast_to_room(broadcast_message, room_id, exclude_user_id=None)
                    logger.debug(f"[WebSocket] 消息廣播完成，ID={new_message.id}, 聊天室={room_id}, 送達人數={sent_count}")
                    continue

                # 處理聊天室加入/離開
                if msg_type == "chat/join_room":
                    room_id = int(message_data.get("room_id", 0))
                    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
                    if not room:
                        await websocket.send_json({"type": "chat/error", "content": "聊天室不存在"})
                        continue
                    if not room.is_public and not user.is_admin:
                        await websocket.send_json({"type": "chat/error", "content": "該聊天室是私有的，需要邀請才能加入"})
                        continue
                    
                    existing_member = db.query(ChatRoomMember).filter(
                        ChatRoomMember.room_id == room_id,
                        ChatRoomMember.user_id == user.id
                    ).first()
                    
                    if not existing_member:
                        new_member = ChatRoomMember(room_id=room_id, user_id=user.id, is_admin=False)
                        db.add(new_member)
                        system_message = ChatRoomMessage(
                            room_id=room_id,
                            user_id=None,
                            content=f"{user.username} 加入了聊天室",
                            is_system=True
                        )
                        db.add(system_message)
                        db.commit()
                        await cleanup_messages(room_id, db)
                    
                    # 更新聊天室成員關係
                    chat_room_manager.add_user_to_room(user.id, room_id)
                    logger.debug(f"[WebSocket] 用戶 {user.id} 加入聊天室 {room_id}")
                    
                    # 廣播加入消息
                    join_message = {
                        "type": "chat/join",
                        "room_id": room_id,
                        "user_id": user.id,
                        "username": user.username,
                        "avatar_url": user.avatar_url,
                        "content": f"{user.username} 加入了聊天室",
                        "timestamp": datetime.now().isoformat()
                    }
                    await chat_room_manager.broadcast_to_room(join_message, room_id)
                    continue
                    
                if msg_type == "chat/leave_room":
                    room_id = int(message_data.get("room_id", 0))
                    member = db.query(ChatRoomMember).filter(
                        ChatRoomMember.room_id == room_id,
                        ChatRoomMember.user_id == user.id
                    ).first()
                    
                    if member:
                        db.delete(member)
                        system_message = ChatRoomMessage(
                            room_id=room_id,
                            user_id=None,
                            content=f"{user.username} 離開了聊天室",
                            is_system=True
                        )
                        db.add(system_message)
                        db.commit()
                        await cleanup_messages(room_id, db)
                        
                        # 更新聊天室成員關係
                        chat_room_manager.remove_user_from_room(user.id, room_id)
                        logger.debug(f"[WebSocket] 用戶 {user.id} 離開聊天室 {room_id}")
                        
                        # 廣播離開消息
                        leave_message = {
                            "type": "chat/leave",
                            "room_id": room_id,
                            "user_id": user.id,
                            "username": user.username,
                            "content": f"{user.username} 離開了聊天室",
                            "timestamp": datetime.now().isoformat()
                        }
                        await chat_room_manager.broadcast_to_room(leave_message, room_id)
                    continue

                # 處理通知
                if msg_type == "notification":
                    # 通知推播給自己
                    await websocket_manager.send_to_user(user.id, {
                        "type": "notification",
                        "content": message_data.get("content"),
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # 處理在線狀態
                if msg_type == "online/status":
                    # 在線狀態推播給全體
                    await websocket_manager.broadcast({
                        "type": "online_status",
                        "user_id": user.id,
                        "status": "online",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # 其他消息類型...

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"[WebSocket] 處理消息失敗: {str(e)}")
                break
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] 用戶 {user.id} 的WebSocket連接已斷開")
    except Exception as e:
        logger.error(f"[WebSocket] 連線處理失敗: {str(e)}")
    finally:
        # 清理連接
        websocket_manager.disconnect(user.id)
        
        # 更新在線狀態
        try:
            await online_status_manager.disconnect_user(user.id)
            logger.info(f"[WebSocket] 已更新用戶 {user.id} 的在線狀態（離線）")
        except Exception as e:
            logger.error(f"[WebSocket] 更新用戶在線狀態失敗: {str(e)}")
            
        # 廣播用戶狀態變更（離線）
        await broadcast_user_status_change(user.id, False, db)

# 輔助函數：廣播用戶狀態變更
async def broadcast_user_status_change(user_id: int, is_online: bool, db: Session):
    """
    廣播用戶在線狀態變更消息
    """
    try:
        # 獲取用戶所在的所有聊天室
        user_rooms = chat_room_manager.get_user_rooms(user_id)
        
        # 向每個聊天室廣播狀態變更消息
        for room_id in user_rooms:
            status_message = {
                "type": "user_status",
                "room_id": room_id,
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": datetime.now().isoformat()
            }
            await chat_room_manager.broadcast_to_room(status_message, room_id, exclude_user_id=user_id)
    except Exception as e:
        logger.error(f"廣播用戶狀態變更失敗: {str(e)}") 