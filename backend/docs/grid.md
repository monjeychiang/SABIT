# 網格交易功能設計文檔

## 1. 概述

網格交易是一種自動化交易策略，通過在特定價格區間內設置多個買入和賣出網格點，當價格在網格間波動時自動執行相應的買賣訂單。此功能旨在幫助交易者在震盪市場中通過頻繁的小額交易獲利。

## 2. 功能特點

### 2.1 交易類型支持
- 合約網格交易（U本位期貨）

### 2.2 網格模式
- 等距網格：按照等間距金額或百分比設置網格
- 等比網格：按照等比例設置網格

### 2.3 網格策略類型
- **多頭網格 (Bullish Grid)**：
  - 適用於看漲市場，預期價格有上漲趨勢
  - 網格區間設計偏向上方，上限價格較遠
  - 資金配置偏向上方網格，買入力度大於賣出
  - 初始倉位：偏向較多資金用於開倉買入
  - 風險控制：設置較大止盈，較小止損點位

- **中性網格 (Neutral Grid)**：
  - 適用於震盪市場，預期價格在特定區間內波動
  - 網格區間均衡分布，上下限距離當前價格相對均等
  - 資金平均分配在買入和賣出訂單
  - 初始倉位：資金均勻分配在各網格點
  - 風險控制：上下限同等距離的止盈止損

- **空頭網格 (Bearish Grid)**：
  - 適用於看跌市場，預期價格有下跌趨勢
  - 網格區間設計偏向下方，下限價格較遠
  - 資金配置偏向下方網格，賣出力度大於買入
  - 初始倉位：偏向較多資金用於開倉賣出（期貨）
  - 風險控制：設置較大止損，較小止盈點位

### 2.4 核心參數
- 交易對：支持所有交易所提供的U本位交易對
- 價格區間：上限價格和下限價格
- 網格數量：在價格區間內設置的網格數量（一般為5-50個）
- 投資金額：用於網格交易的資金總量
- 槓桿倍數：用於放大網格利潤
- 策略類型：多頭、中性或空頭網格

### 2.5 交易對規則與限制

每個交易對都有特定的交易規則和限制，系統將自動獲取並應用這些規則：

- **最小下單數量**：每個交易對都有最小下單數量要求
- **價格精度**：交易對支持的價格小數位數
- **數量精度**：交易對支持的數量小數位數
- **最小名義價值**：最小訂單金額要求（價格 × 數量）
- **槓桿範圍**：支持的最小和最大槓桿倍數
- **費用結構**：Maker和Taker費率
- **合約面值**：對於U本位合約的面值

範例（BTCUSDT）：
```
{
  "symbol": "BTCUSDT",
  "pricePrecision": 2,       // 價格精度：2位小數
  "quantityPrecision": 3,    // 數量精度：3位小數
  "minQty": 0.001,           // 最小下單數量：0.001 BTC
  "minNotional": 5.0,        // 最小訂單價值：5 USDT
  "maxLeverage": 125,        // 最大槓桿：125倍
  "takerFee": 0.0004,        // Taker費率：0.04%
  "makerFee": 0.0002         // Maker費率：0.02%
}
```

## 3. API設計

根據當前系統的 `trading.py` 文件，我們可以擴展以下API端點：

### 3.1 網格策略管理

```
POST /api/v1/grid/create/{exchange}  # 創建網格策略
  參數：
    - symbol: 交易對
    - grid_type: 網格類型（ARITHMETIC/GEOMETRIC）
    - strategy_type: 策略類型（BULLISH/NEUTRAL/BEARISH）
    - upper_price: 上限價格
    - lower_price: 下限價格
    - grid_number: 網格數量
    - total_investment: 總投資金額
    - leverage: 槓桿倍數（合約交易）
    - stop_loss: 止損價格（可選）
    - take_profit: 止盈價格（可選）
    
GET /api/v1/grid/list/{exchange}     # 獲取網格策略列表
GET /api/v1/grid/detail/{exchange}/{grid_id}  # 獲取網格策略詳情
PUT /api/v1/grid/update/{exchange}/{grid_id}  # 更新網格策略
DELETE /api/v1/grid/delete/{exchange}/{grid_id}  # 刪除網格策略
```

### 3.2 網格策略操作

```
POST /api/v1/grid/start/{exchange}/{grid_id}   # 啟動網格策略
POST /api/v1/grid/stop/{exchange}/{grid_id}    # 停止網格策略
POST /api/v1/grid/reset/{exchange}/{grid_id}   # 重置網格策略
```

### 3.3 網格績效統計

```
GET /api/v1/grid/performance/{exchange}/{grid_id}  # 獲取網格策略績效
GET /api/v1/grid/orders/{exchange}/{grid_id}       # 獲取網格策略相關訂單
```

### 3.4 交易對規則查詢

```
GET /api/v1/grid/symbol-rules/{exchange}/{symbol}  # 獲取特定交易對的規則
GET /api/v1/grid/all-symbols/{exchange}            # 獲取所有支持網格交易的交易對
```

## 4. 資料模型

### 4.1 網格策略模型

