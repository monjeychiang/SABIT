# schemas 資料夾檔案作用詳解

`schemas` 資料夾包含四個檔案，皆使用 **Pydantic** 定義資料模型，用於資料驗證、API 請求與響應的格式化。這些檔案是後端 API 的核心部分，以下逐一詳細說明：

## 1. `user.py` - 用戶相關資料模型

定義與用戶相關的資料結構：

- **UserBase**: 用戶基本資料（用戶名、電子郵件）。
- **UserCreate**: 創建新用戶，包含密碼與確認密碼。
- **UserUpdate**: 更新用戶資料，如交易所 API 密鑰。
- **UserTagUpdate**: 更新用戶標籤。
- **UserResponse**: 用戶資料的回應格式。
- **Token**: 認證令牌模型。
- **RefreshToken**: 刷新認證令牌。
- **RefreshTokenResponse**: 刷新令牌後的回應。

**作用**：確保用戶註冊、登入及資料管理過程中資料格式一致且合法。

---

## 2. `trading.py` - 交易相關資料模型

定義所有與交易相關的資料結構，是最大的檔案：

### 交易所和訂單枚舉
- **ExchangeEnum**: 支援的交易所（幣安、OKX、Bybit 等）。
- **OrderType**: 訂單類型（限價、市價等）。
- **OrderSide**: 訂單方向（買/賣）。
- **PositionSide**: 持倉方向（多/空）。
- **OrderStatus**: 訂單狀態（開放、關閉等）。

### 訂單相關模型
- **OrderRequest**: 創建訂單的請求。
- **OrderInfo**: 訂單詳細資訊。
- **OrderResponse**: 訂單操作的響應。

### 持倉和資產模型
- **Position**: 持倉資訊。
- **Balance**: 資產餘額。
- **AccountInfo**: 帳戶資訊。

### 槓桿和止盈止損模型
- **LeverageUpdate**: 更新槓桿設置。
- **StopOrder**: 止盈止損訂單。

### 批量操作模型
- **BatchOrderRequest**: 批量下單請求。
- **BatchCancelRequest**: 批量取消訂單。

### 交易對資訊模型
- **SymbolInfo**: 交易對詳細資訊。

**作用**：支援複雜的交易操作與資訊管理。

---

## 3. `settings.py` - 設置相關資料模型

定義交易所 API 設置相關的資料結構：

- **ExchangeAPIBase**: 交易所 API 基本資訊（交易所、API Key、Secret）。
- **ExchangeAPICreate**: 創建新 API 設置。
- **ExchangeAPIUpdate**: 更新 API 設置。
- **ExchangeAPIInDB**: 資料庫儲存的 API 資訊。
- **ExchangeAPIResponse**: API 操作的響應格式。
- **ExchangeAPIListResponse**: API 列表的響應格式。
- **ApiKeyResponse**: API 密鑰的響應格式（僅返回部分資訊，增強安全性）。

**作用**：讓用戶安全地管理與使用交易所 API 設置。

---

## 4. `notification.py` - 通知相關資料模型

定義系統通知及通知偏好設置的資料結構：

### 通知模型
- **NotificationBase**: 通知基本資訊（標題、內容、類型）。
- **NotificationCreate**: 創建通知（包含目標用戶資訊）。
- **NotificationUpdate**: 更新通知狀態（已讀/未讀）。
- **NotificationResponse**: 通知的回應格式。
- **PaginatedNotifications**: 分頁顯示通知的結構。

### 通知設置模型
- **NotificationSettingsBase**: 通知偏好設置（電子郵件、交易、系統等通知）。
- **NotificationSettingsCreate/Update**: 創建與更新通知設置。
- **NotificationSettingsResponse**: 通知設置的回應格式。

**作用**：根據用戶偏好發送通知並管理通知狀態。

---

## 總結

`schemas` 資料夾中的檔案共同構成後端 API 的資料模型層，主要功能包括：

- **資料驗證**：確保輸入資料符合格式與規則。
- **API 文檔**：自動生成詳細的 API 文檔（透過 FastAPI 的 OpenAPI）。
- **請求/響應格式化**：統一 API 的請求與響應格式。
- **資料轉換**：在資料庫模型與 API 資料模型間進行轉換。

這種結構化設計提升系統健壯性，易於維護與擴展，同時為前端提供清晰的資料接口規範。