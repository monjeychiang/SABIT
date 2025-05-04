# FastAPI 後端 API 端點模組

本目錄包含系統所有的 FastAPI API 端點定義，每個文件對應一個功能模組。這些端點實現了與前端的所有交互功能，包括資料查詢、用戶認證、系統管理等核心功能。本文檔提供了對每個模組的詳細介紹以及開發新功能時的指導方針。

## 目錄結構

- **auth.py** (25KB, 669 行): 用戶身份認證相關 API，包括登入、登出、註冊、密碼重置、Token 刷新等功能
- **admin.py** (12KB, 385 行): 系統管理員專用 API，用於用戶管理、系統配置等管理功能
- **markets.py** (73KB, 1797 行): 加密貨幣市場數據 API 端點，提供現貨和期貨市場價格、WebSocket 實時數據流
- **notifications.py** (26KB, 707 行): 實時通知系統 API，包括 WebSocket 連接、通知發送、訂閱和刪除功能
- **settings.py** (11KB, 334 行): 用戶設置及系統配置 API，用於保存和獲取各類用戶偏好設置
- **system.py** (4.2KB, 135 行): 系統狀態和健康檢查 API，提供系統運行狀態、版本信息等
- **users.py** (3.3KB, 98 行): 用戶資料管理 API，包括用戶資料的查詢、修改和權限管理
- **__init__.py** (33B, 1 行): 模組初始化文件

## 主要模組說明

### 認證模組 (auth.py)

實現了 OAuth2 身份認證，處理用戶的登入、註冊和 Token 管理：

- JWT Token 生成與驗證（基於 PyJWT 實現）
- 安全的密碼哈希與驗證（使用 Passlib 的 Bcrypt 算法）
- 基於角色的訪問控制 (RBAC)
- 支持多種登入方式（標準 OAuth2 和簡化表單登入）
- 刷新令牌機制，減少用戶重複登入頻率
- 安全管控設計，包括登入失敗次數限制、IP 檢查等

#### 核心端點

```python
@router.post("/login", response_model=Token)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
) -> Any:
    """
    標準 OAuth2 登入端點
    
    使用用戶名和密碼進行身份驗證，符合 OAuth2 標準流程。
    成功時返回 access_token 和 refresh_token。
    """
    # ...（實現代碼）
```

```python
@router.post("/login/simple", response_model=Token)
def login_simple(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
) -> Any:
    """
    簡化版用戶登入 - 直接接收表單參數
    
    提供比標準OAuth2流程更簡單的登入方式，直接接收用戶名和密碼參數。
    適用於不方便使用完整OAuth2流程的客戶端。
    """
    # ...（實現代碼）
```

```python
@router.get("/me", response_model=UserResponse)
def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> Any:
    """
    獲取當前用戶資訊
    
    根據請求中的認證令牌，返回當前登入用戶的詳細資訊。
    這是驗證用戶身份和獲取個人資料的標準端點。
    """
    # ...（實現代碼）
```

### 市場數據模組 (markets.py)

提供豐富的加密貨幣市場數據 API：

- 支持多種交易所行情數據（主要實現 Binance API）
- 提供現貨和期貨市場的實時價格
- WebSocket 實時數據推送（使用 FastAPI WebSocket）
- 支持按交易對訂閱特定市場數據
- 24小時交易統計數據
- 價格緩存機制和自動更新，減少外部 API 調用次數
- 支持自定義交易對列表的行情訂閱功能
- 背景任務管理，定期更新市場數據

#### 系統架構

本模組採用分層設計：
1. **緩存層 (PriceCache)**：存儲和管理各交易所與市場類型的行情數據
2. **連接管理 (ConnectionManager)**：處理所有 WebSocket 客戶端連接與廣播通信
3. **API 端點層**：向前端提供 REST 和 WebSocket 接口

#### 核心端點

