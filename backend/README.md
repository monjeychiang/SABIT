# 交易平台後端

## 專案概述

這是一個基於 FastAPI 構建的交易平台後端系統，提供用戶認證、交易 API 集成和通知系統等功能。

## 專案結構

```
backend/
├── app/                   # 主應用程式碼
│   ├── api/               # API 路由和端點
│   ├── core/              # 核心配置
│   ├── db/                # 資料庫模型和配置
│   │   ├── models/        # 資料庫模型定義
│   │   └── database.py    # 資料庫連接和會話管理
│   ├── middlewares/       # 中間件
│   ├── schemas/           # Pydantic 模型/數據驗證
│   ├── services/          # 業務邏輯服務
│   ├── utils/             # 工具函數
│   └── main.py            # 應用入口點
├── docs/                  # 文檔
├── logs/                  # 日誌文件
├── tests/                 # 測試程式碼和管理工具
├── alembic/               # 資料庫遷移文件
├── alembic.ini            # Alembic 配置
├── .env                   # 環境變量
├── requirements.txt       # 專案依賴
├── rebuild_db.py          # 資料庫重建腳本
└── trading.db             # SQLite 資料庫文件
```

## 資料庫模型

系統包含以下主要數據模型：

1. **User**: 用戶信息，包括認證和個人資料
   - 每個用戶擁有唯一的6位英數混合推薦碼
   - 支持推薦關係：用戶可以通過其他用戶的推薦碼註冊
   - 推薦碼在用戶註冊時自動生成，並可在API響應中獲取
2. **RefreshToken**: 用戶刷新令牌
3. **Notification**: 用戶通知
4. **NotificationSetting**: 用戶通知設置
5. **ExchangeAPI**: 交易所 API 密鑰配置

## 資料庫重建

如需重建資料庫，可以使用專案根目錄下的 `rebuild_db.py` 腳本：

```bash
python rebuild_db.py
```

這個腳本會：
1. 刪除所有現有的資料庫表
2. 重新創建所有表結構
3. 保留資料庫文件名和位置不變

> **注意**: 執行此操作將永久刪除所有現有數據，請確保在執行前已備份重要數據。

## 管理員用戶創建

系統提供了一個便捷的管理員用戶創建工具，位於 `tests/create_admin_user.py`。此工具可用於：

1. 創建新的管理員用戶：
```bash
python tests/create_admin_user.py <用戶名> --email <郵箱> --password <密碼>
```

例如：
```bash
python tests/create_admin_user.py admin --email admin@example.com --password secure_password
```

2. 將現有普通用戶升級為管理員：
```bash
python tests/create_admin_user.py <用戶名> --update
```

創建的管理員用戶將具有：
- 管理員權限標誌 (`is_admin=True`)
- 管理員用戶標籤 (`user_tag=UserTag.ADMIN`)
- 已激活狀態 (`is_active=True`)
- 已驗證狀態 (`is_verified=True`)
- 唯一的推薦碼

更多詳細信息，請參閱 `tests/README.md` 文件。

## 登錄測試

系統支持兩種登錄方式：標準密碼登錄和Google OAuth2登錄。為了測試這些功能，我們提供了測試腳本。

### 標準登錄測試

使用 `tests/test_regular_login.py` 可以測試標準登錄流程，包括：

1. 測試不保持登錄的情況：
```bash
python tests/test_regular_login.py --no-keep
```

2. 測試保持登錄的情況：
```bash
python tests/test_regular_login.py --keep
```

### Google登錄測試

使用 `tests/test_regular_login.py` 的Google登錄測試選項可以測試Google OAuth2流程：

```bash
python tests/test_regular_login.py --google
```

這將測試：
1. 獲取Google授權URL
2. 模擬Google回調處理

> **注意**: 由於Google OAuth需要實際的用戶交互，完整測試需要結合手動操作。詳細的Google登錄測試指南可查看 `docs/google_login_testing.md`。

設置相關環境變量可以控制測試行為：
- `TEST_GOOGLE_LOGIN=true`: 在運行全部測試時包含Google登錄測試
- `OPEN_BROWSER=true`: 自動打開瀏覽器進行Google登錄（仍需手動完成認證）

## 環境配置

系統使用 `.env` 文件來管理環境變量，主要配置項包括：

