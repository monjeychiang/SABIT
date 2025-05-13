import os
import uvicorn
import logging
import sys
import pytz
from typing import Dict, Any, Tuple
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from sqlalchemy.orm import Session
import time
# 添加靜態文件支持
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# 设置标准时间
os.environ['TZ'] = 'Asia/Shanghai'
CHINA_TZ = pytz.timezone('Asia/Shanghai')

# 加載環境變量
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

# 配置日誌 - 解决中文编码问题
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别，记录更多日志信息
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            os.path.join(logs_dir, f'app_{datetime.now(CHINA_TZ).strftime("%Y%m%d")}.log'),
            encoding='utf-8'  # 指定utf-8编码
        ),
        logging.StreamHandler(sys.stdout)  # 同时输出到控制台
    ]
)

# 设置第三方库的日志级别
logging.getLogger('multipart').setLevel(logging.INFO)  # 降低multipart模块的日志级别，减少输出
logging.getLogger('uvicorn').setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.info(f"应用启动于：{datetime.now(CHINA_TZ)}...")

# 導入必要的模塊
from app.api.endpoints import auth, admin, notifications, settings, markets, chat, chatroom
# 新增: 导入在线状态API
from app.api.endpoints import online_status
from app.db.database import engine, Base, create_tables

# 添加系统状态API模块
from app.api.endpoints import system

# 在合适的位置添加以下导入和配置
from .middlewares.activity_tracker import ActivityTrackerMiddleware, active_session_store
from .api.endpoints import users as users_router

# 简单的内存速率限制器
class RateLimiter:
    def __init__(self, requests_limit: int = 10, window_seconds: int = 60):
        self.requests_limit = requests_limit  # 时间窗口内允许的最大请求数
        self.window_seconds = window_seconds  # 时间窗口大小（秒）
        self.client_requests: Dict[str, list] = {}  # 记录客户端请求历史
    
    def is_rate_limited(self, client_ip: str) -> Tuple[bool, int]:
        """
        检查客户端是否达到速率限制
        返回 (是否受限, 剩余秒数)
        """
        current_time = time.time()
        
        # 如果是新客户端，初始化记录
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = []
        
        # 清理过期的请求记录
        self.client_requests[client_ip] = [
            req_time for req_time in self.client_requests[client_ip]
            if current_time - req_time < self.window_seconds
        ]
        
        # 检查是否超过限制
        if len(self.client_requests[client_ip]) >= self.requests_limit:
            oldest_request = min(self.client_requests[client_ip])
            time_to_reset = int(self.window_seconds - (current_time - oldest_request))
            return True, max(0, time_to_reset)
        
        # 记录本次请求
        self.client_requests[client_ip].append(current_time)
        return False, 0

# 创建速率限制器实例
ping_rate_limiter = RateLimiter(requests_limit=20, window_seconds=60)  # 每分钟限制20次，允许完成一次15秒的网络测试

# 創建 FastAPI 應用
app = FastAPI(
    title="Trading Platform API",
    description="加密货币交易平台API",
    version="1.0.0"
)

# 添加靜態文件服務
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 設置favicon路由 - 直接從靜態目錄提供favicon
@app.get("/favicon.ico", include_in_schema=False)
async def get_favicon():
    from fastapi.responses import FileResponse
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

# 健康檢查端點
@app.get("/health")
async def health_check():
    china_time = datetime.now(CHINA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"健康检查请求 - 时间: {china_time}")
    return {"status": "healthy", "time": china_time, "environment": os.getenv("ENVIRONMENT", "development")}

# 轻量级Ping端点，用于客户端测量API延迟
@app.get("/api/v1/ping")
async def api_ping(request: Request):
    """
    轻量级Ping端点，用于测量API延迟
    """
    # 获取客户端IP地址
    client_ip = request.client.host if request.client else "unknown"
    
    # 检查是否超过速率限制
    is_limited, reset_time = ping_rate_limiter.is_rate_limited(client_ip)
    if is_limited:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {reset_time} seconds.",
            headers={"Retry-After": str(reset_time)}
        )
    
    # 返回最小化的响应以提高性能
    return {"timestamp": int(datetime.now().timestamp() * 1000)}

# 注册路由 - 确保所有API路由都被包含
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["管理员"])  # 註冊管理員API路由
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["通知"])  # 注册通知API路由
app.include_router(settings.router, prefix="/api/v1", tags=["设置"])  # 注册设置API路由
app.include_router(markets.router, prefix="/api/v1/markets", tags=["市场"])  # 注册市场API路由
app.include_router(system.router, prefix="/api/v1/system", tags=["系统"])  # 注册系统状态API路由
app.include_router(chat.router, prefix="/api/v1/chat", tags=["聊天"])  # 注册Gemini聊天API路由
app.include_router(chatroom.router, prefix="/api/v1/chatroom", tags=["聊天室"])  # 注册聊天室API路由
# 新增: 注册在线状态API路由
app.include_router(online_status.router, prefix="/api/v1/online", tags=["在线状态"])  # 注册在线状态API路由

