# 變更摘要

## 2023-10-04: 完善認證系統配置 - 新增 Refresh Token 有效期

### 背景
在檢查認證系統配置時，發現前端顯示的認證參數中缺少了 refresh token 有效期的明確設定，這可能影響到系統對 refresh token 過期時間的正確處理。

### 變更內容
1. 修改 `backend/app/api/endpoints/auth.py` 中的 `/config` 端點：
   - 新增 `refresh_token_expires_in` 參數（以秒為單位）
   - 將 refresh token 有效期由天轉換為秒，方便前端直接使用
   - 為每個配置參數添加了清晰的中文註釋說明其用途

2. 更新 `frontend/src/services/token.ts` 中的 TokenService：
   - 在 `backendConfig` 介面中添加了 `refresh_token_expires_in` 屬性
   - 改進 `setTokens` 方法，使其能夠正確處理 refresh token 的過期時間
   - 實現了多級優先策略：優先使用後端配置，其次使用參數值，最後使用默認配置

### 技術說明
- refresh token 過期時間現在以三種形式提供：
  1. `refresh_token_expire_days`：以天為單位的設定（主要用於配置）
  2. `refresh_token_expires_in`：以秒為單位的設定（用於前端計算）
  3. 傳入 `setTokens` 方法的 `refreshTokenExpiresIn` 參數（由特定API返回）
- 改進的日誌記錄顯示了 refresh token 過期時間的來源和具體值
- 過期時間保存到 localStorage，確保頁面刷新後仍能正確判斷

### 效果
- 完善了認證系統配置，確保前端正確顯示和處理 refresh token 有效期
- 提高了系統穩定性，避免因配置不完整導致的令牌刷新問題
- 增強了日誌信息，便於診斷和監控令牌管理相關問題
- 保持了向後兼容性，支持舊版本的配置方式

## 2023-10-03: 完整實現認證參數設定系統

### 背景
在檢查系統配置時，發現前端顯示的認證參數（refresh threshold、cookie設定等）直接硬編碼在後端API中，而非通過環境變數配置。這種做法降低了系統的靈活性和可配置性，不符合模組化開發的原則。

### 變更內容
1. 在`backend/app/core/config.py`中添加了新的配置參數：
   - `REFRESH_THRESHOLD_SECONDS`：令牌刷新閾值，控制當訪問令牌剩餘有效期少於多少秒時自動刷新
   - 將`USE_SECURE_COOKIES`、`COOKIE_DOMAIN`、`COOKIE_SAMESITE`改為從環境變數讀取

2. 更新了`backend/app/api/endpoints/auth.py`中的`/config`端點：
   - 使用`settings.REFRESH_THRESHOLD_SECONDS`代替硬編碼的300秒值

3. 在`.env`文件中添加了新的環境變數設定：
   - `REFRESH_THRESHOLD_SECONDS=300`
   - `USE_SECURE_COOKIES=false`
   - `COOKIE_DOMAIN=`（留空表示使用當前域名）
   - `COOKIE_SAMESITE=lax`
   - 並加入了詳細的中文註釋說明每個參數的用途

### 技術說明
- 所有認證相關的配置參數現在都可以通過環境變數控制
- 系統會使用合理的默認值，即使環境變數未設置
- 前端通過`/api/v1/auth/config`端點動態獲取這些設定
- 這些參數對令牌刷新和Cookie安全性至關重要

### 效果
- 提高了系統配置的靈活性，可以根據不同環境調整參數
- 增強了系統安全性，可在生產環境啟用安全Cookie
- 改善了代碼的可維護性，減少了硬編碼值
- 完成了認證系統設定的模組化，符合最佳實踐

## 2023-10-02: 完成 TokenService 遷移清理工作

### 背景
在 2023-10-01 的遷移工作中，我們已經將所有對 TokenManager 和舊版 TokenService 的引用更新為使用新的 tokenService 單例。然而，為了確保系統平穩過渡，我們保留了向後兼容層和舊有的檔案。現在所有系統組件已經穩定運行，可以安全地移除這些過渡文件。

