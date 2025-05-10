<template>
  <div class="online-users-widget">
    <div class="widget-header">
      <h3>在线用户 ({{ onlineUsersCount }})</h3>
      <button class="refresh-button" @click="fetchOnlineUsers" title="刷新在线用户列表">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M23 4v6h-6"></path>
          <path d="M1 20v-6h6"></path>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"></path>
          <path d="M20.49 15a9 9 0 0 1-14.85 3.36L1 14"></path>
        </svg>
      </button>
    </div>
    
    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>加载中...</p>
    </div>
    
    <div v-else-if="error" class="error-state">
      <p>{{ error }}</p>
      <button class="retry-button" @click="fetchOnlineUsers">重试</button>
    </div>
    
    <div v-else>
      <div v-if="onlineUsers.length === 0" class="empty-state">
        <p>当前没有用户在线</p>
      </div>
      
      <div v-else class="users-list">
        <div v-for="user in onlineUsers" :key="user.id" class="user-item">
          <div class="avatar-container">
            <UserAvatar 
              :username="user.username"
              :avatar-url="user.avatar_url"
              size="small"
            />
            <span class="status-indicator"></span>
          </div>
          <div class="user-info">
            <span class="username">{{ user.username }}</span>
            <span class="last-active">活跃: {{ formatLastActive(user.last_active) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import axios from 'axios';
import UserAvatar from '@/components/UserAvatar.vue';

const props = defineProps({
  refreshInterval: {
    type: Number,
    default: 60000 // 默认60秒刷新一次
  },
  maxUsers: {
    type: Number,
    default: 10 // 默认最多显示10个用户
  }
});

const onlineUsers = ref([]);
const onlineUsersCount = ref(0);
const loading = ref(true);
const error = ref(null);
const refreshTimer = ref(null);

// 获取用户头像初始字母
const getUserInitials = (username) => {
  if (!username) return '?';
  return username.charAt(0).toUpperCase();
};

// 格式化最后活跃时间 - 直接使用服务器时间而非相对时间
const formatLastActive = (lastActiveTime) => {
  if (!lastActiveTime) return '未知';
  
  try {
    // 解析ISO格式的日期时间字符串
    const lastActive = new Date(lastActiveTime);
    
    // 检查日期是否有效
    if (isNaN(lastActive.getTime())) {
      return '无效时间';
    }
    
    // 使用本地化日期时间格式
    const options = { 
      year: 'numeric', 
      month: '2-digit', 
      day: '2-digit', 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      hour12: false // 使用24小时制
    };
    
    return lastActive.toLocaleString('zh-CN', options);
  } catch (error) {
    console.error('日期格式化错误:', error);
    return lastActiveTime; // 如果格式化失败，返回原始字符串
  }
};

// 获取在线用户数据
const fetchOnlineUsers = async () => {
  loading.value = true;
  error.value = null;
  
  try {
    // 获取token
    const token = localStorage.getItem('token');
    
    // 设置请求头 - 修正Authorization header格式
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    
    // 获取在线用户计数
    const countResponse = await axios.get('/api/v1/users/active-users-count', { headers });
    onlineUsersCount.value = countResponse.data.active_users || 0;
    
    // 获取在线用户详情 - 使用新的公共API端点
    const detailsResponse = await axios.get('/api/v1/users/active-users-public', { headers });
    
    // 按最后活跃时间排序
    const sortedUsers = [...(detailsResponse.data.users || [])].sort((a, b) => {
      return new Date(b.last_active || 0) - new Date(a.last_active || 0);
    });
    
    // 限制显示数量
    onlineUsers.value = sortedUsers.slice(0, props.maxUsers);
  } catch (err) {
    console.error('获取在线用户信息失败:', err);
    error.value = '获取在线用户信息失败';
  } finally {
    loading.value = false;
  }
};

// 组件挂载时获取数据并设置刷新计时器
onMounted(() => {
  fetchOnlineUsers();
  
  // 设置定期刷新
  if (props.refreshInterval > 0) {
    refreshTimer.value = setInterval(fetchOnlineUsers, props.refreshInterval);
  }
});

// 组件卸载时清除计时器
onUnmounted(() => {
  if (refreshTimer.value) {
    clearInterval(refreshTimer.value);
  }
});
</script>

<style scoped>
.online-users-widget {
  background-color: var(--surface-color, #ffffff);
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  padding: 16px;
  margin-bottom: 20px;
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.widget-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #1f2937);
}

.refresh-button {
  background: none;
  border: none;
  color: var(--text-secondary, #6b7280);
  cursor: pointer;
  padding: 4px;
}

.refresh-button:hover {
  color: var(--primary-color, #4f46e5);
}

.loading-state, .error-state, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  color: var(--text-secondary, #6b7280);
  text-align: center;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color, #e5e7eb);
  border-top-color: var(--primary-color, #4f46e5);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 8px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.retry-button {
  background-color: var(--primary-color, #4f46e5);
  color: white;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  margin-top: 8px;
  cursor: pointer;
}

.users-list {
  max-height: 320px;
  overflow-y: auto;
}

.user-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
}

.user-item:last-child {
  border-bottom: none;
}

.avatar-container {
  margin-right: 12px;
  position: relative;
  flex-shrink: 0;
}

.avatar-container :deep(.user-avatar-component) {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  max-width: 36px;
  max-height: 36px;
  aspect-ratio: 1/1;
}

.status-indicator {
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: #10b981;
  bottom: 0;
  right: 0;
  border: 2px solid var(--surface-color, #ffffff);
}

.user-info {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.username {
  font-weight: 500;
  color: var(--text-primary, #1f2937);
  font-size: 14px;
}

.last-active {
  color: var(--text-tertiary, #9ca3af);
  font-size: 12px;
}

/* 深色模式适配 */
:global(body.dark-theme) .online-users-widget {
  background-color: var(--card-background, #1f2937);
}

:global(body.dark-theme) .status-indicator {
  border-color: var(--card-background, #1f2937);
}
</style> 