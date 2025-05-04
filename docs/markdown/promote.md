# 加密貨幣交易系統開發文檔

## 項目概述

加密貨幣交易系統是一個企業級全棧應用程序，為加密貨幣投資者和交易者提供專業的交易工具和數據分析能力。系統結合了現代Web技術和區塊鏈技術，打造高性能、安全可靠的交易環境。

### 系統目標

- **降低交易門檻**：為普通用戶提供簡單直觀的交易界面，降低加密貨幣交易的技術門檻
- **提高交易效率**：通過自動化交易策略和實時市場數據，提高用戶交易決策效率
- **保障資金安全**：採用業界標準安全措施，確保用戶資金和個人信息安全
- **支持策略交易**：提供網格交易等自動化策略，實現被動收益
- **完善數據分析**：提供專業的技術分析工具和市場指標，輔助交易決策

### 目標用戶

1. **零售投資者**：尋求簡單易用界面的個人投資者
2. **專業交易者**：需要高級分析工具的頻繁交易用戶
3. **策略交易者**：偏好自動化交易系統的被動投資者
4. **加密貨幣愛好者**：關注區塊鏈技術發展的技術用戶

## 系統架構

本系統採用現代化的微服務架構，結合前後端分離的設計，提供高性能、可擴展和安全的交易環境。

### 系統架構圖

```
+------------------------+       +---------------------+
|                        |       |                     |
|    前端應用層          |<----->|    API網關          |
|    (Vue.js + Vite)     |       |    (Nginx/Traefik)  |
|                        |       |                     |
+------------------------+       +----------+----------+
                                           |
     +---------------------------------------------------+
     |                                   |               |
+----v-----------+  +------------------+ | +-------------v--------+
|                |  |                  | | |                      |
|  用戶服務      |  |  交易服務        | | |  市場數據服務        |
|  (FastAPI)     |  |  (FastAPI)       | | |  (FastAPI+WebSocket) |
|                |  |                  | | |                      |
+----+-----------+  +--------+---------+ | +----------+----------+
     |                       |           |            |
     |                       |           |            |
+----v-----------+  +--------v---------+ | +----------v----------+
|                |  |                  | | |                      |
|  用戶數據庫    |  |  交易數據庫      | | |  市場數據庫          |
|  (PostgreSQL)  |  |  (PostgreSQL)    | | |  (TimeScaleDB)       |
|                |  |                  | | |                      |
+----------------+  +------------------+ | +----------------------+
                                         |
                             +-----------v------------+
                             |                        |
                             |  任務隊列             |
                             |  (Redis/RabbitMQ)     |
                             |                        |
                             +------------------------+
```

### 核心技術棧

#### 前端技術棧

- **框架**: Vue 3
- **構建工具**: Vite
- **狀態管理**: Pinia
- **UI框架**: Element Plus
- **圖表庫**: TradingView Lightweight Charts
- **WebSocket**: Socket.io-client
- **HTTP客戶端**: Axios
- **TypeScript**: 類型安全
- **CSS預處理器**: SCSS

#### 後端技術棧

- **API框架**: FastAPI
- **ORM**: SQLAlchemy
- **數據庫**: 
  - PostgreSQL: 主要關係型數據庫
  - TimeScaleDB: 時序數據存儲
  - Redis: 緩存和隊列
- **消息隊列**: RabbitMQ/Celery
- **WebSocket**: FastAPI WebSockets
- **認證**: JWT + OAuth2
- **任務調度**: APScheduler
- **監控**: Prometheus + Grafana

#### DevOps工具鏈

- **容器化**: Docker
- **編排**: Kubernetes
- **CI/CD**: GitLab CI
- **監控**: Prometheus, Grafana
- **日誌收集**: ELK Stack
- **負載均衡**: Nginx/Traefik
- **服務網格**: Istio

### 數據庫設計

系統採用多數據庫架構，針對不同數據類型和訪問模式優化:

#### 用戶數據庫 (PostgreSQL)

主要表結構:

```sql
-- 用戶表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    role VARCHAR(20) DEFAULT 'user'
);

-- 用戶設置表
CREATE TABLE user_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    notification_email BOOLEAN DEFAULT TRUE,
    notification_app BOOLEAN DEFAULT TRUE,
    theme VARCHAR(20) DEFAULT 'light',
    chart_preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- API密鑰表
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    key_name VARCHAR(50) NOT NULL,
    api_key VARCHAR(64) UNIQUE NOT NULL,
    api_secret VARCHAR(64) NOT NULL,
    permissions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP WITH TIME ZONE
);
```

#### 交易數據庫 (PostgreSQL)

主要表結構:

```sql
-- 訂單表
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    type VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    price DECIMAL(18, 8),
    quantity DECIMAL(18, 8) NOT NULL,
    filled_quantity DECIMAL(18, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 交易表
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) REFERENCES orders(order_id),
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(18, 8) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    side VARCHAR(10) NOT NULL,
    fee DECIMAL(18, 8) NOT NULL,
    fee_currency VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 資產表
CREATE TABLE balances (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    currency VARCHAR(10) NOT NULL,
    available DECIMAL(18, 8) NOT NULL,
    frozen DECIMAL(18, 8) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, currency)
);

-- 網格交易策略表
CREATE TABLE grid_strategies (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    strategy_id VARCHAR(50) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    upper_price DECIMAL(18, 8) NOT NULL,
    lower_price DECIMAL(18, 8) NOT NULL,
    grid_number INTEGER NOT NULL,
    total_investment DECIMAL(18, 8) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 市場數據庫 (TimeScaleDB)

主要表結構:

```sql
-- K線數據表 (使用TimescaleDB的超表)
CREATE TABLE kline_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open DECIMAL(18, 8) NOT NULL,
    high DECIMAL(18, 8) NOT NULL,
    low DECIMAL(18, 8) NOT NULL,
    close DECIMAL(18, 8) NOT NULL,
    volume DECIMAL(18, 8) NOT NULL
);