### 變更內容
1. 完全刪除了舊版程式碼：
   - `frontend/src/utils/tokenManager.ts`
   - `frontend/src/services/tokenService.ts`
   - `frontend/src/utils/backwardCompatibility.ts`

2. 移除了 Window 介面中的 tokenManager 全局變量定義

3. 修正了所有與 TokenService 方法相關的型別錯誤：
   - 將 `getAuthorizationHeader()` 更正為 `getAuthHeader()`
   - 將 `refreshAccessToken()` 更正為 `refreshTokenIfNeeded()`
   - 將 `logout()` 更正為 `clearTokens()`

### 技術說明
- 系統現在完全使用新的 TokenService 單例實現
- 不再依賴全局變量 `window.tokenManager`
- 改進了型別安全性，明確定義了所有方法參數的型別
- 移除了向後兼容層，減少了代碼複雜度

### 效果
- 減少了約 1,400 行不必要的代碼
- 提高了系統的穩定性和可維護性
- 消除了由多層抽象引起的混淆
- 完成了令牌管理系統現代化的最後一步
- 減少了函數調用堆疊，可能略微提升效能

## 2023-10-01: 完成 TokenService 遷移工作

### 背景
在之前的架構重構中，我們已經合併了 TokenManager 和 TokenService 為單一的 TokenService 單例實現。然而，系統中仍有多個組件和服務使用舊的 getTokenManager() 方法獲取 TokenManager 實例。為了完成完整的遷移，需要將所有這些引用更新為直接使用新的 tokenService 單例。

### 變更內容
1. 更新了以下文件中的 TokenManager 引用為 TokenService：
   - `frontend/src/utils/api.ts`
   - `frontend/src/services/chatService.ts`
   - `frontend/src/services/chatroomService.ts`

2. 移除了所有 `import { getTokenManager } from '@/services/tokenService'` 引用，替換為 `import { tokenService } from '@/services/token'`

3. 移除了通過 getTokenManager() 獲取實例的代碼，直接使用 tokenService 單例

### 技術說明
- 完全移除了對 getTokenManager() 方法的依賴
- 所有服務現在直接使用統一的 tokenService 單例
- 保持了 API 的一致性，所有方法名稱和功能保持不變
- 通過向後兼容層確保舊代碼仍能正常工作

### 效果
- 簡化了代碼結構，移除了不必要的抽象層
- 提高了系統的可維護性，所有令牌相關功能都集中在一個服務中
- 減少了模塊間的依賴，使代碼更加模塊化
- 完成了系統架構優化的最後一步，實現了完全的令牌管理統一

## 2024-07-XX: 前端頁面背景改為漸層色設計

### 背景
為了提升使用者界面的視覺效果和現代感，決定將原本單一顏色的頁面背景修改為漸層色設計。這種漸層背景能提供更加視覺化的深度和層次感，讓整個應用程式看起來更加專業和現代化。

### 變更內容
1. 修改了 `frontend/src/assets/main.css` 文件中的背景設定：
   - 新增了 `--background-gradient` CSS 變數到根樣式中
   - 為淺色主題設定漸層背景：`linear-gradient(135deg, #f9fafb 0%, #e6f0ff 100%)`
   - 為深色主題設定漸層背景：`linear-gradient(135deg, #121212 0%, #1e2940 100%)`
   - 將 `body` 和 `.page-container` 的 `background-color` 屬性更改為使用 `background: var(--background-gradient)`

### 技術說明
- 使用 CSS 漸層背景提供更有深度的視覺效果
- 保留了深色模式與淺色模式的主題切換機制
- 漸層角度設定為 135 度，創造右上到左下的對角線漸層效果
- 使用與原始顏色方案相協調的顏色，確保與其他UI元素的視覺和諧

### 效果
- 提升了整體用戶界面的視覺吸引力
- 為應用程式增添了更多視覺深度和層次
- 保持了主題切換功能的完整性
- 改善了用戶體驗，使界面更現代化和專業化

## 2023-11-XX: 優化 CCXT 連接預熱功能減少冗餘日誌輸出

