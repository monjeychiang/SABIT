# 變更摘要

## 2024-07-01: 移除 naive-ui 依賴，統一使用 element-plus UI 庫

### 背景
原專案同時使用了 element-plus 和 naive-ui 兩個大型 UI 庫，這導致了打包體積增大、可能的樣式衝突以及維護複雜度提高的問題。為了優化前端效能和降低維護成本，決定統一只使用 element-plus 作為專案的 UI 框架。

### 變更內容
1. **移除 naive-ui 依賴**：
   - 從 package.json 中移除 naive-ui 依賴項
   - 更新 vite.config.ts 中的 AutoImport 插件配置，移除 naive-ui 相關導入
   - 從 auto-imports.d.ts 中移除 naive-ui 的自動導入聲明

2. **優化 SettingsView.vue 組件**：
   - 移除未使用的 naive-ui 組件導入
   - 替換為 element-plus 的對應組件
   - 確保組件功能保持一致

### 技術說明
- 使用 element-plus 的 ElTabs、ElTabPane、ElForm 等組件替代 naive-ui 的對應組件
- 確保自動導入配置只包含 element-plus 組件
- 保留原有的 CSS 樣式和功能，確保 UI 外觀和體驗一致

### 效益
1. **減小打包體積**：移除冗餘的 UI 庫依賴，減少最終打包體積
2. **避免樣式衝突**：使用單一 UI 框架，避免不同框架間的樣式衝突
3. **簡化維護**：開發團隊只需掌握一個 UI 框架的使用方法
4. **提高開發效率**：統一的組件庫使開發更加高效和一致
5. **優化性能**：減少不必要的 JavaScript 代碼，提升應用載入和運行速度

### 相關檔案
- `frontend/package.json`：移除 naive-ui 依賴
- `frontend/vite.config.ts`：更新 AutoImport 插件配置
- `frontend/auto-imports.d.ts`：移除 naive-ui 相關導入聲明
- `frontend/src/views/SettingsView.vue`：移除 naive-ui 組件導入，替換為 element-plus

## 2024-03-18: 刷新令牌並發處理優化 - 實現分佈式鎖機制

### 背景
在高流量環境中，用戶經常會連續多次點擊刷新頁面或在短時間內觸發多個需要令牌刷新的操作。原先的系統採用簡單的節流機制（2秒內返回相同響應），但這種機制無法有效解決多個並發請求同時處理的問題，導致後端可能在節流機制生效前已經處理了多個刷新請求，產生多個不同的令牌。這使得前端存儲的令牌與後端最新有效令牌不一致，導致認證錯誤。

### 變更內容
1. **實現用戶級別的分佈式鎖機制**：
   - 使用線程安全的鎖確保同一用戶在同一時間只能處理一個令牌刷新請求
   - 並發請求採用非阻塞方式嘗試獲取鎖，失敗時進入等待模式
   - 實現最大等待時間（5秒）機制，避免請求無限等待

2. **結果緩存與請求合併**：
   - 成功處理的請求結果被緩存30秒，用於響應同一用戶的後續請求
   - 所有等待中的請求共享同一個處理結果，確保令牌一致性
   - 緩存自動清理機制，避免內存洩漏

3. **健壯的錯誤處理**：
   - 確保鎖在任何情況下都能被正確釋放，防止死鎖
   - 等待超時的請求返回429錯誤，避免服務阻塞
   - 詳細的日誌記錄，便於問題診斷

### 技術說明
- 使用 `threading.RLock` 實現可重入鎖，確保線程安全
- 使用 `time.time()` 進行時間控制，確保請求不會無限等待
- 採用唯一請求ID（UUID）追蹤請求生命週期
- 緩存結果使用 `{user_id: {timestamp, tokens}}` 格式存儲，支持快速查找
- 設計兼容單機部署，同時預留了擴展至Redis分佈式鎖的接口

### 效益
1. **解決令牌不一致問題**：確保用戶在短時間內多次刷新頁面時使用的是同一個令牌
2. **降低系統負載**：減少不必要的令牌生成和數據庫操作
3. **提升用戶體驗**：減少因令牌不一致導致的認證錯誤
4. **優化後端性能**：避免相同用戶的重複處理，提高系統吞吐量
5. **增強系統彈性**：即使用戶「手賤」連續點擊也能穩定運行

### 相關檔案
- `backend/app/api/endpoints/auth.py`：修改 `refresh_access_token` 函數，實現分佈式鎖機制

