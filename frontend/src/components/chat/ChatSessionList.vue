<template>
  <div class="chat-session-list">
    <div class="header">
      <h2>聊天列表</h2>
      <el-button type="primary" size="small" @click="createNewSession" class="new-session-btn" round>
        <el-icon><Plus /></el-icon>
        新對話
      </el-button>
    </div>
    
    <div v-if="isLoading" class="loading-placeholder">
      <el-skeleton :rows="5" animated />
    </div>
    
    <el-scrollbar height="calc(100vh - 180px)" v-else class="custom-scrollbar">
      <div v-if="sessions.length === 0" class="empty-state">
        <el-empty description="暫無聊天會話" />
        <el-button type="primary" @click="createNewSession" class="empty-state-btn" round>
          開始第一個對話
        </el-button>
      </div>
      
      <div v-else class="session-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: activeSessionId === session.id }"
          @click="selectSession(session)"
        >
          <div class="session-info">
            <span class="session-title">{{ session.title }}</span>
            <span class="session-time">{{ formatTime(session.updated_at) }}</span>
          </div>
          
          <div class="session-actions">
            <el-dropdown trigger="click" @command="handleCommand($event, session)">
              <el-button type="text" size="small">
                <el-icon><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu class="rounded-dropdown">
                  <el-dropdown-item command="rename">
                    <el-icon><Edit /></el-icon>
                    重命名
                  </el-dropdown-item>
                  <el-dropdown-item command="delete" divided>
                    <el-icon><Delete /></el-icon>
                    刪除
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </div>
    </el-scrollbar>
    
    <!-- 重命名对话框 -->
    <el-dialog
      v-model="renameDialog.visible"
      title="重命名對話"
      width="30%"
      class="rename-dialog"
      :show-close="true"
    >
      <el-input
        v-model="renameDialog.title"
        placeholder="請輸入新的標題"
        maxlength="100"
        show-word-limit
        class="rounded-input"
      />
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="renameDialog.visible = false" class="cancel-btn" round>取消</el-button>
          <el-button type="primary" @click="renameSession" class="confirm-btn" round>確認</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, MoreFilled } from '@element-plus/icons-vue'
import { chatService } from '@/services/chatService'
import { formatDistanceToNow } from 'date-fns'
import { zhCN } from 'date-fns/locale'

const props = defineProps({
  activeSessionId: {
    type: Number,
    default: null
  }
})

const emit = defineEmits(['session-selected', 'session-created', 'session-deleted', 'session-renamed'])

// 会话列表数据
const sessions = ref([])
const isLoading = ref(true)

// 重命名对话框
const renameDialog = ref({
  visible: false,
  title: '',
  sessionId: null
})

// 获取会话列表
const fetchSessions = async () => {
  try {
    isLoading.value = true
    const data = await chatService.getChatSessions()
    sessions.value = data.items || []
  } catch (error) {
    ElMessage.error('获取聊天列表失败')
    console.error(error)
  } finally {
    isLoading.value = false
  }
}

// 选择会话
const selectSession = (session) => {
  emit('session-selected', session)
}

// 创建新会话
const createNewSession = async () => {
  try {
    const session = await chatService.createChatSession()
    sessions.value.unshift(session)
    emit('session-created', session)
    ElMessage.success('创建新对话成功')
  } catch (error) {
    ElMessage.error('创建新对话失败')
    console.error(error)
  }
}

// 删除会话
const deleteSession = async (session) => {
  try {
    await ElMessageBox.confirm(
      '此操作将永久删除该对话，是否继续？',
      '提示',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await chatService.deleteChatSession(session.id)
    sessions.value = sessions.value.filter(s => s.id !== session.id)
    emit('session-deleted', session.id)
    ElMessage.success('删除成功')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// 重命名会话
const openRenameDialog = (session) => {
  renameDialog.value = {
    visible: true,
    title: session.title,
    sessionId: session.id
  }
}

const renameSession = async () => {
  if (!renameDialog.value.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  
  try {
    const sessionId = renameDialog.value.sessionId
    const newTitle = renameDialog.value.title.trim()
    
    const updatedSession = await chatService.updateChatSession(sessionId, newTitle)
    const index = sessions.value.findIndex(s => s.id === sessionId)
    
    if (index !== -1) {
      sessions.value[index] = updatedSession
    }
    
    emit('session-renamed', updatedSession)
    renameDialog.value.visible = false
    ElMessage.success('重命名成功')
  } catch (error) {
    ElMessage.error('重命名失败')
    console.error(error)
  }
}

// 处理下拉菜单命令
const handleCommand = (command, session) => {
  if (command === 'rename') {
    openRenameDialog(session)
  } else if (command === 'delete') {
    deleteSession(session)
  }
}

// 格式化时间
const formatTime = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return formatDistanceToNow(date, { addSuffix: true, locale: zhCN })
}

// 初始化
onMounted(() => {
  fetchSessions()
})
</script>

<style scoped>
.chat-session-list {
  height: 100%;
  border-right: 1px solid var(--border-color);
  background-color: var(--surface-color);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  border-radius: 20px;
}

.header {
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--border-color);
  border-top-left-radius: 20px;
  border-top-right-radius: 20px;
}

.header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.loading-placeholder {
  padding: 16px;
}

.empty-state {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-secondary);
  border-radius: 20px;
}

.session-list {
  padding: 12px;
  border-radius: 20px;
}

.session-item {
  padding: 14px 16px;
  border-radius: 20px;
  margin-bottom: 10px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s ease;
  background-color: var(--card-background);
  border: 1px solid var(--border-light);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.session-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  background-color: var(--hover-color);
  border-color: var(--border-color);
}

.session-item.active {
  background-color: var(--notification-unread);
  border-color: var(--primary-light);
  box-shadow: 0 4px 12px rgba(var(--el-color-primary-rgb), 0.1);
}

.session-info {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-primary);
}

.session-time {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 4px;
}

.session-actions {
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.session-item:hover .session-actions {
  opacity: 1;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .header {
    padding: 12px;
  }
  
  .session-list {
    padding: 8px;
  }
  
  .session-item {
    padding: 12px;
    margin-bottom: 8px;
  }
}

/* 暗黑模式通过CSS变量自动适配 - 不需要额外的媒体查询 */

.custom-scrollbar :deep(.el-scrollbar__wrap) {
  border-bottom-left-radius: 20px;
  border-bottom-right-radius: 20px;
  overflow: hidden;
}

.new-session-btn {
  border-radius: 16px;
}

/* 对话框样式 */
.rename-dialog :deep(.el-dialog) {
  border-radius: 20px;
  overflow: hidden;
}

.rename-dialog :deep(.el-dialog__header) {
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
}

.rename-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.rename-dialog :deep(.el-dialog__footer) {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
}

.rounded-input :deep(.el-input__inner) {
  border-radius: 16px;
}

.dialog-footer .cancel-btn,
.dialog-footer .confirm-btn {
  border-radius: 16px;
  padding: 8px 20px;
}

.empty-state-btn {
  margin-top: 16px;
  border-radius: 16px;
  padding: 10px 20px;
}

.rounded-dropdown :deep(.el-dropdown-menu) {
  border-radius: 16px;
  overflow: hidden;
  padding: 8px;
}

.rounded-dropdown :deep(.el-dropdown-menu__item) {
  border-radius: 12px;
  margin: 2px 0;
}

.session-actions :deep(.el-button) {
  border-radius: 50%;
}
</style> 