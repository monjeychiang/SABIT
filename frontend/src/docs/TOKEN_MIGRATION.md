# 令牌管理系統遷移指南

## 概述

我們對前端的令牌管理系統進行了重構，將原有的 `TokenManager` 和 `TokenService` 合併為單一的 `TokenService` 單例實現。此文檔旨在指導開發團隊如何從原有的實現遷移到新的統一實現。

## 遷移目標

1. 將所有 `TokenManager` 和 `getTokenManager()` 的使用點遷移到新的 `tokenService` 單例
2. 減少重複代碼和多餘的抽象層
3. 提高認證機制的可維護性和可測試性
4. 最終移除向後兼容層，使系統更加乾淨

## 新舊 API 對照表

| 舊 API | 新 API | 說明 |
|-------|--------|------|
| `getTokenManager()` | `tokenService` | 直接引入單例 |
| `window.tokenManager` | `tokenService` | 全局變量改為模組引入 |
| `tokenManager.setTokens()` | `tokenService.setTokens()` | 功能相同 |
| `tokenManager.isAuthenticated()` | `tokenService.isAuthenticated()` | 功能相同 |
| `tokenManager.getAccessToken()` | `tokenService.getAccessToken()` | 功能相同 |

## 遷移步驟

### 1. 更新引入方式

```typescript
// 舊方式
import { getTokenManager } from '@/services/tokenService';
const tokenManager = getTokenManager();

// 新方式
import { tokenService } from '@/services/token';
```

### 2. 更新組件內注入

```typescript
// 舊方式
const tokenManager = inject('tokenManager');

// 新方式
const tokenService = inject('tokenService');
```

### 3. 更新模板引用

```vue
<!-- 舊方式 -->
<div v-if="$tokenManager.isAuthenticated()">
  已登入
</div>

<!-- 新方式 -->
<script setup>
import { tokenService } from '@/services/token';
</script>

<div v-if="tokenService.isAuthenticated()">
  已登入
</div>
```

### 4. 移除全局變量使用

```typescript
// 舊方式
window.tokenManager.refreshTokenIfNeeded();

// 新方式
import { tokenService } from '@/services/token';
tokenService.refreshTokenIfNeeded();
```

## 向後兼容措施

為了確保系統平穩過渡，我們提供了向後兼容層：

1. `backwardCompatibility.ts` 文件中提供了 `TokenManagerLegacy` 類，代理調用到 `tokenService`
2. 全局變量 `window.tokenManager` 被維持，但會發出警告
3. 現有代碼不會立即中斷，但應該逐步遷移

## 最佳實踐

1. 不再使用全局變量 `window.tokenManager`，改為模組引入方式
2. 在任何需要令牌管理的組件中直接引入 `tokenService`
3. 在 Pinia store 中引入 `tokenService` 而非依賴注入
4. 使用 TypeScript 類型系統確保類型安全

## 完全遷移檢查清單

當您完成以下所有檢查點時，就可以安全地移除向後兼容層：

- [ ] 所有組件中的 `tokenManager` 引用已替換為 `tokenService`
- [ ] 所有 store 中的 `tokenManager` 引用已替換為 `tokenService`
- [ ] 沒有任何代碼依賴全局 `window.tokenManager` 變量
- [ ] 所有依賴注入已從 `tokenManager` 更改為 `tokenService`
- [ ] 單元測試和 E2E 測試已更新，使用新的 `tokenService`

## 常見問題

### Q: 為什麼要進行這次重構？
A: 當前系統中存在兩種 token 處理機制，導致代碼重複和潛在混淆。此重構將簡化系統架構，改進可維護性。

### Q: 應該使用 `tokenService` 還是 `getTokenService()`？
A: 直接使用 `tokenService` 導入是推薦的方式。`getTokenService()` 函數僅作為向後兼容提供。

### Q: 如何處理需要初始化的情況？
A: `tokenService` 在導入時會自動初始化，不需要額外的初始化步驟。

### Q: 我遇到了與舊 API 相關的類型錯誤怎麼辦？
A: 確保從 '@/services/token' 導入 TokenService 類型，而非舊的 TokenManager 類型。

## 聯繫方式

如您在遷移過程中遇到任何問題，請聯繫系統架構團隊。 