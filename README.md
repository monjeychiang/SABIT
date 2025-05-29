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

# 幣安帳戶WebSocket連接測試工具

這個工具用於測試與幣安（Binance）合約賬戶WebSocket連接的完整流程，包括登入、設置API金鑰以及建立WebSocket連接獲取賬戶資訊。專為實際生產環境使用而設計，支持完整的命令行參數和配置文件功能。

## 功能特點

- 自動環境檢查與依賴安裝
- 系統登入獲取JWT令牌
- API金鑰設置與更新**（含寫回數據庫驗證）**
- API金鑰**解密連接**確認
- WebSocket連接測試與持續監控
- 即時賬戶資料獲取與格式化顯示
- 錯誤處理與自動重試機制
- 配置文件支持（保存常用設置）
- 全面的命令行參數選項
- 數據保存到文件功能

## 前提條件

- Python 3.7或更高版本
- 運行中的後端服務（默認為http://localhost:8000）
- 有效的用戶帳號和密碼
- 幣安合約賬戶的API金鑰和密鑰密碼

## 安裝與運行

1. 下載`test_account_websocket.py`腳本
2. 確保Python環境已安裝（Python 3.7+）
3. 運行腳本：

```bash
# 基本運行
python test_account_websocket.py

# 使用命令行參數
python test_account_websocket.py --url http://api.example.com --username your_username --monitor

# 持續監控模式
python test_account_websocket.py --monitor --save-data account_data.log

# 使用配置文件
python test_account_websocket.py --config /path/to/config.ini
```

> 腳本將自動檢查並安裝必要的依賴

## 命令行參數

腳本支持多種命令行參數，適用於不同的使用場景：

```
連接設置:
  --url URL                 API基礎URL (例如: http://localhost:8000)
  --exchange EXCHANGE       交易所名稱 (默認: binance)

認證設置:
  --username USERNAME       用戶名
  --password PASSWORD       密碼 (不推薦，請使用交互式輸入)
  --token TOKEN             直接使用JWT令牌 (高級用法)

API密鑰設置:
  --api-key API_KEY         API密鑰
  --api-secret API_SECRET   API密鑰密碼 (不推薦，請使用交互式輸入)
  --no-api-setup            跳過API密鑰設置

運行模式:
  --monitor                 啟用監控模式，持續顯示賬戶更新
  --save-data SAVE_DATA     保存接收到的數據到指定文件

日誌設置:
  --log-file LOG_FILE       日誌文件路徑
  --debug                   啟用調試日誌

設置:
  --config CONFIG           配置文件路徑 (默認: ~/.binance_ws_tester.ini)
  --save-config             保存當前設置到配置文件
```

## 配置文件

工具支持使用配置文件保存常用設置，減少重複輸入。配置文件使用INI格式：

```ini
[DEFAULT]
url = http://your-api-server.com
username = your_username
exchange = binance
```

> 注意：為安全起見，配置文件中不會保存密碼、API密鑰或其他敏感資訊。

## 使用場景

### 1. 基本測試模式

用於快速測試API金鑰是否能正常連接並獲取賬戶信息：

```bash
python test_account_websocket.py
```

按照提示輸入必要資訊，工具會建立連接並顯示基本賬戶資訊。

### 2. 監控模式

用於持續監控賬戶資訊變動，適合進行交易時實時查看賬戶狀態：

```bash
python test_account_websocket.py --monitor
```

會顯示餘額和持倉的實時更新，按Ctrl+C退出。

### 3. 數據收集模式

將獲取的數據保存到文件，用於後續分析或記錄：

```bash
python test_account_websocket.py --monitor --save-data account_data.log
```

### 4. 自動化集成模式

用於自動化測試或系統集成：

```bash
python test_account_websocket.py --url http://api.server.com --username test_user --api-key YOUR_KEY --api-secret $API_SECRET --no-api-setup
```

## 測試流程詳解

1. **環境檢查**：
   - 檢查必要的依賴是否已安裝
   - 若缺少依賴，嘗試自動安裝

2. **系統登入**：
   - 通過RESTful API發送登入請求
   - 獲取並保存JWT令牌用於後續認證
   - 支持多次重試機制，自動處理臨時連接問題