```python
class GridStrategy(Base):
    __tablename__ = "grid_strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    grid_type = Column(String, nullable=False)  # ARITHMETIC, GEOMETRIC, CUSTOM
    strategy_type = Column(String, nullable=False, default="NEUTRAL")  # BULLISH, NEUTRAL, BEARISH
    market_type = Column(String, nullable=False)  # SPOT, FUTURES
    upper_price = Column(Numeric(28, 8), nullable=False)
    lower_price = Column(Numeric(28, 8), nullable=False)
    grid_number = Column(Integer, nullable=False)
    total_investment = Column(Numeric(28, 8), nullable=False)
    per_grid_amount = Column(Numeric(28, 8), nullable=True)
    leverage = Column(Integer, nullable=True)  # 僅合約有效
    stop_loss = Column(Numeric(28, 8), nullable=True)
    take_profit = Column(Numeric(28, 8), nullable=True)
    profit_collection = Column(Boolean, default=False)  # 是否回收利潤
    status = Column(String, default="CREATED")  # CREATED, RUNNING, STOPPED, FINISHED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # 交易對規則緩存
    symbol_price_precision = Column(Integer, nullable=True)
    symbol_qty_precision = Column(Integer, nullable=True)
    symbol_min_qty = Column(Numeric(28, 8), nullable=True)
    symbol_min_notional = Column(Numeric(28, 8), nullable=True)
    symbol_max_leverage = Column(Integer, nullable=True)
    
    # 關聯
    user = relationship("User", back_populates="grid_strategies")
    grid_orders = relationship("GridOrder", back_populates="strategy")
```

### 4.2 網格訂單模型

```python
class GridOrder(Base):
    __tablename__ = "grid_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("grid_strategies.id"))
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    grid_index = Column(Integer, nullable=False)
    price = Column(Numeric(28, 8), nullable=False)
    quantity = Column(Numeric(28, 8), nullable=False)
    side = Column(String, nullable=False)  # BUY, SELL
    order_id = Column(String, nullable=True)
    status = Column(String, nullable=False)  # PLACED, FILLED, CANCELED
    created_at = Column(DateTime, default=datetime.utcnow)
    filled_at = Column(DateTime, nullable=True)
    profit = Column(Numeric(28, 8), nullable=True)
    
    # 關聯
    strategy = relationship("GridStrategy", back_populates="grid_orders")
```

### 4.3 交易對規則模型

```python
class SymbolRules(Base):
    __tablename__ = "symbol_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    price_precision = Column(Integer, nullable=False)
    quantity_precision = Column(Integer, nullable=False)
    min_quantity = Column(Numeric(28, 8), nullable=False)
    min_notional = Column(Numeric(28, 8), nullable=False)
    max_leverage = Column(Integer, nullable=True)
    taker_fee = Column(Numeric(28, 8), nullable=False)
    maker_fee = Column(Numeric(28, 8), nullable=False)
    contract_value = Column(Numeric(28, 8), nullable=True)  # 合約面值
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', name='uix_exchange_symbol'),
    )
```

## 5. 網格交易邏輯流程

### 5.1 創建網格策略

1. 獲取並驗證交易對規則
   - 檢查交易對是否支持網格交易
   - 獲取價格精度、數量精度、最小下單量等參數
2. 驗證用戶輸入的參數
   - 確保價格區間在合理範圍內
   - 確保網格數量不超過系統限制
   - 驗證投資金額滿足最小訂單要求
   - 驗證槓桿倍數在允許範圍內
3. 計算每個網格點的價格和數量
   - 根據價格精度對網格價格進行修正
   - 根據數量精度對網格數量進行修正
   - 確保每個網格訂單滿足最小下單量和最小名義價值要求
4. 檢查用戶賬戶餘額是否足夠
5. 創建並保存網格策略

### 5.2 啟動網格策略

1. 檢查策略狀態
2. 根據當前市場價格計算初始訂單
   - 應用交易對精度規則格式化價格和數量
   - 確保所有訂單符合交易所規則
3. 確保用戶的WebSocket連接已建立（如未建立則創建）
4. 通過WebSocket API下單並記錄網格訂單信息
5. 更新策略狀態為運行中

### 5.3 網格運行機制

1. 當買單成交（通過WebSocket訂閱接收通知）：
   - 在更高一格的價位設置賣單
   - 確保新訂單符合交易對規則
   - 更新網格訂單狀態

2. 當賣單成交（通過WebSocket訂閱接收通知）：
   - 在更低一格的價位設置買單
   - 確保新訂單符合交易對規則
   - 計算並記錄利潤
   - 更新網格訂單狀態

### 5.4 停止網格策略

1. 取消所有未成交的網格訂單（通過WebSocket API）
2. 計算總利潤和績效
3. 更新策略狀態為已停止
4. 如果用戶沒有其他運行中的網格策略，可選擇關閉WebSocket連接

### 5.5 基於策略類型的網格計算

根據不同的策略類型，我們需要調整網格的分布和資金配置：

1. **多頭網格計算**
   - 網格密度：上方網格間距較大，下方網格間距較小
   - 資金分配：上方網格分配更多資金，下方網格分配較少資金
   - 初始倉位計算：
     ```python
     # 多頭網格資金分配範例
     def calculate_bullish_grid_allocation(strategy, grid_prices, current_price):
         # 當前價格在網格中的位置
         current_index = 0
         for i, price in enumerate(grid_prices):
             if price > current_price:
                 current_index = i - 1
                 break
         
         # 總網格數
         total_grids = len(grid_prices) - 1
         
         # 分配比例：上方網格獲得60-70%的資金，下方網格獲得30-40%的資金
         upper_allocation = 0.65  # 上方網格資金比例
         lower_allocation = 0.35  # 下方網格資金比例
         
         # 計算上下方網格數量
         upper_grids = total_grids - current_index - 1
         lower_grids = current_index
         
         # 計算每個網格的資金（不均勻分配）
         per_grid_investments = []
         
         if lower_grids > 0:
             lower_per_grid = (strategy.total_investment * lower_allocation) / lower_grids
             for i in range(lower_grids):
                 # 越接近當前價格的網格獲得更多資金
                 grid_investment = lower_per_grid * (0.8 + 0.4 * (i / lower_grids))
                 per_grid_investments.append(grid_investment)
         
         if upper_grids > 0:
             upper_per_grid = (strategy.total_investment * upper_allocation) / upper_grids
             for i in range(upper_grids):
                 # 越遠離當前價格的網格獲得更少資金
                 grid_investment = upper_per_grid * (1.2 - 0.4 * (i / upper_grids))
                 per_grid_investments.append(grid_investment)
         
         return per_grid_investments
     ```

