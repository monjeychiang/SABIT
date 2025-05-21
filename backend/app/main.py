import os
import uvicorn
import logging
import sys
import pytz
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, File, UploadFile, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import time
# 添加靜態文件支援
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from contextlib import asynccontextmanager
import json
import asyncio
from starlette.middleware.base import BaseHTTPMiddleware

# 設置標準時間
os.environ['TZ'] = 'Asia/Taipei'
TAIPEI_TZ = pytz.timezone('Asia/Taipei')

# 載入環境變數
load_dotenv()

# 添加當前目錄到Python路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_dir))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# 確保日誌目錄存在
logs_dir = os.path.join(os.path.dirname(current_dir), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# 確保靜態文件目錄存在
static_dir = os.path.join(os.path.dirname(current_dir), 'static')
os.makedirs(static_dir, exist_ok=True)

# 配置日誌 - 解決中文編碼問題
logging.basicConfig(
    level=logging.DEBUG,  # 改為DEBUG級別，記錄更多日誌資訊
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(logs_dir, f'app_{datetime.now(TAIPEI_TZ).strftime("%Y%m%d")}.log'),
            encoding='utf-8'  # 指定utf-8編碼
        ),
        logging.StreamHandler(sys.stdout)  # 同時輸出到控制台
    ]
)

# 設置第三方庫的日誌級別
logging.getLogger('multipart').setLevel(logging.INFO)  # 降低multipart模組的日誌級別，減少輸出
logging.getLogger('uvicorn').setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.info(f"應用啟動於：{datetime.now(TAIPEI_TZ)}...")

# 導入必要的模組
from app.api.endpoints import auth, admin, notifications, settings, markets, chat, chatroom
# 新增: 導入線上狀態API
from app.api.endpoints import online_status
from app.db.database import engine, Base, create_tables

# 添加系統狀態API模組
from app.api.endpoints import system

# 在合適的位置添加以下導入和配置
from .api.endpoints import users as users_router

# 簡單的記憶體速率限制器
class RateLimiter:
    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit  # 時間窗口內允許的最大請求數
        self.window_seconds = window_seconds  # 時間窗口大小（秒）
        self.client_requests: Dict[str, list] = {}  # 記錄客戶端請求歷史
    
    def is_rate_limited(self, client_ip: str) -> Tuple[bool, int]:
        """
        檢查客戶端是否達到速率限制
        返回 (是否受限, 剩餘秒數)
        """
        current_time = time.time()
        
        # 如果是新客戶端，初始化記錄
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = []
        
        # 清理過期的請求記錄
        self.client_requests[client_ip] = [
            req_time for req_time in self.client_requests[client_ip]
            if current_time - req_time < self.window_seconds
        ]
        
        # 檢查是否超過限制
        if len(self.client_requests[client_ip]) >= self.requests_limit:
            oldest_request = min(self.client_requests[client_ip])
            time_to_reset = int(self.window_seconds - (current_time - oldest_request))
            return True, max(0, time_to_reset)
        
        # 記錄本次請求
        self.client_requests[client_ip].append(current_time)
        return False, 0

# 創建速率限制器實例
ping_rate_limiter = RateLimiter(requests_limit=20, window_seconds=60)  # 每分鐘限制20次，允許完成一次15秒的網絡測試

# 應用啟動和關閉事件
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 應用啟動前執行的代碼
    logger.info("應用啟動中...")
    # 在这里可以进行数据库初始化等操作
    yield
    # 應用關閉時執行的代碼
    logger.info("應用關閉中...")
    # 在这里可以进行资源清理等操作

# 創建 FastAPI 應用
app = FastAPI(
    title="Trading Platform API",
    description="加密貨幣交易平台API",
    version="1.0.0",
    lifespan=lifespan
)

# 添加靜態文件服務
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 設置favicon路由 - 直接從靜態目錄提供favicon
@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    favicon_path = os.path.join(static_dir, "favicon.ico")
    # 如果文件不存在，則從前端目錄複製
    if not os.path.exists(favicon_path):
        try:
            import shutil
            frontend_favicon = os.path.join(root_dir, 'frontend', 'public', 'favicon.ico')
            if os.path.exists(frontend_favicon):
                shutil.copy(frontend_favicon, favicon_path)
                logger.info(f"已從前端複製favicon.ico到靜態目錄: {favicon_path}")
        except Exception as e:
            logger.error(f"複製favicon.ico時出錯: {str(e)}")
    
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    
    # 如果文件仍然不存在，返回404
    raise HTTPException(status_code=404, detail="Favicon not found")

# CORS 配置
origins = [
    "http://localhost:5175",  # Vite 開發服務器
    "http://127.0.0.1:5175",
    os.getenv("FRONTEND_URL", "http://localhost:5175")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# 自定義中間件，用於跳過 WebSocket 請求的身份驗證
class CustomAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # WebSocket 連接請求不執行身份驗證檢查
        path = request.url.path
        if path.startswith('/ws/') or path.startswith('/test-websocket') or (path.startswith('/account/') and 'websocket' in path):
            logger.debug(f"跳過 WebSocket 路由的身份驗證檢查: {path}")
            response = await call_next(request)
            return response
        
        # 對於其他請求，執行常規處理
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

# 添加自定義中間件（確保在其他身份驗證中間件之前）
app.add_middleware(CustomAuthMiddleware)

# 請求計時中間件
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# 健康檢查端點
@app.get("/health")
async def health_check():
    taipei_time = datetime.now(TAIPEI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"健康檢查請求 - 時間: {taipei_time}")
    return {"status": "healthy", "time": taipei_time, "environment": os.getenv("ENVIRONMENT", "development")}

# 輕量級Ping端點，用於客戶端測量API延遲
@app.get("/api/v1/ping")
async def api_ping(request: Request):
    """
    輕量級Ping端點，用於測量API延遲
    """
    # 獲取客戶端IP地址
    client_ip = request.client.host if request.client else "unknown"
    
    # 檢查是否超過速率限制
    is_limited, reset_time = ping_rate_limiter.is_rate_limited(client_ip)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail=f"速率限制已超過。請在 {reset_time} 秒後重試。",
            headers={"Retry-After": str(reset_time)}
        )
    
    # 返回最小化的響應以提高性能
    return {"timestamp": int(datetime.now().timestamp() * 1000)}