3. **API金鑰設置與數據庫驗證**：
   - 檢查是否已有API金鑰
   - 若已存在則更新，否則創建新的API金鑰
   - **驗證API金鑰是否成功寫入數據庫**
   - 顯示API金鑰的遮罩版本（僅顯示末尾幾位）
   - API金鑰和密鑰在後端使用AES-256加密存儲

4. **WebSocket連接與解密測試**：
   - 建立到後端的WebSocket連接，附帶心跳機制
   - 發送JWT令牌進行認證
   - 等待連接確認訊息
   - **等待後端解密API金鑰的確認訊息**
   - **確認後端成功解密並使用API金鑰連接到交易所**
   - 接收並格式化解析賬戶資料
   - 顯示餘額和持倉數量及詳情
   - 監控模式下持續顯示資料更新並計算關鍵指標

## 輸出示例 - 基本模式

```
===== 幣安賬戶WebSocket測試工具 =====
請輸入API基礎URL (默認: http://localhost:8000): 
請輸入用戶名: testuser
請輸入密碼: 
2023-08-01 14:30:45,123 - __main__ - INFO - 嘗試登入系統...
2023-08-01 14:30:45,456 - __main__ - INFO - 登入成功，已獲取JWT令牌
是否需要設置API密鑰? (y/n): y
請輸入API密鑰: abcdefg123456789
請輸入API密鑰密碼: 
2023-08-01 14:30:55,123 - __main__ - INFO - 嘗試設置binance的API密鑰...
2023-08-01 14:30:55,234 - __main__ - INFO - 未發現現有API金鑰，創建新的金鑰記錄
2023-08-01 14:30:55,345 - __main__ - INFO - 成功設置binance的API密鑰
2023-08-01 14:30:55,456 - __main__ - INFO - 正在檢查API金鑰是否成功寫入數據庫...
2023-08-01 14:30:55,567 - __main__ - INFO - 確認API金鑰已成功寫入數據庫，ID: 123
2023-08-01 14:30:55,678 - __main__ - INFO - 加密保護: 僅顯示API金鑰末尾 ****6789
開始測試WebSocket連接...
2023-08-01 14:30:56,123 - __main__ - INFO - 嘗試連接到WebSocket: ws://localhost:8000/account/futures-account/binance
2023-08-01 14:30:56,456 - __main__ - INFO - 已發送認證令牌
2023-08-01 14:30:56,789 - __main__ - INFO - WebSocket連接消息: 正在連接到幣安合約WebSocket...
2023-08-01 14:30:57,000 - __main__ - INFO - API金鑰解密確認: 成功解密API金鑰並連接到交易所
2023-08-01 14:30:57,123 - __main__ - INFO - WebSocket連接消息: 已連接到幣安合約WebSocket
2023-08-01 14:30:58,456 - __main__ - INFO - 已收到首次賬戶資料!
2023-08-01 14:30:58,457 - __main__ - INFO - 餘額數量: 12
2023-08-01 14:30:58,458 - __main__ - INFO - 餘額 1: USDT - 可用: 1000.50
2023-08-01 14:30:58,459 - __main__ - INFO - 餘額 2: BTC - 可用: 0.05
2023-08-01 14:30:58,460 - __main__ - INFO - 持倉數量: 3
2023-08-01 14:30:58,461 - __main__ - INFO - 持倉 1: BTCUSDT - 數量: 0.01
2023-08-01 14:30:58,462 - __main__ - INFO - 持倉 2: ETHUSDT - 數量: 0.5
測試成功! WebSocket可以正常獲取賬戶資訊。
```

## 輸出示例 - 監控模式

