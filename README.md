# SABIT - 加密貨幣交易系統

## 專案概述

SABIT是一個現代化的加密貨幣交易平台，提供用戶友好的介面和強大的交易功能。系統結合了現代Web技術和區塊鏈技術，打造高性能、安全可靠的交易環境。

### 系統目標

- **降低交易門檻**：為普通用戶提供簡單直觀的交易介面，降低加密貨幣交易的技術門檻
- **提高交易效率**：通過自動化交易策略和實時市場數據，提高用戶交易決策效率
- **保障資金安全**：採用業界標準安全措施，確保用戶資金和個人信息安全
- **支持策略交易**：提供網格交易等自動化策略，實現被動收益
- **完善數據分析**：提供專業的技術分析工具和市場指標，輔助交易決策

## 系統架構

本系統採用現代化的微服務架構，結合前後端分離的設計，提供高性能、可擴展和安全的交易環境。

### 技術棧

#### 前端
- Vue 3 (組合式API)
- TypeScript
- Vite
- Vue Router
- Pinia狀態管理
- Element Plus UI元件庫
- Axios HTTP客戶端

#### 後端
- Python 3.9+
- FastAPI
- SQLAlchemy ORM
- JWT認證
- WebSocket實時數據
- SQLite資料庫 (可擴展至PostgreSQL)

## 目錄結構

```
/
├── backend/                # 後端Python/FastAPI應用
│   ├── app/                # 主應用程式碼
│   │   ├── api/            # API路由和端點
│   │   ├── core/           # 核心配置
│   │   ├── db/             # 資料庫模型和配置
│   │   ├── schemas/        # Pydantic模型/數據驗證
│   │   ├── services/       # 業務邏輯服務
│   │   └── utils/          # 工具函數
│   ├── logs/               # 日誌文件
│   ├── tests/              # 測試程式碼
│   ├── alembic/            # 資料庫遷移
│   └── requirements.txt    # 專案依賴
├── frontend/               # 前端Vue.js應用
│   ├── src/                # 源程式碼
│   │   ├── assets/         # 靜態資源
│   │   ├── components/     # 通用元件
│   │   ├── views/          # 頁面元件
│   │   ├── router/         # 路由配置
│   │   ├── stores/         # Pinia狀態管理
│   │   └── services/       # API服務
│   └── public/             # 公共文件
├── docs/                   # 項目文檔
├── scripts/                # 實用腳本
└── start_app.sh/bat        # 啟動腳本
```

## 主要功能

- **用戶認證**：支持Google OAuth2.0登錄和JWT認證
- **市場數據**：實時加密貨幣市場數據展示
- **交易功能**：限價/市價下單、訂單管理
- **自動化策略**：網格交易自動執行
- **數據分析**：價格趨勢分析、技術指標
- **資產管理**：餘額查看、資產分配

## 快速開始

### 要求
- Python 3.9+
- Node.js 16+
- npm 7+

### 安裝和運行

1. 克隆倉庫：
   ```bash
   git clone https://github.com/monjeychiang/SABIT.git
   cd SABIT
   ```

2. 後端設置：
   ```bash
   cd backend
   pip install -r requirements.txt
   # 配置環境變量
   # 可以編輯.env文件設置API密鑰
   ```

3. 前端設置：
   ```bash
   cd frontend
   npm install
   # 設置前端環境變量
   ```

4. 啟動應用（使用提供的啟動腳本）：
   - Windows: `start_app.bat`
   - Linux/macOS: `./start_app.sh`

5. 訪問應用：
   - 前端UI: http://localhost:5175
   - API文檔: http://localhost:8000/docs

## 許可證

MIT

## 聯繫方式

如有任何問題或建議，請通過GitHub Issues聯繫我們。 