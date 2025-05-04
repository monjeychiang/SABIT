# 交易平台后端

## 项目概述

这是一个基于 FastAPI 构建的交易平台后端系统，提供用户认证、交易 API 集成和通知系统等功能。

## 项目结构

```
backend/
├── app/                   # 主应用代码
│   ├── api/               # API 路由和端点
│   ├── core/              # 核心配置
│   ├── db/                # 数据库模型和配置
│   │   ├── models/        # 数据库模型定义
│   │   └── database.py    # 数据库连接和会话管理
│   ├── middlewares/       # 中间件
│   ├── schemas/           # Pydantic 模型/数据验证
│   ├── services/          # 业务逻辑服务
│   ├── utils/             # 工具函数
│   └── main.py            # 应用入口点
├── docs/                  # 文档
├── logs/                  # 日志文件
├── tests/                 # 测试代码和管理工具
├── alembic/               # 数据库迁移文件
├── alembic.ini            # Alembic 配置
├── .env                   # 环境变量
├── requirements.txt       # 项目依赖
├── rebuild_db.py          # 数据库重建脚本
└── trading.db             # SQLite 数据库文件
```

## 数据库模型

系统包含以下主要数据模型：

1. **User**: 用户信息，包括认证和个人资料
   - 每个用户拥有唯一的6位英数混合推荐码
   - 支持推荐关系：用户可以通过其他用户的推荐码注册
   - 推荐码在用户注册时自动生成，并可在API响应中获取
2. **RefreshToken**: 用户刷新令牌
3. **Notification**: 用户通知
4. **NotificationSetting**: 用户通知设置
5. **ExchangeAPI**: 交易所 API 密钥配置

## 数据库重建

如需重建数据库，可以使用项目根目录下的 `rebuild_db.py` 脚本：

```bash
python rebuild_db.py
```

这个脚本会：
1. 删除所有现有的数据库表
2. 重新创建所有表结构
3. 保留数据库文件名和位置不变

> **注意**: 执行此操作将永久删除所有现有数据，请确保在执行前已备份重要数据。

## 管理员用户创建

系统提供了一个便捷的管理员用户创建工具，位于 `tests/create_admin_user.py`。此工具可用于：

1. 创建新的管理员用户：
```bash
python tests/create_admin_user.py <用户名> --email <邮箱> --password <密码>
```

例如：
```bash
python tests/create_admin_user.py admin --email admin@example.com --password secure_password
```

2. 将现有普通用户升级为管理员：
```bash
python tests/create_admin_user.py <用户名> --update
```

创建的管理员用户将具有：
- 管理员权限标志 (`is_admin=True`)
- 管理员用户标签 (`user_tag=UserTag.ADMIN`)
- 已激活状态 (`is_active=True`)
- 已验证状态 (`is_verified=True`)
- 唯一的推荐码

更多详细信息，请参阅 `tests/README.md` 文件。

## 登录测试

系统支持两种登录方式：标准密码登录和Google OAuth2登录。为了测试这些功能，我们提供了测试脚本。

### 标准登录测试

使用 `tests/test_regular_login.py` 可以测试标准登录流程，包括：

1. 测试不保持登录的情况：
```bash
python tests/test_regular_login.py --no-keep
```

2. 测试保持登录的情况：
```bash
python tests/test_regular_login.py --keep
```

### Google登录测试

使用 `tests/test_regular_login.py` 的Google登录测试选项可以测试Google OAuth2流程：

```bash
python tests/test_regular_login.py --google
```

这将测试：
1. 获取Google授权URL
2. 模拟Google回调处理

> **注意**: 由于Google OAuth需要实际的用户交互，完整测试需要结合手动操作。详细的Google登录测试指南可查看 `docs/google_login_testing.md`。

设置相关环境变量可以控制测试行为：
- `TEST_GOOGLE_LOGIN=true`: 在运行全部测试时包含Google登录测试
- `OPEN_BROWSER=true`: 自动打开浏览器进行Google登录（仍需手动完成认证）

## 环境配置

系统使用 `.env` 文件来管理环境变量，主要配置项包括：