## 2024-03-15: 實現令牌寬限期機制

### 背景
在高流量環境下，當多個標籤頁或設備同時使用時，系統可能出現前後端令牌不同步的情況。例如，用戶在一個標籤頁登出或重新登入後，其他標籤頁可能仍使用舊令牌，導致請求失敗。為提升系統容錯性和使用者體驗，我們實現了令牌寬限期機制。

### 變更內容
1. **令牌寬限期儲存系統**：
   - 建立 `TokenGraceStore` 類，提供內存中的緩存機制，允許最近撤銷或更新的令牌在短時間內仍然有效
   - 實現自動清理過期令牌的背景任務，避免內存無限增長
   - 添加可配置的寬限期長度和清理間隔設定

2. **令牌管理強化**：
   - 修改 `create_refresh_token` 函數，在更新令牌時將舊令牌添加到寬限期儲存
   - 更新 `revoke_refresh_token` 函數，將撤銷的令牌添加到寬限期儲存
   - 優化 `verify_refresh_token` 函數，增加寬限期令牌驗證邏輯

3. **前端交互優化**：
   - 在API響應中添加 `X-Token-Grace-Period` 標頭，通知前端請求使用了寬限期令牌
   - 優化前端處理，使其能夠理解寬限期相關響應

### 技術說明
- 寬限期機制使用內存緩存實現，無需依賴外部Redis等服務
- 采用線程安全的設計，支持高併發場景
- 可通過環境變量配置寬限期長度、清理間隔和調試日誌開關
- 為使用寬限期機制的令牌添加特殊標記，便於追蹤和監控

### 效益
1. **提升系統容錯性**：多標籤頁或多設備使用時，減少因令牌不同步導致的錯誤
2. **改善使用者體驗**：減少用戶因認證錯誤需要重新登入的情況
3. **優化系統性能**：通過內存緩存機制實現，幾乎無性能開銷
4. **增強系統彈性**：在不添加外部依賴的情況下提高系統穩定性
5. **易於維護**：配置靈活，可根據實際需求調整寬限期參數

### 相關檔案
- `backend/app/core/token_grace_store.py`：新增寬限期存儲類
- `backend/app/core/config.py`：添加寬限期相關配置
- `backend/app/core/security.py`：修改令牌管理相關函數
- `backend/app/api/endpoints/auth.py`：更新刷新令牌API端點
- `backend/.env`：新增寬限期配置參數

## 2025-06-10: 解決刷新令牌重複處理問題並實現節流機制

### 背景
在系統日誌中發現，當前端執行刷新令牌操作時，常常會在短時間內發送多個完全相同的請求，導致後端重複處理這些請求。這不僅增加了伺服器負載，還導致日誌中出現大量冗餘信息，甚至可能引發令牌狀態不一致的問題。

### 變更內容
1. **後端節流機制**：
   - 在 `refresh_access_token` 函數中添加請求 ID 和用戶特定的節流緩存
   - 對於同一用戶在2秒內的重複請求，直接返回之前生成的令牌，避免重複處理
   - 添加請求 ID 到日誌輸出，便於跟蹤和分析請求流程
   - 實現緩存自動清理機制，防止記憶體洩漏

2. **前端統一刷新機制**：
   - 在 `tokenService.refreshToken_` 中添加時間戳節流控制
   - 將 `authService.tryRefreshToken` 和 `authStore.refreshAccessToken` 統一使用 `tokenService.refreshTokenIfNeeded`
   - 使用本地存儲記錄上次刷新時間和結果，避免短時間內重複刷新
   - 增加全局等待機制，確保多個組件同時請求刷新時只發送一個真正的請求

### 技術說明
- 後端使用記憶體緩存實現簡單的節流控制，避免同一用戶短時間內的重複處理
- 前端使用三層防重複機制：
  1. `refreshPromise` 防止同一執行流程中的重複刷新
  2. 時間戳節流控制，限制刷新頻率不超過每2秒一次
  3. 統一的刷新入口，避免不同組件各自實現刷新邏輯

### 效益
1. **減輕伺服器負載**：大幅減少重複的令牌刷新請求，降低數據庫和伺服器負擔
2. **提高系統穩定性**：避免短時間內多次修改同一個令牌記錄，減少並發問題
3. **優化日誌輸出**：減少冗餘日誌，使系統日誌更加清晰易讀
4. **改善用戶體驗**：減少網絡請求次數，提高前端響應速度
5. **提升代碼質量**：統一刷新令牌入口，使令牌管理邏輯更加一致和可維護

