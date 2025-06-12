# Core 模組

## 簡介

Core（核心）模組是交易系統的基礎架構，提供了配置管理、安全認證和交易所連接等關鍵功能。這些元件為整個應用程式提供基礎服務，確保系統的穩定性、安全性和可靠性。

## 模組結構

```
core/
│
├── config.py         - 系統配置管理
├── security.py       - 安全認證與加密
├── exchanges/        - 交易所連接介面
│   ├── base.py       - 交易所抽象基類
│   └── binance.py    - 幣安交易所實現
└── README.md         - 本文檔
```

## 功能說明

### 配置管理 (`config.py`)

此模組負責管理整個應用程式的配置參數，包括：

- **基本設定**：專案名稱、版本號、API 路徑前綴和除錯模式
- **資料庫設定**：SQLAlchemy 資料庫連接 URL
- **JWT 設定**：使用者認證的安全密鑰、加密演算法和存取令牌有效期
- **交易所設定**：支援的交易所列表及其 API 速率限制
- **交易設定**：杠桿倍數上限、最小/最大交易金額和預設交易手續費
- **風控設定**：單個倉位最大規模、每日最大虧損和最大回撤比例
- **通知設定**：電子郵件通知相關配置
- **日誌設定**：日誌級別、格式和檔案路徑
- **WebSocket 設定**：心跳間隔、重連延遲和最大重連次數

使用環境變數優先載入配置，若環境變數不存在則使用預設值，確保系統在不同環境中的靈活部署。

### 安全認證 (`security.py`)

此模組提供所有與使用者認證和資料安全相關的功能：

- **密碼處理**：使用 bcrypt 演算法安全地雜湊和驗證密碼
- **JWT 認證**：生成和驗證 JSON Web Tokens，實現使用者身份驗證
- **刷新令牌**：管理刷新令牌的創建、驗證和撤銷機制
- **API 密鑰加密**：使用 Fernet 對稱加密保護使用者的交易所 API 密鑰
- **OAuth2 整合**：支援使用 Google 等第三方服務進行身份認證
- **授權中間件**：提供依賴項函數，用於保護 API 端點，要求有效的使用者身份驗證

### 交易所連接 (`exchanges/`)

交易所連接模組提供與各大加密貨幣交易所通信的標準化介面：

#### 交易所抽象基類 (`base.py`)

定義了所有交易所實現必須遵循的統一介面：

- **連接管理**：建立和管理 WebSocket 連接
- **市場數據訂閱**：訂閱特定或全部交易對的實時行情
- **資料格式化**：將不同交易所的行情數據轉換為統一格式
- **行情查詢**：提供獲取即時價格、24 小時統計數據等方法

#### 幣安交易所實現 (`binance.py`)

針對幣安交易所的具體實現：

- **WebSocket 連接**：管理與幣安 WebSocket API 的連接
- **資料處理**：解析和處理幣安推送的實時行情數據
- **自動重連**：在連接中斷時提供自動重連機制
- **資料緩存**：維護最新的市場數據，供應用程式即時查詢

## 使用方式

### 配置示例

```python
from app.core.config import settings

# 使用配置參數
database_url = settings.SQLALCHEMY_DATABASE_URL
jwt_secret = settings.SECRET_KEY
```

### 安全功能使用

```python
from app.core.security import (
    verify_password, 
    get_password_hash,
    create_access_token,
    get_current_user
)

# 密碼雜湊
password_hash = get_password_hash("user_password")

# 驗證密碼
is_valid = verify_password("user_password", password_hash)

# 創建訪問令牌
token = create_access_token(data={"sub": username})

# 在 FastAPI 路由中使用授權依賴項
@app.get("/users/me")
async def read_users_me(current_user = Depends(get_current_user)):
    return current_user
```

### 交易所連接使用

```python
from app.core.exchanges.binance import BinanceExchange

# 初始化交易所
exchange = BinanceExchange()

# 連接到交易所
await exchange.connect()

# 訂閱市場數據
await exchange.subscribe_market_type("spot")

# 獲取特定交易對的價格
btc_price = exchange.get_ticker("BTCUSDT", "spot")
```