- **DATABASE_URL**: 数据库连接 URL
- **SECRET_KEY**: JWT 令牌加密密钥
- **ACCESS_TOKEN_EXPIRE_MINUTES**: 访问令牌过期时间
- **REFRESH_TOKEN_EXPIRE_DAYS**: 刷新令牌过期时间
- **GOOGLE_CLIENT_ID**: Google OAuth 客户端 ID
- **GOOGLE_CLIENT_SECRET**: Google OAuth 客户端密钥
- **FRONTEND_URL**: 前端 URL
- **DEBUG**: 是否开启调试模式

### Gemini API配置

系统集成了Google Gemini API用于聊天功能，相关配置包括：

- **GEMINI_API_KEY**: Google Gemini API密钥
- **GEMINI_SYSTEM_PROMPT**: 系统角色提示词，定义AI的行为和角色
- **GEMINI_MAX_MESSAGES_PER_SESSION**: 每个聊天会话的最大消息数量，默认为50条。当超过此限制时，最早的消息会被自动删除
- **GEMINI_MAX_RESPONSE_TOKENS**: AI回复的最大token数量限制，默认为1000
- **GEMINI_MAX_RESPONSE_CHARS**: AI回复的最大字符数限制，默认为4000

这些配置可以通过环境变量设置，例如：

```bash
# 在.env文件中设置
GEMINI_MAX_MESSAGES_PER_SESSION=100  # 增加每个会话的最大消息数
GEMINI_MAX_RESPONSE_CHARS=8000       # 允许更长的回复
```

### WebSocket连接池配置

系统支持实时聊天室功能，通过WebSocket连接池管理来控制资源使用。相关配置包括：

- **WS_MAX_GLOBAL_CONNECTIONS**: 系统支持的全局最大WebSocket连接数，默认为1000
- **WS_MAX_CONNECTIONS_PER_USER**: 每个用户允许的最大连接数，默认为5
- **WS_MAX_CONNECTIONS_PER_ROOM**: 每个聊天室允许的最大连接数，默认为100
- **WS_MESSAGE_RATE_LIMIT**: 消息速率限制（每个时间窗口的最大消息数），默认为10
- **WS_RATE_LIMIT_WINDOW**: 速率限制时间窗口（秒），默认为60

这些配置可以根据服务器资源和预期用户量进行调整，例如：

```bash
# 在.env文件中设置 - 适用于小型部署
WS_MAX_GLOBAL_CONNECTIONS=500    # 减少全局连接数
WS_MAX_CONNECTIONS_PER_USER=3    # 限制每用户连接数
WS_MESSAGE_RATE_LIMIT=5          # 降低消息速率限制
```

完整的WebSocket配置文档可在 `docs/websocket_config.md` 中查看。

## 安装与运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 初始化数据库（如有需要）：
```bash
python rebuild_db.py
```

3. 启动应用：
```bash
uvicorn app.main:app --reload
```

应用将在 http://localhost:8000 启动，API 文档可在 http://localhost:8000/docs 访问。

# Gemini聊天API测试

这个项目包含一个用于测试Gemini聊天API的Python测试脚本。

## 项目概述

该项目测试通过FastAPI实现的Gemini聊天API功能。测试脚本模拟客户端对API的各种操作，包括：

- 用户认证（注册和登录）
- 创建聊天会话
- 发送消息并获取AI回复
- 获取会话列表和历史记录
- 更新和删除会话

## 环境要求

- Python 3.8+
- 安装requirements.txt中的依赖包

## 安装

1. 克隆仓库
2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 配置

在运行测试脚本前，您可以通过以下方式配置测试参数：

1. 创建`.env`文件，设置以下环境变量：

```
API_BASE_URL=http://localhost:8000/api/v1
TEST_USERNAME=your_test_email@example.com
TEST_PASSWORD=your_test_password
```

2. 如果不创建.env文件，脚本将使用默认值。

### 聊天功能限制配置

系统对聊天功能实施了以下限制，以优化性能和控制token消耗：