-- 創建超表
SELECT create_hypertable('kline_data', 'time');

-- 創建索引
CREATE INDEX idx_kline_symbol ON kline_data(symbol, interval, time DESC);

-- 市場行情表
CREATE TABLE ticker_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(18, 8) NOT NULL,
    volume_24h DECIMAL(18, 8) NOT NULL,
    change_24h DECIMAL(8, 4) NOT NULL,
    high_24h DECIMAL(18, 8) NOT NULL,
    low_24h DECIMAL(18, 8) NOT NULL
);

-- 創建超表
SELECT create_hypertable('ticker_data', 'time');

-- 創建索引
CREATE INDEX idx_ticker_symbol ON ticker_data(symbol, time DESC);
```

## 部署架構

### 雲基礎設施

系統可部署於多種雲平台：

- **AWS**: 利用EKS(Elastic Kubernetes Service)進行容器編排
- **GCP**: 利用GKE(Google Kubernetes Engine)進行容器編排
- **Azure**: 利用AKS(Azure Kubernetes Service)進行容器編排

也支持自託管環境部署。


```

### 高可用性設計

系統采用多方面措施確保高可用性：

1. **多可用區部署**：
   - 跨多個可用區部署
   - 服務實例的自動負載均衡

2. **自動擴展**：
   - 基於CPU/內存使用率的水平Pod自動擴展
   - 基於自定義指標(如請求隊列長度)的自動擴展

3. **故障恢復**：
   - 服務健康檢查和自動重啟
   - 數據庫故障轉移配置
   - 持久化存儲備份策略

4. **流量管理**：
   - 輸入流量限制
   - 服務間的斷路器模式
   - 平滑部署和金絲雀發布

## 核心功能詳解

### 用戶管理系統

#### Google OAuth 2.0登錄流程

完整的OAuth 2.0流程實現，支持用戶使用Google賬號快速登錄系統：

1. **登錄發起**：
   - 前端引導用戶到Google授權頁面
   - 生成並驗證狀態參數，防止CSRF攻擊
   - 請求適當的權限範圍（email、profile）

2. **授權回調處理**：
   - 驗證授權碼和狀態參數
   - 交換授權碼獲取訪問令牌和刷新令牌
   - 獲取用戶信息並創建或更新用戶記錄

3. **令牌管理**：
   - 簽發JWT訪問令牌和刷新令牌
   - 設置適當的過期時間（訪問令牌30分鐘，刷新令牌10天）
   - 實現令牌自動刷新機制

4. **認證狀態持久化**：
   - 前端本地存儲令牌
   - 應用啟動時驗證令牌有效性
   - 頁面切換時維持認證狀態

#### 用戶權限管理

系統實現了基於角色的訪問控制（RBAC）：

- **普通用戶**：可訪問基本交易和市場功能
- **VIP用戶**：可訪問高級分析工具和更低的交易費率
- **管理員**：可訪問用戶管理和系統設置

權限判斷通過JWT令牌攜帶的用戶角色信息實現，前後端結合驗證：

```typescript
// 前端路由守衛示例
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore();
  
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    // 顯示無權限提示
    window.dispatchEvent(new CustomEvent('show-toast', { 
      detail: { type: 'error', message: '需要管理員權限訪問此頁面' }
    }));
    next('/');
    return;
  }
  
  next();
});
```

```python
# 後端權限驗證裝飾器示例
def admin_required(func):
    @wraps(func)
    async def wrapper(current_user: User = Depends(get_current_user), *args, **kwargs):
        if not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="需要管理員權限"
            )
        return await func(current_user=current_user, *args, **kwargs)
    return wrapper
```

#### 用戶資料管理

用戶可以管理個人資料和系統設置：

1. **個人信息**：用戶名、頭像、聯繫方式
2. **安全設置**：密碼更新、API密鑰管理
3. **通知偏好**：交易通知、價格提醒、系統公告
4. **UI偏好**：明暗主題、語言設置、時區設置

### 市場數據系統

#### 實時價格信息

系統利用WebSocket技術提供實時的加密貨幣市場數據：

1. **價格更新**：
   - 毫秒級價格更新
   - 支持多交易對並行監控
   - 價格變化視覺指示（漲跌顏色標記）

2. **技術指標**：
   - 移動平均線（MA）
   - 相對強弱指數（RSI）
   - 布林帶（BOLL）
   - 交易量加權平均價格（VWAP）

3. **深度圖**：
   - 展示訂單簿深度
   - 可視化買賣壓力
   - 互動式價格探索

WebSocket連接管理詳解：