### 背景
在使用 CCXT 連接預熱功能時，系統會產生大量詳細的交易所 API 響應日誌，這些日誌包含所有交易對的詳細配置信息。雖然這些信息對於調試很有用，但在正常運行時可能會佔用大量日誌空間，影響系統監控的可讀性。

### 變更內容
1. 修改了 `backend/app/services/trading.py` 中的 `preheat_exchange_connection` 方法：
   - 添加了臨時調整 CCXT 日誌級別的邏輯
   - 在方法開始時保存原始日誌級別並將 CCXT 日誌級別提高到 WARNING
   - 在方法結束時恢復原始日誌級別

### 技術細節
- 具體調整了 `ccxt` 和 `ccxt.base.exchange` 兩個日誌記錄器的級別
- 使用 `finally` 區塊確保無論預熱成功與否都會恢復原始日誌級別
- 此修改不影響預熱功能的正常運作，只減少了日誌輸出

### 影響
- 大幅減少了預熱過程中產生的冗餘日誌
- 提高了系統日誌的可讀性
- 減少了日誌檔案大小和存儲需求
- 保留了必要的信息日誌，確保仍能監控預熱過程的成功與否

## 2023-11-XX: 修復 CCXT 連接預熱功能中的匯入錯誤

### 背景
在 `preheat_exchange_connection` 方法中發現了一個匯入錯誤，系統嘗試使用 `from ...db.models import User` 進行匯入，但這種相對匯入路徑在當前模組結構中是不正確的，導致 Pylance 報告 "無法解析匯入 \"...db.models\"" 錯誤。

### 變更內容
1. 修改了 `backend/app/services/trading.py` 中的 `preheat_exchange_connection` 方法：
   - 移除了重複的 `from ...db.models import User` 匯入語句
   - 使用已經在文件頂部正確匯入的 `User` 模型

### 技術細節
- 問題原因：在方法內部使用了不正確的相對匯入路徑
- 解決方案：移除冗餘匯入，使用文件頂部已經正確匯入的模型
- 這種修改確保了代碼的一致性和正確性，同時解決了靜態類型檢查工具報告的錯誤

### 影響
- 修復了 IDE 中顯示的匯入錯誤
- 提高了代碼的可讀性和一致性
- 確保 CCXT 連接預熱功能能夠正確運行

## 2024-06-15: PowerShell 命令運行方式調整

### 背景
在 Windows PowerShell 環境中，`&&` 不是有效的命令分隔符，這與 Bash 和 CMD 環境不同。在嘗試運行如 `cd backend && python main.py` 這樣的命令時會出現 `The token '&&' is not a valid statement separator in this version` 錯誤。

### 變更內容
1. 更新開發文檔，說明在 PowerShell 中運行命令的正確方式：
   - 使用分號 `;` 作為命令分隔符：`cd backend; python main.py`
   - 或使用單獨的命令行：先 `cd backend`，然後運行 `python main.py`
   - 或使用 PowerShell 的 `-Command` 參數：`powershell -Command "cd backend; python main.py"`

2. 更新相關腳本和文檔：
   - 修改開發指南中的命令示例
   - 更新自動化腳本，使其在 PowerShell 環境中正確運行

### 技術說明
- PowerShell 使用分號 `;` 作為命令分隔符，而不是 Bash 和 CMD 中常用的 `&&`
- 如果需要有條件地執行下一個命令（即前一個命令成功後才執行），可以使用 PowerShell 的錯誤處理語法：
  ```powershell
  cd backend
  if ($?) { python main.py }
  ```

### 效果
- 開發者可以在 Windows PowerShell 環境中正確運行命令
- 避免了因命令語法錯誤導致的開發環境問題
- 提高了跨平台開發的一致性

## 2024-06-15: 修復密鑰類型混用問題 - 明確分離 HMAC-SHA256 和 Ed25519 密鑰

### 背景
系統支持兩種類型的密鑰：HMAC-SHA256 和 Ed25519。HMAC-SHA256 密鑰主要用於 REST API 連接，而 Ed25519 密鑰專用於某些交易所（如 Binance）的 WebSocket API 連接。然而，在代碼中存在邏輯缺陷，如果找不到一種類型的密鑰，系統會自動嘗試使用另一種類型，這可能導致錯誤的認證嘗試和連接失敗。