2. **中性網格計算**
   - 網格密度：均勻分布，間距一致
   - 資金分配：均勻分配，每個網格獲得相同資金
   - 初始倉位計算：
     ```python
     # 中性網格資金分配範例
     def calculate_neutral_grid_allocation(strategy, grid_prices, current_price):
         # 網格數量
         total_grids = len(grid_prices) - 1
         
         # 每個網格平均分配資金
         per_grid_investment = strategy.total_investment / total_grids
         
         # 返回均勻分配的資金列表
         return [per_grid_investment] * total_grids
     ```

3. **空頭網格計算**
   - 網格密度：下方網格間距較大，上方網格間距較小
   - 資金分配：下方網格分配更多資金，上方網格分配較少資金
   - 初始倉位計算：
     ```python
     # 空頭網格資金分配範例
     def calculate_bearish_grid_allocation(strategy, grid_prices, current_price):
         # 當前價格在網格中的位置
         current_index = 0
         for i, price in enumerate(grid_prices):
             if price > current_price:
                 current_index = i - 1
                 break
         
         # 總網格數
         total_grids = len(grid_prices) - 1
         
         # 分配比例：下方網格獲得60-70%的資金，上方網格獲得30-40%的資金
         upper_allocation = 0.35  # 上方網格資金比例
         lower_allocation = 0.65  # 下方網格資金比例
         
         # 計算上下方網格數量
         upper_grids = total_grids - current_index - 1
         lower_grids = current_index
         
         # 計算每個網格的資金（不均勻分配）
         per_grid_investments = []
         
         if lower_grids > 0:
             lower_per_grid = (strategy.total_investment * lower_allocation) / lower_grids
             for i in range(lower_grids):
                 # 越遠離當前價格的網格獲得更多資金
                 grid_investment = lower_per_grid * (1.2 - 0.4 * (i / lower_grids))
                 per_grid_investments.append(grid_investment)
         
         if upper_grids > 0:
             upper_per_grid = (strategy.total_investment * upper_allocation) / upper_grids
             for i in range(upper_grids):
                 # 越接近當前價格的網格獲得更多資金
                 grid_investment = upper_per_grid * (0.8 + 0.4 * (i / upper_grids))
                 per_grid_investments.append(grid_investment)
         
         return per_grid_investments
     ```

4. **綜合網格生成函數**
   ```python
   async def calculate_grid_orders_by_strategy_type(strategy, current_price):
       """根據網格策略類型和當前價格計算網格訂單"""
       # 獲取交易對規則
       rules = await get_symbol_rules(strategy.exchange, strategy.symbol)
       
       # 計算網格價格點
       grid_prices = []
       if strategy.grid_type == "ARITHMETIC":  # 等距網格
           step = (strategy.upper_price - strategy.lower_price) / strategy.grid_number
           for i in range(strategy.grid_number + 1):
               price = strategy.lower_price + i * step
               # 按照價格精度格式化
               grid_prices.append(round_to_precision(price, rules["price_precision"]))
       elif strategy.grid_type == "GEOMETRIC":  # 等比網格
           ratio = (strategy.upper_price / strategy.lower_price) ** (1 / strategy.grid_number)
           for i in range(strategy.grid_number + 1):
               price = strategy.lower_price * (ratio ** i)
               # 按照價格精度格式化
               grid_prices.append(round_to_precision(price, rules["price_precision"]))
       
       # 根據策略類型計算資金分配
       if strategy.strategy_type == "BULLISH":
           grid_investments = calculate_bullish_grid_allocation(strategy, grid_prices, current_price)
       elif strategy.strategy_type == "BEARISH":
           grid_investments = calculate_bearish_grid_allocation(strategy, grid_prices, current_price)
       else:  # 默認為NEUTRAL
           grid_investments = calculate_neutral_grid_allocation(strategy, grid_prices, current_price)
       
       # 計算當前價格所在網格索引
       current_index = 0
       for i, price in enumerate(grid_prices):
           if price > current_price:
               current_index = i - 1
               break
       
       # 計算訂單
       orders = []
       # 生成上方網格賣單
       for i in range(current_index + 1, len(grid_prices) - 1):
           # 計算賣單數量
           investment = grid_investments[i - 1]
           price = grid_prices[i]
           qty = investment / price
           # 格式化數量
           qty = round_to_precision(qty, rules["quantity_precision"])
           # 應用最小訂單量和最小名義價值規則
           if qty < rules["min_quantity"]:
               qty = rules["min_quantity"]
           if qty * price < rules["min_notional"]:
               qty = round_to_precision(rules["min_notional"] / price, rules["quantity_precision"])
           
           orders.append({
               "price": price,
               "quantity": qty,
               "side": "SELL",
               "grid_index": i
           })
       
       # 生成下方網格買單
       for i in range(current_index, 0, -1):
           # 計算買單數量
           investment = grid_investments[i - 1]
           price = grid_prices[i]
           qty = investment / price
           # 格式化數量
           qty = round_to_precision(qty, rules["quantity_precision"])
           # 應用最小訂單量和最小名義價值規則
           if qty < rules["min_quantity"]:
               qty = rules["min_quantity"]
           if qty * price < rules["min_notional"]:
               qty = round_to_precision(rules["min_notional"] / price, rules["quantity_precision"])
           
           orders.append({
               "price": price,
               "quantity": qty,
               "side": "BUY",
               "grid_index": i
           })
       
       return orders
   ```

