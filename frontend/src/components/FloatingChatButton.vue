<template>
  <div class="floating-chat-container">
    <!-- 聊天窗口组件 -->
    <ChatWindow 
      v-if="isChatSupported"
      :is-open="isChatOpen" 
      :is-online="isAgentOnline"
      @close="closeChatWindow"
      @minimize="minimizeChatWindow"
      @send="handleSendMessage"
    />
    
    <!-- 悬浮聊天按钮 -->
    <button 
      @click="toggleChatWindow" 
      class="floating-chat-button" 
      :class="{ 'has-unread': unreadCount > 0 }"
      :aria-label="isChatOpen ? '关闭聊天' : '打开聊天'"
    >
      <!-- 未读消息数量指示器 -->
      <span v-if="unreadCount > 0" class="unread-badge">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
      
      <!-- 聊天图标 -->
      <svg v-if="!isChatOpen" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="chat-icon">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M10 3h4a8 8 0 1 1 0 16v3.5c-5-2-12-5-12-11.5a8 8 0 0 1 8-8z" fill="currentColor"/>
      </svg>
      
      <!-- 关闭图标 -->
      <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="close-icon">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M12 10.586l4.95-4.95 1.414 1.414-4.95 4.95 4.95 4.95-1.414 1.414-4.95-4.95-4.95 4.95-1.414-1.414 4.95-4.95-4.95-4.95L7.05 5.636z" fill="currentColor"/>
      </svg>
    </button>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import ChatWindow from './ChatWindow.vue';
import { useChatroomStore } from '@/stores/chatroom';

// 初始化聊天室store
const chatroomStore = useChatroomStore();

// 检查是否支持聊天功能
const isChatSupported = ref(true);

// 聊天状态
const isChatOpen = ref(false);
const isAgentOnline = ref(true);

// 从聊天室store获取未读消息数量
const unreadCount = computed(() => chatroomStore.totalUnreadCount);

// 切换聊天窗口
async function toggleChatWindow() {
  // 打開聊天窗口時，確保聊天室列表已載入
  if (!isChatOpen.value) {
    // 檢查是否已有聊天室列表，如果沒有則重新載入
    if (chatroomStore.rooms.length === 0) {
      console.log('聊天窗口打開，正在載入聊天室列表...');
      try {
        await chatroomStore.fetchUserRooms();
        console.log('聊天室列表載入成功，共 ' + chatroomStore.rooms.length + ' 個聊天室');
      } catch (error) {
        console.error('載入聊天室列表時出錯：', error);
      }
    }
  }
  
  // 切換窗口狀態
  isChatOpen.value = !isChatOpen.value;
}

// 关闭聊天窗口
function closeChatWindow() {
  isChatOpen.value = false;
}

// 最小化聊天窗口
function minimizeChatWindow() {
  isChatOpen.value = false;
}

// 处理发送消息
function handleSendMessage(message) {
  console.log('发送消息:', message);
  
  // 这里可以添加将消息发送到后端的逻辑
  // 例如：使用API调用发送消息
  // apiService.sendChatMessage(message)
}

// 监听聊天状态变化
watch(isChatOpen, (isOpen) => {
  // 移除清除未读消息计数的代码
  // 不再在打开聊天窗口时重置所有未读消息
});

// 组件加载时
onMounted(() => {
  // 添加未读消息更新事件监听器
  window.addEventListener('chat:unread-updated', handleUnreadUpdate);
  
  // 添加WebSocket連接成功事件監聽器
  window.addEventListener('chat:websocket-connected', handleWebSocketConnected);
  
  // 检查是否支持聊天功能（这里可以根据实际情况调整）
  // 例如：检查用户权限、系统配置等
  // apiService.checkChatAvailability().then(result => {
  //   isChatSupported.value = result.available;
  //   isAgentOnline.value = result.agentOnline;
  // });
});

// 處理WebSocket連接成功事件
async function handleWebSocketConnected() {
  console.log('WebSocket連接成功，正在檢查聊天室列表...');
  // 如果聊天室列表為空，嘗試載入
  if (chatroomStore.rooms.length === 0) {
    try {
      await chatroomStore.fetchUserRooms();
      console.log('WebSocket連接後載入聊天室列表成功，共 ' + chatroomStore.rooms.length + ' 個聊天室');
    } catch (error) {
      console.error('WebSocket連接後載入聊天室列表失敗：', error);
    }
  }
}

// 处理未读消息更新事件
function handleUnreadUpdate(event) {
  console.log('未读消息更新:', event.detail?.totalUnread);
  // 不需要手动更新unreadCount，因为它是一个计算属性
}

// 组件卸载前清除事件监听器
onBeforeUnmount(() => {
  window.removeEventListener('chat:unread-updated', handleUnreadUpdate);
  window.removeEventListener('chat:websocket-connected', handleWebSocketConnected);
});
</script>

<style scoped>
.floating-chat-container {
  position: fixed;
  z-index: 9999;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.floating-chat-button {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background-color: var(--primary-color);
  border: none;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: transform 0.3s, box-shadow 0.3s;
}

.floating-chat-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
}

.floating-chat-button:active {
  transform: translateY(0);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.floating-chat-button.has-unread {
  animation: pulse 2s infinite;
}

.unread-badge {
  position: absolute;
  top: -5px;
  right: -5px;
  background-color: #ff4d4f;
  color: white;
  border-radius: 20px;
  padding: 2px 8px;
  font-size: 12px;
  min-width: 20px;
  text-align: center;
  box-shadow: 0 2px 6px rgba(255, 77, 79, 0.4);
}

.chat-icon, .close-icon {
  width: 28px;
  height: 28px;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.7);
  }
  70% {
    box-shadow: 0 0 0 10px rgba(37, 99, 235, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(37, 99, 235, 0);
  }
}

/* 响应式调整 */
@media (max-width: 768px) {
  .floating-chat-button {
    width: 50px;
    height: 50px;
  }
  
  .chat-icon, .close-icon {
    width: 24px;
    height: 24px;
  }
}

/* 深色模式适配 */
:root.dark .floating-chat-button {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

:root.dark .floating-chat-button:hover {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
}
</style> 