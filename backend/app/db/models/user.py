from sqlalchemy import Boolean, Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship, backref
from ...db.database import Base
from .base import get_china_time, UserTag

class User(Base):
    """
    用戶模型
    
    此模型定義了系統用戶的資料結構，包含驗證信息、個人資料、權限設定等。
    作為系統核心模型，它與多個其他模型建立關聯關係，例如通知、API密鑰等。
    """
    __tablename__ = "users"  # 資料表名稱

    # 用戶基本信息
    id = Column(Integer, primary_key=True, index=True)  # 用戶唯一識別符，主鍵
    username = Column(String(50), unique=True, index=True, nullable=False)  # 用戶名，必須唯一，用於登入
    email = Column(String(100), unique=True, index=True, nullable=False)  # 電子郵件，必須唯一，用於通知和恢復
    hashed_password = Column(String(100), nullable=False)  # 經過雜湊處理的密碼，禁止儲存明文密碼
    is_active = Column(Boolean, default=True)  # 帳戶是否啟用，可用於停用帳戶而不刪除
    is_verified = Column(Boolean, default=False)  # 電子郵件是否已驗證，影響某些功能的使用權限
    is_admin = Column(Boolean, default=False)  # 是否具有管理員權限，影響系統管理功能的訪問
    created_at = Column(DateTime, default=get_china_time)  # 帳戶創建時間，自動設置
    updated_at = Column(DateTime, onupdate=get_china_time)  # 資料更新時間，自動在更新時更新
    
    # 推薦系統相關
    referral_code = Column(String(6), unique=True, index=True, nullable=True)  # 用戶唯一推薦碼，6位英數混合
    referrer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # 推薦人ID
    
    # OAuth 相關欄位（第三方身份驗證）
    oauth_provider = Column(String(20), nullable=True)  # 第三方認證提供者，如 'google', 'github' 等
    full_name = Column(String(100), nullable=True)  # 從 OAuth 提供者獲取的完整姓名
    avatar_url = Column(String(255), nullable=True)  # 頭像 URL，通常從第三方認證服務獲取
    
    # 用戶分類標籤，用於權限控制和差異化服務
    user_tag = Column(Enum(UserTag), default=UserTag.REGULAR, nullable=False)
    
    # 用戶登入信息，用於安全監控和異常行為檢測
    last_login_ip = Column(String(50), nullable=True)  # 最後登入的 IP 地址
    last_login_at = Column(DateTime, nullable=True)  # 最後登入的時間
    
    # 關聯關係：推薦關係
    # 一對多關係，一個用戶可以推薦多個新用戶
    referrals = relationship("User", 
                             backref=backref("referrer", remote_side=[id]),
                             foreign_keys=[referrer_id])
    
    # 關聯關係：用戶通知
    # 一對多關係，一個用戶可以有多個通知
    notifications = relationship("Notification", back_populates="user")
    
    # 關聯關係：刷新令牌
    # 一對多關係，一個用戶可以有多個刷新令牌（支持多設備同時登入）
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
    # 關聯關係：交易所 API 密鑰
    # 一對多關係，一個用戶可以設置多個交易所的 API 密鑰
    exchange_apis = relationship("ExchangeAPI", back_populates="user", cascade="all, delete-orphan")
    
    # 關聯關係：Gemini聊天會話
    # 一對多關係，一個用戶可以有多個聊天會話
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")
    
    # 關聯關係：聊天消息使用統計
    # 一对一关系，每个用户只有一条消息使用统计记录
    chat_message_usage = relationship("ChatMessageUsage", back_populates="user", uselist=False)
    
    # 關聯關係：網格交易策略
    # 一對多關係，一個用戶可以設置多個網格交易策略
    grid_strategies = relationship("GridStrategy", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識用戶物件
        """
        return f"<User {self.username}>"

class RefreshToken(Base):
    """
    刷新令牌模型
    
    用於實現JWT認證中的令牌刷新機制，允許用戶在不重新登入的情況下
    獲取新的訪問令牌。支持多設備登入，並提供令牌撤銷功能，增強安全性。
    """
    __tablename__ = "refresh_tokens"  # 資料表名稱
    
    id = Column(Integer, primary_key=True, index=True)  # 唯一識別符，主鍵
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # 關聯用戶ID，使用級聯刪除
    token = Column(String(255), unique=True, nullable=False, index=True)  # 令牌值，必須唯一，建立索引以加速查詢
    expires_at = Column(DateTime, nullable=False)  # 令牌過期時間，用於自動失效控制
    created_at = Column(DateTime, default=get_china_time)  # 令牌創建時間
    is_revoked = Column(Boolean, default=False)  # 令牌是否已被撤銷，用於手動使令牌失效
    
    # 關聯關係：所屬用戶
    # 多對一關係，多個刷新令牌可以關聯到同一個用戶
    user = relationship("User", back_populates="refresh_tokens")
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識令牌物件
        """
        return f"<RefreshToken for user_id={self.user_id}>" 