## 維護說明

- 添加新的交易所支援時，應繼承 `ExchangeBase` 類並實現所有抽象方法
- 修改配置參數時，建議通過環境變數或 `.env` 檔案進行，避免直接更改 `config.py`
- 安全相關的更新應同時考慮 `security.py` 中可能需要同步更新的多個部分

# 認證系統優化模組

本目錄包含用於提升系統認證效能的優化模組，主要解決高併發場景下的效能瓶頸問題。

## 模組概述

### 1. 非同步認證處理 (`async_auth.py`)

提供高效能的非同步處理能力，透過任務佇列和協程池實現認證相關操作的並行處理和負載均衡。

```python
# 使用範例
from app.core.async_auth import auth_pool

# 添加認證任務
task_id = await auth_pool.add_task("token_validation", {"token": token, "db": db})

# 獲取結果
result = await auth_pool.get_result(task_id, timeout=5.0)
```

### 2. 令牌驗證優化 (`token_validation.py`)

實現高效的令牌驗證策略，通過分層驗證和內存緩存大幅提高令牌驗證性能，減少不必要的計算和數據庫查詢。

```python
# 使用範例
from app.core.token_validation import verify_token_optimized

# 驗證令牌
try:
    payload = verify_token_optimized(token, db)
    # 令牌有效，繼續處理
except HTTPException:
    # 令牌無效，處理錯誤
```

### 3. 令牌刷新優化 (`token_refresh.py`)

實現高效的令牌刷新策略，通過動態閾值計算、批量處理請求和令牌衰減機制，優化系統在高併發情況下的刷新令牌處理性能。

```python
# 使用範例
from app.core.token_refresh import token_refresh_manager

# 獲取動態刷新閾值
threshold = token_refresh_manager.calculate_dynamic_refresh_threshold(user_id)

# 創建帶衰減特性的刷新令牌
token, db_token, decay_info = token_refresh_manager.create_refresh_token_with_decay(
    db, user_id, expires_delta, device_info
)
```

### 4. 認證優化整合 (`auth_optimizations.py`)

整合所有認證相關優化，並提供統一的接口來初始化和使用這些優化功能。

```python
# 使用範例
from app.core.auth_optimizations import initialize_auth_optimizations, get_current_user_optimized

# 在FastAPI應用啟動時初始化
await initialize_auth_optimizations(app)

# 使用優化的依賴項
@app.get("/api/protected")
async def protected_route(user = Depends(get_current_user_optimized)):
    return {"message": "Protected data", "user": user.username}
```

## 配置選項

以下環境變數可用於調整認證優化系統的行為：

| 環境變數 | 描述 | 默認值 |
|---------|------|-------|
| `AUTH_CACHE_SIZE` | 令牌驗證緩存大小 | 5000 |
| `AUTH_CACHE_TTL` | 令牌驗證緩存有效期（秒） | 60 |
| `JWT_SIG_CACHE_SIZE` | JWT簽名緩存大小 | 10000 |
| `JWT_SIG_CACHE_TTL` | JWT簽名緩存有效期（秒） | 300 |
| `AUTH_WORKER_COUNT` | 非同步認證工作者數量 | 5 |
| `REFRESH_BATCH_SIZE` | 令牌刷新批處理大小 | 20 |
| `REFRESH_MAX_WAIT_MS` | 令牌刷新批處理最大等待時間（毫秒） | 200 |

## 效能測試

使用 `test_auth_optimization.py` 腳本測試認證系統的效能：

```bash
# 基本測試
python test_auth_optimization.py

# 自定義測試參數
python test_auth_optimization.py --iterations 500 --threads 50 --requests 10 --charts

# 查看幫助
python test_auth_optimization.py --help
```

## 注意事項

1. 所有緩存都是進程內的，在多進程部署時需要考慮緩存一致性問題
2. 定期監控緩存使用情況，避免記憶體使用過高
3. 在生產環境中，建議根據實際負載調整緩存大小和過期時間 