### 變更內容

#### 1. 修改 `api_key_manager.py`
- 更新 `get_real_api_key` 方法，添加強制性 `key_type` 參數
- 明確區分 "hmac_sha256" 和 "ed25519" 密鑰類型
- 移除自動切換密鑰類型的邏輯
- 添加密鑰類型驗證，防止使用錯誤類型

#### 2. 更新 `exchange_connection_manager.py`
- 新增 `connection_type` 參數（"websocket" 或 "rest"）
- 根據連接類型自動選擇相應的密鑰類型
- 優化緩存鍵生成，加入連接類型作為區分
- 改進錯誤處理和日誌記錄，提供更明確的錯誤信息

#### 3. 修改 `account.py`
- 在 `futures_account_websocket` 和 `get_account_data` 函數中明確指定所需的連接類型和密鑰類型
- 移除嘗試在不同類型密鑰之間切換的邏輯
- 添加更詳細的錯誤信息，幫助用戶理解所需的密鑰類型

### 技術說明
- 密鑰類型現在是明確指定的，而不是自動檢測或切換
- WebSocket 連接需要指定 `connection_type="websocket"`，自動使用 Ed25519 密鑰
- REST API 連接需要指定 `connection_type="rest"`，自動使用 HMAC-SHA256 密鑰
- 緩存機制已更新，根據連接類型和用戶 ID 分別存儲不同類型的連接

### 效果
- 提高系統穩定性，避免因密鑰類型混用導致的認證失敗
- 改善用戶體驗，提供更明確的錯誤信息
- 增強代碼可維護性，明確區分不同連接類型的處理邏輯
- 保留不同密鑰類型的優勢，同時避免相互干擾

### 使用注意事項
- 開發新功能時，應明確指定所需的連接類型和密鑰類型
- 在使用 WebSocket API 時，確保已配置正確的 Ed25519 密鑰
- 在使用 REST API 時，確保已配置正確的 HMAC-SHA256 密鑰

# 更新摘要 (2024-06-13)

## 前端 CCXT 連接預熱功能

### 背景
在用戶登入後，系統需要與交易所建立連接以執行交易操作。原先的設計中，第一次執行交易操作時才會建立連接，導致用戶體驗到明顯的延遲。為了改善這一問題，我們實現了 CCXT 連接預熱功能，在用戶登入後立即初始化交易所連接，以減少後續交易操作的延遲。

### 變更內容

#### 1. 新增 `tradingService.ts` 服務
- 創建了專門的交易服務，用於管理所有交易相關功能
- 實現了 `preheatExchangeConnection` 方法，用於預熱單個交易所的 CCXT 連接
- 實現了 `preheatMultipleExchanges` 方法，用於同時預熱多個交易所的連接
- 添加了基本的交易查詢方法，如 `getAccountInfo`、`getAssetBalance` 和 `getSymbolInfo`

#### 2. 更新 `authService.ts` 服務
- 添加了 `preheatCcxtConnections` 方法，在用戶登入後自動調用
- 整合了 `tradingService` 的預熱功能，確保用戶登入後立即初始化交易所連接

### 技術說明
- 前端通過調用後端的 `/trading/preheat` API 端點來預熱 CCXT 連接
- 預熱過程在背景執行，不會阻塞用戶界面
- 目前默認只預熱 Binance 交易所連接，但代碼已支持擴展到多個交易所
- 預熱失敗不會影響用戶正常使用，只是可能導致首次交易操作有延遲

### 效果
- 減少了用戶首次執行交易操作時的等待時間
- 提高了系統的響應速度和用戶體驗
- 為未來添加更多交易功能奠定了基礎
- 通過模塊化設計，使交易相關功能更易於維護和擴展

---

# 更新摘要 (2024-06-12)

## CCXT 連接邏輯優化 - 僅使用 HMAC-SHA256 密鑰