## 6. 實現考量

### 6.1 技術實現方式

我們將採用WebSocket進行實時網格交易管理，並實現連接共享機制：

1. **用戶級WebSocket連接共享**：
   - 同一用戶的多個網格策略共用同一個WebSocket連接
   - 為每個交易所維護一個獨立的WebSocket連接

   ```python
   # WebSocket連接管理（基於用戶+交易所）
   async def get_or_create_user_websocket(user_id, exchange, db):
       # 檢查用戶是否已有對應交易所的WebSocket連接
       key = f"{user_id}:{exchange}"
       if key in websocket_connections:
           return websocket_connections[key]
       
       # 獲取API密鑰信息
       api_key = db.query(ExchangeAPI).filter(
           ExchangeAPI.user_id == user_id, 
           ExchangeAPI.exchange == exchange
       ).first()
       
       if not api_key:
           raise ValueError(f"未找到{exchange}的API密鑰")
       
       # 解密API密鑰
       from ...core.security import decrypt_api_key
       
       decrypted_key = decrypt_api_key(api_key.api_key)
       decrypted_secret = decrypt_api_key(api_key.api_secret)
       
       if not decrypted_key or not decrypted_secret:
           raise ValueError("API密鑰解密失敗")
           
       # 記錄加密API密鑰的長度（不記錄實際內容以保護安全）
       key_length = len(decrypted_key) if decrypted_key else 0
       secret_length = len(decrypted_secret) if decrypted_secret else 0
       logger.debug(f"[GridWS] API密鑰長度: {key_length}, API密鑰密碼長度: {secret_length}")
       
       # 建立WebSocket連接
       ws_url = "wss://ws-fapi.binance.com/ws-fapi/v1"
       websocket = await establish_websocket_connection(ws_url)
       
       # 通過session.logon進行WebSocket認證
       timestamp = int(time.time() * 1000)
       params = {
           "apiKey": decrypted_key,
           "timestamp": timestamp
       }
       
       # 計算簽名
       query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
       signature = hmac.new(
           decrypted_secret.encode('utf-8'),
           query_string.encode('utf-8'),
           hashlib.sha256
       ).hexdigest()
       
       params["signature"] = signature
       
       # 發送登錄請求
       login_request = {
           "id": f"auth_{user_id}_{int(time.time())}",
           "method": "session.logon",
           "params": params
       }
       
       await websocket.send(json.dumps(login_request))
       login_response = await websocket.receive()
       login_data = json.loads(login_response)
       
       if login_data.get("status") != 200:
           error_msg = login_data.get("error", {}).get("msg", "未知錯誤")
           raise ValueError(f"WebSocket認證失敗: {error_msg}")
           
       logger.info(f"[GridWS] 用戶 {user_id} 的 {exchange} WebSocket連接認證成功")
       
       # 保存連接到連接池
       websocket_connections[key] = {
           "websocket": websocket,
           "api_key": decrypted_key,  # 安全起見，實際實現中應考慮加密存儲或使用更安全的方式
           "api_secret": decrypted_secret
       }
       
       return websocket_connections[key]
   ```

2. **WebSocket API交易操作**：
   - 利用Binance WebSocket API執行交易操作，在同一連接上實現不同功能
   - 獲取帳戶資訊和下單操作共用同一個WebSocket連接
   - 不需要為不同功能建立多個連接

   ```python
   # 獲取帳戶資訊 
   async def get_account_data_via_websocket(websocket_conn):
       """通過WebSocket獲取帳戶信息"""
       # 發送帳戶資訊請求
       account_request = {
           "id": f"account_{int(time.time())}",
           "method": "account.status",  # 使用account.status方法獲取帳戶資訊
           "params": {
               "timestamp": int(time.time() * 1000)
           }
       }
       
       # 使用已認證的WebSocket連接發送請求
       websocket = websocket_conn["websocket"]
       await websocket.send(json.dumps(account_request))
       response = await websocket.receive()
       account_data = json.loads(response)
       
       if account_data.get("status") != 200:
           error_msg = account_data.get("error", {}).get("msg", "未知錯誤")
           logger.error(f"[GridWS] 獲取帳戶資訊失敗: {error_msg}")
           return None
           
       return account_data.get("result", {})
   
   # 透過WebSocket下單
   async def place_grid_order_via_websocket(websocket_conn, order_data, grid_strategy_id, grid_index):
       """通過WebSocket發送下單請求"""
       # 為訂單添加網格策略標識，用於回調處理
       client_order_id = f"grid_{grid_strategy_id}_{grid_index}_{int(time.time() * 1000)}"
       order_data["newClientOrderId"] = client_order_id
       
       # 添加必要的時間戳
       order_data["timestamp"] = int(time.time() * 1000)
       
       # 構建訂單請求
       order_request = {
           "id": client_order_id,
           "method": "order.place",  # 使用order.place方法下單
           "params": order_data
       }
       
       # 使用已認證的WebSocket連接發送請求
       websocket = websocket_conn["websocket"]
       await websocket.send(json.dumps(order_request))
       response = await websocket.receive()
       order_response = json.loads(response)
       
       if order_response.get("status") != 200:
           error_msg = order_response.get("error", {}).get("msg", "未知錯誤")
           logger.error(f"[GridWS] 網格訂單下單失敗: {error_msg}")
           return None
           
       logger.info(f"[GridWS] 成功下單網格訂單 {client_order_id}")
       return order_response.get("result", {})
   
   # 取消訂單
   async def cancel_grid_order_via_websocket(websocket_conn, symbol, orderId):
       """通過WebSocket取消訂單"""
       cancel_data = {
           "symbol": symbol,
           "orderId": orderId,
           "timestamp": int(time.time() * 1000)
       }
       
       # 構建取消訂單請求
       cancel_request = {
           "id": f"cancel_{orderId}_{int(time.time())}",
           "method": "order.cancel",  # 使用order.cancel方法取消訂單
           "params": cancel_data
       }
       
       # 使用已認證的WebSocket連接發送請求
       websocket = websocket_conn["websocket"]
       await websocket.send(json.dumps(cancel_request))
       response = await websocket.receive()
       cancel_response = json.loads(response)
       
       if cancel_response.get("status") != 200:
           error_msg = cancel_response.get("error", {}).get("msg", "未知錯誤")
           logger.error(f"[GridWS] 取消訂單失敗: {error_msg}")
           return None
           
       logger.info(f"[GridWS] 成功取消訂單 {orderId}")
       return cancel_response.get("result", {})
   ```

