from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging
import asyncio
import time

from ...db.database import get_db
from ...db.models.chatroom import ChatRoom, ChatRoomMember, ChatRoomMessage
from ...core.security import verify_token_ws
from .chatroom import cleanup_messages
from ...core.main_ws_manager import main_ws_manager
from ...core.online_status_manager import online_status_manager
from ...core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# 用於存儲用戶所在聊天室的字典，替代之前manager中的相關功能
user_rooms = {}

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
    
    # 連接到主WebSocket管理器
    await main_ws_manager.connect(user.id, websocket)
    logger.info(f"[MainWS] 用戶 {user.id} 已建立主WebSocket連線")
    
    # 同時更新在線狀態管理器
    try:
        await online_status_manager.connect_user(websocket, user.id, already_accepted=True)
        logger.info(f"[MainWS] 已同步更新在線狀態管理器，用戶 {user.id}")
    except Exception as e:
        logger.error(f"[MainWS] 更新在線狀態管理器失敗: {str(e)}")

    # 初始化用戶的聊天室資料
    db_room_ids = (
        db.query(ChatRoomMember.room_id)
        .filter(ChatRoomMember.user_id == user.id)
        .all()
    )
    room_ids = [room[0] for room in db_room_ids]
    
    # 更新用戶聊天室關聯字典
    user_rooms[user.id] = set(room_ids)
    logger.debug(f"[MainWS] 已更新用戶 {user.id} 的聊天室列表: {room_ids}")

    # 發送連線成功訊息
    await websocket.send_json({
        "type": "connected",
        "user_id": user.id,
        "room_ids": room_ids,
        "timestamp": datetime.now().isoformat()
    })

    # 追蹤最後活動時間（僅用於日誌記錄，不主動斷開）
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
                    # 刪除DEBUG日誌記錄
                    # logger.debug(f"[MainWS] 用戶 {user.id} 恢復活動，之前 {time_since_last:.1f} 秒無活動")
                    pass
                
                message_data = json.loads(data)
                msg_type = message_data.get("type")

                # 處理心跳
                if msg_type == "ping":
                    logger.debug(f"PING - user:{user.id}")
                    # 同時更新在線狀態管理器中的最後活動時間
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
                    logger.debug(f"[MainWS] 接收到聊天消息: room_id={room_id}, content_length={len(content)}")
                    if not room_id or not content:
                        logger.warning(f"[MainWS] 無效的聊天消息: room_id={room_id}, content_empty={not content}")
                        continue
                    
                    # 權限檢查
                    member = db.query(ChatRoomMember).filter(
                        ChatRoomMember.room_id == room_id,
                        ChatRoomMember.user_id == user.id
                    ).first()
                    if not member:
                        logger.warning(f"[MainWS] 用戶 {user.id} 不是聊天室 {room_id} 成員，無法發送訊息")
                        await websocket.send_json({
                            "type": "chat/error",
                            "room_id": room_id,
                            "content": "您不是此聊天室成員，無法發送訊息",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    
                    # 寫入訊息
                    logger.debug(f"[MainWS] 將用戶 {user.id} 的消息寫入聊天室 {room_id}")
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
                        "type": "chat/message",  # 使用 chat/message 類型
                        "message_id": new_message.id,
                        "room_id": room_id,
                        "user_id": user.id,
                        "username": user.username,
                        "avatar_url": user.avatar_url,
                        "content": new_message.content,
                        "timestamp": new_message.created_at.isoformat()
                    }
                    logger.debug(f"[MainWS] 廣播消息到聊天室 {room_id}: {broadcast_message}")

                    # 使用廣播聊天室消息函數
                    await broadcast_room_message(room_id, broadcast_message, db)
                    logger.debug(f"[MainWS] 消息廣播完成，ID={new_message.id}, 聊天室={room_id}")
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
                    
                    # 更新用戶-聊天室關聯
                    if user.id not in user_rooms:
                        user_rooms[user.id] = set()
                    user_rooms[user.id].add(room_id)
                    
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
                    await broadcast_room_message(room_id, join_message, db)
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
                        
                        # 更新用戶-聊天室關聯
                        if user.id in user_rooms and room_id in user_rooms[user.id]:
                            user_rooms[user.id].remove(room_id)
                        
                        # 廣播離開消息
                        leave_message = {
                            "type": "chat/leave",
                            "room_id": room_id,
                            "user_id": user.id,
                            "username": user.username,
                            "content": f"{user.username} 離開了聊天室",
                            "timestamp": datetime.now().isoformat()
                        }
                        await broadcast_room_message(room_id, leave_message, db)
                    continue

                # 處理通知
                if msg_type == "notification":
                    # 通知推播給自己（可根據 message_data 調整推播對象）
                    await main_ws_manager.send_to_user(user.id, {
                        "type": "notification",
                        "content": message_data.get("content"),
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # 處理在線狀態
                if msg_type == "online/status":
                    # 在線狀態推播給全體（可根據 message_data 調整推播對象）
                    await main_ws_manager.broadcast({
                        "type": "online_status",
                        "user_id": user.id,
                        "status": "online",
                        "timestamp": datetime.now().isoformat()
                    })
                    continue

                # 其他 type ...

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                logger.error(f"[MainWS] 處理消息失敗: {str(e)}")
                break
    except WebSocketDisconnect:
        logger.info(f"[MainWS] 用戶 {user.id} 的WebSocket連接已斷開")
    except Exception as e:
        logger.error(f"[MainWS] 連線處理失敗: {str(e)}")
    finally:
        # 清理連接
        main_ws_manager.disconnect(user.id)
        
        # 從用戶-聊天室關聯字典中移除用戶
        if user.id in user_rooms:
            del user_rooms[user.id]
        
        # 更新在線狀態系統
        try:
            await online_status_manager.disconnect_user(user.id)
            logger.info(f"[MainWS] 已同步更新在線狀態管理器（斷開連接），用戶 {user.id}")
        except Exception as e:
            logger.error(f"[MainWS] 更新在線狀態管理器（斷開連接）失敗: {str(e)}")
            
        # 廣播用戶狀態變更（離線）
        await broadcast_user_status_change(user.id, False, db)

# 輔助函數：廣播用戶狀態變更
async def broadcast_user_status_change(user_id: int, is_online: bool, db: Session):
    """
    廣播用戶在線狀態變更消息
    """
    try:
        # 獲取用戶所在的所有聊天室
        user_rooms_db = db.query(ChatRoomMember.room_id).filter(
            ChatRoomMember.user_id == user_id
        ).all()
        room_ids = [room[0] for room in user_rooms_db]
        
        # 向每個聊天室廣播狀態變更消息
        for room_id in room_ids:
            status_message = {
                "type": "user_status",
                "room_id": room_id,
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": datetime.now().isoformat()
            }
            await broadcast_room_message(room_id, status_message, db)
    except Exception as e:
        logger.error(f"廣播用戶狀態變更失敗: {str(e)}")

# 輔助函數：廣播消息到聊天室
async def broadcast_room_message(room_id: int, message: dict, db: Session):
    """
    廣播消息到聊天室的所有成員
    """
    try:
        # 獲取聊天室所有成員
        members = db.query(ChatRoomMember.user_id).filter(
            ChatRoomMember.room_id == room_id
        ).all()
        user_ids = [member[0] for member in members]
        
        # 向所有成員發送消息
        for user_id in user_ids:
            try:
                await main_ws_manager.send_to_user(user_id, message)
            except Exception as e:
                logger.error(f"向用戶 {user_id} 發送聊天室消息失敗: {str(e)}")
    except Exception as e:
        logger.error(f"廣播聊天室消息失敗: {str(e)}") 