### 背景
在系統的 WebSocket 連接中，我們已經明確區分了不同交易所對不同密鑰類型的需求（如 Binance WebSocket 需要 Ed25519 密鑰）。但在 CCXT 連接邏輯中，系統原先會嘗試使用所有可用的密鑰類型，包括 Ed25519 密鑰，而 CCXT 僅支持 HMAC-SHA256 密鑰格式。這導致在某些情況下，系統可能會使用不兼容的 Ed25519 密鑰嘗試建立 CCXT 連接，進而導致連接失敗。

### 變更內容

#### 1. 修改 `connection_pool.py` 中的密鑰獲取邏輯
- 更新 `get_client_with_cache` 方法，僅獲取和使用 HMAC-SHA256 密鑰
- 修改 `refresh_client_with_cache` 方法，確保只使用 HMAC-SHA256 密鑰刷新連接
- 更新 `check_client_health_with_cache` 方法，保持與上述變更一致

#### 2. 修改 `trading.py` 中的客戶端獲取邏輯
- 更新 `_get_exchange_client_for_user` 方法，明確指定僅使用 HMAC-SHA256 密鑰
- 添加更明確的錯誤處理，當未找到 HMAC-SHA256 密鑰時提供清晰的錯誤信息

#### 3. 更新 `exchange.py` 中的函數文檔
- 明確標註 `get_exchange_client` 函數只支持 HMAC-SHA256 密鑰格式
- 添加詳細說明，防止誤用 Ed25519 密鑰

### 技術說明
- 修改後的代碼僅會嘗試從 `SecureKeyCache` 或 `ApiKeyManager` 獲取 HMAC-SHA256 密鑰
- 所有與 CCXT 相關的方法均添加了明確的註釋，標明僅支持 HMAC-SHA256 密鑰
- 添加了更明確的錯誤信息，當用戶嘗試使用 Ed25519 密鑰進行 CCXT 連接時提供有用的診斷信息

### 效果
- 避免了 CCXT 使用不兼容的 Ed25519 密鑰導致的連接錯誤
- 增強了系統穩定性，減少不必要的連接失敗
- 提供了更清晰的文檔和錯誤信息，改善開發和使用體驗
- 使密鑰類型的處理更加明確和一致，區分了 WebSocket 和 CCXT 的不同需求

---

# 更新摘要 (2024-06-08)

## 網格交易模塊 API 密鑰管理優化

### 背景
在對系統進行全面檢查時，發現網格交易模塊（gridbot.py）仍在使用舊有的方式直接從數據庫獲取 API 密鑰，而未充分利用已實現的 `ApiKeyManager` 和 `SecureKeyCache` 系統。為提高整體系統的一致性和安全性，我們優化了 `settings.py` 中的 `get_user_api_keys` 函數，使其完全採用現代化的密鑰管理方式。

### 變更內容
1. **優化 `settings.py` 中的 `get_user_api_keys` 函數**：
   - 加入 `SecureKeyCache` 整合，優先從緩存獲取密鑰
   - 移除直接從數據庫解密密鑰的邏輯
   - 統一使用 `ApiKeyManager` 的解密方法
   - 解密後的密鑰自動存入緩存以提高性能

2. **密鑰類型區分**：
   - 明確分離 HMAC-SHA256 和 Ed25519 密鑰的處理邏輯
   - 為不同類型的密鑰添加適當的日誌記錄

### 技術優勢
1. **系統一致性**：所有模塊統一使用 `ApiKeyManager` 和 `SecureKeyCache`
2. **性能提升**：減少重複解密操作，充分利用緩存機制
3. **安全加強**：統一的安全機制確保密鑰處理一致且安全
4. **維護簡化**：代碼結構更清晰，維護更容易

### 影響範圍
- 網格交易相關功能（gridbot.py）
- 所有使用 `get_user_api_keys` 函數的系統組件
- API 密鑰查看和管理功能

### 使用說明
- 系統內部獲取密鑰時，應優先使用 `ApiKeyManager.get_real_api_key`
- 需要批量獲取所有交易所密鑰時，可使用優化後的 `get_user_api_keys`
- 任何新功能開發都應直接使用 `ApiKeyManager` 和 `SecureKeyCache`

