<template>
  <div 
    :class="[
      'message-wrapper', 
      { 'user-message': isUser, 'ai-message': !isUser }
    ]" 
    :id="`message-${message.id}`"
  >
    <div class="message-container">
      <div class="message-header">
        <div class="sender-info">
          <div class="avatar" :class="{ 'user-avatar': isUser, 'ai-avatar': !isUser }">
            <span v-if="isUser">我</span>
            <span v-else>AI</span>
          </div>
          <div class="sender-name" :class="{ 'user-sender': isUser, 'ai-sender': !isUser }">
            {{ isUser ? '我' : 'AI助手' }}
            <span v-if="!isUser" class="ai-badge">GPT</span>
          </div>
        </div>
        <div class="message-time">{{ formatTime(message.timestamp) }}</div>
      </div>
      
      <div class="message-card" :class="{ 'user-card': isUser, 'ai-card': !isUser }">
        <div v-if="message.status === 'error'" class="error-message">
          <el-icon><WarningFilled /></el-icon>
          <span>消息发送失败，请重试</span>
        </div>
        <div v-else-if="message.status === 'sending'" class="sending-status">
          <div class="typing-animation">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
          </div>
          <span>正在响应...</span>
        </div>
        <div v-else class="message-content" :class="{ 'markdown-content': !isUser }">
          <div v-if="isUser">{{ message.content }}</div>
          <MarkdownView 
            v-else 
            :content="message.content" 
            @code-copy="$emit('code-copy', $event)"
          />
        </div>
        
        <div class="message-actions" v-if="!message.status || message.status === 'sent'">
          <div v-if="!isUser" class="action-buttons">
            <el-button class="action-button like-button" size="small" text @click="toggleLike">
              <el-icon><Star :class="{ 'liked': liked }" /></el-icon>
            </el-button>
            <el-button class="action-button copy-button" size="small" text @click="copyMessageContent">
              <el-icon><DocumentCopy /></el-icon>
            </el-button>
          </div>
          <div v-if="isUser && $slots.actions" class="user-actions">
            <slot name="actions"></slot>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
import { Star, DocumentCopy, WarningFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import MarkdownView from './MarkdownView.vue';

// 组件名称已从 ChatMessage 更改为 MessageItem
const name = 'MessageItem';

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
});

defineEmits(['code-copy']);

const isUser = computed(() => props.message.role === 'user');
const liked = ref(false);

const toggleLike = () => {
  liked.value = !liked.value;
  ElMessage({
    message: liked.value ? '已收藏此回答' : '已取消收藏',
    type: 'success',
    duration: 1500
  });
};

const copyMessageContent = () => {
  navigator.clipboard.writeText(props.message.content)
    .then(() => {
      ElMessage({
        message: '内容已复制到剪贴板',
        type: 'success',
        duration: 1500
      });
    })
    .catch(err => {
      console.error('复制失败:', err);
      ElMessage.error('复制失败，请手动复制');
    });
};

