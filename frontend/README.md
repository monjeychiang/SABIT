# 加密货币交易系统前端

## 项目概述
这是使用Vue 3 + TypeScript + Vite开发的加密货币交易平台前端项目。提供用户友好的界面，支持Google账号登录、实时市场数据显示、交易操作等功能。

## 主要功能
- Google OAuth2.0登录集成
- 实时加密货币市场数据展示
- 交易下单界面
- 用户资产管理
- 响应式设计，支持移动端访问

## 技术栈
- Vue 3 (组合式API)
- TypeScript
- Vite
- Vue Router
- Pinia状态管理
- Element Plus UI组件库
- Axios HTTP客户端
- Vitest单元测试
- Playwright E2E测试

## 开发环境配置

### 推荐的IDE设置
- [VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar)（需禁用Vetur）
- 启用Take Over Mode以获得更好的类型支持

=dcxszeAW- Node.js 16+
- npm 7+

### 项目设置

1. 安装依赖：
```bash
npm install
```

2. 创建环境配置文件（.env.local）：
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_GOOGLE_CLIENT_ID=your_google_client_id
```

### 开发服务器启动
```bash
npm run dev
```

### 生产环境构建
```bash
npm run build
```

## 项目结构
```
src/
├── assets/        # 静态资源
├── components/    # 通用组件
├── views/         # 页面组件
├── router/        # 路由配置
├── stores/        # Pinia状态管理
├── services/      # API服务
├── utils/         # 工具函数
└── types/         # TypeScript类型定义
```

## 功能模块说明

### 用户认证
- Google OAuth2.0登录流程
- JWT token管理
- 自动刷新token
- 登录状态持久化

### 市场数据
- WebSocket实时数据更新
- 价格走势图表
- 交易深度图
- 市场概览

### 交易功能
- 限价/市价下单
- 订单管理
- 交易历史
- 资产统计

## 测试

### 单元测试
```bash
npm run test:unit
```

### E2E测试
```bash
# 首次运行需安装浏览器
npx playwright install

# 运行测试
npm run test:e2e
```

## 代码质量

### ESLint代码检查
```bash
npm run lint
```

### TypeScript类型检查
```bash
npm run type-check
```

## 部署说明

### 开发环境
1. 确保后端API服务运行在`http://localhost:8000`
2. 启动开发服务器：`npm run dev`
3. 访问`http://localhost:5175`

### 生产环境
1. 构建项目：`npm run build`
2. 将`dist`目录部署到Web服务器
3. 配置环境变量：
   - `VITE_API_BASE_URL`：生产环境API地址
   - `VITE_GOOGLE_CLIENT_ID`：生产环境Google客户端ID

## 常见问题

### Google登录问题
1. 检查Google Cloud Console配置
2. 确认环境变量设置正确
3. 检查网络请求和响应

### 开发调试
1. 使用Vue DevTools
2. 检查浏览器控制台
3. 启用Vite开发服务器日志

## 性能优化
1. 路由懒加载
2. 组件按需导入
3. 资源压缩
4. 缓存策略

## 贡献指南
1. Fork项目
2. 创建功能分支
3. 提交更改
4. 发起Pull Request

## 许可证
MIT License
