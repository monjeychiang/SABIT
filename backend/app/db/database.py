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
    
    警告：此函數會刪除所有現有數據！僅應在以下情況使用：
    1. 首次設置應用時建立初始數據庫結構
    2. 測試環境中重置數據庫
    3. 在開發過程中重新建立模式結構
    
    在生產環境中，應使用遷移工具（如Alembic）進行數據庫結構變更，
    以保留現有數據。
    
    用法：
        在需要初始化數據庫時，手動調用此函數
        例如在應用啟動腳本中：
        
        if __name__ == "__main__":
            if args.init_db:  # 命令行參數
                from app.db.database import init_db
                init_db()
    
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

# 只建立表格，不清除現有數據（適用於第一次運行或添加新表時）
def create_tables():
    """
    僅創建不存在的表，不刪除現有數據或表結構
    
    此函數適用於：
    1. 應用首次部署時創建表結構
    2. 添加了新的模型類後創建相應的表
    
    與 init_db() 不同，此函數保留現有數據，安全用於生產環境。
    但它不會更新現有表的結構，如需更改表結構，應使用遷移工具。
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("成功創建缺少的表")
    except Exception as e:
        logger.error(f"創建表時出錯：{str(e)}")
        raise

# 注意：在實際使用中，應手動調用 init_db() 或 create_tables()，
# 而不是在模組導入時自動初始化數據庫 