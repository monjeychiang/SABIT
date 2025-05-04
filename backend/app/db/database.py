from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import logging

# 配置日誌記錄器，用於資料庫操作的日誌追蹤
logger = logging.getLogger(__name__)

# 載入環境變數，確保可以從.env檔案獲取配置參數
load_dotenv()

# 資料庫連接 URL，優先使用環境變數中的設置，若無則使用預設的 SQLite 資料庫
# 這種設計允許在不同環境（開發、測試、生產）中輕鬆切換資料庫配置
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./trading.db"
)

# 創建 SQLAlchemy 引擎實例
# 對於 SQLite 資料庫，需要設置 check_same_thread=False 以允許多線程訪問
# 其他參數用於優化資料庫連接池的性能和穩定性
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
    pool_size=50,  # 增加連接池大小，提升系統併發處理能力
    max_overflow=50,  # 增加最大溢出連接數，處理突發流量峰值
    pool_timeout=120,  # 增加連接超時時間，避免短期網絡問題導致連接失敗
    pool_recycle=1800,  # 設置連接回收時間（30分鐘），防止資料庫斷開空閒連接
    pool_pre_ping=True  # 啟用連接預檢查，確保獲取的連接始終有效
)

# 創建會話工廠，用於生成資料庫會話實例
# autocommit=False：需要明確提交事務才能保存更改
# autoflush=False：需要明確呼叫flush才會將更改發送到資料庫
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 創建基礎模型類，所有資料庫模型類都將繼承此類
Base = declarative_base()

# 資料庫依賴項，用於 FastAPI 的依賴注入系統
def get_db():
    """
    創建資料庫會話並在使用後自動關閉
    
    此函數作為 FastAPI 依賴項使用，確保每個請求使用獨立的資料庫會話，
    並在請求處理完成後正確關閉會話，無論處理過程是否出現異常。
    使用 yield 語句實現上下文管理，確保資源正確釋放。
    
    用法示例：
        @app.get("/items/")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    
    返回：
        SQLAlchemy 會話物件，用於執行資料庫操作
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    初始化資料庫：刪除所有現有表並重新創建
    
    此函數在應用啟動時執行，確保資料庫結構與當前模型定義一致。
    警告：在生產環境中應謹慎使用，因為它會刪除所有現有數據。
    生產環境通常應該使用遷移工具（如Alembic）進行資料庫結構變更。
    
    錯誤處理：
        如果初始化過程中出現異常，會記錄錯誤並向上拋出，
        以便應用能夠適當處理並顯示相關錯誤信息。
    """
    try:
        # 刪除所有現有表，重置資料庫結構
        Base.metadata.drop_all(bind=engine)
        logger.info("成功刪除所有現有表")
        
        # 根據模型定義創建所有表
        Base.metadata.create_all(bind=engine)
        logger.info("成功創建所有表")
        
    except Exception as e:
        logger.error(f"初始化資料庫時出錯：{str(e)}")
        raise

# 在應用啟動時自動初始化資料庫
init_db() 