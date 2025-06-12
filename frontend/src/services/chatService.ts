import axios from 'axios'
import { tokenService } from '@/services/token'

// 不再需要獲取 TokenManager 實例，因為 tokenService 已經是單例

// 创建axios实例
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  },
  withCredentials: true
})

// 请求拦截器，添加token
apiClient.interceptors.request.use(
  config => {
    // 使用TokenService获取授权头
    const authHeader = tokenService.getAuthHeader()
    if (authHeader) {
      config.headers['Authorization'] = authHeader
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

export const chatService = {
  // 获取聊天会话列表
  async getChatSessions(page = 1, limit = 20) {
    try {
      const response = await apiClient.get(`/api/v1/chat/sessions`, {
        params: { skip: (page - 1) * limit, limit }
      })
      return response.data
    } catch (error) {
      console.error('Error fetching chat sessions:', error)
      throw error
    }
  },

  // 创建新的聊天会话
  async createChatSession(title = '新的对话') {
    try {
      const response = await apiClient.post(`/api/v1/chat/sessions`, { title })
      return response.data
    } catch (error) {
      console.error('Error creating chat session:', error)
      throw error
    }
  },

  // 获取指定会话的所有消息
  async getChatMessages(sessionId: number) {
    try {
      const response = await apiClient.get(`/api/v1/chat/sessions/${sessionId}`)
      return response.data
    } catch (error) {
      console.error(`Error fetching messages for session ${sessionId}:`, error)
      throw error
    }
  },

  // 发送消息并获取回复
  async sendMessage(sessionId: number, message: string) {
    try {
      const response = await apiClient.post(`/api/v1/chat/send`, {
        session_id: sessionId,
        message
      })
      return response.data
    } catch (error) {
      console.error('Error sending message:', error)
      throw error
    }
  },

  // 更新会话标题
  async updateChatSession(sessionId: number, title: string) {
    try {
      const response = await apiClient.put(`/api/v1/chat/sessions/${sessionId}`, { title })
      return response.data
    } catch (error) {
      console.error(`Error updating session ${sessionId}:`, error)
      throw error
    }
  },

  // 删除会话
  async deleteChatSession(sessionId: number) {
    try {
      await apiClient.delete(`/api/v1/chat/sessions/${sessionId}`)
      return true
    } catch (error) {
      console.error(`Error deleting session ${sessionId}:`, error)
      throw error
    }
  },

  // 获取剩余的每日消息次数
  async getRemainingMessages() {
    try {
      const response = await apiClient.get(`/api/v1/chat/remaining_messages`)
      return response.data
    } catch (error) {
      console.error('Error fetching remaining messages:', error)
      throw error
    }
  }
} 