```python
@router.get("/symbols", response_model=Dict[str, Any])
async def get_symbols(
    exchange: str = Query("binance", description="交易所名稱"),
    market_type: str = Query("spot", description="市場類型 (spot/futures)"),
    filter: Optional[str] = Query(None, description="過濾條件，例如 'BTC' 或 'USDT'")
):
    """
    獲取指定交易所和市場類型的所有交易對
    
    返回特定交易所和市場類型的所有可用交易對列表。
    支援按關鍵字過濾交易對，例如只返回包含 "BTC" 或 "USDT" 的交易對。
    """
    # ...（實現代碼）
```

```python
@router.websocket("/ws/custom")
async def websocket_custom_symbols(
    websocket: WebSocket,
    symbols: str = Query(..., description="逗號分隔的交易對列表，例如 'BTCUSDT,ETHUSDT'")
):
    """
    訂閱自定義交易對列表的實時價格更新
    
    客戶端可以指定一個交易對列表，只接收這些特定交易對的價格更新。
    這比訂閱全部價格更新更加高效，特別是在客戶端只關注少數交易對時。
    """
    # ...（實現代碼）
```

```python
@router.get("/ticker/24h", response_model=Dict[str, Any])
async def get_24h_ticker(
    symbols: List[str] = Query(..., description="交易對列表，例如 ['BTCUSDT', 'ETHUSDT']"),
    exchange: str = Query("binance", description="交易所名稱")
):
    """
    獲取指定交易對的24小時行情數據
    
    返回包含價格變化、成交量、最高價、最低價等交易統計信息。
    可以一次請求多個交易對的數據。
    """
    # ...（實現代碼）
```

### 通知系統 (notifications.py)

實現了實時通知功能：

- WebSocket 連接管理（基於 FastAPI WebSocket）
- 支持個人通知和全局通知（適合系統公告）
- 通知過濾和分類（市場、系統、賬戶等類型）
- 通知持久化存儲與查詢（基於 SQLAlchemy ORM）
- 未讀通知計數
- 通知分頁查詢與搜索
- 通知刪除和標記為已讀
- 廣播機制，支持即時推送給指定用戶或全部用戶

#### 通知生命週期

1. **創建**：通過各種系統事件觸發通知創建
2. **存儲**：將通知保存到數據庫
3. **廣播**：通過 WebSocket 即時推送給目標用戶
4. **查詢**：允許用戶分頁查詢他們的通知
5. **讀取標記**：用戶可以標記通知為已讀
6. **刪除**：用戶可以刪除不需要的通知

#### 核心實現

1. **連接管理器**：維護活躍用戶的 WebSocket 連接
2. **通知數據模型**：包含通知類型、內容、目標用戶等信息
3. **廣播函數**：處理向單個用戶或全部用戶發送通知

#### 核心端點

```python
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    last_activity: Optional[float] = Query(None)
):
    """
    通知系統的 WebSocket 連接端點
    
    建立 WebSocket 長連接，用於接收實時通知。
    客戶端需要提供有效的認證令牌以及最後活動時間。
    系統會發送連接期間錯過的通知以及新產生的通知。
    """
    # ...（實現代碼）
```

```python
@router.post("/broadcast", response_model=Dict[str, Any])
async def broadcast_notification(
    notification: NotificationCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    發送通知到指定用戶或全部用戶
    
    可用於發送系統公告、重要提醒等內容。
    需要管理員權限才能發送全局通知。
    """
    # ...（實現代碼）
```

```python
@router.delete("/all", response_model=Dict[str, Any])
async def delete_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    刪除當前用戶的所有通知
    
    允許用戶一次性清空所有通知，包括個人通知和全局通知。
    """
    # ...（實現代碼）
```

### 用戶管理 (users.py)

用戶資料和權限管理：

- 用戶個人資料管理
- 用戶權限控制
- 用戶偏好設置
- 用戶活動狀態跟踪

#### 核心端點