### 相關檔案
- `backend/app/api/endpoints/auth.py`：添加後端節流機制和請求ID追蹤
- `frontend/src/services/token.ts`：添加前端時間戳節流控制
- `frontend/src/services/authService.ts`：統一使用tokenService的刷新機制
- `frontend/src/stores/auth.ts`：修改刷新訪問令牌的實現，避免重複請求

## 2023-12-01: 優化登出流程日誌記錄

### 背景
在審查系統日誌時，發現登出流程中的日誌訊息存在重複和不夠清晰的問題。特別是當清除刷新令牌 cookie 時，系統會生成多個相似的日誌記錄，增加了日誌分析的難度。此外，一些日誌訊息的表述不夠準確，難以反映實際執行的操作。

### 變更內容
1. **優化 `clear_refresh_token_cookie` 函數**：
   - 移除函數內部的冗餘日誌輸出，避免與調用者日誌重複
   - 將日誌責任轉移到具體的調用函數中，使日誌上下文更加清晰

2. **改進 `logout` 函數日誌**：
   - 使用更精確的描述來反映令牌操作狀態
   - 明確區分「撤銷令牌」和「清除 cookie」兩個不同的操作
   - 調整日誌用詞，使其更準確地描述操作結果

3. **增強 `set_refresh_token_cookie` 函數日誌**：
   - 添加更詳細的令牌有效期信息，包括天數和具體到期日期
   - 使用 `get_china_time()` 函數計算並顯示本地時間格式的到期日期
   - 提供更易於理解的時間格式，而非純秒數

### 技術說明
- 調整了日誌輸出策略，確保每個關鍵操作只記錄一次，避免冗餘
- 統一了日誌訊息格式和用詞，提高了系統日誌的一致性
- 優化了時間顯示格式，從秒數改為更易讀的「天數+日期時間」格式
- 確保在有無 refresh token cookie 的情況下都有清晰的日誌記錄

### 效益
1. **提升日誌可讀性**：更清晰的日誌訊息使系統行為更容易理解
2. **減少日誌噪音**：移除重複和冗餘的日誌記錄，降低日誌數量
3. **改善問題診斷**：更精確的狀態描述有助於快速定位問題
4. **增強系統透明度**：通過明確的日誌記錄，使系統行為更加透明化

### 相關檔案
- `backend/app/api/endpoints/auth.py`：修改了 `set_refresh_token_cookie`、`clear_refresh_token_cookie` 和 `logout` 函數

## 2023-11-30: 優化長期登入體驗

### 背景
用戶需要在長時間不使用應用程式後仍能保持登入狀態，不必每次重新登入。原有的認證系統已經實施了 HTTP-only cookie 和刷新令牌機制，但設定的默認保持時間較短，且「保持登入」選項需要用戶主動勾選，影響了長期使用的用戶體驗。

### 變更內容
1. **延長令牌有效期**：
   - 將刷新令牌有效期從 7 天延長至 90 天（`REFRESH_TOKEN_EXPIRE_DAYS`）
   - 將訪問令牌有效期從 1440 分鐘延長至 2880 分鐘（`ACCESS_TOKEN_EXPIRE_MINUTES`）

2. **自動啟用「保持登入」選項**：
   - 修改前端登入表單，將「保持登入」選項默認設為已勾選
   - 更新 GoogleAuth 登入流程中的 `keepLoggedIn` 默認值為 `true`

3. **令牌刷新邏輯優化**：
   - 修改所有令牌刷新相關函數，將 `keepLoggedIn` 默認值設為 `true`
   - 調整 `localStorage` 判斷邏輯，從「默認為 false」改為「默認為 true」

### 技術說明
- 將所有前端代碼中 `localStorage.getItem('keepLoggedIn') === 'true'` 的判斷改為 `localStorage.getItem('keepLoggedIn') !== 'false'`，確保默認值為 `true`
- 統一 Cookie 設置邏輯，確保長期 Cookie 能被正確設置和使用
- 在用戶使用「保持登入」選項時，確保刷新令牌在 90 天內有效

### 效益
1. **改善用戶體驗**：用戶不再需要頻繁登入，即使長時間未使用應用程式
2. **減少認證請求**：減少了因令牌短期過期而需要的重新認證次數
3. **符合現代應用預期**：大多數現代應用都提供長期登入功能，此變更使系統符合用戶期待
4. **無縫體驗**：用戶在不同裝置間切換使用時，可以獲得更連貫的體驗