3. **WebSocket回調處理機制**：
   - 實現訂單更新事件處理器，將訂單狀態變化分發到對應的網格策略
   ```python
   # WebSocket回調處理器
   async def handle_order_update(user_id, exchange, message):
       # 解析訂單信息
       order_id = message.get("orderId")
       client_order_id = message.get("clientOrderId", "")
       status = message.get("status")
       
       # 檢查是否為網格訂單
       if client_order_id.startswith("grid_"):
           # 解析網格策略ID和網格索引
           _, grid_id, grid_index, _ = client_order_id.split("_")
           
           # 轉發給對應的網格策略處理器
           await process_grid_order_update(
               user_id, exchange, int(grid_id), int(grid_index), 
               order_id, status, message
           )
   ```

### 6.2 交易對規則管理

1. **規則獲取與緩存**：
   ```python
   # 交易對規則緩存
   symbol_rules_cache = {}  # {exchange:symbol -> rules}
   
   async def get_symbol_rules(exchange, symbol, force_refresh=False):
       """獲取交易對規則，優先從緩存獲取，必要時從交易所API獲取"""
       cache_key = f"{exchange}:{symbol}"
       
       # 檢查緩存
       if not force_refresh and cache_key in symbol_rules_cache:
           # 檢查緩存是否過期（24小時）
           cached_rules = symbol_rules_cache[cache_key]
           if cached_rules["updated_at"] > (datetime.now() - timedelta(hours=24)):
               return cached_rules
       
       # 從交易所API獲取最新規則
       try:
           # 調用交易所API
           if exchange == "binance":
               rules = await get_binance_symbol_rules(symbol)
           else:
               raise ValueError(f"不支持的交易所: {exchange}")
               
           # 更新緩存
           rules["updated_at"] = datetime.now()
           symbol_rules_cache[cache_key] = rules
           
           # 存入數據庫
           await save_symbol_rules_to_db(exchange, symbol, rules)
           
           return rules
       except Exception as e:
           logger.error(f"獲取{exchange}:{symbol}交易對規則失敗: {str(e)}")
           # 如果緩存中有數據，返回過期數據
           if cache_key in symbol_rules_cache:
               return symbol_rules_cache[cache_key]
           raise
   ```

2. **規則應用於訂單計算**：
   ```python
   async def calculate_grid_orders(strategy, current_price):
       """根據網格策略和當前價格計算訂單，應用交易對規則"""
       # 獲取交易對規則
       rules = await get_symbol_rules(strategy.exchange, strategy.symbol)
       
       # 計算網格價格點
       grid_prices = []
       if strategy.grid_type == "ARITHMETIC":  # 等距網格
           step = (strategy.upper_price - strategy.lower_price) / strategy.grid_number
           for i in range(strategy.grid_number + 1):
               price = strategy.lower_price + i * step
               # 按照價格精度格式化
               grid_prices.append(round_to_precision(price, rules["price_precision"]))
       elif strategy.grid_type == "GEOMETRIC":  # 等比網格
           ratio = (strategy.upper_price / strategy.lower_price) ** (1 / strategy.grid_number)
           for i in range(strategy.grid_number + 1):
               price = strategy.lower_price * (ratio ** i)
               # 按照價格精度格式化
               grid_prices.append(round_to_precision(price, rules["price_precision"]))
       
       # 計算每格投資金額
       per_grid_investment = strategy.total_investment / strategy.grid_number
       
       # 計算訂單
       orders = []
       for i in range(len(grid_prices) - 1):
           # 確定買賣方向
           if grid_prices[i] < current_price < grid_prices[i+1]:
               # 當前價格在此網格內，上方掛賣單，下方掛買單
               for j in range(i + 1, len(grid_prices) - 1):
                   # 計算賣單數量
                   qty = per_grid_investment / grid_prices[j]
                   # 按照數量精度格式化
                   qty = round_to_precision(qty, rules["quantity_precision"])
                   # 確保滿足最小下單量
                   if qty < rules["min_quantity"]:
                       qty = rules["min_quantity"]
                   # 確保滿足最小名義價值
                   if qty * grid_prices[j] < rules["min_notional"]:
                       qty = round_to_precision(rules["min_notional"] / grid_prices[j], rules["quantity_precision"])
                   
                   orders.append({
                       "price": grid_prices[j],
                       "quantity": qty,
                       "side": "SELL",
                       "grid_index": j
                   })
               
               for j in range(i, -1, -1):
                   # 計算買單數量
                   qty = per_grid_investment / grid_prices[j]
                   # 按照數量精度格式化
                   qty = round_to_precision(qty, rules["quantity_precision"])
                   # 確保滿足最小下單量
                   if qty < rules["min_quantity"]:
                       qty = rules["min_quantity"]
                   # 確保滿足最小名義價值
                   if qty * grid_prices[j] < rules["min_notional"]:
                       qty = round_to_precision(rules["min_notional"] / grid_prices[j], rules["quantity_precision"])
                   
                   orders.append({
                       "price": grid_prices[j],
                       "quantity": qty,
                       "side": "BUY",
                       "grid_index": j
                   })
               break
       
       return orders
   ```

