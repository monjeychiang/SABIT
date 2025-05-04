<template>
  <div class="online-status-wrapper">
    <div 
      class="online-status-indicator" 
      :class="{ 'online': isOnline, 'offline': !isOnline }"
      :title="statusText">
    </div>
    <slot></slot>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { useOnlineStatusStore } from '@/stores/online-status';

// 组件属性
const props = defineProps<{
  userId: number | string;  // 用户ID
  showText?: boolean;       // 是否显示文本
}>();

const onlineStatusStore = useOnlineStatusStore();
const isOnline = ref(false);
const statusText = ref('离线');

// 更新在线状态
const updateStatus = () => {
  isOnline.value = onlineStatusStore.isUserOnline(props.userId);
  statusText.value = isOnline.value ? '在线' : '离线';
};

// 处理用户状态变化事件
const handleStatusChange = (event: CustomEvent) => {
  if (event.detail && event.detail.userId == props.userId) {
    isOnline.value = event.detail.isOnline;
    statusText.value = isOnline.value ? '在线' : '离线';
  }
};

// 监听属性变化
watch(() => props.userId, () => {
  updateStatus();
});

// 监听组件挂载
onMounted(() => {
  // 初始化状态
  updateStatus();
  
  // 如果状态商店没有这个用户的状态信息，先获取
  if (!onlineStatusStore.onlineUsers.hasOwnProperty(props.userId.toString())) {
    onlineStatusStore.fetchOnlineStatus([Number(props.userId)]);
  }
  
  // 监听全局状态变化事件
  window.addEventListener('online:user-status-changed', handleStatusChange as EventListener);
  window.addEventListener('online:status-updated', updateStatus);
});

// 组件卸载时清理
onUnmounted(() => {
  window.removeEventListener('online:user-status-changed', handleStatusChange as EventListener);
  window.removeEventListener('online:status-updated', updateStatus);
});
</script>

<style scoped>
.online-status-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.online-status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  transition: background-color 0.3s ease;
}

.online-status-indicator.online {
  background-color: #4CAF50; /* 绿色表示在线 */
  box-shadow: 0 0 5px #4CAF50;
}

.online-status-indicator.offline {
  background-color: #9e9e9e; /* 灰色表示离线 */
}
</style> 