### 相關檔案
- `backend/.env`：修改令牌有效期設定
- `frontend/src/components/NavBar.vue`：更新登入表單默認值
- `frontend/src/stores/auth.ts`：修改 Google 登入及令牌刷新相關函數
- `frontend/src/services/token.ts`：優化令牌管理及刷新邏輯
- `frontend/src/services/authService.ts`：更新令牌刷新默認行為

## 2023-11-29: 刷新令牌處理機制優化 - 刪除而非標記已撤銷令牌

### 背景
在之前的"更新而非新增"策略實施中，發現一個重要問題：系統在撤銷刷新令牌時只是將其標記為已撤銷（`is_revoked=True`），而未從資料庫中刪除。由於我們實施了用戶ID和設備ID的複合唯一約束，這導致用戶重新登入時無法創建新的令牌，系統被迫使用已撤銷的令牌進行刷新操作，從而引發401未授權錯誤。

### 變更內容
1. 修改 `revoke_refresh_token` 函數，直接刪除令牌而非標記為已撤銷
2. 新增 `clean_revoked_tokens_for_user_device` 函數，專門清理特定用戶和設備上的已撤銷令牌
3. 更新 `create_refresh_token` 函數，在創建新令牌前清理可能存在的已撤銷令牌
4. 優化 `verify_refresh_token` 函數，增加詳細日誌幫助診斷問題
5. 修改 `cleanup_tokens.py` 中的邏輯，直接刪除而非標記冗餘令牌

### 技術說明
- 複合唯一約束（`user_id` + `device_id`）要求每個用戶在每個設備上只能有一個活躍令牌
- 在處理用戶登出或令牌刷新時，需要徹底清理舊令牌以避免唯一約束衝突
- 在保存令牌時添加額外的錯誤處理，確保即使發生衝突也能恢復並重試
- 提升了日誌的詳細度，便於診斷令牌相關問題

### 效益
1. **解決401錯誤問題**：用戶重新登入時不再因唯一約束衝突而無法創建新令牌
2. **提高系統穩定性**：消除了令牌管理中的潛在衝突
3. **優化資料庫使用**：不再保留無用的已撤銷令牌，減少資料庫空間佔用
4. **增強安全性**：確保舊令牌被完全移除，不留安全隱患
5. **改進維護性**：更詳細的日誌記錄，便於問題診斷

### 相關檔案
- `backend/app/core/security.py`：修改了令牌管理相關函數
- `backend/utils/cleanup_tokens.py`：更新了令牌清理腳本
- `CHANGE_SUMMARY.md`：記錄本次變更

## 2023-11-28: 刷新令牌管理優化

### 背景
刷新令牌系統目前採用的是"每次新增"策略，即每次刷新時都會創建一個新的令牌記錄。這導致資料庫中存在大量冗餘的令牌記錄，增加了查詢負擔並降低了效能。此外，多個活躍令牌也增加了安全風險，因為撤銷一個令牌不會影響其他令牌。

### 變更內容
1. 實現"更新而非新增"的令牌管理策略，每個用戶在每個設備上只保留一個活躍的刷新令牌
2. 修改 `create_refresh_token` 函數，使其能夠識別設備並更新現有令牌
3. 優化 `verify_refresh_token` 和 `revoke_refresh_token` 函數，提高查詢效率
4. 添加了從設備資訊中提取設備ID的邏輯，確保準確識別不同設備

### 技術說明
- 從設備資訊中提取設備ID，使用瀏覽器、操作系統和設備類型的組合作為唯一識別符
- 如果無法解析設備資訊，則使用其雜湊值作為設備ID
- 利用資料庫中的複合唯一約束（user_id + device_id）確保每個用戶在每個設備上只有一個活躍令牌
- 在驗證令牌時更新令牌的最後使用時間，以便更好地追蹤令牌活動

### 效益
1. **減少資料庫負擔**：通過減少冗餘記錄，降低了資料庫存儲需求和查詢負擔
2. **提高安全性**：每個用戶在每個設備上只有一個活躍令牌，使令牌管理更加清晰和可控
3. **優化效能**：減少了令牌查詢和驗證的時間，提高了系統響應速度
4. **改進用戶體驗**：用戶不再需要處理多個令牌，登出一次即可撤銷所有訪問權限