### 6.3 風險控制措施

- 設置全局止損：當價格突破網格下限且下跌幅度超過設定閾值時觸發
- 設置全局止盈：當價格突破網格上限且上漲幅度超過設定閾值時觸發
- 虧損控制：單個網格虧損超過設定值時自動暫停策略
- WebSocket連接監控：定期檢查連接健康狀況，在連接斷開時自動重連
- 異常處理：交易所API異常、網絡故障等情況的處理機制
- 訂單合規性檢查：確保每個訂單符合交易所的最小下單量、價格精度等規則

### 6.4 效能優化考慮

1. **WebSocket連接池管理**：
   ```python
   class GridWebSocketManager:
       def __init__(self):
           # 用戶級WebSocket連接池 {user_id:exchange -> connection}
           self.connections = {}
           # 策略到WebSocket的映射 {grid_strategy_id -> (user_id, exchange)}
           self.strategy_mappings = {}
           # 連接引用計數 {user_id:exchange -> count}
           self.reference_counts = {}
       
       async def get_connection_for_strategy(self, user_id, exchange, grid_strategy_id):
           # 為網格策略獲取共享的WebSocket連接
           key = f"{user_id}:{exchange}"
           
           # 記錄策略映射
           self.strategy_mappings[grid_strategy_id] = (user_id, exchange)
           
           # 更新引用計數
           if key in self.reference_counts:
               self.reference_counts[key] += 1
           else:
               self.reference_counts[key] = 1
           
           # 獲取或創建連接
           if key not in self.connections:
               self.connections[key] = await self._create_connection(user_id, exchange)
           
           return self.connections[key]
       
       async def release_connection_for_strategy(self, grid_strategy_id):
           # 當策略停止時釋放WebSocket連接引用
           if grid_strategy_id not in self.strategy_mappings:
               return
           
           user_id, exchange = self.strategy_mappings[grid_strategy_id]
           key = f"{user_id}:{exchange}"
           
           # 減少引用計數
           if key in self.reference_counts:
               self.reference_counts[key] -= 1
               # 如果沒有更多引用，關閉連接
               if self.reference_counts[key] <= 0:
                   await self._close_connection(key)
                   del self.connections[key]
                   del self.reference_counts[key]
           
           # 移除策略映射
           del self.strategy_mappings[grid_strategy_id]
   ```

2. **WebSocket訂閱優化**：
   - 為共享的WebSocket連接動態管理訂閱內容
   - 根據活躍網格策略的交易對自動訂閱和取消訂閱市場數據
   ```python
   async def optimize_websocket_subscriptions(websocket_manager, user_id, exchange):
       # 獲取用戶所有活躍的網格策略
       active_strategies = await get_active_grid_strategies(user_id, exchange)
       
       # 提取需要訂閱的交易對
       symbols = set()
       for strategy in active_strategies:
           symbols.add(strategy.symbol)
       
       # 優化WebSocket訂閱
       await websocket_manager.update_market_data_subscriptions(user_id, exchange, symbols)
   ```

3. **異步事件處理**：
   - 使用異步任務隊列處理WebSocket事件，避免阻塞主WebSocket連接
   ```python
   # 使用消息隊列處理WebSocket事件
   async def process_websocket_events(user_id, exchange):
       queue = asyncio.Queue()
       websocket = websocket_connections.get(f"{user_id}:{exchange}")
       
       if not websocket:
           return
           
       # 事件處理器任務
       async def event_processor():
           while True:
               event = await queue.get()
               try:
                   await handle_websocket_event(user_id, exchange, event)
               except Exception as e:
                   logger.error(f"處理WebSocket事件錯誤: {str(e)}")
               finally:
                   queue.task_done()
       
       # 啟動處理器任務
       processor_task = asyncio.create_task(event_processor())
       
       # 從WebSocket接收消息並放入隊列
       try:
           while True:
               message = await websocket.receive()
               await queue.put(message)
       except Exception as e:
           logger.error(f"WebSocket接收錯誤: {str(e)}")
       finally:
           # 清理
           processor_task.cancel()
   ```

## 7. 前端界面設計建議

### 7.1 網格策略創建頁面

- 交易對選擇器（顯示支持的交易對列表）
- 網格類型選擇（等距/等比）
- **網格策略類型選擇**（多頭/中性/空頭），並提供每種策略的說明
- 價格區間設置（顯示當前價格作為參考）
- 網格數量滑動條
- 投資金額輸入
- 槓桿倍數選擇器（顯示交易對支持的最大槓桿）
- 風險控制參數設置
- 預覽網格分布圖表（根據所選策略類型顯示不同的網格分布）
- **交易對規則展示區**：
  - 顯示所選交易對的最小下單量
  - 顯示價格和數量精度
  - 顯示交易費率
  - 顯示預估每網格利潤