```javascript
// 前端WebSocket連接示例
export function useMarketWebSocket(symbol) {
  const marketData = ref(null);
  const connectionStatus = ref('disconnected');
  let ws = null;
  let reconnectAttempts = 0;
  const maxReconnectAttempts = 5;
  
  const connect = () => {
    connectionStatus.value = 'connecting';
    ws = new WebSocket(`wss://api.example.com/ws/market/${symbol}`);
    
    ws.onopen = () => {
      connectionStatus.value = 'connected';
      reconnectAttempts = 0;
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        marketData.value = data;
      } catch (error) {
        console.error('Failed to parse market data', error);
      }
    };
    
    ws.onclose = () => {
      connectionStatus.value = 'disconnected';
      if (reconnectAttempts < maxReconnectAttempts) {
        reconnectAttempts++;
        setTimeout(connect, 1000 * reconnectAttempts);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error', error);
      ws.close();
    };
  };
  
  const disconnect = () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close();
    }
  };
  
  onMounted(connect);
  onBeforeUnmount(disconnect);
  
  return {
    marketData,
    connectionStatus,
    reconnect: connect
  };
}
```

#### 市場概覽

提供全面的市場概覽功能：

1. **市場排名**：
   - 按市值、交易量和價格變化排序
   - 自定義篩選和排序
   - 收藏常用交易對

2. **市場熱圖**：
   - 可視化整體市場趨勢
   - 分區域展示不同類別資產
   - 顏色編碼展示漲跌幅度

3. **趨勢分析**：
   - 跨時間段比較
   - 相關性分析
   - 波動性指標

#### 圖表分析

使用Chart.js和自定義組件實現專業級交易圖表：

1. **蠟燭圖**：
   - 多時間週期支持（1分鐘到1週）
   - 自定義指標疊加
   - 圖表互動和縮放

2. **技術分析工具**：
   - 趨勢線和通道
   - 斐波那契回調
   - 支撐/阻力位標記

3. **數據導出**：
   - CSV/Excel格式導出
   - 圖表截圖功能
   - 自定義報告生成

圖表配置示例：

```javascript
// 蠟燭圖配置示例
const candlestickOptions = {
  scales: {
    x: {
      type: 'time',
      time: {
        unit: 'day',
        tooltipFormat: 'yyyy-MM-dd HH:mm'
      },
      grid: {
        display: false
      }
    },
    y: {
      position: 'right',
      grid: {
        color: 'rgba(160, 160, 160, 0.1)'
      }
    }
  },
  plugins: {
    legend: {
      display: false
    },
    tooltip: {
      callbacks: {
        label: (context) => {
          const data = context.raw;
          return [
            `開盤: ${data.o}`,
            `最高: ${data.h}`,
            `最低: ${data.l}`,
            `收盤: ${data.c}`,
            `成交量: ${data.v}`
          ];
        }
      }
    }
  },
  responsive: true,
  maintainAspectRatio: false
};
```

### 交易功能

#### 交易下單系統

系統支持多種交易下單方式：

1. **限價單**：
   - 自定義價格和數量
   - 價格驗證和小數位控制
   - 市場價格參考

2. **市價單**：
   - 基於最新市場價格
   - 滑點保護
   - 執行速度優先

3. **止損限價單**：
   - 組合止損和限價功能
   - 觸發價格和執行價格分離
   - 風險管理工具

交易表單驗證示例：

```typescript
// 交易表單驗證
const validateOrderForm = (form: OrderForm): ValidationResult => {
  const errors: Record<string, string> = {};
  
  // 驗證交易類型
  if (!['limit', 'market', 'stop_limit'].includes(form.type)) {
    errors.type = '無效的交易類型';
  }
  
  // 驗證交易方向
  if (!['buy', 'sell'].includes(form.side)) {
    errors.side = '無效的交易方向';
  }
  
  // 驗證數量
  if (!form.quantity || form.quantity <= 0) {
    errors.quantity = '數量必須大於0';
  } else if (form.quantity < minOrderSize) {
    errors.quantity = `數量不能小於最小訂單大小 ${minOrderSize}`;
  }
  
  // 對於限價單，驗證價格
  if (form.type === 'limit' && (!form.price || form.price <= 0)) {
    errors.price = '價格必須大於0';
  }
  
  // 對於止損限價單，驗證觸發價格
  if (form.type === 'stop_limit' && (!form.stopPrice || form.stopPrice <= 0)) {
    errors.stopPrice = '觸發價格必須大於0';
  }
  
  return {
    isValid: Object.keys(errors).length === 0,
    errors
  };
};
```

#### 訂單管理

全面的訂單生命周期管理：

1. **訂單列表**：
   - 開放訂單和歷史訂單視圖
   - 狀態過濾和排序
   - 批量操作支持

2. **訂單詳情**：
   - 詳細執行信息
   - 相關市場數據
   - 執行時間分析

3. **訂單操作**：
   - 取消訂單
   - 修改未成交訂單
   - 重複下單功能

#### 資產管理

用戶資產全面管理：

1. **資產概覽**：
   - 總資產價值
   - 可用和凍結餘額
   - 資產分配餅圖

2. **資產明細**：
   - 按幣種展示餘額
   - 歷史價值變化
   - 盈虧分析

3. **資金流水**：
   - 充值/提現記錄
   - 交易手續費記錄
   - 導出報表功能

### 自動化交易系統

#### 網格交易策略

專業級網格交易功能實現：

1. **策略配置**：
   - 價格區間設置
   - 網格數量和間距
   - 資金分配策略

2. **策略監控**：
   - 實時執行狀態
   - 下單成功率
   - 盈虧實時計算

3. **策略調整**：
   - 運行中參數調整
   - 暫停/恢復功能
   - 緊急止損保護

網格交易策略配置示例：

```typescript
// 網格交易策略配置接口
interface GridStrategyConfig {
  symbol: string;            // 交易對，如 "BTC/USDT"
  upperPrice: number;        // 上限價格
  lowerPrice: number;        // 下限價格
  gridNumber: number;        // 網格數量
  totalInvestment: number;   // 總投資金額
  profitTarget?: number;     // 可選的利潤目標
  stopLoss?: number;         // 可選的止損價格
  autoRebalance: boolean;    // 是否自動重新平衡
  runTimeLimit?: number;     // 可選的運行時間限制（小時）
}