### 相關檔案
- `backend/app/core/security.py`：修改了令牌創建、驗證和撤銷函數
- `backend/alembic/versions/20231127_refresh_token_optimization.py`：添加了設備ID欄位和複合唯一約束的遷移
- `backend/utils/cleanup_tokens.py`：更新了令牌清理腳本，支持新的令牌管理策略

## 2023-11-27: 移除前端對 localStorage 存儲令牌的依賴

### 背景
在前一天的更新中，我們將認證系統從使用 localStorage 存儲 Refresh Token 升級為使用 HTTP-only Cookie，同時將 Access Token 改為僅存儲在記憶體中。然而，部分前端代碼仍然維持著對 localStorage 的依賴，尤其是在一些元件如 `AuthCallback.vue` 和 `user.ts` 中。

### 變更內容
1. **徹底清除 localStorage 中的令牌存取**:
   - 修改 `AuthCallback.vue`，移除直接將令牌寫入 localStorage 的操作，改用 tokenService 管理
   - 更新 `user.ts` 中的 `getEffectiveToken` 方法，從 tokenService 獲取令牌而不是從 localStorage
   - 修改 `auth.ts` 中的相關方法，移除存儲令牌到 localStorage 的操作

2. **統一使用 tokenService**:
   - 所有需要存取令牌的地方，統一使用導入的 tokenService 而非直接操作 localStorage 
   - 在必要的地方添加 tokenService 的引用
   - 修改 `checkIfAlreadyLoggedIn` 方法，使用 tokenService.isAuthenticated() 而不是檢查 localStorage

3. **保留用戶偏好設定**:
   - 仍然保留 'keepLoggedIn' 設定在 localStorage 中，這是用戶偏好而非安全敏感資訊
   - 使用 localStorage 存儲用戶資料緩存，但不再存儲任何認證令牌

### 技術說明
- 完全從前端代碼中移除了對 localStorage 存儲令牌的依賴
- 所有令牌相關操作都統一通過 tokenService 進行管理
- Access Token 僅保存在記憶體中，Refresh Token 則由 HTTP-only cookie 管理
- 用戶資料和偏好設置仍可保存在 localStorage 中，但敏感認證資訊已完全移除

### 安全提升
- **消除遺留風險**: 徹底移除可能被 XSS 攻擊利用的 localStorage 中的令牌
- **統一管理**: 所有令牌操作都經過統一的 tokenService 處理，減少操作錯誤
- **降低表面攻擊範圍**: 系統中不再有多個令牌存儲位置，簡化安全審計

### 效果
- 進一步提高系統安全性，完成認證系統安全強化工作
- 保持程式碼一致性，避免混淆使用不同的令牌存儲方式
- 維持用戶體驗不變，用戶無感知此次安全性變更

## 2023-11-26: 認證系統安全性強化 - HTTP-only Cookie 實作

### 改動內容
將認證系統從使用 localStorage 存儲 Refresh Token 升級為使用 HTTP-only Cookie，同時將 Access Token 改為僅存儲在記憶體中。此改動大幅提升系統安全性，防止 XSS 攻擊者竊取令牌。

### 主要修改
1. **後端改進**:
   - 修改 `RefreshToken` 模型，將 token 欄位重命名為 `token_hash` 並雜湊存儲
   - 更新 `create_refresh_token`、`verify_refresh_token`、`revoke_refresh_token` 函數以支援雜湊比對
   - 修改登入和刷新端點，使用 HTTP-only cookie 傳輸 Refresh Token
   - 實作 Token 輪換機制，每次刷新時換發新的 Refresh Token

2. **前端改進**:
   - 修改 `TokenService` 以不再使用 localStorage 存儲令牌
   - 更新 `authService` 和 `authStore` 以適應新的認證流程
   - 調整刷新令牌機制，不再顯式傳送 Refresh Token
   - 優化登出流程，處理 cookie 清理

### 安全提升
- **XSS 防護**: HTTP-only cookie 無法被 JavaScript 存取，有效防止 XSS 攻擊
- **模擬防護**: 雜湊存儲 Refresh Token，即使資料庫洩露也無法還原原始令牌
- **令牌輪換**: 每次刷新都換發新的 Refresh Token，降低被盜用風險
- **減少暴露**: Access Token 僅存在記憶體中，不再持久化到 localStorage