- **策略表現預測**：
  - 根據所選策略類型顯示不同市場條件下的表現預測
  - 提供風險評估和建議

### 7.2 網格策略管理頁面

- 策略列表顯示（ID、交易對、狀態、收益率等）
- 一鍵啟動/停止按鈕
- 簡要績效圖表
- WebSocket連接狀態指示器

### 7.3 網格策略詳情頁面

- 網格參數詳情
- 交易對規則信息
- 網格訂單列表
- 實時執行狀態視覺化
- 累計收益圖表
- 訂單歷史記錄

## 8. 與現有系統整合

### 8.1 權限管理

```python
# 參考現有的用戶鑑權方式
@router.post("/grid/create/{exchange}", response_model=BaseResponse)
async def create_grid_strategy(
    exchange: ExchangeEnum,
    grid_request: GridCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> Any:
    # 實現...
```

### 8.2 收費模式建議(站不)

- 基礎用戶：限制同時運行的網格策略數量（如2個）
- VIP用戶：更多同時運行的網格策略數量（如5個）
- 專業用戶：無限制網格策略數量，並支援更多高級功能

### 8.3 WebSocket連接管理整合

```python
# 在trading.py中添加WebSocket連接管理模塊
# 網格交易服務將利用此連接池
class TradingService:
    # ... 現有代碼 ...
    
    async def initialize_grid_websocket_if_needed(self, user, db, exchange):
        """
        為用戶初始化網格交易WebSocket連接
        """
        # 檢查用戶是否已有活躍的網格策略
        active_strategies = await self.get_active_grid_strategies(user.id, exchange)
        
        if not active_strategies:
            # 沒有活躍策略，不需要初始化
            return None
            
        # 獲取或創建WebSocket連接
        return await self.grid_websocket_manager.get_connection_for_user(user.id, exchange)
```

### 8.4 交易對規則整合

```python
# 在現有的TradingService中添加交易對規則相關方法
class TradingService:
    # ... 現有代碼 ...
    
    async def get_symbol_rules(self, exchange, symbol, force_refresh=False):
        """
        獲取交易對規則，整合到現有系統
        """
        # 檢查緩存或數據庫
        rules = await self._get_cached_symbol_rules(exchange, symbol)
        
        if rules and not force_refresh:
            return rules
            
        # 從交易所API獲取
        try:
            if exchange == ExchangeEnum.BINANCE:
                return await self._get_binance_symbol_rules(symbol)
            else:
                raise ValueError(f"不支持的交易所: {exchange}")
        except Exception as e:
            logger.error(f"獲取{exchange}:{symbol}交易對規則失敗: {str(e)}")
            if rules:  # 如果有緩存，返回過期數據
                return rules
            raise
    
    async def validate_grid_parameters(self, exchange, grid_request):
        """
        驗證網格參數是否符合交易對規則
        """
        # 獲取交易對規則
        rules = await self.get_symbol_rules(exchange, grid_request.symbol)
        
        # 驗證邏輯
        # 1. 檢查價格精度
        upper_price = round_to_precision(grid_request.upper_price, rules["price_precision"])
        lower_price = round_to_precision(grid_request.lower_price, rules["price_precision"])
        if upper_price != grid_request.upper_price or lower_price != grid_request.lower_price:
            return {
                "valid": False,
                "message": f"價格需要符合精度要求: {rules['price_precision']}位小數"
            }
            
        # 2. 檢查槓桿範圍
        if grid_request.leverage > rules["max_leverage"]:
            return {
                "valid": False,
                "message": f"槓桿倍數超過最大限制: {rules['max_leverage']}"
            }
            
        # 3. 驗證策略類型
        valid_strategy_types = ["BULLISH", "NEUTRAL", "BEARISH"]
        if grid_request.strategy_type not in valid_strategy_types:
            return {
                "valid": False,
                "message": f"策略類型無效，必須是以下之一: {', '.join(valid_strategy_types)}"
            }
            
        # 4. 預先計算並檢查網格訂單
        grid_count = grid_request.grid_number
        price_step = (upper_price - lower_price) / grid_count
        per_grid_investment = grid_request.total_investment / grid_count
        
        # 檢查單個網格訂單是否滿足最小下單量
        sample_price = lower_price + price_step/2  # 取中間價格作為樣本
        sample_qty = per_grid_investment / sample_price
        sample_qty = round_to_precision(sample_qty, rules["quantity_precision"])
        
        if sample_qty < rules["min_quantity"]:
            return {
                "valid": False,
                "message": f"網格訂單數量({sample_qty})低於最小下單量({rules['min_quantity']})"
            }
            
        # 5. 檢查訂單名義價值
        notional = sample_qty * sample_price
        if notional < rules["min_notional"]:
            return {
                "valid": False,
                "message": f"訂單價值({notional})低於最小訂單價值({rules['min_notional']})"
            }
        
        # 6. 針對不同策略類型的特殊驗證
        if grid_request.strategy_type == "BULLISH":
            # 針對多頭網格的額外檢查（例如確保上限價格足夠高）
            current_price = await self.get_current_price(exchange, grid_request.symbol)
            price_range_percentage = (upper_price - current_price) / current_price * 100
            if price_range_percentage < 5:  # 建議上限至少比當前價格高5%
                return {
                    "valid": False,
                    "message": f"多頭策略建議上限價格至少比當前價格高5%，當前設置僅高{price_range_percentage:.2f}%"
                }
        
        elif grid_request.strategy_type == "BEARISH":
            # 針對空頭網格的額外檢查（例如確保下限價格足夠低）
            current_price = await self.get_current_price(exchange, grid_request.symbol)
            price_range_percentage = (current_price - lower_price) / current_price * 100
            if price_range_percentage < 5:  # 建議下限至少比當前價格低5%
                return {
                    "valid": False,
                    "message": f"空頭策略建議下限價格至少比當前價格低5%，當前設置僅低{price_range_percentage:.2f}%"
                }
        
        return {
            "valid": True,
            "rules": rules,
            "normalized_params": {
                "upper_price": upper_price,
                "lower_price": lower_price
            }
        }
```