1. **最大消息数量限制**：每个聊天会话最多保存50条消息（默认值）。当超过此限制时，系统会自动删除最早的消息。这确保了：
   - 控制每个用户的存储使用量
   - 保持聊天历史的相关性和实用性
   - 减少API请求中发送的上下文数据量

2. **回复长度限制**：AI生成的回复会受到两种限制：
   - **Token限制**：默认最大1000个tokens，直接在API请求中限制生成长度
   - **字符限制**：默认最大4000个字符，超过限制的回复将被截断

这些限制可以通过环境变量进行配置（见上文Gemini API配置部分）。

## 使用方法

运行测试脚本：

```bash
python test_gemini_api.py
```

测试脚本将按顺序执行以下操作：

1. 注册测试用户（如果用户不存在）
2. 登录并获取访问令牌
3. 创建新的聊天会话
4. 获取会话列表
5. 获取特定会话详情
6. 发送预设的测试消息并接收AI回复
7. 更新会话标题
8. 验证标题更新是否成功
9. （可选）删除会话

测试结果将在控制台输出，包括每个步骤的执行状态和详细日志。

## Gemini API终端点说明

以下是主要的API终端点及其功能：

### 认证相关

- `POST /api/v1/auth/register` - 注册新用户
- `POST /api/v1/auth/login` - 用户登录并获取令牌

### 聊天会话相关

- `GET /api/v1/chat/sessions` - 获取所有聊天会话列表
- `POST /api/v1/chat/sessions` - 创建新的聊天会话
- `GET /api/v1/chat/sessions/{session_id}` - 获取特定会话详情及消息历史
- `PUT /api/v1/chat/sessions/{session_id}` - 更新会话信息（如标题）
- `DELETE /api/v1/chat/sessions/{session_id}` - 删除特定会话

### 消息相关

- `POST /api/v1/chat/send` - 发送消息并获取AI回复

## 测试脚本功能

`GeminiAPITester`类提供了以下主要功能：

- `setup()` - 设置测试环境，进行认证
- `register()` - 注册测试用户
- `login()` - 用户登录
- `create_chat_session()` - 创建新的聊天会话
- `get_chat_sessions()` - 获取会话列表
- `get_chat_session()` - 获取特定会话详情
- `send_message()` - 发送消息并获取AI回复
- `update_chat_session()` - 更新会话标题
- `delete_chat_session()` - 删除会话
- `run_full_test()` - 运行完整测试流程

## 自定义测试

您可以通过以下方式自定义测试：

1. 修改`TEST_MESSAGES`列表添加或更改测试消息
2. 取消注释`delete_chat_session()`相关代码以测试删除功能
3. 调整延迟时间以适应不同的网络或服务器性能

## 故障排除

如果测试失败，请检查：

1. API服务器是否正在运行
2. 环境变量配置是否正确
3. 网络连接是否正常
4. 后端服务日志中是否有错误消息

## 示例输出

成功测试的输出示例：

```
2023-07-25 14:30:00,123 - INFO - ==================================================
2023-07-25 14:30:00,123 - INFO - 开始运行Gemini API完整测试
2023-07-25 14:30:00,123 - INFO - ==================================================
2023-07-25 14:30:00,123 - INFO - 开始设置测试环境...
2023-07-25 14:30:00,456 - INFO - 登录成功，获取到访问令牌
2023-07-25 14:30:00,456 - INFO - 测试环境设置成功！
2023-07-25 14:30:00,789 - INFO - 聊天会话创建成功，ID: 123
...
2023-07-25 14:30:15,123 - INFO - ==================================================
2023-07-25 14:30:15,123 - INFO - 测试结果摘要:
2023-07-25 14:30:15,123 - INFO - - 创建聊天会话: 成功
2023-07-25 14:30:15,123 - INFO - - 获取会话列表: 成功
...
2023-07-25 14:30:15,123 - INFO - ==================================================
2023-07-25 14:30:15,123 - INFO - ✅ 所有测试通过!
2023-07-25 14:30:15,123 - INFO - ==================================================
```

## 贡献

欢迎提交问题报告和改进建议。 