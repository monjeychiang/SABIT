# 加密货币交易系统

## 项目概述

这是一个完整的加密货币交易平台系统，包括前端用户界面和后端API服务。该系统允许用户查看实时的市场数据、进行交易操作、管理资产，并提供了用户认证、通知和聊天等功能。

## 系统架构

项目由两个主要部分组成：

1. **前端**: 基于Vue 3 + TypeScript + Vite构建的响应式Web应用
2. **后端**: 使用FastAPI + SQLite构建的RESTful API服务

## 主要功能

- **用户认证**: 支持标准登录和Google OAuth2.0登录
- **市场数据**: 实时加密货币行情展示
- **交易操作**: 限价/市价下单，订单管理
- **资产管理**: 用户资产统计和分析
- **通知系统**: 交易和系统通知
- **AI聊天**: 集成Gemini API的聊天功能
- **推荐系统**: 用户推荐码和推荐关系管理

## 技术栈

### 前端
- Vue 3 (组合式API)
- TypeScript
- Vite
- Vue Router
- Pinia状态管理
- Element Plus UI组件库
- Axios HTTP客户端
- Vitest & Playwright测试

### 后端
- Python 3.8+
- FastAPI
- SQLAlchemy ORM
- Alembic数据库迁移
- JWT认证
- Google OAuth2集成
- WebSocket实时通讯
- Google Gemini API集成

## 项目结构

```
project/
├── frontend/             # 前端项目
│   ├── src/              # 源代码
│   ├── public/           # 静态资源
│   └── ...               # 其他前端配置文件
├── backend/              # 后端项目
│   ├── app/              # 主应用代码
│   ├── alembic/          # 数据库迁移
│   ├── tests/            # 测试代码
│   └── ...               # 其他后端配置文件
├── docs/                 # 项目文档
├── scripts/              # 实用脚本
├── start_app.sh          # Linux/Mac启动脚本
└── start_app.bat         # Windows启动脚本
```

## 安装与运行

### 前置条件
- Node.js 16+ 和 npm 7+
- Python 3.8+
- 获取Google OAuth和Gemini API密钥（可选）

### 后端设置
1. 安装Python依赖：
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. 设置环境变量（复制并编辑.env.example文件）：
   ```bash
   cp .env.example .env
   # 编辑.env文件添加必要的API密钥和配置
   ```

3. 初始化数据库：
   ```bash
   python rebuild_db.py
   ```

### 前端设置
1. 安装Node.js依赖：
   ```bash
   cd frontend
   npm install
   ```

2. 设置环境变量：
   ```bash
   cp .env.example .env.local
   # 编辑.env.local添加API URL和Google客户端ID
   ```

### 启动应用
使用提供的启动脚本一键启动整个应用（前端和后端）：

- Windows:
  ```
  start_app.bat
  ```

- Linux/Mac:
  ```bash
  ./start_app.sh
  ```

或者分别启动：

1. 后端：
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

2. 前端：
   ```bash
   cd frontend
   npm run dev
   ```

## 访问应用
- 前端UI: http://localhost:5175
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

## 开发与测试

### 后端测试
```bash
cd backend
pytest
```

### 前端测试
```bash
cd frontend
# 单元测试
npm run test:unit
# E2E测试
npm run test:e2e
```

## 系统健康检查
使用提供的健康检查脚本确认系统运行状态：
```bash
python scripts/health_check.py
```

## 贡献指南
1. Fork这个仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个Pull Request

## 许可证
MIT License 