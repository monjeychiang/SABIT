<template>
  <div class="chat-message" :class="[messageClass, { 'highlighted': isLast }]" ref="messageContainerRef">
    <div class="message-container">
      <div class="message-timestamp">{{ formattedTime }}</div>
      <div class="message-card">
        <div class="avatar-wrapper" :class="{ 'user-avatar': message.role === 'user', 'ai-avatar': message.role === 'assistant' }">
          <el-avatar v-if="message.role === 'user'" class="avatar">
            <User />
          </el-avatar>
          <el-avatar v-else class="avatar">AI</el-avatar>
        </div>
        <div class="message-content">
          <div class="message-header">
            <div class="sender-info">
              <div class="sender-name">{{ message.role === 'user' ? '我' : 'AI助手' }}</div>
              <div class="sender-badge" v-if="message.role === 'assistant'">GPT</div>
            </div>
            <div class="message-tools">
              <div class="tool-button like-button" @click="toggleLike" :class="{ 'active': isLiked }">
                <el-icon><Star /></el-icon>
              </div>
              <div class="tool-button copy-button" @click="copyMessage">
                <el-icon><DocumentCopy /></el-icon>
              </div>
            </div>
          </div>
          <div 
            ref="messageTextRef"
            class="message-text" 
            v-html="formattedContent" 
            @click="handleMessageClick"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { User, DocumentCopy, Star } from '@element-plus/icons-vue'
import { format } from 'date-fns'
import { zhCN } from 'date-fns/locale'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const props = defineProps({
  message: {
    type: Object,
    required: true
  },
  isLast: {
    type: Boolean,
    default: false
  }
})

// 消息容器元素引用
const messageContainerRef = ref(null)
// 消息文本元素引用
const messageTextRef = ref(null)
// 点赞状态
const isLiked = ref(false)

// 切换点赞状态
const toggleLike = () => {
  isLiked.value = !isLiked.value
  ElMessage({
    message: isLiked.value ? '已收藏此消息' : '已取消收藏',
    type: 'success',
    offset: 80
  })
}

// 配置markdown解析器
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><div class="code-header"><span class="code-language">' + lang + '</span>' +
               '<button class="copy-button" data-code="' + encodeURIComponent(str) + '">複製</button></div>' +
               '<code>' + hljs.highlight(str, { language: lang, ignoreIllegals: true }).value + '</code></pre>'
      } catch (__) {}
    }
    return '<pre class="hljs"><div class="code-header"><span class="code-language">文本</span>' +
           '<button class="copy-button" data-code="' + encodeURIComponent(str) + '">複製</button></div>' +
           '<code>' + md.utils.escapeHtml(str) + '</code></pre>'
  }
})

// 计算消息的样式类
const messageClass = computed(() => {
  return {
    'user-message': props.message.role === 'user',
    'ai-message': props.message.role === 'assistant'
  }
})

// 格式化消息内容
const formattedContent = computed(() => {
  // 解析markdown内容
  return md.render(props.message.content)
})

// 格式化消息时间
const formattedTime = computed(() => {
  if (!props.message.created_at) return ''
  
  // 将字符串转换为Date对象
  const date = new Date(props.message.created_at)
  return format(date, 'HH:mm', { locale: zhCN })
})

// 复制消息内容
const copyMessage = () => {
  const content = props.message.content
  navigator.clipboard.writeText(content)
    .then(() => {
      ElMessage({
        message: '消息已複製到剪貼板',
        type: 'success',
        offset: 80
      })
    })
    .catch(() => {
      ElMessage.error('複製失敗，請手動選擇並複製')
    })
}

// 处理消息区域内的点击事件
const handleMessageClick = (event) => {
  // 检查点击的是否是复制按钮
  if (event.target.classList.contains('copy-button') || 
      event.target.closest('.copy-button')) {
    const button = event.target.classList.contains('copy-button') 
      ? event.target 
      : event.target.closest('.copy-button')
    
    const code = decodeURIComponent(button.dataset.code)
    
    navigator.clipboard.writeText(code)
      .then(() => {
        // 显示复制成功状态
        const originalText = button.textContent
        button.textContent = '已複製!'
        button.classList.add('copied')
        
        // 还原按钮文本
        setTimeout(() => {
          button.textContent = originalText
          button.classList.remove('copied')
        }, 2000)
        
        ElMessage({
          message: '代碼已複製到剪貼板',
          type: 'success',
          offset: 80
        })
      })
      .catch(() => {
        ElMessage.error('複製失敗，請手動選擇並複製')
      })
  }
}

