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
  transform: translateY(-3px);
  box-shadow: var(--shadow-md, 0 12px 24px rgba(0, 0, 0, 0.08));
}

.user-card {
  background: var(--message-bg-user, linear-gradient(135deg, #eff6ff, #dbeafe));
  color: var(--message-color-user, #1e3a8a);
  border-radius: 18px 2px 18px 18px;
  margin-left: auto;
}

.ai-card {
  background: var(--surface-color, white);
  color: var(--text-primary, #334155);
  border-radius: 2px 18px 18px 18px;
  border: 1px solid transparent;
  margin-right: auto;
}

body.dark-theme .message-time {
  color: var(--text-tertiary, #64748b);
}

body.dark-theme .user-sender {
  color: var(--primary-light, #60a5fa);
}

body.dark-theme .ai-sender {
  color: var(--secondary-light, #34d399);
}

body.dark-theme .user-card {
  background: var(--message-bg-user-dark, linear-gradient(135deg, #172554, #1e40af));
  color: var(--message-color-user-dark, #e0f2fe);
}

body.dark-theme .ai-card {
  background: var(--surface-color, #1e293b);
  color: var(--text-primary, #e2e8f0);
  border-color: var(--border-color, #374151);
}

.message-content {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  font-size: 15px;
}

.message-text {
  padding: 16px;
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-secondary, #334155);
  white-space: pre-wrap;
  word-break: break-word;
}

.message-text.message-appear {
  animation: message-appear 0.5s cubic-bezier(0.2, 0.8, 0.2, 1);
}

@keyframes message-appear {
  0% {
    opacity: 0;
    transform: translateY(15px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes highlightGlow {
  0% {
    background-color: var(--primary-bg, rgba(59, 130, 246, 0.1));
  }
  100% {
    background-color: transparent;
  }
}

/* 代码块样式 */
.message-text :deep(pre) {
  margin: 16px 0;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: var(--shadow-sm, 0 4px 15px rgba(0, 0, 0, 0.08));
}

.message-text :deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background-color: var(--code-header-bg, #1e293b);
  color: var(--code-header-color, #e2e8f0);
}

.message-text :deep(.code-language) {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-tertiary, #94a3b8);
  letter-spacing: 0.5px;
}

.message-text :deep(.copy-button) {
  background: var(--code-button-bg, rgba(255, 255, 255, 0.1));
  border: none;
  color: var(--code-button-color, #e2e8f0);
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.message-text :deep(.copy-button:hover) {
  background-color: var(--code-button-hover, rgba(255, 255, 255, 0.2));
}

.message-text :deep(.copy-button.copied) {
  background-color: var(--success-color, #10b981);
  color: white;
}

.message-text :deep(code) {
  display: block;
  padding: 16px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 14px;
  line-height: 1.5;
}

/* Markdown样式 */
.message-text :deep(p) {
  margin: 0 0 16px 0;
}

.message-text :deep(p:last-child) {
  margin-bottom: 0;
}

.message-text :deep(a) {
  color: var(--primary-color, #3b82f6);
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s ease;
  border-bottom: 1px solid var(--primary-light-border, rgba(59, 130, 246, 0.3));
}

.message-text :deep(a:hover) {
  color: var(--primary-dark, #2563eb);
  border-bottom-color: var(--primary-dark, #2563eb);
}

.message-text :deep(ul), .message-text :deep(ol) {
  padding-left: 24px;
  margin: 16px 0;
}

.message-text :deep(li) {
  margin-bottom: 8px;
}

.message-text :deep(img) {
  max-width: 100%;
  border-radius: 10px;
  margin: 16px 0;
  box-shadow: var(--shadow-sm, 0 4px 15px rgba(0, 0, 0, 0.08));
}

.message-text :deep(blockquote) {
  border-left: 4px solid var(--text-tertiary, #94a3b8);
  margin: 16px 0;
  padding: 8px 16px;
  background-color: var(--quote-bg, #f8fafc);
  border-radius: 0 8px 8px 0;
  color: var(--text-tertiary, #475569);
}

/* 深色模式变量覆盖 - 使用body.dark-theme选择器 */
body.dark-theme .message-text {
  color: var(--text-primary, #e2e8f0);
}

body.dark-theme .message-text :deep(blockquote) {
  background-color: var(--quote-bg, #334155);
  color: var(--text-secondary, #cbd5e1);
  border-left-color: var(--text-tertiary, #64748b);
}

body.dark-theme .message-text :deep(.code-header) {
  background-color: var(--code-header-bg, #1e293b);
  border-bottom: 1px solid var(--border-color, #334155);
}

body.dark-theme .message-text :deep(code) {
  color: var(--text-primary, #e2e8f0);
}

/* 响应式调整 */
@media screen and (max-width: 768px) {
  .avatar {
    width: 36px !important;
    height: 36px !important;
  }
  
  .message-content {
    max-width: calc(100% - 50px);
  }
  
  .message-header {
    padding: 10px 14px;
  }
  
  .message-text {
    padding: 14px;
    font-size: 14px;
  }
  
  .tool-button {
    width: 26px;
    height: 26px;
  }
}

@media screen and (max-width: 480px) {
  .message-container {
    padding: 0 10px;
  }
  
  .avatar-wrapper {
    margin-right: 12px;
  }
  
  .avatar {
    width: 32px !important;
    height: 32px !important;
  }
  
  .sender-name {
    font-size: 13px;
  }
  
  .message-text {
    padding: 12px;
    font-size: 14px;
  }
  
  .tool-button {
    width: 24px;
    height: 24px;
  }
}
</style> 