- **DATABASE_URL**: 資料庫連接 URL
- **SECRET_KEY**: JWT 令牌加密密鑰
- **ACCESS_TOKEN_EXPIRE_MINUTES**: 訪問令牌過期時間
- **REFRESH_TOKEN_EXPIRE_DAYS**: 刷新令牌過期時間
- **GOOGLE_CLIENT_ID**: Google OAuth 客戶端 ID
- **GOOGLE_CLIENT_SECRET**: Google OAuth 客戶端密鑰
- **FRONTEND_URL**: 前端 URL
- **DEBUG**: 是否開啟調試模式

### Gemini API配置

系統集成了Google Gemini API用於聊天功能，相關配置包括：

- **GEMINI_API_KEY**: Google Gemini API密鑰
- **GEMINI_SYSTEM_PROMPT**: 系統角色提示詞，定義AI的行為和角色
- **GEMINI_MAX_MESSAGES_PER_SESSION**: 每個聊天會話的最大消息數量，預設為50條。當超過此限制時，最早的消息會被自動刪除
- **GEMINI_MAX_RESPONSE_TOKENS**: AI回覆的最大token數量限制，預設為1000
- **GEMINI_MAX_RESPONSE_CHARS**: AI回覆的最大字符數限制，預設為4000

這些配置可以通過環境變量設置，例如：

```bash
# 在.env文件中設置
GEMINI_MAX_MESSAGES_PER_SESSION=100  # 增加每個會話的最大消息數
GEMINI_MAX_RESPONSE_CHARS=8000       # 允許更長的回覆
```

### WebSocket連接池配置

系統支持實時聊天室功能，通過WebSocket連接池管理來控制資源使用。相關配置包括：

- **WS_MAX_GLOBAL_CONNECTIONS**: 系統支持的全局最大WebSocket連接數，預設為1000
- **WS_MAX_CONNECTIONS_PER_USER**: 每個用戶允許的最大連接數，預設為5
- **WS_MAX_CONNECTIONS_PER_ROOM**: 每個聊天室允許的最大連接數，預設為100
- **WS_MESSAGE_RATE_LIMIT**: 消息速率限制（每個時間窗口的最大消息數），預設為10
- **WS_RATE_LIMIT_WINDOW**: 速率限制時間窗口（秒），預設為60

這些配置可以根據伺服器資源和預期用戶量進行調整，例如：

```bash
# 在.env文件中設置 - 適用於小型部署
WS_MAX_GLOBAL_CONNECTIONS=500    # 減少全局連接數
WS_MAX_CONNECTIONS_PER_USER=3    # 限制每用戶連接數
WS_MESSAGE_RATE_LIMIT=5          # 降低消息速率限制
```

完整的WebSocket配置文檔可在 `docs/websocket_config.md` 中查看。

## 安裝與運行

1. 安裝依賴：
```bash
pip install -r requirements.txt
```

2. 初始化資料庫（如有需要）：
```bash
python rebuild_db.py
```

3. 啟動應用：
```bash
uvicorn app.main:app --reload
```

應用將在 http://localhost:8000 啟動，API 文檔可在 http://localhost:8000/docs 訪問。

# Gemini聊天API測試

這個項目包含一個用於測試Gemini聊天API的Python測試腳本。

## 項目概述

該項目測試通過FastAPI實現的Gemini聊天API功能。測試腳本模擬客戶端對API的各種操作，包括：

- 用戶認證（註冊和登錄）
- 創建聊天會話
- 發送消息並獲取AI回覆
- 獲取會話列表和歷史記錄
- 更新和刪除會話

## 環境要求

- Python 3.8+
- 安裝requirements.txt中的依賴包

## 安裝

1. 克隆倉庫
2. 安裝依賴：

```bash
pip install -r requirements.txt
```

## 配置

在運行測試腳本前，您可以通過以下方式配置測試參數：

1. 創建`.env`文件，設置以下環境變量：

```
API_BASE_URL=http://localhost:8000/api/v1
TEST_USERNAME=your_test_email@example.com
TEST_PASSWORD=your_test_password
```

2. 如果不創建.env文件，腳本將使用預設值。

### 聊天功能限制配置

系統對聊天功能實施了以下限制，以優化性能和控制token消耗：