const formatTime = (timestamp) => {
  if (!timestamp) return '';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  
  // 一小时内显示"x分钟前"
  if (diffMins < 60) {
    return diffMins <= 0 ? '刚刚' : `${diffMins}分钟前`;
  }
  
  // 今天内显示"今天 HH:MM"
  if (date.toDateString() === now.toDateString()) {
    return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }
  
  // 昨天显示"昨天 HH:MM"
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
  }
  
  // 超过昨天显示完整日期
  return `${date.getMonth() + 1}月${date.getDate()}日 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
};
</script>

<style scoped>
.message-wrapper {
  margin-bottom: 32px;
  animation: fadeIn 0.5s ease;
  position: relative;
  max-width: 880px;
  margin-left: auto;
  margin-right: auto;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.user-message {
  padding-left: 60px;
  display: flex;
  justify-content: flex-end;
}

.ai-message {
  padding-right: 60px;
  display: flex;
  justify-content: flex-start;
}

.message-container {
  position: relative;
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sender-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
  flex-shrink: 0;
  box-shadow: var(--shadow-sm, 0 4px 8px rgba(0, 0, 0, 0.1));
}

.ai-avatar {
  background: var(--primary-gradient, linear-gradient(135deg, #3b82f6, #2563eb));
  color: white;
}

.user-avatar {
  background: var(--primary-gradient, linear-gradient(135deg, #3b82f6, #2563eb));
  color: white;
}

.sender-name {
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-sender {
  color: var(--primary-color, #3b82f6);
}

.ai-sender {
  color: var(--secondary-color, #10b981);
}

.ai-badge {
  font-size: 10px;
  font-weight: bold;
  background: var(--secondary-gradient, linear-gradient(135deg, #059669, #10b981));
  color: white;
  border-radius: 4px;
  padding: 2px 6px;
  margin-left: 8px;
  letter-spacing: 0.5px;
}

.message-time {
  font-size: 12px;
  color: var(--text-tertiary, #94a3b8);
}

.message-card {
  padding: 18px 20px;
  border-radius: 18px;
  transition: all 0.3s ease;
  position: relative;
  box-shadow: var(--shadow-sm, 0 6px 16px rgba(0, 0, 0, 0.05));
  max-width: 85%;
}

.message-card:hover {
  box-shadow: var(--shadow-md, 0 8px 20px rgba(0, 0, 0, 0.08));
}

.user-card {
  background-color: var(--primary-light, #eff6ff);
  border: 1px solid var(--primary-border, #dbeafe);
  margin-left: auto;
}

.ai-card {
  background-color: white;
  border: 1px solid var(--border-color, #e2e8f0);
  margin-right: auto;
}

.message-content {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary, #1e293b);
  word-break: break-word;
}

.markdown-content {
  color: var(--text-primary, #1e293b);
}

.markdown-content :deep(h1), 
.markdown-content :deep(h2), 
.markdown-content :deep(h3), 
.markdown-content :deep(h4), 
.markdown-content :deep(h5), 
.markdown-content :deep(h6) {
  margin-top: 1.5em;
  margin-bottom: 0.75em;
  font-weight: 600;
  line-height: 1.3;
}

.markdown-content :deep(h1) {
  font-size: 1.8em;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  padding-bottom: 0.3em;
  margin-top: 1em;
}

.markdown-content :deep(h2) {
  font-size: 1.5em;
  border-bottom: 1px solid var(--border-color, #e2e8f0);
  padding-bottom: 0.3em;
  margin-top: 1em;
}

.markdown-content :deep(h3) {
  font-size: 1.3em;
}

.markdown-content :deep(h4) {
  font-size: 1.15em;
}

.markdown-content :deep(h5) {
  font-size: 1em;
}

.markdown-content :deep(h6) {
  font-size: 0.85em;
  color: var(--text-secondary, #64748b);
}

.markdown-content :deep(p) {
  margin: 1em 0;
}

.markdown-content :deep(ul), 
.markdown-content :deep(ol) {
  margin: 1em 0;
  padding-left: 2em;
}

.markdown-content :deep(ul) {
  list-style-type: disc;
}

.markdown-content :deep(ol) {
  list-style-type: decimal;
}

.markdown-content :deep(li) {
  margin: 0.5em 0;
}

.markdown-content :deep(code) {
  font-family: 'Roboto Mono', monospace;
  background-color: var(--code-bg, #f1f5f9);
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  color: var(--code-color, #475569);
}

.markdown-content :deep(pre) {
  background-color: var(--code-block-bg, #0f172a);
  border-radius: 8px;
  padding: 1em;
  margin: 1.2em 0;
  overflow-x: auto;
  position: relative;
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
  color: #e2e8f0;
  font-size: 0.9em;
  line-height: 1.5;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--primary-color, #3b82f6);
  padding-left: 1em;
  margin: 1em 0;
  color: var(--text-secondary, #64748b);
  background-color: var(--blockquote-bg, #f8fafc);
  padding: 0.5em 1em;
  border-radius: 4px;
}

.markdown-content :deep(a) {
  color: var(--primary-color, #3b82f6);
  text-decoration: none;
  border-bottom: 1px dashed var(--primary-light, #93c5fd);
}

.markdown-content :deep(a:hover) {
  border-bottom: 1px solid var(--primary-color, #3b82f6);
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 1.2em 0;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow-sm, 0 4px 8px rgba(0, 0, 0, 0.05));
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  padding: 0.75em 1em;
  border: 1px solid var(--border-color, #e2e8f0);
}

.markdown-content :deep(th) {
  background-color: var(--table-header-bg, #f8fafc);
  font-weight: 600;
  text-align: left;
}

.markdown-content :deep(tr:nth-child(even)) {
  background-color: var(--table-alt-row, #f8fafc);
}

.message-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.action-buttons {
  display: flex;
  gap: 4px;
}

.action-button {
  font-size: 14px;
  color: var(--text-tertiary, #94a3b8);
  transition: all 0.2s ease;
}

.action-button:hover {
  color: var(--primary-color, #3b82f6);
}

.like-button .liked {
  color: var(--yellow-500, #eab308);
}

.error-message {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--error-color, #ef4444);
  font-size: 14px;
}

.sending-status {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary, #64748b);
  font-size: 14px;
}

.typing-animation {
  display: flex;
  gap: 4px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  background-color: var(--text-secondary, #64748b);
  border-radius: 50%;
  animation: typingBounce 1.4s infinite ease-in-out;
}

.typing-dot:nth-child(1) {
  animation-delay: 0s;
}

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typingBounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-4px);
  }
}
</style> 