## API密鑰系統優化 - ApiKeyProxy 直接刪除

### 背景
先前計劃中，我們提出了將 `ApiKeyProxy` 轉為轉發層作為過渡方案。經過進一步評估，發現系統中已無任何地方直接依賴 `ApiKeyProxy`，所有功能均已遷移至 `ApiKeyManager`。因此，決定跳過轉發層階段，直接刪除 `ApiKeyProxy`。

### 變更內容
1. **直接刪除**：完全移除 `ApiKeyProxy` 模組
2. **確認替代**：確認所有功能已由 `ApiKeyManager` 實現
3. **更新文檔**：更新相關文檔，標示 `ApiKeyManager` 為官方 API 密鑰管理接口

### 技術優勢
1. **簡化架構**：消除不必要的抽象層和過渡方案
2. **減少維護成本**：避免維護兩套相似的代碼
3. **性能提升**：直接調用 `ApiKeyManager`，減少函數調用堆疊
4. **清晰依賴**：明確 `ApiKeyManager` 為唯一的 API 密鑰管理方式

### 使用指南
- 所有需要操作 API 密鑰的地方，請直接使用 `ApiKeyManager`
- 常用方法對照：
  - `create_virtual_key`：創建虛擬密鑰
  - `get_real_api_key`：獲取真實 API 密鑰
  - `update_virtual_key_permissions`：更新虛擬密鑰權限
  - `deactivate_virtual_key`：停用虛擬密鑰
  - `log_api_usage`：記錄 API 使用情況

# 更新摘要 (2024-06-04)

## 前端更新
- 添加網格交易功能相關組件
  - 新增 GridStrategyList 組件
  - 添加網格交易服務 (gridTradingService.ts)
  - 實現網格交易狀態管理 (grid-trading.ts)
  - 新增 GridTrading 視圖
- 添加版本歷史對話框組件 (VersionHistoryDialog.vue)
- 添加版本歷史服務 (versionHistoryService.ts)
- 更新環境配置 (.env.development, .env.production)
- 優化 WebSocket 服務連接管理
- 更新路由配置以支持新功能
- 優化聊天室服務

## 後端更新
- 實現網格交易功能
  - 添加網格交易資料庫模型 (app/db/models/grid.py)
  - 添加網格交易相關 schema (app/schemas/grid.py)
  - 實現網格交易服務邏輯 (app/services/grid/)
  - 新增網格交易 API 端點
- 優化聊天室功能
  - 添加聊天室管理器 (app/core/chat_room_manager.py)
  - 更新聊天室 API 端點
- 改進交易所連接管理
  - 新增交易所連接管理器 (utils/exchange_connection_manager.py)
  - 重構連接池邏輯 (utils/connection_pool.py)
  - 更新交易所工具函數 (utils/exchange.py)
- 增強在線狀態管理功能
- 優化 WebSocket 管理器
- 更新用戶模型和相關功能
- 添加資料庫遷移腳本 (20240604_add_grid_trading_models.py)

## 性能優化
- 優化前端組件加載方式
- 改進 WebSocket 連接管理
- 優化資料庫查詢
- 減少不必要的 API 請求

## 修復的問題
- 修復聊天室消息同步問題
- 解決用戶在線狀態更新延遲問題
- 修復交易所 API 連接穩定性問題
- 修正通知系統的處理邏輯

# 更新摘要 (2024-06-05)

## 後端安全性和性能增強
- 加強用戶賬戶安全
  - 更新安全配置 (app/core/security.py)
  - 優化賬戶端點邏輯 (app/api/endpoints/account.py)
  - 改進設置管理 (app/api/endpoints/settings.py)
- 提升交易功能
  - 優化交易端點 (app/api/endpoints/trading.py)
  - 改進交易服務邏輯 (app/services/trading.py)
  - 完善交易所 API 模型 (app/db/models/exchange_api.py)
- 增強 WebSocket 連接處理
  - 改進 Binance WebSocket 客戶端 (utils/binance_ws_client.py)
  - 優化連接池管理 (utils/connection_pool.py)