1. **最大消息數量限制**：每個聊天會話最多保存50條消息（預設值）。當超過此限制時，系統會自動刪除最早的消息。這確保了：
   - 控制每個用戶的存儲使用量
   - 保持聊天歷史的相關性和實用性
   - 減少API請求中發送的上下文數據量

2. **回覆長度限制**：AI生成的回覆會受到兩種限制：
   - **Token限制**：預設最大1000個tokens，直接在API請求中限制生成長度
   - **字符限制**：預設最大4000個字符，超過限制的回覆將被截斷

這些限制可以通過環境變量進行配置（見上文Gemini API配置部分）。

## 使用方法

運行測試腳本：

```bash
python test_gemini_api.py
```

測試腳本將按順序執行以下操作：

1. 註冊測試用戶（如果用戶不存在）
2. 登錄並獲取訪問令牌
3. 創建新的聊天會話
4. 獲取會話列表
5. 獲取特定會話詳情
6. 發送預設的測試消息並接收AI回覆
7. 更新會話標題
8. 驗證標題更新是否成功
9. （可選）刪除會話

測試結果將在控制台輸出，包括每個步驟的執行狀態和詳細日誌。

## Gemini API終端點說明

以下是主要的API終端點及其功能：

### 認證相關

- `POST /api/v1/auth/register` - 註冊新用戶
- `POST /api/v1/auth/login` - 用戶登錄並獲取令牌

### 聊天會話相關

- `GET /api/v1/chat/sessions` - 獲取所有聊天會話列表
- `POST /api/v1/chat/sessions` - 創建新的聊天會話
- `GET /api/v1/chat/sessions/{session_id}` - 獲取特定會話詳情及消息歷史
- `PUT /api/v1/chat/sessions/{session_id}` - 更新會話信息（如標題）
- `DELETE /api/v1/chat/sessions/{session_id}` - 刪除特定會話

### 消息相關

- `POST /api/v1/chat/send` - 發送消息並獲取AI回覆

## 測試腳本功能

`GeminiAPITester`類提供了以下主要功能：

- `setup()` - 設置測試環境，進行認證
- `register()` - 註冊測試用戶
- `login()` - 用戶登錄
- `create_chat_session()` - 創建新的聊天會話
- `get_chat_sessions()` - 獲取會話列表
- `get_chat_session()` - 獲取特定會話詳情
- `send_message()` - 發送消息並獲取AI回覆
- `update_chat_session()` - 更新會話標題
- `delete_chat_session()` - 刪除會話
- `run_full_test()` - 運行完整測試流程

## 自定義測試

您可以通過以下方式自定義測試：

1. 修改`TEST_MESSAGES`列表添加或更改測試消息
2. 取消註釋`delete_chat_session()`相關代碼以測試刪除功能
3. 調整延遲時間以適應不同的網絡或伺服器性能

## 故障排除

如果測試失敗，請檢查：

1. API伺服器是否正在運行
2. 環境變量配置是否正確
3. 網絡連接是否正常
4. 後端服務日誌中是否有錯誤消息

## 示例輸出

成功測試的輸出示例：

```
2023-07-25 14:30:00,123 - INFO - ==================================================
2023-07-25 14:30:00,123 - INFO - 開始運行Gemini API完整測試
2023-07-25 14:30:00,123 - INFO - ==================================================
2023-07-25 14:30:00,123 - INFO - 開始設置測試環境...
2023-07-25 14:30:00,456 - INFO - 登錄成功，獲取到訪問令牌
2023-07-25 14:30:00,456 - INFO - 測試環境設置成功！
2023-07-25 14:30:00,789 - INFO - 聊天會話創建成功，ID: 123
...
2023-07-25 14:30:15,123 - INFO - ==================================================
2023-07-25 14:30:15,123 - INFO - 測試結果摘要:
2023-07-25 14:30:15,123 - INFO - - 創建聊天會話: 成功
2023-07-25 14:30:15,123 - INFO - - 獲取會話列表: 成功
...
2023-07-25 14:30:15,123 - INFO - ==================================================
2023-07-25 14:30:15,123 - INFO - ✅ 所有測試通過!
2023-07-25 14:30:15,123 - INFO - ==================================================
```

## 貢獻

歡迎提交問題報告和改進建議。 