<template>
  <div class="chat-view">
    <!-- 左侧会话列表 -->
    <div class="sessions-panel" :class="{ 'collapsed': isPanelCollapsed }">
      <ChatSessionList 
        :activeSessionId="activeSession?.id"
        @session-selected="handleSessionSelected"
        @session-created="handleSessionCreated"
        @session-deleted="handleSessionDeleted"
        @session-renamed="handleSessionRenamed"
      />
    </div>
    
    <!-- 侧边栏折叠/展开按钮 -->
    <div class="collapse-toggle" @click="togglePanel">
      <el-tooltip :content="isPanelCollapsed ? '展开会话列表' : '收起会话列表'" placement="right">
        <el-icon class="collapse-icon">
          <ArrowLeft v-if="!isPanelCollapsed" />
          <ArrowRight v-else />
        </el-icon>
      </el-tooltip>
    </div>
    
    <!-- 右侧聊天区域 -->
    <div class="chat-container" :class="{ 'panel-expanded': !isPanelCollapsed }">
      <div class="chat-content">
        <!-- 会话标题 -->
        <div v-if="activeSession" class="chat-header">
          <div class="header-content">
            <h1 class="chat-title">{{ activeSession.title }}</h1>
            <div class="header-actions">
              <el-tooltip content="编辑会话标题" placement="top">
                <el-button
                  type="text"
                  size="small"
                  @click="openRenameDialog"
                >
                  <el-icon><Edit /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="导出对话" placement="top">
                <el-button
                  type="text"
                  size="small"
                  @click="exportChat"
                >
                  <el-icon><Download /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </div>
        </div>
        
        <div class="chat-panel">
          <template v-if="activeSession">
            <!-- 消息列表区域 -->
            <div class="messages-container" ref="messagesContainer">
              <div v-if="isLoadingMessages" class="loading-messages">
                <el-skeleton :rows="10" animated />
              </div>
              
              <div v-else-if="messages.length === 0" class="empty-chat">
                <div class="empty-chat-content">
                  <el-icon class="empty-icon"><ChatLineRound /></el-icon>
                  <h2>开始新的对话</h2>
                  <p>AI助手可以帮助您解答问题和提供有用的信息</p>
                  <div class="suggestions">
                    <div class="suggestion-title">您可以尝试问这些问题：</div>
                    <div
                      v-for="(suggestion, index) in chatSuggestions" 
                      :key="index"
                      class="suggestion-item"
                      @click="useSuggestion(suggestion)"
                    >
                      {{ suggestion }}
                    </div>
                  </div>
                </div>
              </div>
              
              <div v-else class="messages-list">
                <Transition
                  v-for="(message, index) in messages" 
                  :key="index"
                  name="message-fade"
                  appear
                >
                  <ChatMessage 
                    :message="message" 
                    @code-copy="handleCodeCopy"
                  />
                </Transition>
                
                <!-- 滚动到底部按钮 -->
                <div
                  v-if="showScrollButton"
                  class="scroll-bottom-button"
                  @click="scrollToBottom"
                >
                  <el-icon><ArrowDown /></el-icon>
                </div>
              </div>
              
              <!-- 加载更多按钮 -->
              <div v-if="hasMoreMessages" class="load-more">
                <el-button size="small" @click="loadMoreMessages">
                  <el-icon><TopRight /></el-icon>
                  加载更多消息
                </el-button>
              </div>
            </div>
            
            <!-- 正在输入提示 -->
            <div v-if="isLoading" class="typing-indicator">
              <div class="typing-content">
                <el-avatar size="small" class="ai-avatar">AI</el-avatar>
                <div class="typing-animation">
                  <div class="typing-dot"></div>
                  <div class="typing-dot"></div>
                  <div class="typing-dot"></div>
                </div>
                <span>AI正在思考...</span>
              </div>
            </div>
          </template>
          
          <div v-else class="no-active-session">
            <div class="welcome-container">
              <el-icon class="welcome-icon"><ChatDotRound /></el-icon>
              <h2>欢迎使用AI助手</h2>
              <p>请选择一个对话或创建一个新的会话开始聊天</p>
              <el-button type="primary" @click="createNewSession" class="welcome-button">
                <el-icon><Plus /></el-icon>
                创建新会话
              </el-button>
            </div>
          </div>
        </div>
        
        <!-- 输入区域 -->
        <div class="input-wrapper">
          <ChatInput 
            :activeSessionId="activeSession?.id"
            :isLoading="isLoading"
            @message-sent="handleMessageSent"
            @update:isLoading="isLoading = $event"
          />
        </div>
      </div>
    </div>
    
    <!-- 重命名对话框 -->
    <el-dialog
      v-model="renameDialog.visible"
      title="重命名对话"
      width="30%"
      destroy-on-close
    >
      <el-input
        v-model="renameDialog.title"
        placeholder="请输入新的标题"
        maxlength="100"
        show-word-limit
        autofocus
      />
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="renameDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="handleRenameSession">确认</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ChatSessionList from '@/components/chat/ChatSessionList.vue'
import ChatMessage from '@/components/MessageItem.vue'
import ChatInput from '@/components/chat/ChatInput.vue'
import { chatService } from '@/services/chatService'
import { 
  ArrowDown, 
  ArrowLeft, 
  ArrowRight, 
  Edit, 
  Download, 
  TopRight, 
  Plus, 
  ChatLineRound,
  ChatDotRound
} from '@element-plus/icons-vue'

