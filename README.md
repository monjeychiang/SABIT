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
│   ├── .env.example        # 環境變量模板
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
   cp .env.example .env
   # 編輯.env文件，設置必要的參數
   # 特別注意：SECRET_KEY必須更改為安全隨機值
   # 可使用以下命令生成：
   # python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. 數據庫初始化：
   ```bash
   # 後端應用首次啟動時會自動創建必要的數據表
   # 如需手動初始化或重置數據庫，可使用以下Python代碼：
   python -c "from app.db.database import create_tables, init_db; create_tables()"  # 只創建表
   # 或
   python -c "from app.db.database import create_tables, init_db; init_db()"  # 重置所有表（會刪除已有數據）
   ```

4. 前端設置：
   ```bash
   cd frontend
   npm install
   # 設置前端環境變量
   ```

5. 啟動應用（使用提供的啟動腳本）：
   - Windows: `start_app.bat`
   - Linux/macOS: `./start_app.sh`

6. 訪問應用：
   - 前端UI: http://localhost:5175
   - API文檔: http://localhost:8000/docs

## 環境變量配置

系統使用`.env`文件管理敏感配置和環境特定設置。主要配置項包括：

- **數據庫連接**: `DATABASE_URL` - 默認使用SQLite，可替換為其他數據庫
- **安全密鑰**: `SECRET_KEY` - JWT令牌簽名和API密鑰加密使用，**必須**設置為強隨機值
- **令牌設置**: 控制訪問令牌和刷新令牌的有效期
- **OAuth設置**: Google登錄相關配置
- **AI聊天設置**: Gemini AI API相關配置（如使用）
- **WebSocket限制**: 連接池大小和速率限制配置

詳細配置項請參考`.env.example`文件的注釋說明。

> **安全提示**: `.env`文件包含敏感信息，切勿提交到版本控制系統或公開分享。

## 數據庫管理

系統使用SQLAlchemy ORM進行數據庫操作，主要管理功能包括：

- **自動創建表**: 應用啟動時會自動創建缺少的數據表
- **數據遷移**: 使用Alembic管理數據庫結構變更（生產環境推薦）
- **初始化工具**: 提供`create_tables()`（僅創建表）和`init_db()`（重置所有表）函數

> **注意**: `init_db()`會刪除所有現有數據，僅建議在開發/測試環境使用。

## 許可證

MIT

## 聯繫方式

如有任何問題或建議，請通過GitHub Issues聯繫我們。

# Crawl4AI 使用示例

這個項目展示了如何使用 Crawl4AI 庫來爬取網頁內容並轉換為 Markdown 格式，以及如何提取網頁中的特定數據。

## 簡介

[Crawl4AI](https://docs.crawl4ai.com/) 是一個專為大語言模型(LLM)設計的開源網絡爬蟲工具，它可以：

1. 生成乾淨的 Markdown 數據，適合 RAG 管道或直接輸入到 LLM 中
2. 使用 CSS 選擇器、XPath 或基於 LLM 的方法進行結構化數據提取
3. 提供高級瀏覽器控制功能，如鉤子、代理、隱身模式和會話重用
4. 實現高性能爬取，支持並行爬取和基於塊的提取

## 安裝

1. 安裝 Python 依賴：

```bash
pip install -r backend/requirements.txt
```

2. 安裝 Playwright 瀏覽器引擎：

```bash
python -m playwright install
```

## 示例程序

項目包含以下示例：

### 1. 基礎爬取示例

`crawl4ai_example.py` 中的 `basic_crawl_example` 函數展示了如何：

- 配置 Crawl4AI 爬蟲
- 爬取網頁內容
- 將內容轉換為 Markdown
- 提取頁面元數據
- 保存結果到文件

### 2. 數據提取示例

`crawl4ai_example.py` 中的 `extract_data_example` 函數展示了如何：

- 使用 CSS 選擇器定義提取策略
- 從網頁中提取特定數據
- 處理提取結果

## 運行示例

執行以下命令運行示例程序：

```bash
python crawl4ai_example.py
```

默認情況下，程序會爬取 Crawl4AI 的文檔頁面。您可以修改 `main` 函數中的 URL 來爬取其他網站。

## 高級用法

Crawl4AI 還支持許多高級功能：

1. **深度爬取**：爬取多個鏈接相連的頁面
2. **文件下載**：下載網頁中的媒體文件
3. **懶加載處理**：處理需要滾動才能加載的内容
4. **代理和認證**：使用代理和處理需要認證的頁面
5. **LLM 輔助提取**：使用大語言模型幫助提取結構化數據

有關更多信息，請參閱 [Crawl4AI 官方文檔](https://docs.crawl4ai.com/)。

## 注意事項

- 使用爬蟲時請遵守目標網站的使用條款和robots.txt規則
- 考慮添加適當的請求延遲，避免對目標伺服器造成過大負擔
- 对于大規模爬取任務，建議實現更複雜的錯誤處理和重試機制 