# 新增: 導入和註冊主要WebSocket路由 (不加前綴，從根路徑訪問)
from app.api.endpoints import ws_main
app.include_router(ws_main.router, tags=["WebSocket"])  # 註冊主要WebSocket路由，從根路徑訪問

# 导入和注册交易API路由
#from app.api.endpoints import trading
#app.include_router(trading.router, prefix="/api/v1/trading", tags=["交易"])  # 注册交易API路由

# 包含用户活跃状态API路由
app.include_router(
    users_router.router,
    prefix="/api/v1/users",
    tags=["users"]
)

# 添加活跃跟踪中间件（在其他中间件之后添加）
app.add_middleware(ActivityTrackerMiddleware)

# 创建数据库表（使用database.py中的create_tables函数，而不是直接调用Base.metadata.create_all）
create_tables()
logger.info("数据库表创建完成")

@app.on_event("startup")
async def startup_event():
    # 检查服务器时间是否同步
    try:
        import ntplib
        import time
        from datetime import datetime
        
        logger.info("检查服务器时间同步状态...")
        
        # 创建NTP客户端
        client = ntplib.NTPClient()
        
        # 使用多个NTP服务器以提高可靠性
        ntp_servers = [
            'time.windows.com',
            'time.google.com',
            'pool.ntp.org'
        ]
        
        # 尝试连接每个NTP服务器，直到成功
        for server in ntp_servers:
            try:
                logger.info(f"尝试连接NTP服务器: {server}")
                response = client.request(server, timeout=3)
                
                # 获取网络时间与本地时间的差异（秒）
                offset = response.offset
                ntp_time = datetime.fromtimestamp(response.tx_time)
                local_time = datetime.now()
                
                logger.info(f"NTP服务器: {server}")
                logger.info(f"NTP时间: {ntp_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
                logger.info(f"本地时间: {local_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
                logger.info(f"时间差异: {offset:.3f} 秒")
                
                if abs(offset) > 2:
                    logger.warning("=" * 60)
                    logger.warning(f"⚠️ 警告: 服务器时间与标准时间不同步!")
                    logger.warning(f"⚠️ 时间差异为 {offset:.2f} 秒!")
                    logger.warning(f"⚠️ 这可能会导致OAuth认证问题和JWT令牌验证失败!")
                    logger.warning(f"⚠️ 建议同步服务器时间后再使用OAuth功能!")
                    logger.warning("=" * 60)
                elif abs(offset) > 1:
                    logger.warning(f"服务器时间与标准时间存在轻微差异，差异为 {offset:.2f} 秒。")
                else:
                    logger.info(f"✅ 服务器时间同步正常，与标准时间的差异为 {offset:.2f} 秒。")
                
                # 成功获取时间信息后跳出循环
                break
                
            except Exception as e:
                logger.warning(f"连接NTP服务器 {server} 失败: {str(e)}")
                continue
        else:
            # 所有NTP服务器都连接失败
            logger.error("所有NTP服务器连接失败，无法检查时间同步状态!")
    
    except ImportError:
        logger.warning("未找到ntplib库，无法检查时间同步状态。如需检查服务器时间同步，请安装：pip install ntplib")
    except Exception as e:
        logger.warning(f"检查时间同步状态失败: {str(e)}")
    
    # 启动活跃会话清理任务
    await active_session_store.start_cleanup_task()
    
    # 启动在线状态管理器
    from app.core.online_status_manager import online_status_manager
    logger.info("正在启动在线状态管理器...")
    await online_status_manager.start()
    logger.info("在线状态管理器启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件处理"""
    logger.info("应用正在关闭...")
    
    # 关闭活跃会话清理任务
    await active_session_store.stop_cleanup_task()
    
    # 关闭在线状态管理器
    try:
        from app.core.online_status_manager import online_status_manager
        logger.info("正在关闭在线状态管理器...")
        await online_status_manager.shutdown()
        logger.info("在线状态管理器已关闭")
    except Exception as e:
        logger.error(f"关闭在线状态管理器时出错: {str(e)}")
    
    logger.info("应用已完全关闭")

if __name__ == '__main__':
    # 啟動服務器
    config = uvicorn.Config(
        app="app.main:app",
        host='127.0.0.1',
        port=8000,
        reload=True,
        log_level="debug"  # 改为debug级别
    )
    server = uvicorn.Server(config)
    server.run() 