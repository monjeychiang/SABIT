# 刷新令牌功能說明文檔

## 概述

刷新令牌（Refresh Token）功能允許客戶端在訪問令牌（Access Token）過期後獲取新的訪問令牌，而無需用戶重新登錄。這種機制提高了用戶體驗，同時保持了安全性，允許您使用較短的訪問令牌有效期。

## 功能特點

- **長生命週期**：刷新令牌默認有效期為 30 天，而訪問令牌僅有 30 分鐘
- **安全存儲**：刷新令牌存儲在服務器的數據庫中，支持撤銷操作
- **無縫體驗**：前端可以自動處理令牌刷新過程，用戶無需感知
- **支持撤銷**：管理員可以撤銷特定用戶的刷新令牌，強制用戶重新登錄

## 實現原理

1. 用戶登錄時，服務器同時返回訪問令牌和刷新令牌
2. 訪問令牌用於認證 API 請求，有較短的有效期（默認 30 分鐘）
3. 刷新令牌用於獲取新的訪問令牌，有較長的有效期（默認 30 天）
4. 當訪問令牌過期時，客戶端使用刷新令牌請求新的訪問令牌
5. 服務器驗證刷新令牌，如有效則簽發新的訪問令牌

## 數據庫表結構

刷新令牌存儲在 `refresh_tokens` 表中，該表結構如下：

| 欄位名稱 | 類型 | 說明 |
| ------- | --- | ---- |
| id | Integer | 主鍵 |
| user_id | Integer | 關聯用戶的 ID，外鍵 |
| token | String | 刷新令牌值 |
| expires_at | DateTime | 過期時間 |
| created_at | DateTime | 創建時間 |
| is_revoked | Boolean | 是否已撤銷 |

## 安裝說明

要啟用刷新令牌功能，請按照以下步驟操作：

1. 確保您的系統已安裝所有必要的依賴項：

   ```bash
   pip install -r requirements.txt
   ```

2. 運行遷移腳本以創建刷新令牌表：

   ```bash
   cd backend
   python scripts/create_refresh_token_table.py
   ```

3. 可以通過環境變量配置令牌有效期：
   - `ACCESS_TOKEN_EXPIRE_MINUTES`：訪問令牌有效期（分鐘），默認為 30
   - `REFRESH_TOKEN_EXPIRE_DAYS`：刷新令牌有效期（天），默認為 30

## API 使用說明

### 登錄獲取令牌

```http
POST /api/v1/auth/login
Content-Type: application/x-www-form-urlencoded

username=your_username&password=your_password
```

響應：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "refresh_token": "5a4b3c2d1e..."
}
```

### 使用刷新令牌

當訪問令牌過期後，使用刷新令牌獲取新的訪問令牌：

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "5a4b3c2d1e..."
}
```

響應：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### 登出

登出並撤銷刷新令牌：

```http
POST /api/v1/auth/logout
Content-Type: application/json

{
  "refresh_token": "5a4b3c2d1e..."
}
```

響應：

```json
{
  "message": "成功登出"
}
```

## 前端實現示例

以下是在前端實現自動令牌刷新的示例代碼：

