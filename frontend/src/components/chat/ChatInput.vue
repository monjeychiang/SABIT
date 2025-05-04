<template>
  <div class="chat-input-container">
    <div class="limit-info" v-if="remainingInfo">
      <el-tooltip 
        effect="dark" 
        :content="`當前等級: ${remainingInfo.user_tag}, 每日限制: ${remainingInfo.daily_limit}`" 
        placement="top"
      >
        <div class="limit-text-container">
          <span class="limit-text">
            <el-icon v-if="remainingInfo.unlimited"><Medal /></el-icon>
            剩餘: {{ remainingInfo.unlimited ? '無限制' : 
              `${remainingInfo.remaining}/${remainingInfo.daily_limit}` }}
          </span>
        </div>
      </el-tooltip>
    </div>
    
    <div class="input-area">
      <div class="textarea-container">
        <el-input
          ref="inputRef"
          v-model="message"
          type="textarea"
          resize="none"
          :autosize="textareaSize"
          :placeholder="placeholderText"
          :disabled="isLoading || !activeSessionId"
          @keydown.enter.exact.prevent="sendMessage"
          @keydown.shift.enter.prevent="handleShiftEnter"
          @focus="inputFocused = true"
          @blur="inputFocused = false"
          class="message-input"
          :class="{ 'focused': inputFocused }"
        />
        
        <div class="clean-button" v-if="message && !isMobile">
          <el-button
            type="text"
            class="tool-button"
            @click="clearMessage"
          >
            <el-icon><Delete /></el-icon>
          </el-button>
        </div>
      </div>
      
      <div class="input-actions">
        <el-button 
          type="primary" 
          :loading="isLoading" 
          :disabled="!canSend"
          @click="sendMessage"
          class="send-button"
          round
        >
          <el-icon v-if="!isLoading"><Position /></el-icon>
          <span v-if="!isMobile">發送</span>
        </el-button>
      </div>
    </div>
    
    <div class="assistant-info">
      <p v-if="!activeSessionId">選擇或創建一個會話開始聊天</p>
      <p v-else-if="remainingInfo && remainingInfo.remaining === 0" class="warning-text">
        <el-icon><Warning /></el-icon>
        今日消息數量已達上限，請明天再試或升級賬戶
      </p>
      <p v-else>
        <el-icon><InfoFilled /></el-icon>
        <span>使用Gemini AI生成供參考，不構成投資建議</span>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { chatService } from '@/services/chatService'
import { 
  Position, 
  Delete,
  Medal,
  InfoFilled,
  Warning
} from '@element-plus/icons-vue'

