# 後端工具模組 (Utils)

此資料夾包含專案所需的各種通用工具函數和類別，用於支援整個後端的功能運作。

## 目錄

- [日期時間工具 (date_utils.py)](#日期時間工具-date_utilspy)
- [交易所客戶端 (exchange.py)](#交易所客戶端-exchangepy)
- [交易所連接池 (connection_pool.py)](#交易所連接池-connection_poolpy)
- [WebSocket 管理器 (websocket_manager.py)](#websocket-管理器-websocket_managerpy)
- [WebSocket 數據格式化 (ws_data_formatter.py)](#websocket-數據格式化-ws_data_formatterpy)

## 日期時間工具 (date_utils.py)

提供日期時間相關的工具函數，支援台灣標準時間（UTC+8）的操作。

### 主要功能

- `get_taiwan_time()`: 獲取當前台灣標準時間
- `format_datetime()`: 格式化日期時間為指定格式的字符串
- `parse_datetime()`: 將字符串解析為日期時間對象
- `get_date_range()`: 獲取兩個日期之間的所有日期列表
- `get_time_ago()`: 計算距離給定時間戳過去了多長時間，以易讀格式返回（如 "2 分鐘前"）

### 使用示例

```python
from app.utils.date_utils import get_taiwan_time, format_datetime, get_time_ago

# 獲取當前台灣時間
now = get_taiwan_time()

# 格式化時間為字符串
formatted_time = format_datetime(now, "%Y年%m月%d日 %H:%M:%S")

# 獲取相對時間描述
relative_time = get_time_ago(timestamp)  # 返回如 "5 分鐘前"
```

## 交易所客戶端 (exchange.py)

提供統一的交易所客戶端實例創建功能，支援多種加密貨幣交易所。

### 主要功能

- `get_exchange_client()`: 根據提供的交易所類型、API密鑰和密碼創建相應的交易所客戶端實例

### 支援的交易所

- 幣安 (Binance)
- OKX
- Bybit
- Gate.io
- MEXC

### 使用示例

```python
from backend.utils.exchange import get_exchange_client
from app.schemas.trading import ExchangeEnum

# 創建幣安交易所客戶端
binance_client = await get_exchange_client(
    exchange=ExchangeEnum.BINANCE,
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# 使用客戶端獲取市場數據
markets = await binance_client.fetch_markets()
```

## 交易所連接池 (connection_pool.py)

管理並複用交易所客戶端連接，避免頻繁創建和銷毀連接，提供連接獲取、釋放和健康檢查等功能。

### 主要功能

- 連接池管理: 自動創建、複用、刷新和釋放交易所連接
- 健康檢查: 定期檢查連接健康狀態，確保連接可用
- 請求頻率限制: 實現交易所API請求的頻率限制管理
- 連接統計: 提供各種統計資訊，如創建連接數、重用次數等

### 主要方法

- `get_client()`: 獲取一個可用的交易所客戶端
- `release_client()`: 釋放客戶端到連接池
- `close_client()`: 關閉並移除客戶端
- `refresh_client()`: 刷新客戶端連接
- `check_client_health()`: 檢查客戶端連接健康狀態
- `cleanup_idle_connections()`: 清理空閒連接
- `get_stats()`: 獲取連接池統計信息

### 使用示例

```python
from backend.utils.connection_pool import ExchangeConnectionPool
from app.schemas.trading import ExchangeEnum

# 創建連接池
connection_pool = ExchangeConnectionPool()

# 獲取客戶端
client = await connection_pool.get_client(
    user_id=1001,
    exchange=ExchangeEnum.BINANCE,
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# 使用客戶端執行操作
result = await client.fetch_balance()

# 釋放客戶端到連接池
await connection_pool.release_client(user_id=1001, exchange=ExchangeEnum.BINANCE)
```

## WebSocket 管理器 (websocket_manager.py)

管理與各交易所的WebSocket連接，處理賬戶數據推送，支援實時獲取賬戶餘額、持倉和訂單更新信息。

### 主要功能

- WebSocket連接管理: 創建、監控和關閉與交易所的WebSocket連接
- 賬戶數據處理: 接收並處理來自交易所的實時賬戶數據
- 自動重連機制: 在連接斷開時自動嘗試重新建立連接
- 心跳維護: 定期發送心跳訊息保持連接活躍

### 主要方法

- `connect()`: 建立WebSocket連接
- `disconnect()`: 斷開WebSocket連接
- `get_account_data()`: 獲取賬戶數據
- `get_formatted_account_data()`: 獲取格式化的賬戶數據
- `get_connection_status()`: 獲取連接狀態
- `get_stats()`: 獲取WebSocket連接統計信息

### 使用示例

```python
from app.utils.websocket_manager import WebSocketManager
from app.schemas.trading import ExchangeEnum

# 創建WebSocket管理器
ws_manager = WebSocketManager()

# 建立連接
connected = await ws_manager.connect(
    user_id=1001,
    exchange=ExchangeEnum.BINANCE,
    api_key="your_api_key",
    api_secret="your_api_secret"
)

# 獲取賬戶數據
account_data = await ws_manager.get_account_data(
    user_id=1001,
    exchange=ExchangeEnum.BINANCE
)

# 斷開連接
await ws_manager.disconnect(user_id=1001, exchange=ExchangeEnum.BINANCE)
```

## WebSocket 數據格式化 (ws_data_formatter.py)

用於將交易所推送的WebSocket賬戶數據轉換為更易讀和理解的格式，支援多種交易所的數據格式化，提供統一的數據結構。

### 主要功能

- 數據格式標準化: 將不同交易所的WebSocket數據轉換為統一格式
- 易讀性優化: 將原始數據轉換為更易於理解和使用的結構
- 性能優化: 支援使用Cython加速版本提高處理效率

### 數據類型

- 賬戶餘額更新 (BALANCE)
- 持倉信息更新 (POSITION)
- 保證金預警 (MARGIN_CALL)
- 訂單更新 (ORDER)
- 資金費率結算 (FUNDING)

### 主要方法

- `format_account_update()`: 格式化賬戶更新數據
- `get_human_readable_summary()`: 獲取人類可讀的數據摘要

### 支援的交易所

- 幣安 (Binance)
- Bybit
- OKX

### 使用示例

```python
from app.utils.ws_data_formatter import WebSocketDataFormatter
from app.schemas.trading import ExchangeEnum

# 格式化原始WebSocket數據
formatted_data = WebSocketDataFormatter.format_account_update(
    exchange=ExchangeEnum.BINANCE,
    data=raw_websocket_data
)

# 獲取可讀性更好的摘要
summary = WebSocketDataFormatter.get_human_readable_summary(
    exchange=ExchangeEnum.BINANCE,
    data=formatted_data
)
``` 