```javascript
// 令牌管理與自動刷新
class TokenManager {
  constructor() {
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
    this.refreshTimerId = null;
    
    // 如果有訪問令牌，設置自動刷新
    if (this.accessToken && this.refreshToken) {
      this.setupTokenRefresh();
    }
  }
  
  // 設置令牌（登錄後調用）
  setTokens(accessToken, refreshToken) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    
    this.setupTokenRefresh();
  }
  
  // 清除令牌（登出時調用）
  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    
    if (this.refreshTimerId) {
      clearTimeout(this.refreshTimerId);
      this.refreshTimerId = null;
    }
  }
  
  // 獲取訪問令牌
  getAccessToken() {
    return this.accessToken;
  }
  
  // 設置自動令牌刷新
  setupTokenRefresh() {
    // 清除之前的定時器
    if (this.refreshTimerId) {
      clearTimeout(this.refreshTimerId);
    }
    
    // 設置定時器，提前5分鐘刷新令牌（假設默認30分鐘過期）
    const refreshTime = (30 * 60 - 300) * 1000; // 25分鐘後刷新
    this.refreshTimerId = setTimeout(() => this.refreshAccessToken(), refreshTime);
    
    console.log(`Token refresh scheduled in ${refreshTime/1000} seconds`);
  }
  
  // 刷新訪問令牌
  async refreshAccessToken() {
    try {
      if (!this.refreshToken) {
        console.error('No refresh token available');
        return false;
      }
      
      const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: this.refreshToken
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to refresh token');
      }
      
      const data = await response.json();
      
      // 更新訪問令牌
      this.accessToken = data.access_token;
      localStorage.setItem('access_token', data.access_token);
      
      // 設置下一次刷新
      const refreshTime = (data.expires_in - 300) * 1000; // 提前5分鐘
      this.refreshTimerId = setTimeout(() => this.refreshAccessToken(), refreshTime);
      
      console.log(`Token refreshed, next refresh in ${refreshTime/1000} seconds`);
      return true;
      
    } catch (error) {
      console.error('Error refreshing token:', error);
      // 刷新失敗，可能需要重新登錄
      
      // 這裡可以觸發登錄事件或跳轉到登錄頁面
      // window.dispatchEvent(new CustomEvent('auth:login-required'));
      
      return false;
    }
  }
  
  // 登出
  async logout() {
    try {
      if (!this.refreshToken) {
        this.clearTokens();
        return true;
      }
      
      const response = await fetch('http://localhost:8000/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: this.refreshToken
        }),
      });
      
      // 無論成功與否，都清除本地令牌
      this.clearTokens();
      
      return response.ok;
      
    } catch (error) {
      console.error('Error during logout:', error);
      // 即使出錯，也清除本地令牌
      this.clearTokens();
      return false;
    }
  }
}

// 使用示例
const tokenManager = new TokenManager();

// 登錄後設置令牌
async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  
  try {
    const response = await fetch('http://localhost:8000/api/v1/auth/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error('Login failed');
    }
    
    const data = await response.json();
    tokenManager.setTokens(data.access_token, data.refresh_token);
    
    return true;
  } catch (error) {
    console.error('Login error:', error);
    return false;
  }
}

// API請求工具函數，自動處理令牌刷新
async function apiRequest(url, options = {}) {
  // 設置默認選項
  const defaultOptions = {
    headers: {
      'Authorization': `Bearer ${tokenManager.getAccessToken()}`
    }
  };
  
  // 合併選項
  const requestOptions = { ...defaultOptions, ...options };
  if (options.headers) {
    requestOptions.headers = { ...defaultOptions.headers, ...options.headers };
  }
  
  try {
    let response = await fetch(url, requestOptions);
    
    // 如果返回401未授權，嘗試刷新令牌並重試請求
    if (response.status === 401) {
      const refreshSuccess = await tokenManager.refreshAccessToken();
      
      if (refreshSuccess) {
        // 更新授權頭
        requestOptions.headers['Authorization'] = `Bearer ${tokenManager.getAccessToken()}`;
        // 重試請求
        response = await fetch(url, requestOptions);
      } else {
        throw new Error('Unauthorized and token refresh failed');
      }
    }
    
    return response;
    
  } catch (error) {
    console.error('API request error:', error);
    throw error;
  }
}

// 使用示例
async function fetchUserProfile() {
  try {
    const response = await apiRequest('http://localhost:8000/api/v1/auth/me');
    if (!response.ok) {
      throw new Error('Failed to fetch user profile');
    }
    
    const userData = await response.json();
    console.log('User profile:', userData);
    return userData;
    
  } catch (error) {
    console.error('Error fetching user profile:', error);
    return null;
  }
}
```

## 安全性考量

1. 刷新令牌應該只在安全的 HTTPS 連接下傳輸
2. 前端應將令牌存儲在安全的地方，避免 XSS 攻擊
3. 服務器應該實施適當的 CSRF 保護
4. 刷新令牌不應存儲在 Cookie 中，除非配置了適當的安全選項（如 HttpOnly, Secure, SameSite）

## 配置參數

可以通過環境變量自定義以下配置：

| 環境變量 | 說明 | 默認值 |
| ------- | --- | ------ |
| ACCESS_TOKEN_EXPIRE_MINUTES | 訪問令牌有效期（分鐘） | 30 |
| REFRESH_TOKEN_EXPIRE_DAYS | 刷新令牌有效期（天） | 30 |
| SECRET_KEY | 用於簽署令牌的密鑰 | 無，必須設置 |

## 故障排除

如果您在使用刷新令牌功能時遇到問題，請檢查以下幾點：

1. 確保已正確運行數據庫遷移腳本
2. 檢查環境變量是否正確設置
3. 查看服務器日誌以獲取詳細錯誤信息
4. 檢查刷新令牌是否已過期或被撤銷

如需更多幫助，請參考 API 文檔或聯繫技術支持。 