## 9. 參考資料

- Binance API文檔：[U本位合約 WebSocket API](https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/websocket-api)
- Binance WebSocket下單文檔：[New Order (TRADE)](https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/websocket-api#new-ordertrade)
- Binance交易對信息文檔：[Exchange Information](https://binance-docs.github.io/apidocs/futures/en/#exchange-information)
- 現有系統API：參考 `backend/app/api/endpoints/trading.py`

## 10. 待辦事項和優先級

1. **高優先級**
   - 實現交易對規則獲取與緩存系統
   - 實現用戶級WebSocket連接共享機制
   - 基本網格交易策略邏輯實現
   - 訂單參數驗證與格式化機制

2. **中優先級**
   - WebSocket事件處理器和消息分發系統
   - 網格監控和自動調整機制
   - 前端界面實現
   - 交易對規則顯示組件

3. **低優先級**
   - 高級網格功能（自適應網格、AI輔助網格等）
   - 多策略組合管理
   - WebSocket連接監控和性能指標收集

## 11. 詳細運作流程

網格交易系統的完整運作流程如下：

### 11.1 網格策略初始化流程

1. **用戶建立網格**
   - 用戶在前端選擇交易對、網格類型和參數
   - 前端根據用戶參數實時計算和顯示網格分布
   - 前端執行初步參數驗證（確保參數在合理範圍內）
   - 用戶確認後提交創建請求

2. **後端參數驗證**
   - 獲取交易對最新規則（價格精度、數量精度等）
   - 驗證網格參數合規性（槓桿、最小訂單值等）
   - 格式化價格和數量以符合交易所要求
   - 計算資金需求並驗證用戶賬戶餘額

3. **網格計算**
   - 根據網格類型計算網格點位置：
     - 等距網格：均勻分布在上下限之間
     - 等比網格：按比例分布在上下限之間
   - 調整網格點價格以符合交易所價格精度
   - 優化網格分布（避免過密或過疏）

4. **下單預準備**
   - 獲取當前市場價格
   - 將網格點分為「市價以上」和「市價以下」兩組
   - 準備初始訂單批次（買單在當前價格下方，賣單在當前價格上方）
   - 生成唯一的訂單標識符，用於後續追蹤

### 11.2 訂單執行與監控流程

1. **初始訂單下單**
   - 確保WebSocket連接已建立
   - 獲取或建立用戶WebSocket連接
   - 將初始網格訂單通過WebSocket API批量發送
   - 接收訂單確認並更新數據庫狀態

2. **訂單狀態監控**
   - 通過WebSocket接收實時訂單更新
   - 解析訂單ID識別對應的網格策略和位置
   - 當訂單狀態更新時觸發相應處理邏輯
   - 維護網格訂單實時狀態

3. **網格訂單成交處理**
   - 買單成交時：
     - 在上一個網格位置（更高價格）創建賣單
     - 將成交訂單標記為已完成
     - 記錄已使用資金和持倉變化
   - 賣單成交時：
     - 在下一個網格位置（更低價格）創建買單
     - 計算並記錄網格利潤
     - 更新網格訂單狀態

4. **異常情況處理**
   - 訂單被拒絕：調整參數後重試或通知用戶
   - 訂單部分成交：處理剩餘部分訂單
   - 網絡中斷：實現重連機制並恢復監控
   - WebSocket連接異常：自動重新建立連接

### 11.3 風險管理流程

1. **止盈止損觸發**
   - 監控市場價格變動
   - 當價格超出網格上限+設定值時觸發全局止盈
   - 當價格低於網格下限-設定值時觸發全局止損
   - 執行平倉操作並取消所有未成交訂單

2. **流動性不足監控**
   - 監控訂單成交時間
   - 標記長時間未成交的訂單
   - 提供自動調整網格參數的建議
   - 可選擇性地微調網格位置以提高成交率

3. **資金管理**
   - 監控資金使用情況
   - 確保網格策略不會耗盡用戶可用資金
   - 預留部分資金用於手續費支付
   - 若槓桿交易，監控保證金率並預警

### 11.4 網格優化與調整流程

1. **動態網格調整**
   - 基於市場波動性調整網格間距
   - 在市場趨勢轉變時提示可能需要重設網格
   - 提供網格參數自動優化建議
   - 允許用戶在不停止策略的情況下微調參數

2. **網格重置流程**
   - 用戶請求重置網格
   - 系統取消所有未成交訂單
   - 可選擇平倉持有頭寸
   - 按照新參數創建網格並重新下單

### 11.5 終止流程

1. **用戶終止**
   - 用戶請求停止網格策略
   - 系統取消所有未成交訂單
   - 計算並展示最終收益統計
   - 更新策略狀態為已停止

2. **自動終止**
   - 觸發全局止盈/止損
   - 發生嚴重市場異常
   - 資金不足無法持續運作
   - 交易所API長時間無法連接

