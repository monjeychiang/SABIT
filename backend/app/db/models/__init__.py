from .base import get_china_time, NotificationType, UserTag
from .user import User, RefreshToken
from .notification import Notification
from .exchange_api import ExchangeAPI
from .chat import ChatSession, ChatMessage

# 確保所有模型都被導入，以便 SQLAlchemy 能夠正確創建資料表
# 此列表定義了哪些類和函數可以從 app.db.models 模組直接導入
# 例如：from app.db.models import User, Notification
__all__ = [
    "get_china_time",       # 獲取台灣標準時間的工具函數
    "NotificationType",     # 通知類型枚舉，定義不同種類的系統通知
    "UserTag",              # 用戶標籤枚舉，用於用戶分類和權限控制
    "User",                 # 用戶模型，系統的核心模型之一
    "RefreshToken",         # 刷新令牌模型，用於JWT認證機制中的令牌刷新
    "Notification",         # 通知模型，用於存儲系統通知和用戶消息
    "ExchangeAPI",          # 交易所API密鑰模型，管理用戶的交易所連接憑證
    "ChatSession",          # 聊天會話模型，存儲用戶與Gemini的對話會話
    "ChatMessage"           # 聊天消息模型，存儲會話中的單條消息
] 