// 活跃的会话
const activeSession = ref(null)
// 消息列表
const messages = ref([])
// 加载状态
const isLoading = ref(false)
const isLoadingMessages = ref(false)
// 是否有更多消息（用于分页加载）
const hasMoreMessages = ref(false)
// 消息容器引用，用于自动滚动
const messagesContainer = ref(null)
// 显示滚动到底部按钮
const showScrollButton = ref(false)
// 侧边栏折叠状态
const isPanelCollapsed = ref(false)
// 重命名对话框
const renameDialog = ref({
  visible: false,
  title: '',
})

// 问题建议列表
const chatSuggestions = [
  "请告诉我关于人工智能的发展历史",
  "如何使用Python进行数据分析？",
  "推荐几本最近流行的科幻小说",
  "如何提高英语口语能力？",
  "未来十年科技发展趋势是什么？"
]

// 选择会话
const handleSessionSelected = async (session) => {
  if (activeSession.value?.id === session.id) return
  
  activeSession.value = session
  await loadSessionMessages(session.id)
}

// 创建会话
const handleSessionCreated = (session) => {
  activeSession.value = session
  messages.value = []
}

// 创建新会话（从空状态）
const createNewSession = async () => {
  try {
    const session = await chatService.createChatSession()
    activeSession.value = session
    messages.value = []
    ElMessage({
      message: '创建新对话成功',
      type: 'success',
      offset: 80
    })
  } catch (error) {
    ElMessage.error('创建新对话失败')
    console.error(error)
  }
}

// 删除会话
const handleSessionDeleted = (sessionId) => {
  if (activeSession.value?.id === sessionId) {
    activeSession.value = null
    messages.value = []
  }
}

// 重命名会话
const handleSessionRenamed = (session) => {
  if (activeSession.value?.id === session.id) {
    activeSession.value = session
  }
}

// 打开重命名对话框
const openRenameDialog = () => {
  if (!activeSession.value) return
  
  renameDialog.value = {
    visible: true,
    title: activeSession.value.title,
  }
}