// 計算網格交易參數
const calculateGridParameters = (config: GridStrategyConfig) => {
  // 驗證輸入
  if (config.upperPrice <= config.lowerPrice) {
    throw new Error('上限價格必須大於下限價格');
  }
  
  if (config.gridNumber < 2) {
    throw new Error('網格數量必須至少為2');
  }
  
  // 計算網格間距
  const priceRange = config.upperPrice - config.lowerPrice;
  const gridInterval = priceRange / config.gridNumber;
  
  // 計算每個網格的投資金額
  const investmentPerGrid = config.totalInvestment / config.gridNumber;
  
  // 生成網格價格點
  const gridPrices = Array.from({ length: config.gridNumber + 1 }, (_, i) => {
    return config.lowerPrice + i * gridInterval;
  });
  
  // 計算理論收益率（不考慮交易費用）
  const theoreticalProfitPercentage = ((config.upperPrice / config.lowerPrice - 1) / config.gridNumber) * 100;
  
  return {
    gridInterval,
    investmentPerGrid,
    gridPrices,
    theoreticalProfitPercentage
  };
};
```

#### 回測系統

策略回測功能支持：

1. **歷史數據回測**：
   - 導入歷史價格數據
   - 模擬策略執行
   - 性能指標分析

2. **參數優化**：
   - 網格參數敏感性分析
   - 最優參數推薦
   - 多策略比較

3. **風險評估**：
   - 最大回撤計算
   - 風險調整後回報
   - 極端市場情景測試

### 通知系統

#### 實時通知

多渠道通知系統：

1. **應用內通知**：
   - 實時彈窗提醒
   - 通知中心管理
   - 標記已讀/未讀

2. **郵件通知**：
   - 交易確認郵件
   - 安全警報
   - 系統公告

3. **自定義通知**：
   - 價格提醒
   - 訂單狀態變更
   - 賬戶活動提醒

通知系統實現示例：

```python
# 後端通知服務示例
class NotificationService:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
    
    async def create_notification(self, notification_type: str, title: str, content: str, is_read: bool = False):
        """創建新通知"""
        notification = Notification(
            user_id=self.user_id,
            type=notification_type,
            title=title,
            content=content,
            is_read=is_read,
            created_at=datetime.now(CHINA_TZ)
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        # 檢查用戶通知設置
        notification_settings = self.db.query(NotificationSetting).filter(
            NotificationSetting.user_id == self.user_id
        ).first()
        
        # 如果設置允許，發送推送通知
        if notification_settings and getattr(notification_settings, f"enable_{notification_type}_push", True):
            await self.send_push_notification(notification)
        
        # 如果設置允許，發送郵件通知
        if notification_settings and getattr(notification_settings, f"enable_{notification_type}_email", False):
            await self.send_email_notification(notification)
        
        return notification
    
    async def send_push_notification(self, notification: Notification):
        """發送推送通知"""
        # 實現推送通知邏輯...
        pass
    
    async def send_email_notification(self, notification: Notification):
        """發送郵件通知"""
        # 實現郵件通知邏輯...
        pass
    
    def mark_as_read(self, notification_id: int):
        """將通知標記為已讀"""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == self.user_id
        ).first()
        
        if notification:
            notification.is_read = True
            notification.read_at = datetime.now(CHINA_TZ)
            self.db.commit()
            return True
        return False
    
    def get_unread_count(self):
        """獲取未讀通知數量"""
        return self.db.query(Notification).filter(
            Notification.user_id == self.user_id,
            Notification.is_read == False
        ).count()
```

#### 通知偏好設置

用戶可自定義通知設置：

1. **通知類型**：
   - 交易通知
   - 系統通知
   - 安全通知

2. **通知渠道**：
   - 應用內
   - 郵件
   - 瀏覽器推送

3. **通知頻率**：
   - 實時通知
   - 批量通知
   - 免打擾時段

### 管理功能

#### 用戶管理

管理員用戶管理功能：

1. **用戶列表**：
   - 用戶搜索和過濾
   - 用戶狀態管理
   - 用戶詳細信息查看

2. **權限管理**：
   - 用戶角色分配
   - 特殊權限設置
   - 臨時訪問授權

3. **活動監控**：
   - 用戶登錄歷史
   - 活躍用戶統計
   - 異常行為檢測

#### 系統監控

系統狀態監控工具：

1. **服務健康**：
   - API服務狀態
   - 數據庫連接狀態
   - 外部服務集成狀態

2. **性能指標**：
   - 響應時間監控
   - 資源使用率
   - 錯誤率統計

3. **安全監控**：
   - 登錄嘗試跟蹤
   - API調用頻率監控
   - 異常訪問模式檢測

## API服務

系統提供豐富的API服務，包括:

1. **認證API**: 用戶註冊、登錄、令牌刷新
2. **通知API**: 獲取和管理通知
3. **交易API**: 執行交易操作
4. **市場API**: 獲取市場數據
5. **系統API**: 系統狀態和信息
6. **管理員API**: 管理功能
7. **設置API**: 用戶設置
8. **用戶API**: 用戶信息
9. **網格交易API**: 自動化交易策略管理
10. **個人資料API**: 用戶資料管理

## API服務詳解

系統提供豐富的RESTful API服務，所有API遵循統一的設計原則和錯誤處理機制。

### API設計原則

1. **RESTful設計**：
   - 使用HTTP方法表示操作（GET、POST、PUT、DELETE）
   - 使用URL表示資源
   - 使用HTTP狀態碼表示結果

2. **版本控制**：
   - 所有API包含版本號（如`/api/v1/`）
   - 向後兼容的API更新策略
   - 版本遷移路徑明確

3. **認證機制**：
   - JWT令牌認證
   - 令牌在Authorization頭中傳遞
   - 刷新令牌延長會話

4. **統一響應格式**：
```json
{
  "data": {},      // 响应数据
  "message": "",   // 响应消息
  "status": 200,   // 状态码
  "timestamp": "", // 时间戳
  "error": null    // 错误信息(如有)
}
```

5. **错误处理**：
   - 明确的错误代码
   - 详细的错误消息
   - 开发环境下提供堆栈跟踪

### 关键API端点详解

#### 1. 认证API

##### 用户注册
- **端点**: `/api/v1/auth/register`
- **方法**: `POST`
- **请求体**:
```json
{
  "username": "example_user",
  "email": "user@example.com",
  "password": "securepassword",
  "confirm_password": "securepassword"
}
```
- **响应**:
```json
{
  "data": {
    "id": 1,
    "username": "example_user",
    "email": "user@example.com",
    "is_active": true,
    "is_verified": false,
    "created_at": "2023-03-15T10:30:00"
  },
  "message": "用户注册成功",
  "status": 201,
  "timestamp": "2023-03-15T10:30:00",
  "error": null
}
```

##### 用户登录
- **端点**: `/api/v1/auth/login`
- **方法**: `POST`
- **请求体**:
```json
{
  "username": "example_user",
  "password": "securepassword"
}
```
- **响应**:
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "refresh_token": "5a4b3c2d1e...",
    "expires_in": 1800
  },
  "message": "登录成功",
  "status": 200,
  "timestamp": "2023-03-15T10:35:00",
  "error": null
}
```

