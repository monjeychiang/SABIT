from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, ForeignKey, Text, func, JSON, Enum
import datetime
import pytz
import enum

# 定義東八區時區，用於生成符合台灣標準的時間戳記
TZ_CHINA = pytz.timezone('Asia/Shanghai')

def get_china_time():
    """
    返回台灣標準時間（UTC+8）
    
    此函數提供當前的台灣標準時間，用於數據庫記錄的時間戳。
    在模型定義中常用於設置 created_at 和 updated_at 欄位的預設值，
    確保所有時間記錄符合系統用戶的時區習慣。
    
    返回：
        datetime: 帶有時區信息的當前台灣標準時間物件
    """
    return datetime.datetime.now(TZ_CHINA)

# 定義通知類型枚舉，用於分類不同類型的系統通知
class NotificationType(str, enum.Enum):
    """
    通知類型枚舉
    
    用於標識不同類型的系統通知，以便前端以不同方式展示，
    並允許用戶根據通知類型設置個性化的接收偏好。
    繼承自 str 以便在 JSON 序列化時能直接使用字符串值。
    """
    INFO = "info"         # 一般信息：普通系統公告、提示等中性通知
    SUCCESS = "success"   # 成功信息：操作成功、交易完成等正面通知
    WARNING = "warning"   # 警告信息：風險提示、余額不足等需注意事項
    ERROR = "error"       # 錯誤信息：操作失敗、系統錯誤等負面通知
    SYSTEM = "system"     # 系統通知：維護公告、版本更新等重要系統事件

# 定義用戶標籤枚舉，用於分類不同類型的用戶
class UserTag(str, enum.Enum):
    """
    用戶標籤枚舉
    
    用於標識不同類型的用戶，實現權限控制和差異化服務。
    影響用戶可訪問的功能範圍、資源限制和界面展示等方面。
    繼承自 str 以便在 JSON 序列化時能直接使用字符串值。
    """
    ADMIN = "admin"       # 管理員：具有系統管理權限，可訪問所有功能
    REGULAR = "regular"   # 一般用戶：基礎功能訪問權限，標準服務級別
    PREMIUM = "premium"   # 高級用戶：高級功能訪問權限，優先服務級別 