### 使用者體驗
- 保持與原有流程一致，用戶無感知變化
- 「保持登入」功能仍然可用，僅實現方式有所不同
- 頁面刷新後仍能自動恢復登入狀態 

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

# 系統變更記錄

## 2025-06-10: 修復 Google OAuth 認證流程中的回調處理錯誤與刷新令牌機制

### 背景
1. 用戶在使用 Google 帳號登入時，系統出現未定義變數錯誤，導致登入失敗。
2. 系統在 AJAX 方式刷新令牌時未能正確設置 HTTP-only cookie，導致刷新令牌在頁面重整後丟失。

### 修改內容
1. **Google OAuth 回調處理錯誤修復**：
   - 移除對未定義變數的引用，改為直接拋出異常以便外層捕獲處理
   - 確保只在建立重定向時創建響應對象，而不是在中間過程中創建臨時響應對象
   - 簡化刷新令牌處理流程，確保錯誤能被正確處理和記錄

2. **AJAX 刷新令牌機制修復**：
   - 在 `/refresh` 端點中，當請求是 AJAX 類型時也設置刷新令牌 cookie
   - 確保刷新令牌在所有響應方式（JSON和重定向）中都能正確更新

### 技術說明
1. **修改了 `backend/app/api/endpoints/auth.py` 文件**：
   - 修復了 `google_callback` 函數中的變數引用錯誤
   - 在 `refresh_access_token` 函數中，為 AJAX 響應添加了 cookie 設置代碼
   - 統一了所有響應類型的 cookie 處理邏輯

2. **改進的 cookie 設置流程**：
   ```python
   # 在 AJAX (JSON) 響應中設置 cookie
   set_refresh_token_cookie(response, new_refresh_token, expires_delta=refresh_token_expires)
   ```

### 效益
1. **修復 Google 登入功能**：用戶可以正常使用 Google 帳號登入系統
2. **修復刷新令牌機制**：解決頁面重整後自動刷新 token 失敗的問題
3. **提高系統穩定性**：統一 cookie 處理邏輯，減少潛在的登入狀態丟失問題
4. **改善用戶體驗**：減少用戶因刷新令牌問題而需要重新登入的情況
5. **提高安全性**：確保 HTTP-only cookie 在所有響應中都被正確設置

## 2023-11-30: 優化長期登入功能

### 背景
用戶需要在長時間不使用應用程式後仍能保持登入狀態，不必每次重新登入。原有的認證系統已經實施了 HTTP-only cookie 和刷新令牌機制，但設定的默認保持時間較短，且「保持登入」選項需要用戶主動勾選，影響了長期使用的用戶體驗。

### 變更內容
1. **延長令牌有效期**：
   - 將刷新令牌有效期從 7 天延長至 90 天（`REFRESH_TOKEN_EXPIRE_DAYS`）
   - 將訪問令牌有效期從 1440 分鐘延長至 2880 分鐘（`ACCESS_TOKEN_EXPIRE_MINUTES`）

2. **自動啟用「保持登入」選項**：
   - 修改前端登入表單，將「保持登入」選項默認設為已勾選
   - 更新 GoogleAuth 登入流程中的 `keepLoggedIn` 默認值為 `true`

3. **令牌刷新邏輯優化**：
   - 修改所有令牌刷新相關函數，將 `keepLoggedIn` 默認值設為 `true`
   - 調整 `localStorage` 判斷邏輯，從「默認為 false」改為「默認為 true」

### 技術說明
- 將所有前端代碼中 `localStorage.getItem('keepLoggedIn') === 'true'` 的判斷改為 `localStorage.getItem('keepLoggedIn') !== 'false'`，確保默認值為 `true`
- 統一 Cookie 設置邏輯，確保長期 Cookie 能被正確設置和使用
- 在用戶使用「保持登入」選項時，確保刷新令牌在 90 天內有效

### 效益
1. **改善用戶體驗**：用戶不再需要頻繁登入，即使長時間未使用應用程式
2. **減少認證請求**：減少了因令牌短期過期而需要的重新認證次數
3. **符合現代應用預期**：大多數現代應用都提供長期登入功能，此變更使系統符合用戶期待
4. **無縫體驗**：用戶在不同裝置間切換使用時，可以獲得更連貫的體驗

### 相關檔案
- `backend/.env`：修改令牌有效期設定
- `frontend/src/components/NavBar.vue`：更新登入表單默認值
- `frontend/src/stores/auth.ts`：修改 Google 登入及令牌刷新相關函數
- `frontend/src/services/token.ts`：優化令牌管理及刷新邏輯
- `frontend/src/services/authService.ts`：更新令牌刷新默認行為