##### 令牌刷新
- **端点**: `/api/v1/auth/refresh`
- **方法**: `POST`
- **请求体**:
```json
{
  "refresh_token": "5a4b3c2d1e..."
}
```
- **响应**:
```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  },
  "message": "令牌刷新成功",
  "status": 200,
  "timestamp": "2023-03-15T10:55:00",
  "error": null
}
```

#### 2. 市场数据API

##### 获取市场列表
- **端点**: `/api/v1/markets`
- **方法**: `GET`
- **参数**:
  - `limit`: 返回结果数量限制 (默认 50)
  - `sort_by`: 排序字段 (默认 "volume")
  - `order`: 排序方式 (默认 "desc")
- **响应**:
```json
{
  "data": {
    "markets": [
      {
        "symbol": "BTC/USDT",
        "base_currency": "BTC",
        "quote_currency": "USDT",
        "price": 50000.00,
        "change_24h": 2.5,
        "volume_24h": 1500000.00,
        "high_24h": 51000.00,
        "low_24h": 49000.00
      },
      // 更多市场数据...
    ],
    "total": 150
  },
  "message": "获取市场列表成功",
  "status": 200,
  "timestamp": "2023-03-15T11:00:00",
  "error": null
}
```

##### 获取K线数据
- **端点**: `/api/v1/markets/{symbol}/klines`
- **方法**: `GET`
- **参数**:
  - `interval`: 时间间隔 (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
  - `limit`: 返回结果数量 (默认 100)
  - `start_time`: 开始时间戳 (毫秒)
  - `end_time`: 结束时间戳 (毫秒)
- **响应**:
```json
{
  "data": {
    "symbol": "BTC/USDT",
    "interval": "1h",
    "klines": [
      {
        "open_time": 1615810800000,
        "open": 50000.00,
        "high": 50500.00,
        "low": 49800.00,
        "close": 50300.00,
        "volume": 100.50,
        "close_time": 1615814399999
      },
      // 更多K线数据...
    ]
  },
  "message": "获取K线数据成功",
  "status": 200,
  "timestamp": "2023-03-15T11:05:00",
  "error": null
}
```

#### 3. 交易API

##### 创建订单
- **端点**: `/api/v1/trading/orders`
- **方法**: `POST`
- **请求头**: 
  - `Authorization: Bearer {access_token}`
- **请求体**:
```json
{
  "symbol": "BTC/USDT",
  "type": "limit",
  "side": "buy",
  "price": 50000.00,
  "quantity": 0.1,
  "time_in_force": "GTC"
}
```
- **响应**:
```json
{
  "data": {
    "order_id": "12345678",
    "status": "new",
    "symbol": "BTC/USDT",
    "type": "limit",
    "side": "buy",
    "price": 50000.00,
    "quantity": 0.1,
    "filled_quantity": 0,
    "created_at": "2023-03-15T11:10:00"
  },
  "message": "订单创建成功",
  "status": 201,
  "timestamp": "2023-03-15T11:10:00",
  "error": null
}
```

##### 获取订单列表
- **端点**: `/api/v1/trading/orders`
- **方法**: `GET`
- **请求头**: 
  - `Authorization: Bearer {access_token}`
- **参数**:
  - `symbol`: 交易对符号 (可选)
  - `status`: 订单状态 (new, filled, partially_filled, canceled)
  - `limit`: 返回结果数量 (默认 50)
  - `page`: 页码 (默认 1)
- **响应**:
```json
{
  "data": {
    "orders": [
      {
        "order_id": "12345678",
        "status": "new",
        "symbol": "BTC/USDT",
        "type": "limit",
        "side": "buy",
        "price": 50000.00,
        "quantity": 0.1,
        "filled_quantity": 0,
        "created_at": "2023-03-15T11:10:00"
      },
      // 更多订单...
    ],
    "total": 25,
    "page": 1,
    "limit": 50
  },
  "message": "获取订单列表成功",
  "status": 200,
  "timestamp": "2023-03-15T11:15:00",
  "error": null
}
```

#### 4. 网格交易API

##### 创建网格策略
- **端点**: `/api/v1/grid/strategies`
- **方法**: `POST`
- **请求头**: 
  - `Authorization: Bearer {access_token}`
- **请求体**:
```json
{
  "symbol": "BTC/USDT",
  "upper_price": 55000.00,
  "lower_price": 45000.00,
  "grid_number": 10,
  "total_investment": 1000.00,
  "run_type": "live"
}
```
- **响应**:
```json
{
  "data": {
    "strategy_id": "grid-12345",
    "symbol": "BTC/USDT",
    "upper_price": 55000.00,
    "lower_price": 45000.00,
    "grid_number": 10,
    "grid_interval": 1000.00,
    "total_investment": 1000.00,
    "status": "active",
    "created_at": "2023-03-15T11:20:00"
  },
  "message": "网格策略创建成功",
  "status": 201,
  "timestamp": "2023-03-15T11:20:00",
  "error": null
}
```

### WebSocket API

系统提供WebSocket API用于实时数据传输：

#### 1. 连接建立

```
wss://api.example.com/ws
```

#### 2. 认证

连接后发送认证消息：

```json
{
  "action": "auth",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### 3. 订阅主题

订阅市场数据：

```json
{
  "action": "subscribe",
  "topics": ["market:BTC/USDT", "trades:BTC/USDT"]
}
```

#### 4. 接收消息

市场数据消息格式：

```json
{
  "topic": "market:BTC/USDT",
  "data": {
    "symbol": "BTC/USDT",
    "price": 50123.45,
    "change_24h": 2.5,
    "volume_24h": 1500000.00,
    "bid": 50123.00,
    "ask": 50124.00,
    "timestamp": 1615812345678
  }
}
```

交易数据消息格式：

```json
{
  "topic": "trades:BTC/USDT",
  "data": {
    "id": "trade-12345",
    "symbol": "BTC/USDT",
    "price": 50123.45,
    "quantity": 0.05,
    "side": "buy",
    "timestamp": 1615812345678
  }
}
```

## 详细开发环境搭建

### 前端开发环境配置

#### 详细的环境要求

- **Node.js**: v16.x 或更高
- **npm**: v7.x 或更高
- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **浏览器**: Chrome 90+, Firefox 90+, Edge 90+, Safari 14+
- **IDE**: VSCode (推荐)，WebStorm或任何现代JavaScript IDE

#### 详细的安装和配置步骤

1. **克隆项目**:
   ```bash
   git clone [项目仓库URL]
   cd [项目目录]/frontend
   ```

2. **安装Node.js和npm**:
   - Windows/macOS: 从[官方网站](https://nodejs.org/)下载安装包
   - Linux:
     ```bash
     curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
     sudo apt-get install -y nodejs
     ```

3. **安装依赖**:
   ```bash
   npm install
   ```

4. **VSCode配置**:
   - 安装推荐的扩展:
     - Volar (禁用Vetur)
     - ESLint
     - Prettier
     - TypeScript Vue Plugin
     - i18n Ally (如果使用国际化)

5. **配置环境变量**:
   创建`.env.local`文件:
   ```
   VITE_API_BASE_URL=http://localhost:8000
   VITE_GOOGLE_CLIENT_ID=[YOUR_GOOGLE_CLIENT_ID]
   VITE_WEBSOCKET_URL=ws://localhost:8000/ws
   VITE_DEBUG=true
   ```

6. **启动开发服务器**:
   ```bash
   npm run dev
   ```
   
   前端将在 http://localhost:5175 启动，自动打开默认浏览器

7. **代码检查**:
   ```bash
   npm run lint
   ```

8. **类型检查**:
   ```bash
   npm run type-check
   ```

### 后端开发环境配置

#### 详细的环境要求

- **Python**: 3.9+ (推荐3.10)
- **数据库**: SQLite (开发), PostgreSQL 12+ (生产)
- **操作系统**: Windows 10/11, macOS 10.15+, Linux
- **IDE**: PyCharm, VSCode或任何支持Python的IDE
- **虚拟环境管理**: venv, conda或pyenv

#### 详细的安装和配置步骤

1. **克隆项目**:
   ```bash
   git clone [项目仓库URL]
   cd [项目目录]/backend
   ```

2. **创建虚拟环境**:
   ```bash
   # 使用venv
   python -m venv venv
   
   # 激活虚拟环境 (Windows)
   venv\Scripts\activate
   
   # 激活虚拟环境 (macOS/Linux)
   source venv/bin/activate
   ```

3. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**:
   创建或编辑`.env`文件:
   ```
   DATABASE_URL=sqlite:///./trading.db
   SECRET_KEY=your-secret-key-change-in-production
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   REFRESH_TOKEN_EXPIRE_DAYS=10
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
   FRONTEND_URL=http://localhost:5175
   FRONTEND_CALLBACK_URL=http://localhost:5175/auth/callback
   DEBUG=True
   ENVIRONMENT=development
   ```

5. **初始化数据库**:
   ```bash
   python rebuild_db.py
   ```

6. **运行Alembic迁移**:
   ```bash
   alembic upgrade head
   ```

7. **启动服务器**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   
   后端API服务将在 http://localhost:8000 启动，API文档在 http://localhost:8000/docs

8. **运行测试**:
   ```bash
   pytest
   ```

9. **代码覆盖率检查**:
   ```bash
   pytest --cov=app tests/
   ```

## 详细部署指南

### 前端部署详解

#### 开发环境构建

```bash
# 开发环境构建
npm run build -- --mode development
```

#### 生产环境构建

```bash
# 生产环境构建
npm run build
```

#### Nginx配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    # 重定向HTTP到HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    # SSL配置
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # 压缩配置
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;
    
    # 前端静态文件
    location / {
        root /var/www/html/crypto-trading;
        index index.html;
        try_files $uri $uri/ /index.html;
        
        # 缓存配置
        expires 1d;
        add_header Cache-Control "public, max-age=86400";
        
        # HTML文件不缓存
        location ~* \.html$ {
            expires -1;
            add_header Cache-Control "no-store, no-cache, must-revalidate";
        }
    }
    
    # API代理
    location /api/ {
        proxy_pass http://backend-server:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket代理
    location /ws/ {
        proxy_pass http://backend-server:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Docker部署

```dockerfile
# 构建阶段
FROM node:16-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# 生产阶段
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 后端部署详解

#### 生产环境配置

```bash
# 生产环境变量配置
DATABASE_URL=postgresql://user:password@database:5432/crypto_trading
SECRET_KEY=[生成一个强密钥]
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
GOOGLE_CLIENT_ID=[生产环境ID]
GOOGLE_CLIENT_SECRET=[生产环境密钥]
GOOGLE_REDIRECT_URI=https://your-domain.com/api/v1/auth/google/callback
FRONTEND_URL=https://your-domain.com
FRONTEND_CALLBACK_URL=https://your-domain.com/auth/callback
DEBUG=False
ENVIRONMENT=production
```

#### Gunicorn部署配置

```python
# gunicorn_conf.py
import multiprocessing

# 服务器配置
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"

# 进程名称
proc_name = "crypto_trading_api"

# 日志配置
loglevel = "info"
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"

# 进程管理
max_requests = 1000
max_requests_jitter = 50
timeout = 60
keepalive = 5
```

启动命令:
```bash
gunicorn -c gunicorn_conf.py app.main:app
```

#### Docker Compose部署

```yaml
version: '3.8'

services:
  db:
    image: postgres:14-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data/
    env_file:
      - ./.env.prod.db
    environment:
      - POSTGRES_USER=crypto_user
      - POSTGRES_PASSWORD=crypto_password
      - POSTGRES_DB=crypto_trading
    ports:
      - "5432:5432"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    command: gunicorn -c gunicorn_conf.py app.main:app
    volumes:
      - ./backend:/app
      - ./logs:/app/logs
    env_file:
      - ./.env.prod
    depends_on:
      - db
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    volumes:
      - ./frontend/nginx:/etc/nginx/conf.d
    ports:
      - "80:80"
      - "443:443"
    depends_on:
      - backend

volumes:
  postgres_data:
```

### 持续集成/持续部署 (CI/CD)

#### GitHub Actions配置示例

```yaml
name: Build and Deploy

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          cd backend
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest --cov=app tests/

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Use Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '16'
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      - name: Run tests
        run: |
          cd frontend
          npm run test:unit

  deploy:
    needs: [test-backend, test-frontend]
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Deploy to production
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /path/to/project
            git pull
            docker-compose -f docker-compose.prod.yml down
            docker-compose -f docker-compose.prod.yml up -d --build
```

## 扩展与优化详解

### 性能优化详细策略

#### 前端性能优化

1. **代码分割**:
   ```javascript
   // 使用动态导入实现路由懒加载
   const routes = [
     {
       path: '/',
       component: () => import('@/views/Home.vue')
     },
     {
       path: '/trading',
       component: () => import('@/views/Trading.vue')
     }
   ];
   ```

2. **静态资源优化**:
   - 使用CDN分发静态资源
   - 图片压缩和WebP格式转换
   - 懒加载图片和组件

3. **Vue性能优化**:
   - 合理使用`v-once`和`v-memo`指令
   - 大列表使用虚拟滚动
   - 避免不必要的组件重渲染

4. **缓存策略**:
   - Service Worker缓存静态资源
   - IndexedDB存储用户数据
   - 使用PWA实现离线功能

#### 后端性能优化

1. **数据库优化**:
   - 添加适当的索引
   - 优化查询语句
   - 实现查询缓存

2. **API优化**:
   - 请求结果缓存
   - 分页和过滤优化
   - 压缩响应数据

3. **异步处理**:
   - 使用后台任务处理耗时操作
   - 实现消息队列
   - 避免阻塞主进程

### 安全加固详细措施

1. **前端安全**:
   - CSP (Content Security Policy)
   - XSS防护
   - CSRF令牌

2. **API安全**:
   - 速率限制
   - 请求验证
   - 输入过滤

3. **认证安全**:
   - 密码哈希存储
   - 多因素认证
   - 会话管理

4. **数据安全**:
   - 传输加密
   - 敏感数据加密存储
   - 定期备份

## 开发指南详解

### 代码规范详细说明

#### 前端代码规范

1. **命名约定**:
   - 组件文件名: PascalCase (如 `UserProfile.vue`)
   - 实例名称: camelCase (如 `userProfile`)
   - 常量: UPPER_SNAKE_CASE (如 `MAX_RETRY_COUNT`)

2. **文件结构**:
   ```vue
   <script setup lang="ts">
   // 导入语句
   import { ref } from 'vue';
   import type { User } from '@/types';
   
   // Props/Emits定义
   const props = defineProps<{
     user: User;
   }>();
   
   const emit = defineEmits<{
     (e: 'update', value: User): void;
   }>();
   
   // 响应式状态
   const isLoading = ref(false);
   
   // 计算属性和方法
   const fullName = computed(() => `${props.user.firstName} ${props.user.lastName}`);
   
   // 生命周期钩子
   onMounted(() => {
     console.log('Component mounted');
   });
   
   // 方法定义
   const handleClick = () => {
     // 实现...
   };
   </script>
   
   <template>
     <div class="user-profile">
       <!-- 模板内容 -->
     </div>
   </template>
   
   <style scoped lang="scss">
   .user-profile {
     // 样式定义...
   }
   </style>
   ```

3. **TypeScript使用**:
   - 为所有变量和函数添加类型注解
   - 使用接口定义复杂对象结构
   - 避免使用`any`类型

#### 后端代码规范

1. **命名约定**:
   - 模块名: 小写，单词使用下划线分隔 (如 `user_service.py`)
   - 类名: PascalCase (如 `UserService`)
   - 函数和变量: snake_case (如 `get_user_by_id`)
   - 常量: UPPER_SNAKE_CASE (如 `MAX_LOGIN_ATTEMPTS`)

2. **代码组织**:
   ```python
   """
   用户服务模块。
   
   提供用户相关的业务逻辑服务。
   """
   from typing import List, Optional
   from datetime import datetime
   
   from sqlalchemy.orm import Session
   from pydantic import EmailStr
   
   from app.db.models.user import User
   from app.schemas.user import UserCreate, UserUpdate
   from app.core.security import get_password_hash
   
   
   class UserService:
       """用户服务类，处理用户相关业务逻辑。"""
       
       def __init__(self, db: Session):
           """初始化用户服务。
           
           Args:
               db: 数据库会话
           """
           self.db = db
       
       def get_by_id(self, user_id: int) -> Optional[User]:
           """通过ID获取用户。
           
           Args:
               user_id: 用户ID
               
           Returns:
               User对象或None
           """
           return self.db.query(User).filter(User.id == user_id).first()
   ```

3. **注释和文档**:
   - 使用docstring为所有模块、类和方法提供文档
   - 对复杂逻辑添加详细注释
   - 使用类型提示增强代码可读性

### 测试策略详细说明

#### 前端测试策略

1. **单元测试**:
   ```typescript
   // 组件测试示例
   import { describe, it, expect } from 'vitest';
   import { mount } from '@vue/test-utils';
   import UserProfile from '@/components/UserProfile.vue';
   
   describe('UserProfile', () => {
     it('renders user name correctly', () => {
       const user = {
         id: 1,
         firstName: 'John',
         lastName: 'Doe',
         email: 'john@example.com'
       };
       
       const wrapper = mount(UserProfile, {
         props: {
           user
         }
       });
       
       expect(wrapper.text()).toContain('John Doe');
     });
     
     it('emits update event when save button is clicked', async () => {
       const user = {
         id: 1,
         firstName: 'John',
         lastName: 'Doe',
         email: 'john@example.com'
       };
       
       const wrapper = mount(UserProfile, {
         props: {
           user
         }
       });
       
       await wrapper.find('button.save').trigger('click');
       
       const updateEvents = wrapper.emitted('update');
       expect(updateEvents).toBeTruthy();
       expect(updateEvents![0][0]).toEqual(user);
     });
   });
   ```

2. **E2E测试**:
   ```typescript
   // Playwright E2E测试示例
   import { test, expect } from '@playwright/test';
   
   test('user can login and access dashboard', async ({ page }) => {
     await page.goto('/');
     
     // 点击登录按钮
     await page.click('button:has-text("登录")');
     
     // 填写登录表单
     await page.fill('input[name="username"]', 'testuser');
     await page.fill('input[name="password"]', 'password123');
     await page.click('button:has-text("提交")');
     
     // 验证登录成功
     await expect(page).toHaveURL('/dashboard');
     await expect(page.locator('.user-greeting')).toContainText('欢迎, testuser');
     
     // 测试仪表盘功能
     await page.click('text=市场概览');
     await expect(page.locator('.market-overview')).toBeVisible();
   });
   ```

#### 后端测试策略

1. **单元测试**:
   ```python
   # 服务测试示例
   import pytest
   from unittest.mock import MagicMock
   
   from app.services.user_service import UserService
   from app.schemas.user import UserCreate
   
   
   def test_create_user():
       # 准备模拟数据库会话
       mock_db = MagicMock()
       user_service = UserService(mock_db)
       
       # 准备测试数据
       user_data = UserCreate(
           username="testuser",
           email="test@example.com",
           password="password123"
       )
       
       # 调用被测方法
       user = user_service.create_user(user_data)
       
       # 验证结果
       assert user.username == "testuser"
       assert user.email == "test@example.com"
       assert user.password != "password123"  # 密码应该被哈希
       
       # 验证数据库操作
       mock_db.add.assert_called_once()
       mock_db.commit.assert_called_once()
       mock_db.refresh.assert_called_once()
   ```

2. **API测试**:
   ```python
   # API端点测试示例
   import pytest
   from httpx import AsyncClient
   
   
   @pytest.mark.asyncio
   async def test_register_user(client: AsyncClient):
       # 准备测试数据
       user_data = {
           "username": "testuser",
           "email": "test@example.com",
           "password": "password123",
           "confirm_password": "password123"
       }
       
       # 发送请求
       response = await client.post("/api/v1/auth/register", json=user_data)
       
       # 验证响应
       assert response.status_code == 201
       data = response.json()
       assert data["data"]["username"] == "testuser"
       assert data["data"]["email"] == "test@example.com"
       assert "password" not in data["data"]
   ```

## 未来规划详细路线图

### 短期目标 (1-3个月)

1. **功能完善**:
   - 完成所有核心API开发
   - 实现更多交易所集成
   - 优化用户体验

2. **测试和稳定**:
   - 提高测试覆盖率
   - 修复已知问题
   - 性能优化

3. **文档完善**:
   - 更新API文档
   - 编写用户指南
   - 添加开发者文档

### 中期目标 (3-6个月)

1. **功能扩展**:
   - 实现移动端适配
   - 添加高级交易功能
   - 集成更多技术指标

2. **社区功能**:
   - 用户交流论坛
   - 策略分享平台
   - 社交交易功能

3. **安全增强**:
   - 实现双因素认证
   - 安全审计和渗透测试
   - 合规性评估

### 长期目标 (6-12个月)

1. **生态扩展**:
   - 移动应用开发
   - API开放平台
   - 生态合作伙伴计划

2. **高级分析**:
   - 机器学习预测模型
   - 自然语言处理市场情绪分析
   - 自动化策略优化

3. **国际化和本地化**:
   - 多语言支持
   - 多时区支持
   - 多币种支持

---

© 2023 加密货币交易系统团队。保留所有权利。 