// 组件挂载后
onMounted(async () => {
  // 等待DOM更新
  await nextTick()
  
  // 如果是最后一条消息，添加进入动画类
  if (props.isLast && messageTextRef.value) {
    messageTextRef.value.classList.add('message-appear')
  }
  
  // 确保AI消息对齐正确
  if (props.message.role === 'assistant' && messageContainerRef.value) {
    // 强制重新计算样式
    const forceReflow = messageContainerRef.value.offsetHeight
    
    // 确保消息容器样式正确应用
    messageContainerRef.value.style.paddingLeft = '15px'
  }
})
</script>

<style scoped>
.chat-message {
  width: 100%;
  margin: 0 0 30px;
  position: relative;
}

.chat-message.highlighted {
  animation: highlightGlow 2s ease-out;
}

.chat-message.user-message {
  /* 用户消息靠右 */
  display: flex;
  justify-content: flex-end;
}

.chat-message.ai-message {
  /* AI消息靠左 */
  display: flex;
  justify-content: flex-start;
  padding-left: 15px !important; /* 添加!important确保优先级，强制与标题对齐 */
  box-sizing: border-box;
  width: 100%;
  position: relative;
  z-index: 1; /* 确保不被其他元素覆盖 */
}

.message-container {
  max-width: 900px;
  margin: 0 auto;
  position: relative;
  padding: 0 15px;
  /* 控制消息容器宽度 */
  width: 85%;
}

/* 添加AI消息特定容器样式，使其与标题对齐 */
.ai-message .message-container {
  margin-left: 0 !important; /* 使用!important确保优先级 */
  padding-left: 0;
  box-sizing: border-box;
  position: relative; /* 确保定位一致性 */
  left: 0; /* 固定在左侧 */
}

.message-timestamp {
  text-align: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
  /* 确保时间戳居中 */
  position: absolute;
  left: 0;
  right: 0;
  width: 100%;
  top: -22px;
}

.message-card {
  display: flex;
  position: relative;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.chat-message:hover .message-card {
  transform: translateY(-2px);
}

.avatar-wrapper {
  flex-shrink: 0;
  margin-right: 16px;
  align-self: flex-start;
  position: relative;
}

.avatar-wrapper::after {
  content: '';
  position: absolute;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  bottom: 2px;
  right: 0;
}

.user-avatar::after {
  background-color: #3b82f6;
}

.ai-avatar::after {
  background-color: #10b981;
}

.avatar {
  width: 40px !important;
  height: 40px !important;
  background-color: #f0f9ff;
  border: 2px solid white;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.08);
  font-weight: bold;
}