```python
@router.get("/active-users-count")
async def get_active_users_count(current_user: User = Depends(get_current_active_user)):
    """
    獲取當前活躍用戶數量
    
    該端點返回系統中目前在線的活躍用戶總數。
    只有已認證的用戶才能訪問此資訊。
    """
    return {"active_users": active_session_store.get_active_users_count()}
```

### 系統管理 (system.py)

系統運行狀態監控：

- 系統健康檢查
- 版本和更新信息
- 資源使用統計
- 服務可用性監控
- 系統運行時間和基本統計數據

### 管理員功能 (admin.py)

系統管理員專用功能：

- 用戶帳號管理（搜索、分頁查詢、禁用或啟用）
- 系統設置配置
- 資料分析和報表
- 系統日誌查詢
- 用戶標籤管理

#### 核心端點

```python
@router.get("/users", response_model=PaginatedUsers)
async def get_all_users(
    db: Session = Depends(get_db),
    page: int = 1, 
    per_page: int = 10,
    search: Optional[str] = None,
    current_admin: User = Depends(get_current_admin_user)
) -> Any:
    """
    獲取所有用戶（管理員權限），支援分頁和搜索
    
    此端點返回系統中的用戶列表，可透過分頁參數控制返回數量，
    並支援按用戶名和電子郵件進行模糊搜索。
    """
    # ...（實現代碼）
```

### 設置管理 (settings.py)

應用和用戶設置管理：

- 用戶偏好設置儲存與讀取
- 系統預設配置
- 界面自定義設置
- 通知偏好設定
- 加密貨幣交易所 API 密鑰管理（安全加密存儲）

#### 核心組件

1. **通知設置**：控制用戶接收哪些類型的通知
2. **交易所 API 管理**：安全地存儲和管理用戶的交易所 API 密鑰
3. **界面設置**：管理用戶界面展示偏好

#### 核心端點

```python
@router.put("/exchange/{exchange_id}", response_model=ExchangeAPIResponse)
async def update_exchange_api(
    exchange_id: int,
    api_data: ExchangeAPIUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    更新特定交易所的 API 密鑰設置
    
    允許用戶更新已存在的交易所 API 密鑰設置。
    API 密鑰在存儲前會進行加密處理，確保數據安全。
    """
    # ...（實現代碼）
```

## 開發指南

### 路由器註冊流程

在開發新模組時，需要遵循以下步驟將其註冊到 API 路由系統：

1. 在適當的模組文件中定義 `router = APIRouter()` 
2. 在模組中定義所有 API 端點
3. 在 `backend/app/api/api.py` 中導入並註冊路由器：

```python
from .endpoints import auth, users, markets, notifications, settings, system, admin

api_router = APIRouter()

# 註冊各功能模組的路由器
api_router.include_router(auth.router, prefix="/auth", tags=["認證"])
api_router.include_router(users.router, prefix="/users", tags=["用戶"])
# ... 其他路由器
```

### 新增 API 端點

在開發新功能時，請遵循以下步驟：

1. 確定功能所屬的模組，或創建新模組文件
2. 按照 FastAPI 路由定義規範編寫端點函數：

```python
@router.get("/resource-name", response_model=ResponseModel)
async def get_resource(
    param1: Type = Query(..., description="參數說明"),
    param2: Optional[Type] = Query(None, description="可選參數說明"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    端點詳細功能描述（繁體中文）
    
    詳細解釋此端點的功能、使用場景和限制條件等。
    
    參數:
        param1: 參數1的說明
        param2: 參數2的說明
        
    返回:
        返回數據的說明
        
    錯誤:
        可能發生的錯誤類型及原因
    """
    # 實現代碼
    ...
    
    # 返回結果
    return result_data
```

3. 使用 Pydantic 模型定義請求和響應數據結構
4. 實現適當的錯誤處理和日誌記錄
5. 編寫詳細的繁體中文註解和文檔字符串
6. 添加必要的身份驗證和權限檢查

### 代碼風格要求

- 遵循 PEP 8 Python 代碼風格指南
- 使用類型提示增強代碼可讀性：

