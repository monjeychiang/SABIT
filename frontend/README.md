# 加密貨幣交易系統前端

## 專案概述
這是使用Vue 3 + TypeScript + Vite開發的加密貨幣交易平台前端項目。提供用戶友好的介面，支持Google賬號登錄、實時市場數據顯示、交易操作等功能。

## 主要功能
- Google OAuth2.0登錄集成
- 實時加密貨幣市場數據展示
- 交易下單介面
- 用戶資產管理
- 響應式設計，支持移動端訪問

## 技術棧
- Vue 3 (組合式API)
- TypeScript
- Vite
- Vue Router
- Pinia狀態管理
- Element Plus UI元件庫
- Axios HTTP客戶端
- Vitest單元測試
- Playwright E2E測試

## 開發環境配置

### 推薦的IDE設置
- [VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar)（需禁用Vetur）
- 啟用Take Over Mode以獲得更好的類型支持

=dcxszeAW- Node.js 16+
- npm 7+

### 項目設置

1. 安裝依賴：
```bash
npm install
```

2. 創建環境配置文件（.env.local）：
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

### 開發伺服器啟動
```bash
npm run dev
```

### 生產環境構建
```bash
npm run build
```

## 專案結構
```
src/
├── assets/        # 靜態資源
├── components/    # 通用元件
├── views/         # 頁面元件
├── router/        # 路由配置
├── stores/        # Pinia狀態管理
├── services/      # API服務
├── utils/         # 工具函數
└── types/         # TypeScript類型定義
```

## 功能模塊說明

### 用戶認證
- Google OAuth2.0登錄流程
- JWT token管理
- 自動刷新token
- 登錄狀態持久化

### 市場數據
- WebSocket實時數據更新
- 價格走勢圖表
- 交易深度圖
- 市場概覽

### 交易功能
- 限價/市價下單
- 訂單管理
- 交易歷史
- 資產統計

## 測試

### 單元測試
```bash
npm run test:unit
```

### E2E測試
```bash
# 首次運行需安裝瀏覽器
npx playwright install

# 運行測試
npm run test:e2e
```

## 代碼質量

### ESLint代碼檢查
```bash
npm run lint
```

### TypeScript類型檢查
```bash
npm run type-check
```

## 部署說明

### 開發環境
1. 確保後端API服務運行在`http://localhost:8000`
2. 啟動開發伺服器：`npm run dev`
3. 訪問`http://localhost:5175`

### 生產環境
1. 構建項目：`npm run build`
2. 將`dist`目錄部署到Web伺服器
3. 配置環境變量：
   - `VITE_API_BASE_URL`：生產環境API地址
   - `VITE_GOOGLE_CLIENT_ID`：生產環境Google客戶端ID

## 常見問題

### Google登錄問題
1. 檢查Google Cloud Console配置
2. 確認環境變量設置正確
3. 檢查網絡請求和響應

### 開發調試
1. 使用Vue DevTools
2. 檢查瀏覽器控制台
3. 啟用Vite開發伺服器日誌

## 性能優化
1. 路由懶加載
2. 元件按需導入
3. 資源壓縮
4. 緩存策略

## 貢獻指南
1. Fork項目
2. 創建功能分支
3. 提交更改
4. 發起Pull Request

## 許可證
MIT License
