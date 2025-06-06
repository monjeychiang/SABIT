from fastapi import APIRouter

from .endpoints import (
    users,
    auth,
    admin,
    tasks,
    search,
    chatroom,
    notifications,
    uploads,
    ws_main,
    events,
    account,
    gridbot
)

api_router = APIRouter()

# 註冊各模塊的路由器
api_router.include_router(auth.router, prefix="/auth", tags=["認證"])
api_router.include_router(users.router, prefix="/users", tags=["用戶"])
api_router.include_router(admin.router, prefix="/admin", tags=["管理"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["任務"])
api_router.include_router(search.router, prefix="/search", tags=["搜索"])
api_router.include_router(chatroom.router, prefix="/chatroom", tags=["聊天室"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["上傳"])
api_router.include_router(ws_main.router, prefix="/ws", tags=["WebSocket"])
api_router.include_router(events.router, prefix="/events", tags=["事件"])
api_router.include_router(account.router, prefix="/account", tags=["賬戶"])
api_router.include_router(gridbot.router, prefix="/trading", tags=["網格交易"]) 