## 2023-06-18: 優化使用者認證狀態同步與緩存優化

### 問題背景
頁面重新載入時，雖然在 localStorage 中存有使用者資料，但導航欄在初始渲染時仍顯示為未登入狀態，需要等待認證流程完成後才會更新。

### 改進方案

1. **優化使用者認證流程**
   - 改進了緩存策略，增加了更智能的緩存管理機制
   - 實現緩存版本控制，確保緩存一致性
   - 優化認證初始化流程，採用非阻塞方式處理令牌驗證
   - 立即顯示緩存中的用戶資料，同時在後台進行令牌驗證

2. **提升性能與用戶體驗**
   - 實現令牌刷新的防抖和冷卻機制，避免頻繁刷新
   - 優化組件掛載流程，採用階段性加載策略
   - 模組化關鍵函數，提高代碼可維護性
   - 改進資源加載順序，優先渲染UI關鍵元素

3. **增強錯誤處理與日誌記錄**
   - 添加性能監控日誌，便於後續優化
   - 優化錯誤處理流程，增強系統穩定性
   - 改進日誌信息，使其更具可讀性和調試價值

### 技術實現要點

1. **緩存機制改進**
   - 實現了緩存版本控制，避免版本不一致問題
   - 區分"新鮮"和"過期但可用"的緩存數據狀態
   - 在後台自動刷新過期但仍可用的緩存

2. **非阻塞式初始化**
   - 使用 `setTimeout` 將認證初始化移至非阻塞模式
   - 將初始化流程分解為多個優先級階段
   - 使用性能計時器監控各階段耗時

3. **令牌刷新優化**
   - 實現請求合併，多個刷新請求共享同一個 Promise
   - 添加冷卻時間機制，避免頻繁調用刷新API
   - 優化錯誤恢復機制，提高系統穩定性

### 效果評估
該改進顯著提升了用戶體驗，頁面重新載入時不再出現未登入閃爍，並且降低了對後端API的請求頻率，整體性能得到明顯提升。

## 2024-03-16: 令牌刷新機制的並發優化

### 背景
在高流量環境下，多個標籤頁或設備同時刷新令牌可能導致競爭條件，造成令牌不一致或請求失敗。為解決這一問題，我們實現了分佈式鎖和結果緩存機制，確保同一用戶的並發請求獲得一致的令牌。

### 變更內容
1. 在 `refresh_access_token` 函數中實現了以下優化：
   - 添加提前檢查緩存邏輯，在嘗試獲取鎖之前先檢查是否有有效的緩存結果
   - 將非阻塞鎖改為帶超時的阻塞鎖，提高獲取鎖的成功率
   - 獲取鎖後二次檢查緩存，避免在等待過程中產生的重複處理
   - 完善鎖釋放邏輯，確保在任何情況下都能正確釋放鎖
   - 增強日誌記錄，包含更詳細的請求處理信息
   - 重新啟用緩存清理功能，定期清理過期的令牌緩存
   
2. 創建了 `test_token_refresh.py` 測試腳本，用於模擬並發請求場景，驗證優化效果。

### 技術細節
- 使用 Python 的 `threading.RLock` 實現分佈式鎖機制，確保同一時間只有一個請求處理令牌刷新
- 採用基於內存的緩存存儲最近刷新的令牌結果，使後續請求可直接使用緩存結果
- 實現了自動清理機制，避免緩存無限增長，減少內存壓力
- 添加了 `X-Token-Grace-Period` 和 `X-Used-Cache` 響應標頭，幫助前端識別緩存狀態

### 效益
- 有效解決了並發請求導致的令牌不一致問題
- 顯著減少了服務器處理負載，同一用戶的短時間內多次請求可重用緩存結果
- 降低了數據庫壓力，避免重複的查詢和更新操作
- 提升了用戶體驗，特別是在多標籤頁或多設備場景下
- 改善了系統穩定性，降低了因並發請求造成的錯誤率

### 相關文件
- `backend/app/api/endpoints/auth.py`: 修改 `refresh_access_token` 函數，增加並發控制和緩存機制
- `backend/test_token_refresh.py`: 新增測試腳本，用於驗證並發優化效果
- `backend/test_lock.py`: 測試鎖機制和緩存機制的原型測試