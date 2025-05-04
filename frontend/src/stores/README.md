# 通知系统设计文档

## 功能概述

通知系统为用户提供实时和历史通知服务，确保用户能及时收到系统消息、交易相关通知以及管理员发送的重要信息。系统支持以下核心功能：

1. 实时通知推送 - 通过WebSocket实时接收新通知
2. 离线通知恢复 - 用户登录后能收到离线期间的通知
3. 通知历史查询 - 访问并管理历史通知
4. 桌面通知支持 - 通过浏览器通知API展示桌面提醒
5. 通知状态管理 - 标记已读/未读状态

## 技术实现

### 前端实现 (Pinia Store)

通知系统的前端实现基于Pinia状态管理库，提供了完整的通知生命周期管理：

```javascript
// 导入通知存储
import { useNotificationStore, NotificationType } from '@/stores/notification';

// 在组件中使用
const notificationStore = useNotificationStore();

// 初始化通知系统
onMounted(() => {
  notificationStore.initialize();
  
  // 可选：设置新通知回调
  notificationStore.setNewNotificationCallback((notification) => {
    console.log('收到新通知:', notification);
  });
});

// 获取通知列表
const notifications = computed(() => notificationStore.sortedNotifications);

// 未读通知数量
const unreadCount = computed(() => notificationStore.unreadCount);
```

### 后端实现

后端实现基于FastAPI的WebSocket支持和SQLAlchemy ORM，提供以下API端点：

- `GET /api/v1/notifications` - 获取通知列表
- `GET /api/v1/notifications/missed` - 获取离线期间的通知
- `PATCH /api/v1/notifications/{id}/read` - 标记通知为已读
- `PATCH /api/v1/notifications/read-all` - 标记所有通知为已读
- `WebSocket /api/v1/notifications/ws` - 实时通知推送

## 离线通知恢复机制

通知系统实现了完善的离线通知恢复机制，确保用户不会错过任何重要信息：

1. **登出时间记录** - 用户登出时，记录登出时间戳到localStorage
2. **WebSocket连接参数** - 登录后连接WebSocket时，传递上次活动时间
3. **自动发送离线通知** - 服务器在接收到带时间戳的连接后，自动发送离线期间的通知
4. **通知去重处理** - 前端对接收到的通知进行去重合并，避免重复显示
5. **备份HTTP请求** - 如WebSocket连接失败，通过常规HTTP请求获取离线通知

## 最佳实践

### 在组件中使用通知系统

```vue
<script setup>
import { onMounted, computed } from 'vue';
import { useNotificationStore } from '@/stores/notification';

const notificationStore = useNotificationStore();

// 通知相关数据
const notifications = computed(() => notificationStore.filteredNotifications);
const unreadCount = computed(() => notificationStore.unreadCount);

// 初始化
onMounted(() => {
  // 通知系统会在登录后自动初始化，一般不需要手动初始化
  
  // 如果需要手动初始化，可以调用：
  // notificationStore.initialize();
});

// 标记通知为已读
const markAsRead = (notificationId) => {
  notificationStore.markAsRead(notificationId);
};

// 标记所有通知为已读
const markAllAsRead = () => {
  notificationStore.markAllAsRead();
};

// 按类型筛选通知
const filterByType = (type) => {
  notificationStore.setTypeFilter(type);
};
</script>
```

### 通知类型及样式

系统支持多种类型的通知，每种类型有不同的视觉样式：

- `info` - 一般信息通知
- `success` - 成功操作通知
- `warning` - 警告信息通知
- `error` - 错误信息通知
- `system` - 系统级通知

## 性能优化

通知系统针对性能进行了多项优化：

1. **连接合并** - 使用单一WebSocket连接处理所有通知
2. **智能刷新** - 仅在WebSocket断开时通过HTTP刷新通知
3. **批量处理** - 服务器批量发送离线通知，减少网络开销
4. **数据合并** - 前端智能合并通知数据，避免重复
5. **定期清理** - 释放不再需要的资源和连接

## 调试和故障排除

如果通知系统出现问题，可以检查以下几点：

1. 确认用户已登录且认证token有效
2. 检查WebSocket连接状态 (`notificationStore.isWebSocketConnected`)
3. 查看浏览器控制台是否有WebSocket相关错误
4. 检查服务器日志中的通知系统相关错误

## 未来改进计划

1. 添加通知分组功能，相似通知智能合并
2. 支持通知优先级排序
3. 实现通知过滤规则自定义
4. 添加通知模板功能，支持富文本和交互式通知 