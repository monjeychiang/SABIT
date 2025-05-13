from typing import Optional, Dict, Any, List, Union
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing_extensions import Annotated
import os
from dotenv import load_dotenv
import secrets
import socket
import uuid

# 載入.env檔案中的環境變數
load_dotenv()

class Settings(BaseSettings):
    """應用程式設定
    
    此類定義了整個應用程式的全域設定，包括基本設定、資料庫連接、安全性配置、
    交易所參數、交易限制、風險控制、通知系統、日誌和WebSocket等配置項目。
    所有設定優先從環境變數讀取，若環境變數不存在則使用預設值。
    """
    
    # 基本設定：定義專案名稱、版本、API路徑前綴和除錯模式
    PROJECT_NAME: str = "Trading Bot"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # 資料庫設定：定義SQLAlchemy的資料庫連接URL
    SQLALCHEMY_DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///trading.db")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///trading.db")
    
    # JWT設定：用於使用者認證的安全密鑰、加密演算法和存取令牌有效期
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7天有效期
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7天刷新令牌有效期
    TWO_FACTOR_EXPIRE_MINUTES: int = 10  # 兩因素認證碼有效期
    
    # 加密設定：用於敏感資料加密的密鑰
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "your-encryption-key")
    
    # Google OAuth設定
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: Optional[str] = os.getenv("GOOGLE_REDIRECT_URI")
    
    # 前端相關設定
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5175")
    FRONTEND_CALLBACK_URL: str = os.getenv("FRONTEND_CALLBACK_URL", "http://localhost:5175/auth/callback")
    
    # Cookie 設定
    USE_SECURE_COOKIES: bool = False
    COOKIE_DOMAIN: Optional[str] = None
    COOKIE_SAMESITE: str = "lax"
    
    # Gemini API相關設定
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_SYSTEM_PROMPT: str = os.getenv("GEMINI_SYSTEM_PROMPT", "你是一個有幫助的AI助手，提供準確、有用的回答。")
    GEMINI_MAX_MESSAGES_PER_SESSION: int = int(os.getenv("GEMINI_MAX_MESSAGES_PER_SESSION", "50"))  # 每個會話最大訊息數
    GEMINI_MAX_RESPONSE_TOKENS: int = int(os.getenv("GEMINI_MAX_RESPONSE_TOKENS", "1000"))  # 最大回覆長度(token)
    GEMINI_MAX_RESPONSE_CHARS: int = int(os.getenv("GEMINI_MAX_RESPONSE_CHARS", "4000"))  # 最大回覆長度(字符)
    
    # 用戶等級對應的聊天功能限制
    # 每日訊息限制：不同用戶等級的每日可發送訊息數量
    DAILY_MESSAGE_LIMITS: Dict[str, int] = {
        "admin": int(os.getenv("ADMIN_DAILY_MESSAGE_LIMIT", "-1")),  # 管理員無限制
        "premium": int(os.getenv("PREMIUM_DAILY_MESSAGE_LIMIT", "100")),  # 高級用戶每日100條
        "regular": int(os.getenv("REGULAR_DAILY_MESSAGE_LIMIT", "20"))  # 普通用戶每日20條
    }
    
    # 交易所設定：支援的交易所列表及其API速率限制
    SUPPORTED_EXCHANGES: list = ["binance", "okx", "bybit"]
    EXCHANGE_RATE_LIMITS: Dict[str, Dict[str, Any]] = {
        "binance": {
            "weight_per_minute": 1200,  # 每分鐘允許的權重
            "orders_per_second": 10,    # 每秒允許的訂單數
            "orders_per_day": 200000    # 每天允許的訂單總數
        },
        "okx": {
            "weight_per_minute": 600,
            "orders_per_second": 20,
            "orders_per_day": 100000
        },
        "bybit": {
            "weight_per_minute": 600,
            "orders_per_second": 10,
            "orders_per_day": 100000
        }
    }
    
    # 交易設定：定義杠桿倍數上限、最小/最大交易金額和預設交易手續費
    MAX_LEVERAGE: int = 20
    MIN_TRADE_AMOUNT: float = 10.0
    MAX_TRADE_AMOUNT: float = 100000.0
    DEFAULT_TRADE_FEE: float = 0.001  # 0.1%手續費
    
    # 風控設定：定義單個倉位最大規模、每日最大虧損和最大回撤比例
    MAX_POSITION_SIZE: float = 100000.0
    MAX_DAILY_LOSS: float = 1000.0
    MAX_DRAWDOWN: float = 0.2  # 最大回撤20%
    
    # 通知設定：電子郵件通知相關設定
    ENABLE_EMAIL_NOTIFICATIONS: bool = True
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: Optional[int] = os.getenv("SMTP_PORT", 587)
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    
    # 日誌設定：日誌級別、格式和檔案路徑
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/trading.log"
    
    # WebSocket設定：心跳間隔、重連延遲和最大重連次數
    WS_HEARTBEAT_INTERVAL: int = 30  # 秒
    WS_RECONNECT_DELAY: int = 5      # 秒
    WS_MAX_RECONNECTS: int = 5
    
    # WebSocket連接池配置 - 從環境變數讀取
    WS_MAX_GLOBAL_CONNECTIONS: int = int(os.getenv("WS_MAX_GLOBAL_CONNECTIONS", "1000"))
    WS_MAX_CONNECTIONS_PER_USER: int = int(os.getenv("WS_MAX_CONNECTIONS_PER_USER", "5"))
    WS_MAX_CONNECTIONS_PER_ROOM: int = int(os.getenv("WS_MAX_CONNECTIONS_PER_ROOM", "100"))
    WS_MESSAGE_RATE_LIMIT: int = int(os.getenv("WS_MESSAGE_RATE_LIMIT", "10"))
    WS_RATE_LIMIT_WINDOW: int = int(os.getenv("WS_RATE_LIMIT_WINDOW", "60"))
    
    # WebSocket相關配置 - 已棄用，保留為向後相容
    WEBSOCKET_MAX_CONNECTIONS: int = int(os.getenv("WS_MAX_GLOBAL_CONNECTIONS", "1000"))
    WEBSOCKET_MAX_CONNECTIONS_PER_USER: int = int(os.getenv("WS_MAX_CONNECTIONS_PER_USER", "5"))
    WEBSOCKET_MAX_CONNECTIONS_PER_ROOM: int = int(os.getenv("WS_MAX_CONNECTIONS_PER_ROOM", "100"))
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30
    WEBSOCKET_HEARTBEAT_TIMEOUT: int = 60
    WEBSOCKET_MESSAGE_RATE_LIMIT: int = int(os.getenv("WS_MESSAGE_RATE_LIMIT", "10"))
    WEBSOCKET_RATE_LIMIT_WINDOW: int = int(os.getenv("WS_RATE_LIMIT_WINDOW", "60"))
    
    # Redis配置
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    
    # 節點標識
    NODE_ID: str = None
    
    # 事件處理相關配置
    LOGIN_EVENT_DELAY_SECONDS: int = int(os.getenv("LOGIN_EVENT_DELAY_SECONDS", "3"))
    
    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: Optional[str], info) -> Optional[str]:
        if v:
            return v
        # 獲取values參數
        values = info.data
        if values.get("REDIS_ENABLED", False):
            password_part = f":{values.get('REDIS_PASSWORD')}@" if values.get("REDIS_PASSWORD") else ""
            return f"redis://{password_part}{values.get('REDIS_HOST', 'localhost')}:{values.get('REDIS_PORT', 6379)}/{values.get('REDIS_DB', 0)}"
        return None
    
    @field_validator("NODE_ID", mode="before")
    @classmethod
    def generate_node_id(cls, v: Optional[str]) -> str:
        if v:
            return v
        # 生成一個唯一的節點ID，基於主機名和一個隨機UUID
        hostname = socket.gethostname()
        random_id = str(uuid.uuid4())[:8]
        return f"{hostname}-{random_id}"
    
    model_config = {
        "case_sensitive": True,  # 設定名稱大小寫敏感
        "env_file": ".env",      # 指定環境變數檔案位置
        "extra": "ignore"        # 允許額外的輸入（環境變數）
    }

# 創建全域設定實例，供整個應用程式使用
settings = Settings() 