```
===== 幣安賬戶WebSocket測試工具 =====
開始測試WebSocket連接...
監控模式已啟用，按 Ctrl+C 退出
2023-08-01 14:30:56,123 - __main__ - INFO - 嘗試連接到WebSocket: ws://localhost:8000/account/futures-account/binance
2023-08-01 14:30:56,456 - __main__ - INFO - 已發送認證令牌
2023-08-01 14:30:56,789 - __main__ - INFO - WebSocket連接消息: 正在連接到幣安合約WebSocket...
2023-08-01 14:30:57,000 - __main__ - INFO - API金鑰解密確認: 成功解密API金鑰並連接到交易所
2023-08-01 14:30:58,456 - __main__ - INFO - 已收到首次賬戶資料!
2023-08-01 14:30:58,457 - __main__ - INFO - 餘額數量: 12
2023-08-01 14:30:58,458 - __main__ - INFO - USDT餘額: 1000.50 (可用) + 0.0 (凍結)
2023-08-01 14:30:58,459 - __main__ - INFO - 非零餘額資產:
2023-08-01 14:30:58,460 - __main__ - INFO -   USDT: 1000.50 (可用) + 0.0 (凍結)
2023-08-01 14:30:58,461 - __main__ - INFO -   BTC: 0.05 (可用) + 0.0 (凍結)
2023-08-01 14:30:58,462 - __main__ - INFO - 持倉數量: 2/30
2023-08-01 14:30:58,463 - __main__ - INFO - 活躍持倉:
2023-08-01 14:30:58,464 - __main__ - INFO -   BTCUSDT: 多 0.01 @ 30000 (當前: 31000, 盈虧: 10.0)
2023-08-01 14:30:58,465 - __main__ - INFO -   ETHUSDT: 空 0.5 @ 1800 (當前: 1750, 盈虧: 25.0)
2023-08-01 14:32:15,123 - __main__ - INFO - [2023-08-01 14:32:15] 收到賬戶資料更新
2023-08-01 14:32:15,124 - __main__ - INFO - 餘額數量: 12
2023-08-01 14:32:15,125 - __main__ - INFO - USDT餘額: 1050.50 (可用) + 0.0 (凍結)
...
```

## 後端流程說明

### API金鑰存儲流程
1. 前端發送API金鑰和密鑰到後端
2. 後端使用AES-256加密算法加密API金鑰和密鑰
3. 加密後的數據寫入數據庫
4. 後端返回成功訊息和加密後的金鑰ID

### API金鑰解密與連接流程
1. 用戶通過WebSocket連接後端
2. 後端驗證用戶JWT令牌
3. 後端從數據庫檢索用戶的加密API金鑰
4. 後端使用AES-256解密API金鑰和密鑰
5. 後端使用解密後的API金鑰連接到幣安交易所WebSocket API
6. 後端將連接狀態和解密結果通知客戶端
7. 建立連接後，後端開始接收和轉發賬戶數據

## 實際使用案例

### 系統維護人員
維護人員可以使用此工具快速測試API連接是否正常，驗證加密和解密過程：
```bash
python test_account_websocket.py --debug --log-file /var/log/binance_test.log
```

### 交易員
交易者可以使用監控模式查看賬戶實時變動情況：
```bash
python test_account_websocket.py --monitor
```

### 自動化測試團隊
測試團隊可以將此工具整合到CI/CD流程中：
```bash
python test_account_websocket.py --url $API_URL --username $TEST_USER --api-key $API_KEY --api-secret $API_SECRET --no-api-setup
```

### 數據分析師
分析師可以收集賬戶數據進行後續分析：
```bash
python test_account_websocket.py --monitor --save-data /data/account_$(date +%Y%m%d).log
```

## 故障排除

- **登入失敗**：
  - 檢查用戶名和密碼是否正確
  - 確認後端服務是否正常運行
  - 查看是否有網絡連接限制
  - 使用`--debug`查看詳細錯誤日誌

- **API金鑰設置失敗**：
  - 確認API金鑰格式是否正確
  - 檢查後端設置API的端點是否正常工作
  - 查看後端日誌以確認加密過程是否出錯

- **數據庫寫入驗證失敗**：
  - 檢查數據庫連接狀態
  - 確認API端點返回正確的金鑰ID
  - 查看後端日誌以確認數據庫操作

- **API金鑰解密失敗**：
  - 檢查後端日誌以確認解密過程
  - 確認加密密鑰配置正確
  - 可能需要重新設置API金鑰

- **WebSocket連接失敗**：
  - 確認API金鑰已正確設置
  - 檢查後端WebSocket服務是否正常
  - 確認網絡連接是否良好
  - 嘗試使用`--debug`獲取更多連接細節

- **依賴安裝失敗**：
  - 嘗試手動安裝依賴：`pip install requests websockets aiohttp`
  - 確認Python環境正確
  - 在某些環境下可能需要管理員權限

## 注意事項

- API金鑰是敏感資訊，請確保安全使用
- 此工具僅用於測試和開發目的
- 若在生產環境使用，請確保使用HTTPS和WSS協議
- 腳本中有完整的API金鑰加密和解密流程驗證
- 監控模式下會一直佔用連接，請謹慎使用
- 保存到文件的數據可能包含敏感信息，請妥善保管