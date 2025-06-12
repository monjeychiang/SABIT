# 身份驗證系統配置參考

本文檔提供身份驗證系統的完整配置參數參考，包括環境變數設置、預設值及其對系統行為的影響。

## 環境變數配置

以下環境變數可在 `.env` 文件中配置：

| 環境變數 | 預設值 | 說明 |
|---------|-------|------|
| `SECRET_KEY` | "your-secret-key" | JWT 簽名密鑰，**生產環境必須更改** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 30 | 存取令牌有效期（分鐘） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 90 | 刷新令牌有效期（天） |
| `EXTENDED_TOKEN_EXPIRE_MINUTES` | 43200 (30天) | 擴展存取令牌有效期（分鐘） |
| `API_ENCRYPTION_KEY` | 從 SECRET_KEY 派生 | API 密鑰加密密鑰 |
| `GOOGLE_CLIENT_ID` | "your-google-client-id" | Google OAuth2 客戶端 ID |
| `GOOGLE_CLIENT_SECRET` | "your-google-client-secret" | Google OAuth2 客戶端密鑰 |
| `GOOGLE_REDIRECT_URI` | "http://localhost:8000/api/v1/auth/google/callback" | Google OAuth2 重定向 URI |
| `DEBUG` | False | 是否啟用調試模式 |

## 程式碼配置常數

以下常數定義於程式碼中，可通過修改源碼調整：

| 常數 | 預設值 | 文件位置 | 說明 |
|-----|-------|---------|------|
| `ALGORITHM` | "HS256" | security.py | JWT 簽名演算法 |
| `TOKEN_CACHE_EXPIRATION` | 5 | security.py | 令牌驗證快取有效期（秒） |
| `REFRESH_CACHE_EXPIRATION` | 45 | auth.py | 刷新結果快取有效期（秒） |
| `GRACE_PERIOD_SECONDS` | 300 | token_grace_store.py | 令牌寬限期（秒） |
| `CACHE_CLEAN_THRESHOLD` | 100 | security.py | 快取清理閾值（項目數） |
| `CACHE_CLEAN_PROBABILITY` | 0.1 | security.py | 快取清理概率 |
| `BATCH_SIZE` | 10 | token_refresh.py | 批次處理大小 |
| `BATCH_INTERVAL` | 0.05 | token_refresh.py | 批次處理間隔（秒） |
| `BATCH_TIMEOUT` | 0.2 | token_refresh.py | 批次處理超時（秒） |

## 特殊配置場景

### 1. 高併發環境

對於高併發環境，建議以下配置：

```
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
TOKEN_CACHE_EXPIRATION=10
REFRESH_CACHE_EXPIRATION=60
BATCH_SIZE=20
```

**說明**：
- 延長存取令牌有效期，減少刷新頻率
- 增加快取有效期，提高快取命中率
- 增加批次處理大小，提高處理效率

### 2. 高安全性環境

對於高安全性要求的環境，建議以下配置：

```
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
TOKEN_CACHE_EXPIRATION=3
REFRESH_CACHE_EXPIRATION=30
GRACE_PERIOD_SECONDS=60
```

**說明**：
- 縮短令牌有效期，降低令牌被盜用的風險
- 減少快取有效期，確保更頻繁的驗證
- 縮短令牌寬限期，減少已撤銷令牌的可用時間

### 3. 移動應用環境

對於主要服務移動應用的環境，建議以下配置：

```
ACCESS_TOKEN_EXPIRE_MINUTES=120
REFRESH_TOKEN_EXPIRE_DAYS=180
TOKEN_CACHE_EXPIRATION=10
EXTENDED_TOKEN_EXPIRE_MINUTES=86400
```

**說明**：
- 延長令牌有效期，減少移動設備的網絡請求
- 增加刷新令牌有效期，改善離線使用體驗
- 啟用擴展存取令牌，支援長時間背景操作

## 配置影響分析

### 存取令牌有效期

| 值 | 安全性 | 使用者體驗 | 伺服器負載 |
|----|-------|-----------|----------|
| 短 (15分鐘) | 高 | 較差，需頻繁刷新 | 高，頻繁刷新請求 |
| 中 (30分鐘) | 中 | 良好 | 中等 |
| 長 (60+分鐘) | 較低 | 優秀，減少刷新 | 低，減少刷新請求 |

### 刷新令牌有效期

| 值 | 安全性 | 使用者體驗 | 說明 |
|----|-------|-----------|------|
| 短 (7天) | 高 | 需要頻繁登入 | 適合敏感資料應用 |
| 中 (30天) | 中 | 良好，月度登入 | 適合一般應用 |
| 長 (90+天) | 較低 | 優秀，極少登入 | 適合消費者應用 |

### 快取配置

| 快取有效期 | 效能 | 即時性 | 適用場景 |
|----------|------|-------|---------|
| 短 (3-5秒) | 中等 | 高 | 標準環境 |
| 中 (10-30秒) | 高 | 中 | 高併發環境 |
| 長 (60+秒) | 非常高 | 低 | 極高併發、低變更環境 |

## 特殊情況處理

### 1. 多設備登入

系統支援同一用戶在多個設備上同時登入，每個設備會獲得獨立的刷新令牌。配置影響：

- `device_id` 生成邏輯位於 `create_refresh_token` 函數
- 預設使用瀏覽器、操作系統和設備資訊的組合作為設備識別符
- 可通過修改 `device_id` 生成邏輯來調整多設備策略

### 2. 令牌撤銷

當用戶登出或管理員強制登出用戶時，系統會撤銷刷新令牌：

- 撤銷實現為直接從資料庫刪除令牌記錄
- 撤銷的令牌會添加到寬限期存儲中
- 寬限期預設為 300 秒，可通過 `GRACE_PERIOD_SECONDS` 調整

### 3. 特殊有效期

某些特殊情況下，系統會使用非預設的令牌有效期：

- Google OAuth2 登入：預設使用標準有效期
- 記住我功能：使用 `EXTENDED_TOKEN_EXPIRE_MINUTES` (預設 30 天)
- API 金鑰認證：無過期時間，但可被撤銷

## 配置檔案範例

### 標準環境 (.env)

```
SECRET_KEY=your-production-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=90
DEBUG=False
```

### 開發環境 (.env.development)

```
SECRET_KEY=dev-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7
DEBUG=True
```

### 測試環境 (.env.test)

```
SECRET_KEY=test-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=5
REFRESH_TOKEN_EXPIRE_DAYS=1
DEBUG=True
``` 