```python
from typing import List, Dict, Any, Optional, Union

def function_name(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    # 函數實現
    return {"result": "value"}
```

- 提供詳細的繁體中文文檔字符串，包含：
  - 功能描述
  - 參數說明
  - 返回值說明
  - 錯誤處理說明
  - 使用示例（如適用）

- 錯誤處理最佳實踐：

```python
try:
    # 可能出錯的代碼
    result = some_function()
except SpecificError as e:
    # 記錄錯誤信息
    logger.error(f"處理請求時發生錯誤: {str(e)}", exc_info=True)
    # 返回適當的 HTTP 錯誤
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="發生錯誤的詳細說明"
    )
```

- 函數和方法應保持單一職責原則

### WebSocket 端點規範

對於 WebSocket 端點，請遵循以下最佳實踐：

- 連接管理框架：

```python
@router.websocket("/ws/endpoint")
async def websocket_endpoint(websocket: WebSocket, param: str = Query(...)):
    # 1. 接受連接
    await websocket.accept()
    
    try:
        # 2. 用戶認證（如需要）
        await authenticate_user(websocket, token)
        
        # 3. 向連接管理器註冊此連接
        manager.add_connection(websocket, param)
        
        # 4. 處理連接
        await handle_websocket_communication(websocket)
    except WebSocketDisconnect:
        # 5. 連接斷開時清理
        logger.info(f"WebSocket 連接斷開: {param}")
    finally:
        # 6. 確保連接從管理器中移除
        manager.remove_connection(websocket, param)
```

- 心跳機制實現：

```python
async def handle_websocket_communication(websocket: WebSocket):
    last_heartbeat = time.time()
    
    while True:
        # 設置接收超時
        try:
            # 接收客戶端消息（或心跳）
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            
            # 更新最後心跳時間
            if data == "ping":
                await websocket.send_text("pong")
                last_heartbeat = time.time()
                continue
                
            # ... 處理其他消息 ...
            
        except asyncio.TimeoutError:
            # 檢查是否超過心跳超時
            if time.time() - last_heartbeat > 60:  # 60秒無心跳則斷開
                logger.info("心跳超時，關閉連接")
                break
            
            # 發送心跳檢查
            try:
                await websocket.send_text("ping")
            except:
                logger.info("心跳檢查失敗，連接可能已斷開")
                break
```

- 優化數據傳輸：
  - 只發送真正變化的數據
  - 使用適當的數據壓縮或過濾
  - 批量更新而非頻繁單條更新
  - 按照客戶端訂閱的內容定制數據推送

## 安全性考量

1. **身份驗證**：所有非公開端點都必須使用 `Depends(get_current_active_user)` 進行保護
2. **權限控制**：管理員端點使用 `Depends(get_current_admin_user)` 確保只有管理員可訪問
3. **輸入驗證**：使用 Pydantic 模型和 FastAPI 查詢參數驗證所有輸入
4. **錯誤處理**：不要在錯誤消息中暴露敏感信息
5. **資料加密**：敏感數據（如 API 密鑰）必須加密存儲
6. **日誌安全**：確保不記錄敏感信息（密碼、令牌等）

## 監控與日誌

每個模組都應使用適當的日誌記錄：

```python
import logging
logger = logging.getLogger(__name__)

# 信息級別日誌
logger.info(f"處理請求: {request_id}")

# 警告級別日誌
logger.warning(f"異常情況: {condition}")

# 錯誤級別日誌（包含異常堆棧）
logger.error(f"操作失敗: {error_msg}", exc_info=True)
```

## 效能優化建議

1. **使用異步處理**：盡可能使用 `async/await` 以提高並發性能
2. **數據庫查詢優化**：避免 N+1 查詢問題，合理使用 ORM 關係載入
3. **緩存機制**：對頻繁訪問但不常變化的數據實施緩存
4. **分頁處理**：大數據集合必須實現分頁返回
5. **背景任務**：耗時操作應使用 `BackgroundTasks` 在背景執行 