const props = defineProps({
  activeSessionId: {
    type: Number,
    default: null
  },
  isLoading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['message-sent', 'update:isLoading'])

// 消息输入
const message = ref('')
const inputRef = ref(null)
const inputFocused = ref(false)

// 剩余消息信息
const remainingInfo = ref(null)

// 是否为移动设备
const isMobile = computed(() => {
  return window.innerWidth < 768
})

// 计算textarea大小
const textareaSize = computed(() => {
  return isMobile.value 
    ? { minRows: 1, maxRows: 2 }
    : { minRows: 1, maxRows: 4 }
})

// 动态占位符文本
const placeholderText = computed(() => {
  if (!props.activeSessionId) {
    return '請先選擇一個對話'
  }
  
  if (isMobile.value) {
    return '輸入問題，Gemini AI生成僅供參考...'
  }
  
  return '輸入您的問題，使用Gemini AI生成供參考，不構成投資建議 (Shift+Enter換行)'
})

// 是否可以发送消息
const canSend = computed(() => {
  if (!props.activeSessionId) return false
  if (!message.value.trim()) return false
  if (props.isLoading) return false
  if (remainingInfo.value && !remainingInfo.value.unlimited && remainingInfo.value.remaining <= 0) return false
  return true
})

// 发送消息
const sendMessage = async () => {
  if (!canSend.value) return
  
  const messageText = message.value.trim()
  if (!messageText) return
  
  try {
    emit('update:isLoading', true)
    
    // 先清空输入框
    message.value = ''
    
    // 创建临时本地消息对象
    const tempUserMsg = {
      role: 'user',
      content: messageText,
      created_at: new Date().toISOString()
    }
    
    // 发送消息并获取回复
    const response = await chatService.sendMessage(props.activeSessionId, messageText)
    
    // 处理成功响应
    emit('message-sent', { userMessage: tempUserMsg, aiResponse: response })
    
    // 更新剩余消息数
    await fetchRemainingMessages()
    
    // 重新聚焦输入框
    nextTick(() => {
      if (inputRef.value && inputRef.value.focus) {
        inputRef.value.focus()
      }
    })
  } catch (error) {
    if (error.response && error.response.status === 429) {
      ElMessage.error(error.response.data.detail || '您今日消息數量已達上限')
    } else {
      ElMessage.error('發送消息失敗')
    }
    console.error('發送消息出錯:', error)
  } finally {
    emit('update:isLoading', false)
  }
}

// 处理Shift+Enter
const handleShiftEnter = () => {
  message.value += '\n'
}

// 清空消息
const clearMessage = () => {
  message.value = ''
  nextTick(() => {
    if (inputRef.value && inputRef.value.focus) {
      inputRef.value.focus()
    }
  })
}

// 获取剩余消息数量
const fetchRemainingMessages = async () => {
  try {
    const data = await chatService.getRemainingMessages()
    remainingInfo.value = data
  } catch (error) {
    console.error('獲取剩餘消息數量失敗:', error)
  }
}

// 監聽會話ID變化
watch(() => props.activeSessionId, async (newVal) => {
  if (newVal) {
    await fetchRemainingMessages()
    // 清空消息和關閉工具面板
    message.value = ''
  }
}, { immediate: true })

// 監聽窗口大小變化
const handleResize = () => {
  // 監聽窗口大小變化，以適應響應式设计
  window.addEventListener('resize', handleResize)
}

// 组件挂载時
onMounted(() => {
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>
.chat-input-container {
  padding: 10px;
  margin-top: 10px;
  border-top: 1px solid var(--border-color);
  background-color: var(--input-bg, var(--surface-color, #ffffff));
  box-shadow: var(--input-shadow, 0 -4px 20px rgba(0, 0, 0, 0.05));
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: all 0.3s ease;
  border-radius: var(--border-radius-lg, 16px);
  position: relative;
  width: 100%;
  box-sizing: border-box;
}

.limit-info {
  display: flex;
  align-items: center;
  margin-bottom: 2px;
}

.limit-text-container {
  width: 100%;
  text-align: right;
  padding: 4px 8px;
  transition: all 0.3s ease;
}

.limit-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}

.input-area {
  display: flex;
  gap: 12px;
  position: relative;
}

.textarea-container {
  flex: 1;
  position: relative;
}

.message-input {
  width: 100%;
  transition: all 0.3s ease;
}

.message-input :deep(.el-textarea__inner) {
  resize: none;
  transition: all 0.3s ease;
  border-radius: var(--border-radius-lg, 16px);
  padding: 8px 16px;
  padding-right: 40px; /* 為清除按钮留出空间 */
  font-size: 14px;
  box-shadow: var(--shadow-sm, 0 2px 12px rgba(0, 0, 0, 0.05));
  border: 1px solid var(--border-color, #e5e7eb);
  background-color: var(--input-bg, #ffffff);
  color: var(--text-primary, #1f2937);
}

.message-input.focused :deep(.el-textarea__inner) {
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(var(--el-color-primary-rgb, 59, 130, 246), 0.2);
}

.clean-button {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
}

.tool-button {
  padding: 4px 8px;
  color: var(--text-secondary, #4b5563);
  transition: all 0.2s ease;
  border-radius: 50%;
}

.tool-button:hover {
  color: var(--primary-color, #3b82f6);
  background-color: var(--hover-color, rgba(0, 0, 0, 0.04));
}

.input-actions {
  display: flex;
  align-items: flex-end;
}

.send-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 60px;
  transition: all 0.3s ease;
  min-height: 40px;
  border-radius: var(--border-radius-lg, 16px);
  font-weight: 500;
  box-shadow: var(--shadow-md, 0 4px 12px rgba(var(--el-color-primary-rgb, 59, 130, 246), 0.2));
}

.send-button:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg, 0 6px 16px rgba(var(--el-color-primary-rgb, 59, 130, 246), 0.3));
}

.assistant-info {
  font-size: 11px;
  color: var(--text-tertiary, #6b7280);
  text-align: center;
  margin-top: 4px;
}

.assistant-info p {
  margin: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.warning-text {
  color: var(--el-color-danger, #ef4444);
}

/* 暗黑模式特定調整 */
body.dark-theme .chat-input-container {
  background-color: var(--input-bg, var(--surface-color, #1e293b));
  box-shadow: var(--input-shadow, 0 -4px 20px rgba(0, 0, 0, 0.15));
}

body.dark-theme .message-input :deep(.el-textarea__inner) {
  background-color: var(--surface-color, #1e293b);
  border-color: var(--border-color, #374151);
  color: var(--text-primary, #f9fafb);
  box-shadow: var(--shadow-sm, 0 2px 12px rgba(0, 0, 0, 0.15));
}

body.dark-theme .message-input.focused :deep(.el-textarea__inner) {
  border-color: var(--primary-color, #3b82f6);
  box-shadow: 0 0 0 2px rgba(var(--el-color-primary-rgb, 59, 130, 246), 0.3);
}

body.dark-theme .tool-button {
  color: var(--text-secondary, #9ca3af);
}

body.dark-theme .tool-button:hover {
  color: var(--primary-light, #60a5fa);
  background-color: var(--hover-color, rgba(255, 255, 255, 0.05));
}

/* 響應式調整 */
@media screen and (max-width: 768px) {
  .chat-input-container {
    padding: 8px;
    gap: 6px;
    border-radius: var(--border-radius-lg, 16px);
  }
  
  .input-area {
    gap: 6px;
  }
  
  .message-input :deep(.el-textarea__inner) {
    padding: 8px 12px;
    font-size: 14px;
    border-radius: var(--border-radius-lg, 16px);
  }
  
  .send-button {
    min-width: 40px;
    min-height: 38px;
    padding: 8px;
    border-radius: var(--border-radius-lg, 16px);
  }
  
  .limit-info {
    margin-bottom: 0;
  }
  
  .assistant-info {
    font-size: 10px;
    margin-top: 2px;
  }
}
</style> 