.ai-avatar .avatar {
  background-color: var(--secondary-color, #10b981);
  color: white;
}

.message-content {
  flex: 1;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.user-message .message-content {
  background-color: var(--message-bg-user, #e0f2fe);
  border-left: 4px solid var(--primary-color, #3b82f6);
  /* 确保用户消息顺序调整 */
  margin-left: auto;
  border-radius: 16px 2px 16px 16px; /* 调整圆角，右上为尖角 */
}

.ai-message .message-content {
  background: white;
  border-left: 4px solid var(--secondary-color, #10b981);
  /* 确保AI消息顺序调整 */
  margin-right: auto;
  margin-left: 0; /* 确保左对齐 */
  border-radius: 2px 16px 16px 16px; /* 调整圆角，左上为尖角 */
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
}

.sender-info {
  display: flex;
  align-items: center;
}

.sender-name {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.user-message .sender-name {
  color: #3b82f6;
}

.ai-message .sender-name {
  color: #10b981;
}

.sender-badge {
  font-size: 10px;
  font-weight: bold;
  background-color: var(--secondary-color, #10b981);
  color: white;
  border-radius: 4px;
  padding: 2px 6px;
  margin-left: 8px;
  letter-spacing: 0.5px;
}

.message-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.tool-button {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #64748b;
  background-color: rgba(0, 0, 0, 0.02);
}

.tool-button:hover {
  background-color: rgba(0, 0, 0, 0.05);
  color: #334155;
}

.like-button.active {
  color: #f59e0b;
  background-color: rgba(245, 158, 11, 0.1);
}

.message-text {
  padding: 16px;
  font-size: 15px;
  line-height: 1.6;
  color: #334155;
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
    background-color: rgba(59, 130, 246, 0.1);
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
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
}

.message-text :deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background-color: #1e293b;
  color: #e2e8f0;
}

.message-text :deep(.code-language) {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  color: #94a3b8;
  letter-spacing: 0.5px;
}

.message-text :deep(.copy-button) {
  background: rgba(255, 255, 255, 0.1);
  border: none;
  color: #e2e8f0;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.message-text :deep(.copy-button:hover) {
  background-color: rgba(255, 255, 255, 0.2);
}

.message-text :deep(.copy-button.copied) {
  background-color: #10b981;
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
  color: #3b82f6;
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(59, 130, 246, 0.3);
}

.message-text :deep(a:hover) {
  color: #2563eb;
  border-bottom-color: #2563eb;
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
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
}

.message-text :deep(blockquote) {
  border-left: 4px solid #94a3b8;
  margin: 16px 0;
  padding: 8px 16px;
  background-color: #f8fafc;
  border-radius: 0 8px 8px 0;
  color: #475569;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  .message-timestamp {
    color: #64748b;
  }
  
  .message-content {
    background: #1e293b;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  }
  
  .user-message .message-content {
    background: linear-gradient(120deg, #172554, #1e3a8a);
    border-left-color: #3b82f6;
  }
  
  .ai-message .message-content {
    background: #1e293b;
    border-left-color: #10b981;
  }
  
  .avatar {
    border-color: #1e293b;
    background-color: #334155;
  }
  
  .message-header {
    border-bottom-color: rgba(255, 255, 255, 0.05);
  }
  
  .sender-name {
    color: #e2e8f0;
  }
  
  .user-message .sender-name {
    color: #60a5fa;
  }
  
  .ai-message .sender-name {
    color: #34d399;
  }
  
  .tool-button {
    color: #94a3b8;
    background-color: rgba(255, 255, 255, 0.05);
  }
  
  .tool-button:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
  }
  
  .message-text {
    color: #e2e8f0;
  }
  
  .message-text :deep(blockquote) {
    background-color: #334155;
    color: #cbd5e1;
    border-left-color: #64748b;
  }
  
  @keyframes highlightGlow {
    0% {
      background-color: rgba(59, 130, 246, 0.2);
    }
    100% {
      background-color: transparent;
    }
  }
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
  
  .message-container {
    width: 90%; /* 在小屏幕上增加消息宽度 */
  }
  
  .chat-message.ai-message {
    padding-left: 5px; /* 移动设备上减小左边距 */
  }
  
  .ai-message .message-container {
    margin-left: 0; /* 移动设备上保持无左边距 */
  }
}

@media screen and (max-width: 480px) {
  .message-container {
    padding: 0 5px;
    width: 95%; /* 在很小的屏幕上进一步增加消息宽度 */
  }
  
  .avatar-wrapper {
    margin-right: 10px;
  }
  
  .user-message .avatar-wrapper {
    margin-left: 10px;
  }
  
  .avatar {
    width: 32px !important;
    height: 32px !important;
  }
  
  .message-content {
    max-width: calc(100% - 44px);
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
  
  .chat-message.ai-message {
    padding-left: 0; /* 很小的屏幕上移除左边距 */
  }
  
  .ai-message .message-container {
    margin-left: 0; /* 非常小的屏幕上移除边距 */
    padding: 0 5px;
  }
}

/* 调整用户消息的头像顺序 */
.user-message .message-card {
  flex-direction: row-reverse;
}

.user-message .avatar-wrapper {
  margin-right: 0;
  margin-left: 16px;
}

/* 针对头像和消息容器的位置微调 */
.ai-message .avatar-wrapper {
  margin-right: 12px; /* 稍微减小头像和消息之间的间距 */
  margin-left: 5px; /* 添加左侧边距使头像与标题更好地对齐 */
}
</style> 