// 处理重命名
const handleRenameSession = async () => {
  if (!activeSession.value) return
  
  if (!renameDialog.value.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  
  try {
    const sessionId = activeSession.value.id
    const newTitle = renameDialog.value.title.trim()
    
    const updatedSession = await chatService.updateChatSession(sessionId, newTitle)
    activeSession.value = updatedSession
    
    // 触发重命名事件，让会话列表进行更新
    handleSessionRenamed(updatedSession)
    
    renameDialog.value.visible = false
    ElMessage({
      message: '重命名成功',
      type: 'success',
      offset: 80
    })
  } catch (error) {
    ElMessage.error('重命名失败')
    console.error(error)
  }
}

// 导出聊天记录
const exportChat = async () => {
  if (!activeSession.value || messages.value.length === 0) {
    ElMessage.warning('没有可导出的聊天记录')
    return
  }
  
  try {
    // 格式化聊天内容
    const title = activeSession.value.title
    const date = new Date().toLocaleDateString()
    
    let content = `# ${title}\n\n导出日期: ${date}\n\n`;
    
    messages.value.forEach(msg => {
      const role = msg.role === 'user' ? '我' : 'AI助手'
      content += `## ${role} (${new Date(msg.created_at).toLocaleString()})\n\n${msg.content}\n\n---\n\n`
    })
    
    // 创建下载链接
    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${title}-聊天记录-${date}.md`
    link.click()
    
    // 清理
    URL.revokeObjectURL(url)
    
    ElMessage({
      message: '聊天记录导出成功',
      type: 'success',
      offset: 80
    })
  } catch (error) {
    ElMessage.error('导出聊天记录失败')
    console.error(error)
  }
}

// 切换侧边栏
const togglePanel = () => {
  isPanelCollapsed.value = !isPanelCollapsed.value
  
  // 保存到本地存储，记住用户偏好
  localStorage.setItem('chat-panel-collapsed', isPanelCollapsed.value)
}

// 使用建议问题
const useSuggestion = (suggestion) => {
  if (!activeSession.value) return
  
  // 创建临时消息对象
  const userMessage = {
    role: 'user',
    content: suggestion,
    created_at: new Date().toISOString()
  }
  
  // 发送消息
  messages.value.push(userMessage)
  sendSuggestionMessage(suggestion)
}

// 发送建议消息
const sendSuggestionMessage = async (messageText) => {
  if (!activeSession.value) return
  
  try {
    isLoading.value = true
    
    // 发送消息并获取回复
    const response = await chatService.sendMessage(activeSession.value.id, messageText)
    
    // 添加AI回复
    if (response) {
      messages.value.push(response)
    }
    
    // 滚动到底部
    nextTick(() => {
      scrollToBottom()
    })
  } catch (error) {
    ElMessage.error('发送消息失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

// 加载会话消息
const loadSessionMessages = async (sessionId) => {
  try {
    isLoadingMessages.value = true
    const sessionData = await chatService.getChatMessages(sessionId)
    
    if (sessionData && sessionData.messages) {
      messages.value = sessionData.messages
      hasMoreMessages.value = sessionData.messages.length >= 50 // 假设每页50条
    } else {
      messages.value = []
      hasMoreMessages.value = false
    }
  } catch (error) {
    ElMessage.error('获取消息失败')
    console.error(error)
    messages.value = []
  } finally {
    isLoadingMessages.value = false
    // 滚动到底部
    await nextTick()
    scrollToBottom()
  }
}

// 加载更多消息（分页）
const loadMoreMessages = async () => {
  ElMessage.info('加载更多消息功能暂未实现')
  // TODO: 实现分页加载逻辑
  // 当API支持分页查询时，实现此功能
}

// 发送消息后的处理
const handleMessageSent = ({ userMessage, aiResponse }) => {
  // 先添加用户消息
  messages.value.push(userMessage)
  
  // 然后添加AI回复
  if (aiResponse) {
    messages.value.push(aiResponse)
  }
  
  // 滚动到底部
  nextTick(() => {
    scrollToBottom()
  })
}

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    // 滚动后隐藏按钮
    showScrollButton.value = false
  }
}

// 监听消息变化，自动滚动到底部
watch(messages, async () => {
  // 如果用户在底部或新增消息则自动滚动
  if (!showScrollButton.value || messages.value[messages.value.length - 1]?.role === 'assistant') {
    await nextTick()
    scrollToBottom()
  }
}, { deep: true })

// 页面滚动事件处理
const handleScroll = () => {
  if (messagesContainer.value) {
    const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value
    // 距离底部20px以内就认为已滚动到底部
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20
    showScrollButton.value = !isAtBottom
  }
}

// 处理代码复制
const handleCodeCopy = (code) => {
  ElMessage({
    message: '代码已复制到剪贴板',
    type: 'success',
    duration: 2000
  })
}

// 监听滚动事件
const setupScrollListener = () => {
  if (messagesContainer.value) {
    messagesContainer.value.addEventListener('scroll', handleScroll)
  }
}

// 页面挂载时
onMounted(() => {
  // 恢复侧边栏状态
  const savedCollapsed = localStorage.getItem('chat-panel-collapsed')
  if (savedCollapsed !== null) {
    isPanelCollapsed.value = savedCollapsed === 'true'
  }
  
  // 设置滚动监听
  setupScrollListener()
})

// 页面卸载时
onUnmounted(() => {
  // 移除滚动监听
  if (messagesContainer.value) {
    messagesContainer.value.removeEventListener('scroll', handleScroll)
  }
})
</script>

<style scoped>
.chat-view {
  display: flex;
  position: relative;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
  background-color: var(--bg-color);
  transition: background-color 0.3s ease;
}

.sessions-panel {
  position: relative;
  width: 280px;
  height: 100vh;
  background-color: var(--panel-bg);
  box-shadow: var(--panel-shadow);
  transition: width 0.3s ease, transform 0.3s ease;
  z-index: 100;
  overflow-y: auto;
  flex-shrink: 0;
}

.sessions-panel.collapsed {
  width: 0;
  transform: translateX(-280px);
}

.collapse-toggle {
  position: absolute;
  left: 280px;
  top: 50%;
  transform: translateY(-50%);
  width: 36px;
  height: 36px;
  background: var(--surface-color);
  color: var(--primary-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 101;
  transition: all 0.3s ease;
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-color);
}

.sessions-panel.collapsed ~ .collapse-toggle {
  left: 0;
}

.collapse-toggle:hover {
  transform: translateY(-50%) scale(1.1);
  box-shadow: var(--shadow-lg);
  color: var(--primary-dark);
}

.collapse-icon {
  font-size: 16px;
}

.chat-container {
  flex: 1;
  position: relative;
  height: 100vh;
  transition: all 0.3s ease;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 1;
}

.chat-container.panel-expanded {
  /* 不需要margin-left，因为sessions-panel已经是flex的一部分 */
}

.chat-content {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.chat-header {
  height: 60px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  background-color: var(--header-bg);
  box-shadow: var(--header-shadow);
  position: sticky;
  top: 0;
  z-index: 99;
  transition: all 0.3s ease;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.chat-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 70%;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.header-actions .el-button {
  border-radius: 8px;
  transition: all 0.3s ease;
}

.header-actions .el-button:hover {
  background-color: var(--hover-color);
  transform: translateY(-2px);
}

.chat-panel {
  flex: 1;
  position: relative;
  height: calc(100vh - 120px);
  overflow-y: auto;
  background-color: var(--bg-color);
  transition: background-color 0.3s ease;
  padding-bottom: 20px;
}

.messages-container {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
  padding-bottom: 20px;
  scroll-behavior: smooth;
  background-color: var(--bg-color);
}

.messages-list {
  position: relative;
  min-height: 100%;
  width: 100%;
  max-width: 1000px;
  margin: 0 auto;
}

/* 确保消息渲染区域也能正确响应主题变化 */
:deep(.chat-message) {
  background-color: var(--card-bg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  transition: background-color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease, color 0.3s ease;
}

:deep(.chat-message.user-message) {
  background-color: var(--primary-color);
  color: white;
  border: none;
}

:deep(.chat-message.ai-message) {
  background-color: var(--card-bg);
  color: var(--text-primary);
  border-color: var(--border-color);
}

body.dark-theme :deep(.chat-message.ai-message) {
  background-color: var(--card-bg);
  color: var(--text-primary);
  border-color: var(--border-color);
}

:deep(.message-content) {
  color: var(--text-primary);
  transition: color 0.3s ease;
}

:deep(.user-message .message-content) {
  color: white;
}

:deep(.code-block) {
  background-color: var(--code-bg) !important;
  border: 1px solid var(--border-color) !important;
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

body.dark-theme :deep(.code-block) {
  background-color: var(--code-bg) !important;
  border-color: var(--border-color) !important;
}

:deep(.user-message .code-block) {
  background-color: rgba(255, 255, 255, 0.1) !important;
  border-color: rgba(255, 255, 255, 0.3) !important;
}

:deep(.user-message .code-block pre) {
  color: white !important;
}

:deep(.blockquote) {
  background-color: var(--quote-bg);
  border-left-color: var(--quote-border);
  color: var(--text-secondary);
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

body.dark-theme :deep(.blockquote) {
  background-color: var(--quote-bg);
  color: var(--text-secondary);
}

:deep(.user-message .blockquote) {
  background-color: rgba(255, 255, 255, 0.2);
  border-left-color: rgba(255, 255, 255, 0.5);
  color: white;
}

:deep(.code-inline) {
  background-color: var(--inline-code-bg);
  color: var(--inline-code-color);
  border: 1px solid var(--border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

body.dark-theme :deep(.code-inline) {
  background-color: var(--inline-code-bg);
  color: var(--inline-code-color);
  border-color: var(--border-color);
}

:deep(.user-message .code-inline) {
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
  border-color: rgba(255, 255, 255, 0.3);
}

.empty-chat {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 40px 20px;
  background-color: var(--bg-color);
  transition: background-color 0.3s ease;
}

.empty-chat-content {
  max-width: 600px;
  text-align: center;
  background: var(--card-bg);
  border-radius: 20px;
  padding: 30px;
  box-shadow: var(--card-shadow);
  animation: fadeIn 0.5s ease-out;
  border: 1px solid var(--border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.empty-icon {
  font-size: 40px;
  color: var(--primary-color);
  margin-bottom: 20px;
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  background-color: var(--bg-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-light);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.empty-chat-content h2 {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.empty-chat-content p {
  color: var(--text-secondary);
  margin-bottom: 40px;
  font-size: 16px;
  line-height: 1.6;
}

.suggestions {
  margin-top: 30px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  text-align: left;
}

.suggestion-item {
  background-color: var(--card-bg);
  padding: 16px 20px;
  border: 1px solid var(--border-color);
  border-radius: 12px;
  margin-bottom: 10px;
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  text-align: left;
  transition: all 0.3s;
  color: var(--text-primary);
}

.suggestion-item:hover {
  background-color: var(--hover-color);
  border-color: var(--primary-light);
  box-shadow: var(--shadow-hover);
  transform: translateY(-3px) scale(1.02);
}

.no-active-session {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: var(--bg-color);
  transition: background-color 0.3s ease;
}

.welcome-container {
  text-align: center;
  max-width: 500px;
  padding: 40px 20px;
  background: var(--card-bg);
  border-radius: 20px;
  padding: 30px;
  box-shadow: var(--card-shadow);
  animation: fadeIn 0.5s ease-out;
  border: 1px solid var(--border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.welcome-icon {
  font-size: 48px;
  color: var(--primary-color);
  margin-bottom: 20px;
  width: 80px;
  height: 80px;
  margin: 0 auto 20px;
  background-color: var(--bg-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-light);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.welcome-container h2 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.welcome-container p {
  color: var(--text-secondary);
  margin-bottom: 40px;
  font-size: 17px;
  line-height: 1.6;
}

.welcome-button {
  margin-top: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 24px;
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-size: 16px;
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}

.welcome-button:hover {
  transform: translateY(-3px) scale(1.02);
  box-shadow: var(--shadow-md);
}

.typing-indicator {
  position: absolute;
  bottom: 70px;
  left: 20px;
  right: 20px;
  padding: 8px 0;
  z-index: 10;
}

.typing-content {
  display: inline-flex;
  align-items: center;
  background-color: var(--surface-color);
  padding: 8px 15px;
  border-radius: 16px;
  box-shadow: var(--shadow-md);
}

.ai-avatar {
  background-color: var(--primary-color);
  color: white;
  font-weight: 600;
  font-size: 14px;
  margin-right: 8px;
}

.typing-animation {
  display: flex;
  gap: 4px;
  margin: 0 10px;
  align-items: center;
}

.typing-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--primary-color);
  animation: typingAnimation 1.4s infinite ease-in-out;
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

@keyframes typingAnimation {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.6;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

.scroll-bottom-button {
  position: absolute;
  bottom: 80px;
  right: 30px;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background-color: var(--primary-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  z-index: 20;
  font-size: 20px;
  transition: transform 0.3s ease, box-shadow 0.3s ease, background-color 0.3s ease;
  border: none;
}

.scroll-bottom-button:hover {
  transform: translateY(-3px) scale(1.05);
  box-shadow: var(--shadow-md);
  background-color: var(--primary-dark);
}

.load-more {
  display: flex;
  justify-content: center;
  padding: 20px 0;
  margin: 10px 0 30px;
}

.load-more button {
  background-color: var(--card-bg);
  border-color: var(--border-color);
  color: var(--text-primary);
  padding: 10px 20px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 500;
}

.load-more button:hover {
  background-color: var(--hover-color);
  border-color: var(--primary-light);
  box-shadow: var(--shadow-hover);
}

.message-fade-enter-active, .message-fade-leave-active {
  transition: opacity 0.4s ease, transform 0.4s cubic-bezier(0.16, 1, 0.3, 1);
}

.message-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

/* 输入框区域样式 */
.input-wrapper {
  position: sticky;
  bottom: 0;
  left: 0;
  width: 100%;
  padding: 0;
  background-color: transparent;
  z-index: 150;
  transition: background-color 0.3s ease;
  margin-top: 0;
}

/* 重命名对话框 */
:deep(.el-dialog) {
  background: var(--surface-color);
  box-shadow: var(--shadow-xl);
  border-radius: 16px;
  overflow: hidden;
}

:deep(.el-dialog__header) {
  background: var(--dialog-header-bg);
  margin: 0;
  padding: 20px;
}

:deep(.el-dialog__title) {
  color: var(--text-primary);
  font-weight: 600;
}

:deep(.el-dialog__footer) {
  border-top: 1px solid var(--border-color);
  padding: 20px;
}

:deep(.el-input__inner) {
  background-color: var(--input-bg);
  border-color: var(--border-color);
  color: var(--text-primary);
  border-radius: 10px;
  height: 46px;
}

:deep(.el-button) {
  border-radius: 10px;
  padding: 10px 24px;
  font-weight: 500;
  transition: all 0.3s ease;
}

/* 媒体查询 - 小屏幕下的响应式布局 */
@media (max-width: 768px) {
  .chat-view {
    flex-direction: column;
  }
  
  .sessions-panel {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100vh;
    z-index: 200;
    box-shadow: 0 0 30px rgba(0, 0, 0, 0.3);
  }
  
  .sessions-panel.collapsed {
    transform: translateY(-100%);
    width: 100%;
  }
  
  .collapse-toggle {
    position: fixed;
    left: auto;
    right: 20px;
    top: 10px;
    transform: none;
    border-radius: 4px;
    z-index: 201;
  }
  
  .sessions-panel.collapsed ~ .collapse-toggle {
    left: auto;
    top: 10px;
  }
  
  .chat-container {
    width: 100%;
  }
  
  .chat-panel {
    height: calc(100vh - 110px);
    padding-bottom: 16px;
  }
  
  .scroll-bottom-button {
    right: 20px;
    bottom: 80px;
    width: 40px;
    height: 40px;
    font-size: 18px;
  }
  
  /* 添加灰色透明遮罩，当侧边栏展开时 */
  .sessions-panel:not(.collapsed) ~ .chat-container::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: var(--overlay-bg);
    z-index: 180;
    animation: fadeIn 0.3s ease;
    pointer-events: none;
  }
  
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  .input-wrapper {
    margin-top: 0;
  }
  
  .typing-indicator {
    bottom: 60px;
  }
  
  .chat-panel {
    padding-bottom: 30px;
  }
}

/* 非常小的屏幕 */
@media (max-width: 480px) {
  .chat-title {
    max-width: 50%;
    font-size: 1rem;
  }
  
  .messages-container {
    padding: 15px;
    padding-bottom: 15px;
  }
  
  .welcome-container,
  .empty-chat-content {
    padding: 30px 20px;
    max-width: 90%;
  }
  
  .welcome-button {
    padding: 10px 20px;
    font-size: 15px;
  }
  
  .scroll-bottom-button {
    right: 10px;
    bottom: 70px;
    width: 36px;
    height: 36px;
  }
  
  .input-wrapper {
    padding: 8px 15px;
  }
  
  .typing-indicator {
    max-width: 260px;
    padding: 8px 16px;
    bottom: 70px;
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

:deep(.blockquote) {
  background-color: var(--quote-bg);
  border-left-color: var(--quote-border);
  color: var(--text-secondary);
}

:deep(.user-message .blockquote) {
  background-color: rgba(255, 255, 255, 0.2);
  border-left-color: rgba(255, 255, 255, 0.5);
  color: white;
}

:deep(.code-inline) {
  background-color: var(--inline-code-bg);
  color: var(--inline-code-color);
  border: 1px solid var(--border-color);
}

:deep(.user-message .code-inline) {
  background-color: rgba(255, 255, 255, 0.2);
  color: white;
  border-color: rgba(255, 255, 255, 0.3);
}

:deep(.message-bubble) {
  position: relative;
}

:deep(.message-bubble::before) {
  display: none;
}

:deep(.ai-message .message-bubble::before) {
  display: none;
}

:deep(.user-message .message-bubble::before) {
  display: none;
}

/* 添加深色模式下滚动条样式 */
body.dark-theme .messages-container::-webkit-scrollbar,
body.dark-theme .chat-panel::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

body.dark-theme .messages-container::-webkit-scrollbar-track,
body.dark-theme .chat-panel::-webkit-scrollbar-track {
  background: #1e293b;
}

body.dark-theme .messages-container::-webkit-scrollbar-thumb,
body.dark-theme .chat-panel::-webkit-scrollbar-thumb {
  background: #334155;
  border-radius: 4px;
}

body.dark-theme .messages-container::-webkit-scrollbar-thumb:hover,
body.dark-theme .chat-panel::-webkit-scrollbar-thumb:hover {
  background: #475569;
}

/* 覆盖ElementPlus组件的样式，确保适应深色模式 */
body.dark-theme :deep(.el-button) {
  --el-button-hover-text-color: #60a5fa;
  --el-button-hover-bg-color: rgba(96, 165, 250, 0.1);
}

body.dark-theme :deep(.el-input__inner) {
  background-color: var(--input-bg, #1e293b);
  border-color: var(--border-color, #374151);
  color: var(--text-primary, #f9fafb);
}

body.dark-theme :deep(.el-input__wrapper) {
  background-color: var(--input-bg, #1e293b);
}

body.dark-theme :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--primary-color, #3b82f6) inset;
}

/* 深色模式下对话框样式 */
body.dark-theme :deep(.el-dialog) {
  background-color: var(--surface-color, #1f2937);
  border: 1px solid var(--border-color, #374151);
}

body.dark-theme :deep(.el-dialog__header) {
  border-bottom: 1px solid var(--border-color, #374151);
}

body.dark-theme :deep(.el-dialog__footer) {
  border-top: 1px solid var(--border-color, #374151);
}

body.dark-theme :deep(.el-overlay) {
  background-color: rgba(0, 0, 0, 0.6);
}

/* 在移动设备上的响应式样式 */
@media (max-width: 768px) {
  /* 深色模式下移动端样式调整 */
  body.dark-theme .sessions-panel {
    box-shadow: 0 0 30px rgba(0, 0, 0, 0.5);
  }

  body.dark-theme .sessions-panel:not(.collapsed) ~ .chat-container::before {
    background-color: rgba(0, 0, 0, 0.7);
  }
}

:deep(.message-time) {
  color: var(--text-secondary, #64748b);
  transition: color 0.3s ease;
}

:deep(.user-message .message-time) {
  color: rgba(255, 255, 255, 0.8);
}
</style> 