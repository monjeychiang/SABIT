from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from ...db.database import Base
from .base import get_china_time
from ...schemas.trading import ExchangeEnum

class ExchangeAPI(Base):
    """
    交易所 API 密鑰模型
    
    用於存儲用戶添加的交易所 API 訪問憑證，系統通過這些密鑰代表用戶執行
    交易操作、查詢賬戶信息等。支持多個交易所，一個用戶可添加多組密鑰。
    
    API 密鑰和秘鑰在存儲前會經過加密處理，確保敏感信息安全。密鑰可添加
    描述信息，方便用戶區分不同用途（如主力交易、自動化策略等）的密鑰組。
    
    支持兩種密鑰類型：
    - HMAC-SHA256: 傳統的 API 密鑰和密鑰密碼
    - Ed25519: 使用 Ed25519 加密算法的密鑰對
    """
    __tablename__ = "exchange_apis"  # 資料表名稱
    
    id = Column(Integer, primary_key=True, index=True)  # 唯一識別符，主鍵
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # 關聯用戶ID，使用級聯刪除
    exchange = Column(Enum(ExchangeEnum), nullable=False)  # 交易所類型，使用枚舉確保值的有效性
    
    # HMAC-SHA256 API密鑰部分
    api_key = Column(String(100), nullable=True)  # API 密鑰，存儲前經過加密處理
    api_secret = Column(String(100), nullable=True)  # API 秘鑰，存儲前經過加密處理
    
    # Ed25519 API密鑰部分
    ed25519_key = Column(String(100), nullable=True)  # Ed25519 公鑰
    ed25519_secret = Column(String(100), nullable=True)  # Ed25519 私鑰
    
    description = Column(String(200), nullable=True)  # API 密鑰描述，方便用戶區分不同用途的密鑰
    created_at = Column(DateTime, default=get_china_time)  # 記錄創建時間
    updated_at = Column(DateTime, onupdate=get_china_time)  # 記錄更新時間，自動在更新時更新
    
    # 關聯關係：所屬用戶
    # 多對一關係，多個交易所API密鑰可以屬於同一個用戶
    user = relationship("User", back_populates="exchange_apis")
    
    # Pydantic ORM 模式配置
    # 實現 ORM 模型與 API 模型的自動轉換
    class Config:
        orm_mode = True
    
    def __repr__(self):
        """
        模型的字符串表示方法
        
        用於在日誌記錄和調試輸出中標識API密鑰物件
        """
        key_types = []
        if self.api_key:
            key_types.append("HMAC")
        if self.ed25519_key:
            key_types.append("ED25519")
        return f"<ExchangeAPI {self.exchange} {'+'.join(key_types)} for user_id={self.user_id}>" 