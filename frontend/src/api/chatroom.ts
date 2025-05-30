import { ref, reactive } from 'vue'
import { useUserStore } from '../stores/user'
import { useRouter } from 'vue-router'
import { useChatroomStore } from '@/stores/chatroom'
import webSocketManager from '@/services/webSocketService'

// WebSocket连接状态
export const connectionStatus = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')
export const currentRoomId = ref<number | null>(null)
export const socket = ref<WebSocket | null>(null)
export const chatMessages = reactive<any[]>([])
export const usersTyping = reactive<Set<number>>(new Set())
export const connectionError = ref<string | null>(null)
export const reconnectAttempts = ref(0)
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_INTERVAL = 3000 // 3秒
let reconnectTimeout: number | null = null
let lastPingTime = 0
let heartbeatInterval: number | null = null

// 重置聊天状态
export function resetChatState() {
  const chatroomStore = useChatroomStore()
  chatroomStore.resetState()
}

// 连接到WebSocket
export function connectToWebSocket() {
  // 使用主WebSocket連接
  webSocketManager.connect()
}

// 心跳检测
function startHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval)
  }
  
  lastPingTime = Date.now()
  
  // 创建心跳计时器
  heartbeatInterval = window.setInterval(() => {
    // 检查最后一次ping时间，如果超过60秒没有收到ping，认为连接可能已断开
    const currentTime = Date.now()
    if (currentTime - lastPingTime > 65000) { // 65秒，略大于服务器端的60秒超时
      console.warn('No ping received for 65 seconds, connection may be lost')
      
      // 尝试主动发送ping
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        socket.value.send(JSON.stringify({
          type: 'ping',
          timestamp: new Date().toISOString()
        }))
      } else {
        // 如果连接已经关闭，尝试重连
        if (currentRoomId.value) {
          console.log('Connection appears to be closed, attempting to reconnect')
          socket.value?.close()
          connectionStatus.value = 'disconnected'
          handleReconnect(currentRoomId.value)
        }
      }
    }
  }, 15000) // 每15秒检查一次
}

// 发送pong响应
function sendPong() {
  if (socket.value && socket.value.readyState === WebSocket.OPEN) {
    socket.value.send(JSON.stringify({
      type: 'pong',
      timestamp: new Date().toISOString()
    }))
  }
}

// 处理重连
function handleReconnect(roomId: number) {
  // 如果已经达到最大重连尝试次数，停止重连
  if (reconnectAttempts.value >= MAX_RECONNECT_ATTEMPTS) {
    connectionError.value = '重连失败，请刷新页面重试'
    return
  }
  
  // 增加重连计数
  reconnectAttempts.value++
  
  // 清理之前的重连定时器
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
  }
  
  // 设置重连定时器
  const delay = RECONNECT_INTERVAL * reconnectAttempts.value
  console.log(`Attempting to reconnect in ${delay}ms (attempt ${reconnectAttempts.value})`)
  
  reconnectTimeout = window.setTimeout(() => {
    if (connectionStatus.value !== 'connected') {
      console.log(`Reconnecting... (attempt ${reconnectAttempts.value})`)
      connectToWebSocket()
    }
  }, delay)
}

// 处理聊天消息
function handleChatMessage(data: any) {
  // 将消息添加到聊天消息列表
  chatMessages.push({
    id: data.id || `temp-${Date.now()}`,
    content: data.content,
    userId: data.userId,
    username: data.username,
    avatar: data.avatar,
    timestamp: data.timestamp || new Date().toISOString(),
    isSystem: false
  })
  
  // 如果该用户正在输入中，收到消息后移除输入状态
  if (data.userId && usersTyping.has(data.userId)) {
    usersTyping.delete(data.userId)
  }
}

// 处理正在输入状态
function handleTypingStatus(data: any) {
  if (data.userId) {
    // 添加用户到正在输入列表
    usersTyping.add(data.userId)
    
    // 设置定时器，5秒后自动移除输入状态
    setTimeout(() => {
      usersTyping.delete(data.userId)
    }, 5000)
  }
}

// 处理系统消息
function handleSystemMessage(data: any) {
  // 添加系统消息到聊天列表
  chatMessages.push({
    id: data.id || `system-${Date.now()}`,
    content: data.content,
    timestamp: data.timestamp || new Date().toISOString(),
    isSystem: true
  })
  
  // 如果是用户加入/离开等消息，可能需要更新在線用戶列表
  if (data.event === 'user_joined' || data.event === 'user_left') {
    // 这里可以触发更新在線用戶列表的逻辑
    // 如果后端提供了更新后的在線用戶列表，可以直接更新
    if (data.onlineUsers) {
      // 更新在線用戶列表的逻辑
      // onlineUsers.value = data.onlineUsers
    }
  }
}

// 处理错误消息
function handleErrorMessage(data: any) {
  // 记录错误消息
  console.error('WebSocket error message:', data.message || data.error)
  
  // 设置错误状态
  connectionError.value = data.message || data.error || '发生未知错误'
  
  // 可以选择将错误消息显示为系统消息
  chatMessages.push({
    id: `error-${Date.now()}`,
    content: `错误: ${data.message || data.error || '发生未知错误'}`,
    timestamp: new Date().toISOString(),
    isSystem: true,
    isError: true
  })
}

// 发送聊天消息
export function sendChatMessage(content: string) {
  const chatroomStore = useChatroomStore()
  return chatroomStore.sendChatMessage(content)
}

// 发送正在输入状态
export function sendTypingStatus() {
  const chatroomStore = useChatroomStore()
  chatroomStore.sendTypingStatus()
}

// 加载聊天室消息
export async function loadRoomMessages(roomId: number) {
  const chatroomStore = useChatroomStore()
  await chatroomStore.loadRoomMessages(roomId)
}

// ... existing message handler functions ... 