- 更新項目文檔 (backend/README.md)

## 性能優化
- 減少交易 API 請求延遲
- 優化 WebSocket 連接穩定性
- 改進數據庫查詢效率

## 修復的問題
- 修正交易所 API 鑰匙存取權限問題
- 解決賬戶設置同步延遲
- 修復部分 API 端點的錯誤處理

# 變更摘要

## 2023-11-XX: 修復 CCXT 連接預熱功能中的匯入錯誤

### 背景
在 `preheat_exchange_connection` 方法中發現了一個匯入錯誤，系統嘗試使用 `from ...db.models import User` 進行匯入，但這種相對匯入路徑在當前模組結構中是不正確的，導致 Pylance 報告 "無法解析匯入 \"...db.models\"" 錯誤。

### 變更內容
1. 修改了 `backend/app/services/trading.py` 中的 `preheat_exchange_connection` 方法：
   - 移除了重複的 `from ...db.models import User` 匯入語句
   - 使用已經在文件頂部正確匯入的 `User` 模型

### 技術細節
- 問題原因：在方法內部使用了不正確的相對匯入路徑
- 解決方案：移除冗餘匯入，使用文件頂部已經正確匯入的模型
- 這種修改確保了代碼的一致性和正確性，同時解決了靜態類型檢查工具報告的錯誤

### 影響
- 修復了 IDE 中顯示的匯入錯誤
- 提高了代碼的可讀性和一致性
- 確保 CCXT 連接預熱功能能夠正確運行

## 2023-11-XX: 修復 CCXT 連接預熱功能

### 背景
在用戶登入後，系統會嘗試預熱 CCXT 連接以減少首次交易操作的延遲，但發現 API 端點 `/api/v1/trading/preheat` 返回 404 錯誤。

### 變更內容
1. **修復後端路由配置**：
   - 在 `backend/app/main.py` 中取消註釋交易 API 路由的部分，啟用 `/api/v1/trading/preheat` 端點。
   - 確保 `trading.py` 中定義的 API 路由能夠被正確註冊。

2. **增強前端錯誤處理**：
   - 在 `tradingService.ts` 中增加了路徑嘗試邏輯，當一個路徑失敗時會自動嘗試其他可能的路徑。
   - 添加了詳細的錯誤日誌，便於診斷問題。

### 技術細節
- 問題原因：在 `main.py` 中，交易 API 路由被註釋掉，導致 `/api/v1/trading/preheat` 端點無法訪問。
- 解決方案：取消註釋並啟用交易 API 路由，同時保留網格交易路由。
- 前端增強：增加了多路徑嘗試邏輯，提高了系統的健壯性。

### 效果
- 修復了 CCXT 連接預熱功能，用戶登入後能夠成功預熱連接。
- 減少了用戶首次交易操作的延遲時間。
- 提高了系統的錯誤處理能力和用戶體驗。

## 2023-10-01: Token 管理系統重構

### 變更摘要
重新設計前端的令牌（Token）管理機制，將原有的 TokenManager 和 TokenService 合併為單一的 TokenService 單例實現。

### 技術細節
- 實現了統一的 TokenService 單例類，整合所有令牌管理功能
- 提供向後兼容層，確保現有代碼持續運作
- 更新了應用初始化流程，使用新的 TokenService
- 添加了遷移文檔，幫助開發者從舊系統遷移到新系統

### 動機
1. 消除「解決不了就再加一層」的情況，簡化系統架構
2. 減少重複代碼和多餘的抽象層
3. 提高認證機制的可維護性和可測試性
4. 消除對全局變量的依賴，改進模塊化設計

### 影響範圍
- 所有依賴 TokenManager 和 TokenService 的組件
- 主應用初始化流程
- 認證相關功能

### 遷移計劃
分三階段完成遷移：
1. 建立新架構並提供向後兼容層（當前階段）
2. 逐步更新各組件和服務使用新的 TokenService
3. 一旦所有代碼都更新，移除向後兼容層

詳細遷移指南請參見 `frontend/src/docs/TOKEN_MIGRATION.md`。 