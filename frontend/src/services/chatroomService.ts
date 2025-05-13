import axios from 'axios'
import { getTokenManager } from './tokenService'

// 获取TokenManager实例
const tokenManager = getTokenManager()

// 创建axios实例
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器，添加token
apiClient.interceptors.request.use(
  config => {
    // 使用TokenManager获取授权头
    const authHeader = tokenManager.getAuthorizationHeader()
    if (authHeader) {
      config.headers['Authorization'] = authHeader
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 定义聊天室相关的接口
export interface ChatRoom {
  id: number;
  name: string;
  description?: string;
  is_public: boolean;
  is_official: boolean;
  created_by?: number;
  created_at: string;
  updated_at: string;
  creator?: UserBasic;
  member_count: number;
  is_member: boolean;
  is_admin: boolean;
  online_users?: number;
}

export interface ChatRoomCreate {
  name: string;
  description?: string;
  is_public: boolean;
  is_official?: boolean;
}

export interface ChatRoomUpdate {
  name?: string;
  description?: string;
  is_public?: boolean;
}

export interface ChatMessage {
  id: number;
  room_id: number;
  user_id?: number;
  content: string;
  is_system: boolean;
  created_at: string;
  user?: UserBasic;
}

export interface UserBasic {
  id: number;
  username: string;
  avatar_url?: string;
}

export const chatroomService = {
  // 获取聊天室列表
  async getChatRooms(page = 1, limit = 20) {
    try {
      const response = await apiClient.get(`/api/v1/chatroom/rooms`, {
        params: { skip: (page - 1) * limit, limit }
      })
      return response.data
    } catch (error) {
      console.error('Error fetching chat rooms:', error)
      throw error
    }
  },

  // 创建新的聊天室
  async createChatRoom(data: ChatRoomCreate) {
    try {
      const response = await apiClient.post(`/api/v1/chatroom/rooms`, data)
      return response.data
    } catch (error) {
      console.error('Error creating chat room:', error)
      throw error
    }
  },

  // 获取指定聊天室及其消息
  async getChatRoom(roomId: number, messageLimit = 50) {
    try {
      const response = await apiClient.get(`/api/v1/chatroom/rooms/${roomId}`, {
        params: { message_limit: messageLimit }
      })
      return response.data
    } catch (error) {
      console.error(`Error fetching room ${roomId}:`, error)
      throw error
    }
  },

  // 更新聊天室信息
  async updateChatRoom(roomId: number, data: ChatRoomUpdate) {
    try {
      const response = await apiClient.put(`/api/v1/chatroom/rooms/${roomId}`, data)
      return response.data
    } catch (error) {
      console.error(`Error updating room ${roomId}:`, error)
      throw error
    }
  },

  // 删除聊天室
  async deleteChatRoom(roomId: number) {
    try {
      await apiClient.delete(`/api/v1/chatroom/rooms/${roomId}`)
      return true
    } catch (error) {
      console.error(`Error deleting room ${roomId}:`, error)
      throw error
    }
  },

  // 发送聊天消息（HTTP备用方法，主要使用WebSocket）
  async sendMessage(roomId: number, content: string) {
    try {
      const response = await apiClient.post(`/api/v1/chatroom/messages`, {
        room_id: roomId,
        content
      })
      return response.data
    } catch (error) {
      console.error('Error sending message:', error)
      throw error
    }
  },

  // 获取聊天室的消息
  async getChatMessages(roomId: number, page = 1, limit = 50) {
    try {
      // 移除分頁參數，直接獲取所有消息
      const response = await apiClient.get(`/api/v1/chatroom/messages/${roomId}`)
      return response.data
    } catch (error) {
      console.error(`Error fetching messages for room ${roomId}:`, error)
      throw error
    }
  },

  // 获取聊天室活跃用户
  async getRoomUsers(roomId: number) {
    try {
      const response = await apiClient.get(`/api/v1/chatroom/rooms/${roomId}/users`)
      return response.data
    } catch (error) {
      console.error(`Error fetching users for room ${roomId}:`, error)
      throw error
    }
  },

  // 获取WebSocket连接URL
  getWebSocketUrl() {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const wsProtocol = baseUrl.startsWith('https') ? 'wss' : 'ws'
    const wsBaseUrl = baseUrl.replace(/^https?:\/\//, `${wsProtocol}://`)
    
    // 使用本地存储中的访问令牌，这是WebSocket验证需要的
    const token = localStorage.getItem('token') || ''
    
    // 改为使用用户级别的连接，不再需要房间ID
    return `${wsBaseUrl}/api/v1/chatroom/ws/user/${token}`
  }
} 