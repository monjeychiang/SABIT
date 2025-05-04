# 資料庫模組

## 簡介

資料庫（DB）模組是交易系統的資料持久化核心，負責定義資料庫連接、資料模型結構和提供資料存取接口。本模組使用 SQLAlchemy 作為 ORM（物件關係映射）工具，支援多種資料庫後端，預設使用 SQLite 以便於開發和測試，同時可透過環境變數輕鬆切換至生產環境中的 PostgreSQL 或 MySQL 等資料庫系統。

## 模組結構

```
db/
│
├── database.py         - 資料庫連接和會話管理
├── models/             - 資料模型定義
│   ├── __init__.py     - 模型導出聲明
│   ├── base.py         - 基礎型別和工具函數
│   ├── user.py         - 使用者模型
│   ├── notification.py - 通知模型
│   ├── notification_settings.py - 通知設定模型
│   └── exchange_api.py - 交易所API密鑰模型
└── README.md           - 本文件
```

## 功能說明

### 資料庫連接 (`database.py`)

此模組負責管理與資料庫的連接和會話，主要功能包括：

- **連接管理**：建立和配置資料庫連接，支援從環境變數讀取連接字串
- **連接池優化**：設定連接池大小、超時時間、連接回收策略等，提升性能和穩定性
- **會話管理**：提供 `get_db()` 依賴函數，確保每個 API 請求使用獨立的資料庫會話
- **資料庫初始化**：提供 `init_db()` 函數，用於應用啟動時初始化資料庫結構

核心配置參數：
- 連接池大小：20個連接（預設）
- 最大溢出連接：30個（處理流量峰值）
- 連接回收時間：3600秒（1小時）
- 連接預檢機制：啟用（避免使用失效連接）

### 資料模型 (`models/`)

這個目錄包含系統所有的資料模型定義，使用 SQLAlchemy 的宣告式模型風格。

#### 基礎模型 (`base.py`)

提供所有模型共用的基礎元素：

- **時區處理**：定義東八區時區（UTC+8），提供生成台灣標準時間的工具函數
- **通知類型枚舉**：定義不同類型的系統通知（INFO, SUCCESS, WARNING, ERROR, SYSTEM）
- **使用者標籤枚舉**：定義不同類型的使用者（ADMIN, REGULAR, PREMIUM）

#### 使用者模型 (`user.py`)

系統的核心模型之一，定義使用者資料結構：

- **`User` 類**：存儲使用者帳號資訊、驗證資料、權限設定和個人檔案
- **`RefreshToken` 類**：實現 JWT 認證的令牌刷新機制，支援多裝置登入

主要欄位包括：使用者名稱、電子郵件、雜湊密碼、帳號狀態、OAuth 整合資訊等。

#### 通知模型 (`notification.py`)

管理系統向使用者發送的各類通知：

- **通知內容**：標題、訊息內容、類型（使用通知類型枚舉）
- **通知狀態**：已讀/未讀狀態、建立時間
- **通知範圍**：支援個人通知和全域通知（發送給所有使用者）

#### 通知設定模型 (`notification_settings.py`)

存儲使用者的通知偏好設定：

- **通知頻道**：電子郵件通知、桌面通知、聲音通知等
- **通知類型**：交易通知、系統通知等不同類別的通知
- **詳細偏好**：使用 JSON 欄位存儲更靈活的通知偏好設定

#### 交易所 API 密鑰模型 (`exchange_api.py`)

管理使用者的交易所 API 連接憑證：

- **API 認證資訊**：API 密鑰和秘鑰（加密存儲）
- **交易所類型**：使用枚舉定義不同的支援交易所
- **使用者關聯**：建立與使用者模型的關聯關係

## 資料關聯圖

下面是主要資料模型之間的關聯關係：

```
User (使用者)
  │
  ├─── RefreshToken (多個刷新令牌)
  │
  ├─── Notification (多個通知)
  │
  ├─── NotificationSetting (一個通知設定)
  │
  └─── ExchangeAPI (多個交易所API密鑰)
```

## 使用方式

### 定義新的模型

```python
from sqlalchemy import Column, Integer, String
from ..database import Base

class NewModel(Base):
    __tablename__ = "new_models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    # 其他欄位定義...
```

### 在 API 端點中使用資料庫

```python
from fastapi import Depends
from ..db.database import get_db
from ..db.models import User

@app.get("/users/")
def read_users(db = Depends(get_db)):
    users = db.query(User).all()
    return users
```

### 執行資料庫操作

```python
# 新增記錄
def create_user(db, user_data):
    db_user = User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# 查詢記錄
def get_user_by_username(db, username):
    return db.query(User).filter(User.username == username).first()

# 更新記錄
def update_user(db, user_id, update_data):
    db_user = db.query(User).filter(User.id == user_id).first()
    for key, value in update_data.items():
        setattr(db_user, key, value)
    db.commit()
    db.refresh(db_user)
    return db_user

# 刪除記錄
def delete_user(db, user_id):
    db_user = db.query(User).filter(User.id == user_id).first()
    db.delete(db_user)
    db.commit()
    return True
```

## 設計考量

1. **安全性**：密碼使用雜湊處理，API 密鑰使用加密存儲
2. **關聯完整性**：使用外鍵約束和級聯刪除確保資料一致性
3. **高效查詢**：對頻繁查詢的欄位建立索引，優化查詢效能
4. **彈性配置**：使用環境變數和預設值機制，支援不同部署環境
5. **資源管理**：自動釋放資料庫連接，避免資源洩漏

## 注意事項

- 在生產環境中，應使用 Alembic 等遷移工具管理資料庫結構變更，而不是使用 `init_db()` 函數
- 敏感資料（如 API 密鑰）在存儲前必須經過加密處理
- 資料庫查詢應適當使用索引，避免全表掃描影響效能
- 使用 SQLAlchemy 的 ORM 功能時要注意 N+1 查詢問題，適當使用聯接查詢和預加載 