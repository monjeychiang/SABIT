# SABIT - 加密货币交易系统

## 项目概述

SABIT是一个现代化的加密货币交易平台，提供用户友好的界面和强大的交易功能。系统结合了现代Web技术和区块链技术，打造高性能、安全可靠的交易环境。

### 系统目标

- **降低交易门槛**：为普通用户提供简单直观的交易界面，降低加密货币交易的技术门槛
- **提高交易效率**：通过自动化交易策略和实时市场数据，提高用户交易决策效率
- **保障资金安全**：采用业界标准安全措施，确保用户资金和个人信息安全
- **支持策略交易**：提供网格交易等自动化策略，实现被动收益
- **完善数据分析**：提供专业的技术分析工具和市场指标，辅助交易决策

## 系统架构

本系统采用现代化的微服务架构，结合前后端分离的设计，提供高性能、可扩展和安全的交易环境。

### 技术栈

#### 前端
- Vue 3 (组合式API)
- TypeScript
- Vite
- Vue Router
- Pinia状态管理
- Element Plus UI组件库
- Axios HTTP客户端

#### 后端
- Python 3.9+
- FastAPI
- SQLAlchemy ORM
- JWT认证
- WebSocket实时数据
- SQLite数据库 (可扩展至PostgreSQL)

## 目录结构

```
/
├── backend/                # 后端Python/FastAPI应用
│   ├── app/                # 主应用代码
│   │   ├── api/            # API路由和端点
│   │   ├── core/           # 核心配置
│   │   ├── db/             # 数据库模型和配置
│   │   ├── schemas/        # Pydantic模型/数据验证
│   │   ├── services/       # 业务逻辑服务
│   │   └── utils/          # 工具函数
│   ├── logs/               # 日志文件
│   ├── tests/              # 测试代码
│   ├── alembic/            # 数据库迁移
│   └── requirements.txt    # 项目依赖
├── frontend/               # 前端Vue.js应用
│   ├── src/                # 源代码
│   │   ├── assets/         # 静态资源
│   │   ├── components/     # 通用组件
│   │   ├── views/          # 页面组件
│   │   ├── router/         # 路由配置
│   │   ├── stores/         # Pinia状态管理
│   │   └── services/       # API服务
│   └── public/             # 公共文件
├── docs/                   # 项目文档
├── scripts/                # 实用脚本
└── start_app.sh/bat        # 启动脚本
```

## 主要功能

- **用户认证**：支持Google OAuth2.0登录和JWT认证
- **市场数据**：实时加密货币市场数据展示
- **交易功能**：限价/市价下单、订单管理
- **自动化策略**：网格交易自动执行
- **数据分析**：价格趋势分析、技术指标
- **资产管理**：余额查看、资产分配

## 快速开始

### 要求
- Python 3.9+
- Node.js 16+
- npm 7+

### 安装和运行

1. 克隆仓库：
   ```bash
   git clone https://github.com/monjeychiang/SABIT.git
   cd SABIT
   ```

2. 后端设置：
   ```bash
   cd backend
   pip install -r requirements.txt
   # 配置环境变量
   # 可以编辑.env文件设置API密钥
   ```

3. 前端设置：
   ```bash
   cd frontend
   npm install
   # 设置前端环境变量
   ```

4. 启动应用（使用提供的启动脚本）：
   - Windows: `start_app.bat`
   - Linux/macOS: `./start_app.sh`

5. 访问应用：
   - 前端UI: http://localhost:5175
   - API文档: http://localhost:8000/docs

## 许可证

MIT

## 联系方式

如有任何问题或建议，请通过GitHub Issues联系我们。 