# 加密貨幣交易系統 API 參考文檔

## 目錄
1. [認證 API](#認證-api)
2. [通知 API](#通知-api)
3. [交易 API](#交易-api)
4. [市場 API](#市場-api)
5. [系統 API](#系統-api)
6. [管理員 API](#管理員-api)
7. [設置 API](#設置-api)
8. [用戶 API](#用戶-api)
9. [聊天室 API](#聊天室-api)
10. [在線狀態 API](#在線狀態-api)

## 認證 API

### 用戶註冊
- **URL**: `/api/v1/auth/register`
- **方法**: `POST`
- **描述**: 註冊新用戶
- **請求體**:
  ```json
  {
    "username": "example_user",
    "email": "user@example.com",
    "password": "securepassword",
    "confirm_password": "securepassword"
  }
  ```
- **響應**: 
  ```json
  {
    "id": 1,
    "username": "example_user",
    "email": "user@example.com",
    "is_active": true,
    "is_verified": false,
    "is_admin": false,
    "user_tag": "regular",
    "created_at": "2023-03-15T10:30:00"
  }
  ```

#### 示例用法

**使用 curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"example_user","email":"user@example.com","password":"securepassword","confirm_password":"securepassword"}'
```

**使用 JavaScript/Fetch API**:
```javascript
fetch('http://localhost:8000/api/v1/auth/register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    username: 'example_user',
    email: 'user@example.com',
    password: 'securepassword',
    confirm_password: 'securepassword'
  }),
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 用戶登錄（OAuth2）
- **URL**: `/api/v1/auth/login`
- **方法**: `POST`
- **描述**: 用戶登錄並獲取訪問令牌和刷新令牌
- **請求體** (form-data):
  ```
  username: example_user
  password: securepassword
  ```
- **響應**: 
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "refresh_token": "5a4b3c2d1e..."
  }
  ```

#### 示例用法

**使用 curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=example_user&password=securepassword"
```

**使用 JavaScript/Fetch API**:
```javascript
const formData = new URLSearchParams();
formData.append('username', 'example_user');
formData.append('password', 'securepassword');

fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/x-www-form-urlencoded',
  },
  body: formData,
})
.then(response => response.json())
.then(data => {
  console.log(data);
  // 保存令牌到本地存儲
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
})
.catch(error => console.error('Error:', error));
```

### 簡化版用戶登錄
- **URL**: `/api/v1/auth/login/simple`
- **方法**: `POST`
- **描述**: 簡化版用戶登錄接口，直接接收表單參數
- **請求體** (form-data):
  ```
  username: example_user
  password: securepassword
  ```
- **響應**: 
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "refresh_token": "5a4b3c2d1e..."
  }
  ```

#### 示例用法

**使用 curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/simple \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=example_user&password=securepassword"
```

**使用 JavaScript/Fetch API**:
```javascript
const formData = new FormData();
formData.append('username', 'example_user');
formData.append('password', 'securepassword');

fetch('http://localhost:8000/api/v1/auth/login/simple', {
  method: 'POST',
  body: formData,
})
.then(response => response.json())
.then(data => {
  console.log(data);
  // 保存令牌到本地存儲
  localStorage.setItem('access_token', data.access_token);
  localStorage.setItem('refresh_token', data.refresh_token);
})
.catch(error => console.error('Error:', error));
```

### 刷新訪問令牌
- **URL**: `/api/v1/auth/refresh`
- **方法**: `POST`
- **描述**: 使用刷新令牌獲取新的訪問令牌，可以在訪問令牌過期後使用，避免用戶重新登錄
- **請求體**:
  ```json
  {
    "refresh_token": "5a4b3c2d1e..."
  }
  ```
- **響應**: 
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 1800
  }
  ```

#### 示例用法

**使用 curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"5a4b3c2d1e..."}'
```

**使用 JavaScript/Fetch API**:
```javascript
// 自動刷新令牌功能
function setupTokenRefresh() {
  // 從本地存儲獲取刷新令牌
  const refreshToken = localStorage.getItem('refresh_token');
  
  if (!refreshToken) {
    console.error('No refresh token available');
    return;
  }
  
  fetch('http://localhost:8000/api/v1/auth/refresh', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      refresh_token: refreshToken
    }),
  })
  .then(response => response.json())
  .then(data => {
    // 更新訪問令牌
    localStorage.setItem('access_token', data.access_token);
    
    // 設置定時器，提前5分鐘刷新令牌
    const refreshTime = (data.expires_in - 300) * 1000; // 轉換為毫秒，提前5分鐘
    setTimeout(setupTokenRefresh, refreshTime);
    
    console.log(`Token refreshed, next refresh in ${refreshTime/1000} seconds`);
  })
  .catch(error => {
    console.error('Error refreshing token:', error);
    // 如果刷新失敗，可能需要重新登錄
  });
}

// 使用方法：在用戶登錄成功後調用
// setupTokenRefresh();
```

### 登出
- **URL**: `/api/v1/auth/logout`
- **方法**: `POST`
- **描述**: 登出並撤銷刷新令牌
- **請求體**:
  ```json
  {
    "refresh_token": "5a4b3c2d1e..."
  }
  ```
- **響應**: 
  ```json
  {
    "message": "成功登出"
  }
  ```

#### 示例用法

**使用 curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"5a4b3c2d1e..."}'
```

**使用 JavaScript/Fetch API**:
```javascript
function logout() {
  // 從本地存儲獲取刷新令牌
  const refreshToken = localStorage.getItem('refresh_token');
  
  if (!refreshToken) {
    console.error('No refresh token available');
    // 清除本地存儲
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    return;
  }
  
  fetch('http://localhost:8000/api/v1/auth/logout', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      refresh_token: refreshToken
    }),
  })
  .then(response => response.json())
  .then(data => {
    console.log('Logout successful:', data);
    // 清除本地存儲
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    // 跳轉到登錄頁面或首頁
    // window.location.href = '/login';
  })
  .catch(error => {
    console.error('Error during logout:', error);
    // 即使出錯，也清除本地存儲
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  });
}
```

### 獲取當前用戶信息
- **URL**: `/api/v1/auth/me`
- **方法**: `GET`
- **描述**: 獲取當前登錄用戶的詳細信息
- **授權**: 需要Bearer Token
- **響應**:
  ```json
  {
    "id": 1,
    "username": "example_user",
    "email": "user@example.com",
    "is_active": true,
    "is_verified": false,
    "is_admin": false,
    "user_tag": "regular",
    "created_at": "2023-03-15T10:30:00"
  }
  ```

#### 示例用法

**使用 curl**:
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

**使用 JavaScript/Fetch API**:
```javascript
// 獲取當前用戶信息
function getCurrentUser() {
  const token = localStorage.getItem('access_token');
  
  if (!token) {
    console.error('No access token available');
    return;
  }
  
  fetch('http://localhost:8000/api/v1/auth/me', {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${token}`
    },
  })
  .then(response => {
    // 如果返回401未授權，嘗試刷新令牌
    if (response.status === 401) {
      setupTokenRefresh(); // 使用上面定義的刷新令牌函數
      throw new Error('Unauthorized, token refreshed');
    }
    return response.json();
  })
  .then(data => {
    console.log('Current user:', data);
    // 處理用戶數據
  })
  .catch(error => console.error('Error:', error));
}
```

## 通知 API

API前綴: `/api/v1/notifications`

### 獲取通知列表

- **URL**: `/`
- **方法**: `GET`
- **描述**: 獲取當前用戶的通知列表（包括全局通知和用戶特定通知）
- **授權**: 需要 Bearer Token
- **查詢參數**:
  - `page`: 頁碼 (默認: 1)
  - `per_page`: 每頁項目數 (默認: 10, 最大: 100)
  - `notification_type`: 通知類型 (可選)
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "items": [
        {
          "id": "integer",
          "title": "string",
          "message": "string",
          "notification_type": "string",
          "read": "boolean",
          "is_global": "boolean",
          "user_id": "integer",
          "created_at": "datetime"
        }
      ],
      "total": "integer",
      "page": "integer",
      "per_page": "integer"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取通知列表
curl -X GET "http://localhost:8000/api/v1/notifications?page=1&per_page=20&notification_type=info" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlciIsImV4cCI6MTcyODAxMjM0NX0.example_token_signature"
```

```javascript
// 使用 JavaScript/Fetch API 獲取通知列表
fetch('http://localhost:8000/api/v1/notifications?page=1&per_page=20&notification_type=info', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

#### 範例響應

```json
{
  "items": [
    {
      "id": 42,
      "title": "系統維護通知",
      "message": "系統將於2025年4月10日進行維護升級，預計停機時間為2小時。",
      "notification_type": "info",
      "read": false,
      "is_global": true,
      "user_id": null,
      "created_at": "2025-04-05T14:30:00.123456"
    },
    {
      "id": 38,
      "title": "交易成功",
      "message": "您的BTC/USDT訂單已成功執行，交易金額：5000 USDT",
      "notification_type": "success",
      "read": true,
      "is_global": false,
      "user_id": 12,
      "created_at": "2025-04-04T09:45:30.654321"
    }
  ],
  "total": 48,
  "page": 1,
  "per_page": 20
}
```

### 創建通知

- **URL**: `/`
- **方法**: `POST`
- **描述**: 創建通知（僅管理員）
- **授權**: 需要 Bearer Token（管理員權限）
- **請求體**:
  ```json
  {
    "title": "string",
    "message": "string",
    "notification_type": "string",
    "is_global": "boolean",
    "user_ids": ["integer"]
  }
  ```
- **響應**:
  - 狀態碼: `201 CREATED`
  - 返回創建的通知列表

#### 範例用法

```bash
# 使用 curl 創建通知
curl -X POST http://localhost:8000/api/v1/notifications \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbnVzZXIiLCJleHAiOjE3MjgwMTIzNDV9.example_admin_token" \
  -d '{
    "title": "重要系統更新",
    "message": "我們已經更新了交易系統，帶來更多功能和優化。",
    "notification_type": "info",
    "is_global": true,
    "user_ids": []
  }'
```

```javascript
// 使用 JavaScript/Fetch API 創建通知
fetch('http://localhost:8000/api/v1/notifications', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('adminToken')
  },
  body: JSON.stringify({
    title: "重要系統更新",
    message: "我們已經更新了交易系統，帶來更多功能和優化。",
    notification_type: "info",
    is_global: true,
    user_ids: []
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

#### 範例響應

```json
[
  {
    "id": 50,
    "title": "重要系統更新",
    "message": "我們已經更新了交易系統，帶來更多功能和優化。",
    "notification_type": "info",
    "read": false,
    "is_global": true,
    "user_id": null,
    "created_at": "2025-04-05T17:30:22.123456"
  }
]
```

### 標記通知為已讀

- **URL**: `/{notification_id}/read`
- **方法**: `PATCH`
- **描述**: 將指定的通知標記為已讀
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `notification_id`: 通知 ID
- **響應**:
  - 狀態碼: `200 OK`
  - 返回更新後的通知

#### 範例用法

```bash
# 使用 curl 標記通知為已讀
curl -X PATCH http://localhost:8000/api/v1/notifications/42/read \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlciIsImV4cCI6MTcyODAxMjM0NX0.example_token_signature"
```

```javascript
// 使用 JavaScript/Fetch API 標記通知為已讀
fetch('http://localhost:8000/api/v1/notifications/42/read', {
  method: 'PATCH',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

#### 範例響應

```json
{
  "id": 42,
  "title": "系統維護通知",
  "message": "系統將於2025年4月10日進行維護升級，預計停機時間為2小時。",
  "notification_type": "info",
  "read": true,
  "is_global": true,
  "user_id": null,
  "created_at": "2025-04-05T14:30:00.123456"
}
```

### 全部標記為已讀

- **URL**: `/read-all`
- **方法**: `PATCH`
- **描述**: 將所有通知標記為已讀
- **授權**: 需要 Bearer Token
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "status": "success",
      "message": "所有通知已標記為已讀"
    }
    ```

#### 範例用法

```bash
# 使用 curl 標記所有通知為已讀
curl -X PATCH http://localhost:8000/api/v1/notifications/read-all \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlciIsImV4cCI6MTcyODAxMjM0NX0.example_token_signature"
```

```javascript
// 使用 JavaScript/Fetch API 標記所有通知為已讀
fetch('http://localhost:8000/api/v1/notifications/read-all', {
  method: 'PATCH',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### WebSocket 實時通知

- **URL**: `/ws`
- **方法**: `WebSocket`
- **描述**: 建立 WebSocket 連接接收實時通知
- **授權**: 需要通過 URL 參數提供有效的令牌
- **查詢參數**:
  - `token`: JWT 訪問令牌

#### 範例用法

```javascript
// 使用 JavaScript WebSocket API 建立實時通知連接
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8000/api/v1/notifications/ws?token=${token}`);

ws.onopen = function() {
  console.log('通知WebSocket連接已建立');
};

ws.onmessage = function(event) {
  const notification = JSON.parse(event.data);
  console.log('收到新通知:', notification);
  
  // 處理接收到的通知，例如顯示通知或更新UI
  showNotification(notification);
};

ws.onclose = function(event) {
  console.log('通知WebSocket連接已關閉，代碼:', event.code, '原因:', event.reason);
  
  // 可以在這裡實現重連邏輯
  setTimeout(function() {
    console.log('嘗試重新連接通知WebSocket...');
    // 重新建立WebSocket連接
  }, 5000);
};

ws.onerror = function(error) {
  console.error('通知WebSocket錯誤:', error);
};

// 顯示通知的函數
function showNotification(notification) {
  // 根據通知類型顯示不同樣式的通知
  switch(notification.notification_type) {
    case 'info':
      // 顯示信息通知
      break;
    case 'success':
      // 顯示成功通知
      break;
    case 'warning':
      // 顯示警告通知
      break;
    case 'error':
      // 顯示錯誤通知
      break;
    default:
      // 默認顯示方式
  }
}
```

#### 範例接收消息

```json
{
  "id": 51,
  "title": "新交易機會",
  "message": "BTC/USDT價格波動幅度增大，可能是交易機會。",
  "notification_type": "info",
  "read": false,
  "is_global": false,
  "user_id": 12,
  "created_at": "2025-04-05T17:45:12.123456"
}
```

## 交易 API

API前綴: `/api/v1/trading`

### 獲取支持的交易所列表

- **URL**: `/exchanges`
- **方法**: `GET`
- **描述**: 獲取系統支持的所有交易所列表
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    [
      "binance",
      "okx",
      "bybit"
    ]
    ```

#### 範例用法

```bash
# 使用 curl 獲取支持的交易所列表
curl -X GET http://localhost:8000/api/v1/trading/exchanges
```

```javascript
// 使用 JavaScript/Fetch API 獲取支持的交易所列表
fetch('http://localhost:8000/api/v1/trading/exchanges')
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取賬戶信息

- **URL**: `/account/{exchange}`
- **方法**: `GET`
- **描述**: 獲取指定交易所的賬戶信息
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
  "success": true,
  "data": {
    "accountType": "SPOT",
    "balances": [
      {
        "asset": "BTC",
        "free": "0.01234500",
        "locked": "0.00000000"
      },
      {
        "asset": "USDT",
            "free": "1234.56",
            "locked": "100.00"
          }
        ],
        "permissions": ["SPOT", "MARGIN", "FUTURES"],
        "updateTime": 1678234567890
      },
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取賬戶信息
curl -X GET http://localhost:8000/api/v1/trading/account/binance \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取賬戶信息
fetch('http://localhost:8000/api/v1/trading/account/binance', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取資產餘額

- **URL**: `/balance/{exchange}/{asset}`
- **方法**: `GET`
- **描述**: 獲取指定交易所特定資產的餘額
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
  - `asset`: 資產名稱（如 BTC, USDT）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
  "success": true,
  "data": {
    "asset": "BTC",
    "free": "0.01234500",
    "locked": "0.00000000",
    "total": "0.01234500"
      },
      "exchange": "binance",
      "asset": "BTC"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取資產餘額
curl -X GET http://localhost:8000/api/v1/trading/balance/binance/BTC \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取資產餘額
fetch('http://localhost:8000/api/v1/trading/balance/binance/BTC', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 現貨下單

- **URL**: `/spot/order/{exchange}`
- **方法**: `POST`
- **描述**: 在指定交易所下現貨訂單
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **請求體**:
```json
    {
      "symbol": "BTCUSDT",
      "side": "BUY",
      "type": "LIMIT",
    "quantity": 0.01,
    "price": 50000,
    "timeInForce": "GTC"
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "success": true,
      "data": {
        "orderId": "123456789",
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "price": "50000.00",
        "origQty": "0.01",
        "executedQty": "0.00",
        "status": "NEW",
        "timeInForce": "GTC",
        "createTime": 1678234567890
      },
      "exchange": "binance",
      "order_type": "spot"
    }
    ```

#### 範例用法

```bash
# 使用 curl 下現貨訂單
curl -X POST http://localhost:8000/api/v1/trading/spot/order/binance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "quantity": 0.01,
    "price": 50000,
    "timeInForce": "GTC"
  }'
```

```javascript
// 使用 JavaScript/Fetch API 下現貨訂單
fetch('http://localhost:8000/api/v1/trading/spot/order/binance', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    symbol: 'BTCUSDT',
    side: 'BUY',
    type: 'LIMIT',
    quantity: 0.01,
    price: 50000,
    timeInForce: 'GTC'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 合約下單

- **URL**: `/futures/order/{exchange}`
- **方法**: `POST`
- **描述**: 在指定交易所下合約訂單
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **請求體**:
```json
{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "quantity": 0.01,
    "price": 50000,
    "timeInForce": "GTC",
    "leverage": 10,
    "reduceOnly": false
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
  "success": true,
  "data": {
        "orderId": "123456789",
    "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "price": "50000.00",
    "origQty": "0.01",
    "executedQty": "0.00",
        "status": "NEW",
    "timeInForce": "GTC",
        "createTime": 1678234567890,
        "leverage": 10,
        "reduceOnly": false
      },
      "exchange": "binance",
      "order_type": "futures"
    }
    ```

#### 範例用法

```bash
# 使用 curl 下合約訂單
curl -X POST http://localhost:8000/api/v1/trading/futures/order/binance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "LIMIT",
    "quantity": 0.01,
    "price": 50000,
    "timeInForce": "GTC",
    "leverage": 10,
    "reduceOnly": false
  }'
```

```javascript
// 使用 JavaScript/Fetch API 下合約訂單
fetch('http://localhost:8000/api/v1/trading/futures/order/binance', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    symbol: 'BTCUSDT',
    side: 'BUY',
    type: 'LIMIT',
    quantity: 0.01,
    price: 50000,
    timeInForce: 'GTC',
    leverage: 10,
    reduceOnly: false
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取訂單歷史

- **URL**: `/orders/history/{exchange}`
- **方法**: `GET`
- **描述**: 獲取指定交易所的訂單歷史
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **查詢參數**:
  - `symbol`: 交易對（可選，如 BTCUSDT）
  - `order_type`: 訂單類型（可選，spot 或 futures）
  - `start_time`: 開始時間（可選，ISO 格式）
  - `end_time`: 結束時間（可選，ISO 格式）
  - `limit`: 返回結果數量限制（默認: 100）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
  "success": true,
      "data": [
        {
          "orderId": "123456789",
    "symbol": "BTCUSDT",
          "side": "BUY",
          "type": "LIMIT",
          "price": "50000.00",
    "origQty": "0.01",
          "executedQty": "0.01",
          "status": "FILLED",
    "timeInForce": "GTC",
          "createTime": 1678234567890,
          "updateTime": 1678234569890
        }
      ],
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取訂單歷史
curl -X GET "http://localhost:8000/api/v1/trading/orders/history/binance?symbol=BTCUSDT&order_type=spot&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取訂單歷史
fetch('http://localhost:8000/api/v1/trading/orders/history/binance?symbol=BTCUSDT&order_type=spot&limit=10', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取當前持倉

- **URL**: `/positions/{exchange}`
- **方法**: `GET`
- **描述**: 獲取指定交易所的當前持倉
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **查詢參數**:
  - `symbol`: 交易對（可選，如 BTCUSDT）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
    {
      "success": true,
      "data": [
        {
          "symbol": "BTCUSDT",
          "positionAmt": "0.01",
          "entryPrice": "50000.00",
          "markPrice": "51000.00",
          "unRealizedProfit": "10.00",
          "liquidationPrice": "45000.00",
          "leverage": "10",
          "marginType": "isolated"
        }
      ],
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取當前持倉
curl -X GET "http://localhost:8000/api/v1/trading/positions/binance?symbol=BTCUSDT" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取當前持倉
fetch('http://localhost:8000/api/v1/trading/positions/binance?symbol=BTCUSDT', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 取消訂單

- **URL**: `/order/{exchange}/{order_id}`
- **方法**: `DELETE`
- **描述**: 取消指定交易所的訂單
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
  - `order_id`: 訂單 ID
- **查詢參數**:
  - `symbol`: 交易對（必需，如 BTCUSDT）
  - `order_type`: 訂單類型（必需，spot 或 futures）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
      "success": true,
      "data": {
        "orderId": "123456789",
  "symbol": "BTCUSDT",
        "status": "CANCELED",
        "createTime": 1678234567890,
        "updateTime": 1678234569890
      },
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 取消訂單
curl -X DELETE "http://localhost:8000/api/v1/trading/order/binance/123456789?symbol=BTCUSDT&order_type=spot" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 取消訂單
fetch('http://localhost:8000/api/v1/trading/order/binance/123456789?symbol=BTCUSDT&order_type=spot', {
  method: 'DELETE',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取未成交訂單

- **URL**: `/open-orders/{exchange}`
- **方法**: `GET`
- **描述**: 獲取指定交易所的未成交訂單
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **查詢參數**:
  - `symbol`: 交易對（可選，如 BTCUSDT）
  - `order_type`: 訂單類型（可選，spot 或 futures）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
      "success": true,
      "data": [
        {
          "orderId": "123456789",
          "symbol": "BTCUSDT",
          "side": "BUY",
          "type": "LIMIT",
          "price": "50000.00",
          "origQty": "0.01",
          "executedQty": "0.00",
          "status": "NEW",
          "timeInForce": "GTC",
          "createTime": 1678234567890
        }
      ],
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取未成交訂單
curl -X GET "http://localhost:8000/api/v1/trading/open-orders/binance?symbol=BTCUSDT&order_type=spot" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取未成交訂單
fetch('http://localhost:8000/api/v1/trading/open-orders/binance?symbol=BTCUSDT&order_type=spot', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 設置槓桿

- **URL**: `/leverage/{exchange}`
- **方法**: `POST`
- **描述**: 設置槓桿倍數和保證金模式
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **請求體**:
```json
{
    "symbol": "BTCUSDT",
    "leverage": 10,
    "margin_type": "isolated"
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "success": true,
      "data": {
        "symbol": "BTCUSDT",
        "leverage": 10,
        "margin_type": "isolated",
        "max_notional_value": "1000000"
      },
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 設置槓桿
curl -X POST http://localhost:8000/api/v1/trading/leverage/binance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "symbol": "BTCUSDT",
    "leverage": 10,
    "margin_type": "isolated"
  }'
```

```javascript
// 使用 JavaScript/Fetch API 設置槓桿
fetch('http://localhost:8000/api/v1/trading/leverage/binance', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    symbol: 'BTCUSDT',
    leverage: 10,
    margin_type: 'isolated'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 下止盈止損訂單

- **URL**: `/stop-order/{exchange}`
- **方法**: `POST`
- **描述**: 下止盈止損訂單
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **請求體**:
```json
{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "quantity": 0.01,
    "stop_price": 50000,
    "price": 49900,
    "type": "STOP_LOSS_LIMIT",
    "time_in_force": "GTC",
    "working_type": "MARK_PRICE",
    "reduce_only": true,
    "close_position": false
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
      "success": true,
      "data": {
        "orderId": "123456789",
        "symbol": "BTCUSDT",
        "type": "STOP_LOSS_LIMIT",
        "side": "SELL",
        "quantity": "0.01",
        "stopPrice": "50000",
        "price": "49900",
        "status": "NEW",
        "createTime": 1678234567890
      },
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 下止盈止損訂單
curl -X POST http://localhost:8000/api/v1/trading/stop-order/binance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "symbol": "BTCUSDT",
    "side": "SELL",
    "quantity": 0.01,
    "stop_price": 50000,
    "price": 49900,
    "type": "STOP_LOSS_LIMIT",
    "time_in_force": "GTC",
    "working_type": "MARK_PRICE",
    "reduce_only": true,
    "close_position": false
  }'
```

```javascript
// 使用 JavaScript/Fetch API 下止盈止損訂單
fetch('http://localhost:8000/api/v1/trading/stop-order/binance', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    symbol: 'BTCUSDT',
    side: 'SELL',
    quantity: 0.01,
    stop_price: 50000,
    price: 49900,
    type: 'STOP_LOSS_LIMIT',
    time_in_force: 'GTC',
    working_type: 'MARK_PRICE',
    reduce_only: true,
    close_position: false
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 批量下單

- **URL**: `/batch-orders/{exchange}`
- **方法**: `POST`
- **描述**: 批量下單（最多5個訂單）
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **請求體**:
```json
{
    "orders": [
      {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": 0.01,
        "price": 50000,
        "timeInForce": "GTC"
      },
      {
        "symbol": "BTCUSDT",
        "side": "SELL",
        "quantity": 0.01,
        "stop_price": 60000,
        "price": 59900,
        "type": "STOP_LOSS_LIMIT",
        "time_in_force": "GTC",
        "working_type": "MARK_PRICE",
        "reduce_only": true
      }
    ],
    "order_type": "futures"
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
      "success": true,
      "data": [
        {
          "orderId": "123456789",
          "symbol": "BTCUSDT",
          "status": "NEW",
          "message": "success"
        },
        {
          "orderId": "987654321",
          "symbol": "BTCUSDT",
          "status": "NEW",
          "message": "success"
        }
      ],
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 批量下單
curl -X POST http://localhost:8000/api/v1/trading/batch-orders/binance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "orders": [
      {
        "symbol": "BTCUSDT",
        "side": "BUY",
        "type": "LIMIT",
        "quantity": 0.01,
        "price": 50000,
        "timeInForce": "GTC"
      },
      {
        "symbol": "BTCUSDT",
        "side": "SELL",
        "quantity": 0.01,
        "stop_price": 60000,
        "price": 59900,
        "type": "STOP_LOSS_LIMIT",
        "time_in_force": "GTC",
        "working_type": "MARK_PRICE",
        "reduce_only": true
      }
    ],
    "order_type": "futures"
  }'
```

```javascript
// 使用 JavaScript/Fetch API 批量下單
fetch('http://localhost:8000/api/v1/trading/batch-orders/binance', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    orders: [
      {
        symbol: 'BTCUSDT',
        side: 'BUY',
        type: 'LIMIT',
        quantity: 0.01,
        price: 50000,
        timeInForce: 'GTC'
      },
      {
        symbol: 'BTCUSDT',
        side: 'SELL',
        quantity: 0.01,
        stop_price: 60000,
        price: 59900,
        type: 'STOP_LOSS_LIMIT',
        time_in_force: 'GTC',
        working_type: 'MARK_PRICE',
        reduce_only: true
      }
    ],
    order_type: 'futures'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 批量取消訂單

- **URL**: `/batch-cancel/{exchange}`
- **方法**: `POST`
- **描述**: 批量取消訂單（最多10個訂單）
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **請求體**:
  ```json
  {
    "symbol": "BTCUSDT",
    "order_ids": ["123456789", "987654321"],
    "order_type": "futures"
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "success": true,
      "data": [
        {
          "orderId": "123456789",
          "status": "CANCELED",
          "message": "success"
        },
        {
          "orderId": "987654321",
          "status": "FAILED",
          "message": "order filled"
        }
      ],
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 批量取消訂單
curl -X POST http://localhost:8000/api/v1/trading/batch-cancel/binance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "symbol": "BTCUSDT",
    "order_ids": ["123456789", "987654321"],
    "order_type": "futures"
  }'
```

```javascript
// 使用 JavaScript/Fetch API 批量取消訂單
fetch('http://localhost:8000/api/v1/trading/batch-cancel/binance', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    symbol: 'BTCUSDT',
    order_ids: ['123456789', '987654321'],
    order_type: 'futures'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取交易對信息

- **URL**: `/symbols/{exchange}`
- **方法**: `GET`
- **描述**: 獲取交易對信息
- **路徑參數**:
  - `exchange`: 交易所名稱（如 binance）
- **查詢參數**:
  - `symbol`: 交易對（可選，如 BTCUSDT）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
```json
{
  "success": true,
      "data": {
        "symbol": "BTCUSDT",
        "status": "TRADING",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "price_precision": 2,
        "quantity_precision": 6,
        "min_price": "0.01",
        "max_price": "1000000",
        "min_quantity": "0.000001",
        "min_notional": "10",
        "max_leverage": 125,
        "margin_types": ["isolated", "cross"],
        "order_types": ["LIMIT", "MARKET", "STOP", "STOP_MARKET"],
        "time_in_force": ["GTC", "IOC", "FOK"]
      },
      "exchange": "binance"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取交易對信息
curl -X GET "http://localhost:8000/api/v1/trading/symbols/binance?symbol=BTCUSDT"
```

```javascript
// 使用 JavaScript/Fetch API 獲取交易對信息
fetch('http://localhost:8000/api/v1/trading/symbols/binance?symbol=BTCUSDT')
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

## 市場 API

API前綴: `/api/v1/markets`

### 獲取市場行情

- **URL**: `/prices`
- **方法**: `GET`
- **描述**: 獲取所有交易對的最新價格
- **響應**:
  - 狀態碼: `200 OK`
  - 返回價格列表

#### 範例用法

```bash
# 使用 curl 獲取所有交易對價格
curl -X GET http://localhost:8000/api/v1/markets/prices
```

```javascript
// 使用 JavaScript/Fetch API 獲取所有交易對價格
fetch('http://localhost:8000/api/v1/markets/prices')
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

#### 範例響應

```json
[
  {
    "id": 12,
    "username": "testuser",
    "email": "test@example.com",
    "is_admin": false,
    "created_at": "2025-03-15T10:30:45.123456"
  },
  {
    "id": 25,
    "username": "testadmin",
    "email": "testadmin@example.com",
    "is_admin": true,
    "created_at": "2025-02-10T14:20:30.654321"
  },
  {
    "id": 36,
    "username": "janetester",
    "email": "janet@testing.com",
    "is_admin": false,
    "created_at": "2025-03-22T09:15:45.789012"
  }
]
```

## 系統 API

API前綴: `/api/v1/system`

### 獲取伺服器狀態

- **URL**: `/status`
- **方法**: `GET`
- **描述**: 獲取伺服器狀態資訊，包括CPU、記憶體使用情況等
- **授權**: 需要管理員權限 (Bearer Token)
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "status": "running",
      "system": {
        "system": "Windows",
        "version": "10.0.19045",
        "processor": "Intel64 Family 6 Model 142 Stepping 12, GenuineIntel",
        "hostname": "SERVER-PC",
        "ip": "192.168.1.100"
      },
      "resources": {
        "cpu_percent": 12.5,
        "memory": {
          "total": 16.0,
          "used": 8.5,
          "percent": 53.1
        },
        "disk": {
          "total": 512.0,
          "used": 256.0,
          "percent": 50.0
        }
      },
      "time": {
        "server_time": "2025-04-10 14:30:45",
        "uptime": {
          "days": 5,
          "hours": 12,
          "minutes": 30,
          "seconds": 15
        },
        "start_time": "2025-04-05 02:00:30"
      }
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取伺服器狀態
curl -X GET http://localhost:8000/api/v1/system/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取伺服器狀態
fetch('http://localhost:8000/api/v1/system/status', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 測試API延遲

- **URL**: `/ping`
- **方法**: `GET`
- **描述**: 簡單的Ping端點，用於測量API延遲
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "timestamp": 1618234567890
    }
    ```

#### 範例用法

```bash
# 使用 curl 测试API延迟
curl -X GET http://localhost:8000/api/v1/system/ping
```

```javascript
// 使用 JavaScript/Fetch API 测试API延迟
const startTime = Date.now();
fetch('http://localhost:8000/api/v1/system/ping')
.then(response => response.json())
.then(data => {
  const latency = Date.now() - startTime;
  console.log(`API延迟: ${latency}ms`);
  console.log(data);
})
.catch(error => console.error('Error:', error));
```

### 獲取用戶登入歷史

- **URL**: `/users-login-history`
- **方法**: `GET`
- **描述**: 獲取用戶登入歷史記錄，包括最近登入時間和IP地址
- **授權**: 需要管理員權限 (Bearer Token)
- **查詢參數**:
  - `limit`: 要返回的記錄數量上限（預設: 20）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    [
      {
        "id": 1,
        "username": "example_user",
        "email": "user@example.com",
        "is_active": true,
        "user_tag": "regular",
        "last_login_at": "2025-04-10 08:15:30",
        "last_login_ip": "192.168.1.50"
      },
      {
        "id": 2,
        "username": "admin_user",
        "email": "admin@example.com",
        "is_active": true,
        "user_tag": "admin",
        "last_login_at": "2025-04-10 09:20:45",
        "last_login_ip": "192.168.1.60"
      }
    ]
    ```

#### 範例用法

```bash
# 使用 curl 獲取用戶登入歷史
curl -X GET "http://localhost:8000/api/v1/system/users-login-history?limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取用戶登入歷史
fetch('http://localhost:8000/api/v1/system/users-login-history?limit=10', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

## 管理員 API

API前綴: `/api/v1/admin`

### 獲取所有用戶

- **URL**: `/users`
- **方法**: `GET`
- **描述**: 獲取所有用戶（管理員權限），支援分頁和搜索
- **授權**: 需要管理員權限 (Bearer Token)
- **查詢參數**:
  - `page`: 頁碼，從1開始（預設: 1）
  - `per_page`: 每頁顯示的記錄數量（預設: 10）
  - `search`: 搜索關鍵字，用於過濾用戶名和電子郵件（可選）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "items": [
        {
          "id": 1,
          "username": "example_user",
          "email": "user@example.com",
          "is_active": true,
          "is_verified": true,
          "is_admin": false,
          "user_tag": "regular",
          "created_at": "2025-03-15T10:30:00"
        }
      ],
      "total": 50,
      "page": 1,
      "per_page": 10
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取所有用戶
curl -X GET "http://localhost:8000/api/v1/admin/users?page=1&per_page=20&search=example" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取所有用戶
fetch('http://localhost:8000/api/v1/admin/users?page=1&per_page=20&search=example', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取特定用戶

- **URL**: `/users/{user_id}`
- **方法**: `GET`
- **描述**: 通過ID獲取用戶資訊（管理員權限）
- **授權**: 需要管理員權限 (Bearer Token)
- **路徑參數**:
  - `user_id`: 要查詢的用戶ID
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "id": 1,
      "username": "example_user",
      "email": "user@example.com",
      "is_active": true,
      "is_verified": true,
      "is_admin": false,
      "user_tag": "regular",
      "created_at": "2025-03-15T10:30:00"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取特定用戶
curl -X GET http://localhost:8000/api/v1/admin/users/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取特定用戶
fetch('http://localhost:8000/api/v1/admin/users/1', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 更新用戶資訊

- **URL**: `/users/{user_id}`
- **方法**: `PUT`
- **描述**: 更新用戶資訊（管理員權限）
- **授權**: 需要管理員權限 (Bearer Token)
- **路徑參數**:
  - `user_id`: 要更新的用戶ID
- **請求體**:
  ```json
  {
    "username": "new_username",
    "email": "new_email@example.com",
    "is_active": true,
    "is_admin": false
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 返回更新後的用戶資訊

#### 範例用法

```bash
# 使用 curl 更新用戶資訊
curl -X PUT http://localhost:8000/api/v1/admin/users/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "username": "new_username",
    "email": "new_email@example.com",
    "is_active": true,
    "is_admin": false
  }'
```

```javascript
// 使用 JavaScript/Fetch API 更新用戶資訊
fetch('http://localhost:8000/api/v1/admin/users/1', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    username: 'new_username',
    email: 'new_email@example.com',
    is_active: true,
    is_admin: false
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 更新用戶狀態

- **URL**: `/users/{user_id}/status`
- **方法**: `PUT`
- **描述**: 更新用戶狀態（啟用/禁用）
- **授權**: 需要管理員權限 (Bearer Token)
- **路徑參數**:
  - `user_id`: 要更新狀態的用戶ID
- **請求體**:
  ```json
  {
    "is_active": true
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 返回更新後的用戶資訊

#### 範例用法

```bash
# 使用 curl 更新用戶狀態
curl -X PUT http://localhost:8000/api/v1/admin/users/1/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "is_active": true
  }'
```

```javascript
// 使用 JavaScript/Fetch API 更新用戶狀態
fetch('http://localhost:8000/api/v1/admin/users/1/status', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    is_active: true
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 更新用戶管理員權限

- **URL**: `/users/{user_id}/admin`
- **方法**: `PUT`
- **描述**: 更新用戶的管理員權限
- **授權**: 需要管理員權限 (Bearer Token)
- **路徑參數**:
  - `user_id`: 要更新權限的用戶ID
- **請求體**:
  ```json
  {
    "is_admin": true
  }
  ```
- **響應**:
  - 狀態碼: `200 OK`
  - 返回更新後的用戶資訊

#### 範例用法

```bash
# 使用 curl 更新用戶管理員權限
curl -X PUT http://localhost:8000/api/v1/admin/users/1/admin \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "is_admin": true
  }'
```

```javascript
// 使用 JavaScript/Fetch API 更新用戶管理員權限
fetch('http://localhost:8000/api/v1/admin/users/1/admin', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    is_admin: true
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 刪除用戶

- **URL**: `/users/{user_id}`
- **方法**: `DELETE`
- **描述**: 刪除指定的用戶
- **授權**: 需要管理員權限 (Bearer Token)
- **路徑參數**:
  - `user_id`: 要刪除的用戶ID
- **響應**:
  - 狀態碼: `204 NO CONTENT`

#### 範例用法

```bash
# 使用 curl 刪除用戶
curl -X DELETE http://localhost:8000/api/v1/admin/users/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 刪除用戶
fetch('http://localhost:8000/api/v1/admin/users/1', {
  method: 'DELETE',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => {
  if (response.status === 204) {
    console.log('用戶已成功刪除');
  }
})
.catch(error => console.error('Error:', error));
```

## 用戶 API

API前綴: `/api/v1/users`

### 獲取活躍用戶數量

- **URL**: `/active-users-count`
- **方法**: `GET`
- **描述**: 獲取當前活躍用戶數量
- **授權**: 需要 Bearer Token
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "active_users": 42
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取活躍用戶數量
curl -X GET http://localhost:8000/api/v1/users/active-users-count \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取活躍用戶數量
fetch('http://localhost:8000/api/v1/users/active-users-count', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 檢查用戶是否活躍

- **URL**: `/is-active/{user_id}`
- **方法**: `GET`
- **描述**: 檢查用戶是否處於活躍狀態
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `user_id`: 要檢查的用戶ID
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "user_id": 1,
      "is_active": true,
      "last_active": "2025-04-10T14:30:45.123456"
    }
    ```

#### 範例用法

```bash
# 使用 curl 檢查用戶是否活躍
curl -X GET http://localhost:8000/api/v1/users/is-active/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 檢查用戶是否活躍
fetch('http://localhost:8000/api/v1/users/is-active/1', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取用戶公開信息

- **URL**: `/user-info/{user_id}`
- **方法**: `GET`
- **描述**: 獲取用戶的公開信息
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `user_id`: 要查詢的用戶ID
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "id": 1,
      "username": "example_user",
      "avatar_url": "https://example.com/avatars/user1.jpg",
      "user_tag": "regular",
      "created_at": "2025-03-15T10:30:00"
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取用戶公開信息
curl -X GET http://localhost:8000/api/v1/users/user-info/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取用戶公開信息
fetch('http://localhost:8000/api/v1/users/user-info/1', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

## 聊天室 API

API前綴: `/api/v1/chatroom`

### 創建聊天室

- **URL**: `/rooms`
- **方法**: `POST`
- **描述**: 創建新的聊天室
- **授權**: 需要 Bearer Token（僅管理員可創建官方聊天室）
- **請求體**:
  ```json
  {
    "name": "交易策略討論",
    "description": "討論各種加密貨幣交易策略的地方",
    "is_public": true,
    "is_official": false,
    "icon_url": "https://example.com/icons/trading.png"
  }
  ```
- **響應**:
  - 狀態碼: `201 CREATED`
  - 返回創建的聊天室信息

#### 範例用法

```bash
# 使用 curl 創建聊天室
curl -X POST http://localhost:8000/api/v1/chatroom/rooms \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -d '{
    "name": "交易策略討論",
    "description": "討論各種加密貨幣交易策略的地方",
    "is_public": true,
    "is_official": false,
    "icon_url": "https://example.com/icons/trading.png"
  }'
```

```javascript
// 使用 JavaScript/Fetch API 創建聊天室
fetch('http://localhost:8000/api/v1/chatroom/rooms', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  },
  body: JSON.stringify({
    name: '交易策略討論',
    description: '討論各種加密貨幣交易策略的地方',
    is_public: true,
    is_official: false,
    icon_url: 'https://example.com/icons/trading.png'
  })
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取聊天室列表

- **URL**: `/rooms`
- **方法**: `GET`
- **描述**: 獲取聊天室列表
- **授權**: 需要 Bearer Token
- **查詢參數**:
  - `skip`: 跳過的記錄數（默認: 0）
  - `limit`: 返回的記錄數（默認: 100，最大: 100）
- **響應**:
  - 狀態碼: `200 OK`
  - 返回聊天室列表

#### 範例用法

```bash
# 使用 curl 獲取聊天室列表
curl -X GET "http://localhost:8000/api/v1/chatroom/rooms?skip=0&limit=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取聊天室列表
fetch('http://localhost:8000/api/v1/chatroom/rooms?skip=0&limit=20', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取特定聊天室

- **URL**: `/rooms/{room_id}`
- **方法**: `GET`
- **描述**: 獲取特定聊天室的詳細信息
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `room_id`: 聊天室ID
- **響應**:
  - 狀態碼: `200 OK`
  - 返回聊天室詳細信息

#### 範例用法

```bash
# 使用 curl 獲取特定聊天室
curl -X GET http://localhost:8000/api/v1/chatroom/rooms/1 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取特定聊天室
fetch('http://localhost:8000/api/v1/chatroom/rooms/1', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### WebSocket 聊天連接

- **URL**: `/ws/user/{token}`
- **方法**: `WebSocket`
- **描述**: 建立聊天WebSocket連接
- **授權**: 通過URL參數提供JWT令牌
- **路徑參數**:
  - `token`: JWT訪問令牌

#### 範例用法

```javascript
// 使用 JavaScript WebSocket API 建立聊天連接
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8000/api/v1/chatroom/ws/user/${token}`);

ws.onopen = function() {
  console.log('聊天WebSocket連接已建立');
  
  // 加入聊天室
  const joinRoomMessage = {
    type: 'join_room',
    room_id: 1
  };
  ws.send(JSON.stringify(joinRoomMessage));
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  console.log('收到消息:', message);
  
  // 處理不同類型的消息
  switch(message.type) {
    case 'chat_message':
      // 處理聊天消息
      displayChatMessage(message);
      break;
    case 'user_joined':
      // 處理用戶加入通知
      break;
    case 'user_left':
      // 處理用戶離開通知
      break;
  }
};

ws.onclose = function(event) {
  console.log('聊天WebSocket連接已關閉');
};

// 發送聊天消息
function sendMessage(roomId, content) {
  const message = {
    type: 'chat_message',
    room_id: roomId,
    content: content
  };
  ws.send(JSON.stringify(message));
}
```

## 在線狀態 API

API前綴: `/api/v1/online-status`

### WebSocket 在線狀態連接

- **URL**: `/ws/status/{token}`
- **方法**: `WebSocket`
- **描述**: 建立在線狀態WebSocket連接
- **授權**: 通過URL參數提供JWT令牌
- **路徑參數**:
  - `token`: JWT訪問令牌

#### 範例用法

```javascript
// 使用 JavaScript WebSocket API 建立在線狀態連接
const token = localStorage.getItem('token');
const ws = new WebSocket(`ws://localhost:8000/api/v1/online-status/ws/status/${token}`);

ws.onopen = function() {
  console.log('在線狀態WebSocket連接已建立');
  
  // 設置定時發送心跳包
  setInterval(() => {
    ws.send(JSON.stringify({ type: 'ping' }));
  }, 30000);
};

ws.onmessage = function(event) {
  const message = JSON.parse(event.data);
  console.log('收到在線狀態消息:', message);
};

ws.onclose = function(event) {
  console.log('在線狀態WebSocket連接已關閉');
};
```

### 獲取聊天室在線用戶

- **URL**: `/rooms/{room_id}/online`
- **方法**: `GET`
- **描述**: 獲取特定聊天室的在線用戶列表
- **授權**: 需要 Bearer Token
- **路徑參數**:
  - `room_id`: 聊天室ID
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "room_id": 1,
      "online_count": 3,
      "online_users": [
        {
          "id": 1,
          "username": "user1",
          "avatar_url": "https://example.com/avatars/user1.jpg",
          "last_active": "2025-04-10T14:30:45.123456"
        },
        {
          "id": 2,
          "username": "user2",
          "avatar_url": "https://example.com/avatars/user2.jpg",
          "last_active": "2025-04-10T14:28:15.654321"
        },
        {
          "id": 3,
          "username": "user3",
          "avatar_url": "https://example.com/avatars/user3.jpg",
          "last_active": "2025-04-10T14:25:10.987654"
        }
      ]
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取聊天室在線用戶
curl -X GET http://localhost:8000/api/v1/online-status/rooms/1/online \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取聊天室在線用戶
fetch('http://localhost:8000/api/v1/online-status/rooms/1/online', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```

### 獲取用戶在線狀態

- **URL**: `/users/online`
- **方法**: `GET`
- **描述**: 獲取指定用戶列表的在線狀態
- **授權**: 需要 Bearer Token
- **查詢參數**:
  - `user_ids`: 用戶ID列表，以逗號分隔（可選，如果未提供，返回當前用戶所在聊天室的所有用戶）
- **響應**:
  - 狀態碼: `200 OK`
  - 格式:
    ```json
    {
      "online_status": {
        "1": true,
        "2": true,
        "3": false
      },
      "total_online": 24
    }
    ```

#### 範例用法

```bash
# 使用 curl 獲取用戶在線狀態
curl -X GET "http://localhost:8000/api/v1/online-status/users/online?user_ids=1,2,3" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

```javascript
// 使用 JavaScript/Fetch API 獲取用戶在線狀態
fetch('http://localhost:8000/api/v1/online-status/users/online?user_ids=1,2,3', {
  method: 'GET',
  headers: {
    'Authorization': 'Bearer ' + localStorage.getItem('token')
  }
})
.then(response => response.json())
.then(data => console.log(data))
.catch(error => console.error('Error:', error));
```