# 註冊路由 - 確保所有API路由都被包含
app.include_router(auth.router, prefix="/api/v1/auth", tags=["認證"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["管理員"])  # 註冊管理員API路由
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["通知"])  # 註冊通知API路由
app.include_router(settings.router, prefix="/api/v1", tags=["設置"])  # 註冊設置API路由
app.include_router(markets.router, prefix="/api/v1/markets", tags=["市場"])  # 註冊市場API路由
app.include_router(system.router, prefix="/api/v1/system", tags=["系統"])  # 註冊系統狀態API路由
app.include_router(chat.router, prefix="/api/v1/chat", tags=["聊天"])  # 註冊Gemini聊天API路由
app.include_router(chatroom.router, prefix="/api/v1/chatroom", tags=["聊天室"])  # 註冊聊天室API路由（已整合WebSocket功能）
# 新增: 註冊線上狀態API路由
app.include_router(online_status.router, prefix="/api/v1/online", tags=["線上狀態"])  # 註冊線上狀態API路由

# 新增: 導入和註冊主要WebSocket路由 (不加前綴，從根路徑訪問)
from app.api.endpoints import ws_main
app.include_router(ws_main.router, tags=["WebSocket"])  # 註冊主要WebSocket路由，從根路徑訪問

# 導入和註冊交易API路由
#from app.api.endpoints import trading
#app.include_router(trading.router, prefix="/api/v1/trading", tags=["交易"])  # 註冊交易API路由

# 包含用戶活躍狀態API路由
app.include_router(
    users_router.router,
    prefix="/api/v1/users",
    tags=["users"]
)

# 創建數據庫表（使用database.py中的create_tables函數，而不是直接調用Base.metadata.create_all）
create_tables()
logger.info("數據庫表創建完成")

@app.on_event("startup")
async def startup_event():
    """
    應用程式啟動時的初始化操作
    """
    # 確保日誌目錄存在
    if not os.path.exists("logs"):
        os.makedirs("logs")
    
    # 初始化在線狀態管理器
    from app.core.online_status_manager import online_status_manager
    await online_status_manager.start()
    
    # 啟用自動清理功能，因前端 ping 已能正確更新活動時間
    # online_status_manager.disable_auto_cleanup_feature(True)
    logger.info("在線狀態管理器已啟動，自動清理功能已啟用")
    
    # 初始化WebSocket管理器
    try:
        node_id = settings.NODE_ID
        from app.core.websocket_redis import init_redis_ws_manager
        if settings.REDIS_ENABLED:
            ws_manager = await init_redis_ws_manager(node_id)
            if ws_manager:
                logger.info(f"Redis WebSocket管理器初始化成功，節點ID: {node_id}")
            else:
                logger.warning("Redis WebSocket管理器初始化失敗，將使用本地管理器")
    except Exception as e:
        logger.error(f"初始化Redis WebSocket管理器時出錯: {str(e)}")
        logger.info("將使用本地WebSocket管理器")
    
    # 注意：暫時移除了掛單管理器和市場數據管理器的啟動代碼
    # 因為這些模組目前尚未實現
    logger.info("應用程式啟動完成")

@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉事件處理"""
    logger.info("應用正在關閉...")
    
    # 關閉線上狀態管理器
    try:
        from app.core.online_status_manager import online_status_manager
        logger.info("正在關閉線上狀態管理器...")
        await online_status_manager.shutdown()
        logger.info("線上狀態管理器已關閉")
    except Exception as e:
        logger.error(f"關閉線上狀態管理器時出錯: {str(e)}")
    
    logger.info("應用已完全關閉")

# 在其他路由註冊之後添加
# 直接導入 WebSocket 路由
from .api.endpoints import account, ws_main

# 註冊額外的路由（不在api_router中的）
app.include_router(account.router)
app.include_router(ws_main.router)

# 添加一個測試路由
@app.get("/test")
async def test_endpoint():
    """測試伺服器是否運行正常"""
    return {"status": "ok", "message": "Server is running"}

# 增加一個測試中間件狀態的路由
@app.get("/debug/middleware")
async def debug_middleware():
    """顯示中間件和路由信息，用於調試"""
    middleware_list = [str(m.__class__.__name__) for m in app.user_middleware]
    routes = [{"path": route.path, "name": route.name} for route in app.routes]
    return {
        "middleware": middleware_list,
        "routes": routes,
        "websocket_routes": [
            r.path for r in app.routes if r.path.startswith('/ws') 
            or r.path.startswith('/test-websocket')
            or (r.path.startswith('/account') and 'websocket' in str(r))
        ]
    }

if __name__ == '__main__':
    # 啟動伺服器
    config = uvicorn.Config(
        app="app.main:app",
        host='127.0.0.1',
        port=8000,
        reload=True,
        log_level="debug"  # 改為debug級別
    )
    server = uvicorn.Server(config)
    server.run() 