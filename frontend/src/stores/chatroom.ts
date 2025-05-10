import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import router from '@/router'
import webSocketManager, { WebSocketType } from '@/services/webSocketService'

// 添加接口定义
interface ChatMessageData {
  room_id: number;
  message_id?: string;
  content: string;
  user_id?: number;
  username?: string;
  avatar_url?: string;
  timestamp?: string;
  userId?: number; // 兼容性字段
  type?: string;
}

interface SystemMessageData {
  room_id: number;
  id?: string;
  content: string;
  timestamp?: string;
  type: string;
  user_id?: number;
}

interface ErrorMessageData {
  room_id?: number;
  content?: string;
  message?: string;
}

interface UserStatusData {
  user_id: number;
  status: string;
  timestamp?: string;
}

interface ChatRoomData {
  id: number;
  name: string;
  is_public: boolean;
  is_official: boolean;
  is_member: boolean;
  is_admin: boolean;
  member_count: number;
  online_users?: number;
  max_members: number;
  creator?: {
    id: number;
    username: string;
    avatar_url?: string;
  };
}

// 获取API基础URL
const getApiBaseUrl = () => {
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};

// 获取WebSocket基础URL
const getWsBaseUrl = () => {
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return apiBaseUrl.replace(/^http(s)?:/, wsProtocol);
};

export const useChatroomStore = defineStore('chatroom', {
  state: () => ({
    // WebSocket连接
    socket: null as WebSocket | null,
    connectionStatus: 'disconnected' as 'connecting' | 'connected' | 'disconnected',
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectInterval: 3000, // 3秒
    reconnectTimeout: null as number | null,
    heartbeatInterval: null as number | null,
    heartbeatTimeout: null as number | null,
    connectionError: null as string | null,
    
    // 聊天室数据
    rooms: [] as any[],
    currentRoomId: null as number | null,
    joinedRoomIds: [] as number[],
    messages: {} as Record<number, any[]>,
    usersTyping: {} as Record<number, Set<number>>,
    
    // 未读消息计数 - 新增
    unreadMessagesByRoom: {} as Record<number, number>,
  }),

  getters: {
    isConnected: (state) => state.connectionStatus === 'connected',
    currentRoomMessages: (state) => state.currentRoomId ? (state.messages[state.currentRoomId] || []) : [],
    currentRoomUsersTyping: (state) => state.currentRoomId ? (state.usersTyping[state.currentRoomId] || new Set()) : new Set(),
    
    // 获取特定聊天室的未读消息数
    getUnreadCountByRoom: (state) => (roomId: number) => state.unreadMessagesByRoom[roomId] || 0,
    
    // 计算所有聊天室的未读消息总数
    totalUnreadCount: (state) => {
      return Object.values(state.unreadMessagesByRoom).reduce((total, count) => total + count, 0);
    },
    
    // 更新rooms数据，包含未读消息信息
    roomsWithUnread: (state) => {
      return state.rooms.map(room => ({
        ...room,
        hasNewMessages: (state.unreadMessagesByRoom[room.id] || 0) > 0,
        unreadCount: state.unreadMessagesByRoom[room.id] || 0
      }));
    }
  },

  actions: {
    // 初始化聊天系统
    initialize() {
      // 加载已加入的聊天室列表
      this.fetchUserRooms();
      
      // 注意：不再直接连接WebSocket，由authService统一管理
      // WebSocket连接将在authService.initializeWebSockets()中处理
    },
    
    // 处理WebSocket消息
    handleWebSocketMessage(event: MessageEvent) {
      try {
        const data = JSON.parse(event.data);
        console.debug('[Chat] 收到WebSocket消息:', data);

        // 处理不同类型的消息
        switch (data.type) {
          case 'ping':
            // 收到服务器ping，回复pong
            this.sendPong();
            break;
          
          case 'pong':
            // 收到服务器pong响应，不需要处理
            break;

          case 'message':
            // 处理新消息 - 修改逻辑，确保消息数组总是被初始化
            if (data.room_id) {
              // 确保消息数组已经初始化
              if (!this.messages[data.room_id]) {
                this.messages[data.room_id] = [];
                console.log(`[Chat] 为聊天室 ${data.room_id} 初始化消息数组`);
              }
              this.handleChatMessage(data);
            }
            break;
            
          case 'join':
          case 'leave':
            // 用户加入/离开聊天室 - 同样确保消息数组已初始化
            if (data.room_id) {
              // 确保消息数组已经初始化
              if (!this.messages[data.room_id]) {
                this.messages[data.room_id] = [];
                console.log(`[Chat] 为聊天室 ${data.room_id} 初始化消息数组`);
              }
              this.handleSystemMessage(data);
            }
            break;
            
          case 'error':
            // 错误消息 - 同样确保消息数组已初始化
            if (data.room_id) {
              // 确保消息数组已经初始化
              if (!this.messages[data.room_id]) {
                this.messages[data.room_id] = [];
                console.log(`[Chat] 为聊天室 ${data.room_id} 初始化消息数组`);
              }
              this.handleErrorMessage(data);
            } else {
              console.error('[Chat] 收到错误消息:', data.content || data.message || '未知错误');
            }
            break;
            
          case 'user_status':
            // 用户状态变化
            this.handleUserStatusChange(data);
            break;
            
          default:
            console.log('收到未知类型的WebSocket消息:', data);
        }
      } catch (error) {
        console.error('[Chat] 处理WebSocket消息错误:', error);
      }
    },
    
    // 当WebSocket连接成功时的回调
    onWebSocketConnected() {
      console.log('[Chat] 聊天WebSocket连接已建立');
      this.connectionStatus = 'connected';
      this.reconnectAttempts = 0;
      this.connectionError = null;
      
      // 重新订阅所有已加入的聊天室
      this.resubscribeToRooms();
      
      // 触发连接成功事件，通知UI更新
      window.dispatchEvent(new Event('chat:websocket-connected'));
    },
    
    // 当WebSocket连接断开时的回调
    onWebSocketDisconnected() {
      console.log('[Chat] 聊天WebSocket连接已断开');
      this.connectionStatus = 'disconnected';
      
      // 触发断开连接事件，通知UI更新
      window.dispatchEvent(new Event('chat:websocket-disconnected'));
    },
    
    // 发送pong响应
    sendPong() {
      webSocketManager.send(WebSocketType.CHATROOM, { type: 'pong' });
    },
    
    // 发送ping请求
    sendPing() {
      webSocketManager.send(WebSocketType.CHATROOM, { type: 'ping' });
    },
    
    // 发送聊天消息
    sendChatMessage(content: string) {
      if (!this.currentRoomId) return false;
      
      const message = {
        type: 'message',
        room_id: this.currentRoomId,
        content: content
      };
      
      return webSocketManager.send(WebSocketType.CHATROOM, message);
    },
    
    // 兼容方法：提供与旧版API兼容的WebSocket连接方法
    // 此方法仅用于兼容现有代码，不应在新代码中使用
    connectWebSocket() {
      console.warn('[Chat] connectWebSocket方法已弃用，WebSocket连接现在由WebSocketManager统一管理');
      return webSocketManager.connect(WebSocketType.CHATROOM);
    },
    
    // 兼容方法：提供与旧版API兼容的WebSocket关闭方法
    // 此方法仅用于兼容现有代码，不应在新代码中使用
    closeWebSocket() {
      console.warn('[Chat] closeWebSocket方法已弃用，WebSocket连接现在由WebSocketManager统一管理');
      return webSocketManager.disconnect(WebSocketType.CHATROOM);
    },
    
    // 重置状态
    resetState() {
      // 不再需要关闭WebSocket连接，由WebSocketManager统一管理
      
      // 重置状态
      this.rooms = [];
      this.currentRoomId = null;
      this.joinedRoomIds = [];
      this.messages = {};
      this.usersTyping = {};
      this.connectionStatus = 'disconnected';
      this.reconnectAttempts = 0;
      this.connectionError = null;
      this.unreadMessagesByRoom = {}; // 重置未读消息计数
    },
    
    // 发送聊天室加入通知给WebSocket服务器
    sendJoinRoomNotification(roomId: number) {
      // 发送订阅消息，通知WebSocket服务器用户加入了此聊天室
      const message = {
        type: 'subscribe',
        room_id: roomId
      };
      
      console.log(`[Chat] 发送聊天室 ${roomId} 加入通知到WebSocket服务器`);
      webSocketManager.send(WebSocketType.CHATROOM, message);
    },
    
    // 重新订阅到所有已加入的聊天室
    resubscribeToRooms() {
      // 确保WebSocket已连接
      if (!webSocketManager.isConnected(WebSocketType.CHATROOM)) {
        console.log('[Chat] WebSocket未连接，无法重新订阅聊天室');
        return;
      }
      
      // 对每个已加入的聊天室发送加入通知
      this.joinedRoomIds.forEach(roomId => {
        this.sendJoinRoomNotification(roomId);
      });
      
      console.log(`[Chat] 已重新订阅 ${this.joinedRoomIds.length} 个聊天室`);
    },

    // 处理聊天消息
    handleChatMessage(data: ChatMessageData) {
      const roomId = data.room_id;
      
      // 确保消息数组已经初始化
      if (!this.messages[roomId]) {
        this.messages[roomId] = [];
      }
      
      // 将消息添加到对应聊天室的消息列表
      this.messages[roomId].push({
        id: data.message_id || `temp-${Date.now()}`,
        content: data.content,
        userId: data.user_id,
        username: data.username,
        avatar: data.avatar_url,
        timestamp: data.timestamp || new Date().toISOString(),
        isSystem: false
      });
      
      // 如果该用户正在输入中，收到消息后移除输入状态
      if (data.user_id && this.usersTyping[roomId] && this.usersTyping[roomId].has(data.user_id)) {
        this.usersTyping[roomId].delete(data.user_id);
      }
      
      // 如果消息属于当前聊天室，滚动到底部
      if (roomId === this.currentRoomId) {
        this.scrollToBottom();
      }
      
      // 如果消息不是当前用户发送的，且不是在当前浏览的聊天室中，增加未读消息计数
      const authStore = useAuthStore();
      const currentUserId = authStore.user?.id;
      
      if (data.userId !== currentUserId && roomId !== this.currentRoomId) {
        // 初始化该聊天室的未读消息计数（如果不存在）
        if (typeof this.unreadMessagesByRoom[roomId] === 'undefined') {
          this.unreadMessagesByRoom[roomId] = 0;
        }
        
        // 增加未读消息计数
        this.unreadMessagesByRoom[roomId]++;
        
        // 触发未读消息更新事件
        window.dispatchEvent(new CustomEvent('chat:unread-updated', {
          detail: { totalUnread: this.totalUnreadCount }
        }));
        
        // 更新rooms数组中的hasNewMessages标志
        this.updateRoomNewMessageStatus(roomId, true);
      }
    },

    // 处理系统消息（加入/离开聊天室）
    handleSystemMessage(data: SystemMessageData) {
      const roomId = data.room_id;
      
      // 确保消息数组已经初始化
      if (!this.messages[roomId]) {
        this.messages[roomId] = [];
      }
      
      // 添加系统消息到聊天列表
      this.messages[roomId].push({
        id: data.id || `system-${Date.now()}`,
        content: data.content,
        timestamp: data.timestamp || new Date().toISOString(),
        isSystem: true,
        event: data.type // 'join' 或 'leave'
      });
      
      // 如果是当前用户加入了一个新聊天室，更新joinedRoomIds
      const authStore = useAuthStore();
      if (data.type === 'join' && data.user_id === authStore.user?.id) {
        if (!this.joinedRoomIds.includes(roomId)) {
          this.joinedRoomIds.push(roomId);
        }
      } else if (data.type === 'leave' && data.user_id === authStore.user?.id) {
        this.joinedRoomIds = this.joinedRoomIds.filter(id => id !== roomId);
      }
      
      // 如果消息属于当前聊天室，滚动到底部
      if (roomId === this.currentRoomId) {
        this.scrollToBottom();
      }
    },

    // 处理错误消息
    handleErrorMessage(data: ErrorMessageData) {
      console.error('WebSocket错误消息:', data.content || data.message || '未知错误');
      
      if (data.room_id) {
        // 添加错误消息到聊天列表
        this.messages[data.room_id].push({
          id: `error-${Date.now()}`,
          content: `错误: ${data.content || data.message || '发生未知错误'}`,
          timestamp: new Date().toISOString(),
          isSystem: true,
          isError: true
        });
        
        // 如果消息属于当前聊天室，滚动到底部
        if (data.room_id === this.currentRoomId) {
          this.scrollToBottom();
        }
      }
    },

    // 处理用户状态变化
    handleUserStatusChange(data: UserStatusData) {
      console.log('用户状态变化:', data);
      // 这里可以实现用户在线/离线状态的更新逻辑
    },

    // 滚动到底部
    scrollToBottom() {
      // 这个方法通常在聊天组件中实现，这里只是一个占位函数
      setTimeout(() => {
        const chatContainer = document.querySelector('.chat-messages');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
      }, 50);
    },

    // 清除指定聊天室的消息
    clearRoomMessages(roomId: number) {
      if (roomId && this.messages[roomId]) {
        console.log(`清除聊天室 ${roomId} 的所有消息`);
        // 删除该聊天室的所有消息
        delete this.messages[roomId];
      }
    },

    // 标记聊天室所有消息为已读
    markRoomAsRead(roomId: number) {
      if (!roomId) return;
      
      // 清除该聊天室的未读消息计数
      if (this.unreadMessagesByRoom[roomId]) {
        this.unreadMessagesByRoom[roomId] = 0;
        
        // 触发未读消息更新事件
        window.dispatchEvent(new CustomEvent('chat:unread-updated', {
          detail: { totalUnread: this.totalUnreadCount }
        }));
        
        // 更新rooms数组中的hasNewMessages标志
        this.updateRoomNewMessageStatus(roomId, false);
      }
    },
    
    // 标记所有聊天室的消息为已读
    markAllRoomsAsRead() {
      // 重置所有聊天室的未读消息计数
      for (const roomId in this.unreadMessagesByRoom) {
        this.unreadMessagesByRoom[roomId] = 0;
        // 更新rooms数组中的hasNewMessages标志
        this.updateRoomNewMessageStatus(parseInt(roomId), false);
      }
      
      // 触发未读消息更新事件
      window.dispatchEvent(new CustomEvent('chat:unread-updated', {
        detail: { totalUnread: 0 }
      }));
    },
    
    // 更新聊天室的新消息状态
    updateRoomNewMessageStatus(roomId: number, hasNewMessages: boolean) {
      const roomIndex = this.rooms.findIndex(room => room.id === roomId);
      if (roomIndex !== -1) {
        // 创建一个新的room对象，保留原来的所有属性，更新hasNewMessages
        this.rooms[roomIndex] = {
          ...this.rooms[roomIndex],
          hasNewMessages
        };
      }
    },

    // 加载聊天室消息
    async loadRoomMessages(roomId: number) {
      if (!roomId) return;
      
      try {
        // 如果已有消息，不再重新加载
        if (this.messages[roomId] && this.messages[roomId].length > 0) {
          console.log(`已有聊天室 ${roomId} 的消息，不再重新加载`);
          
          // 进入聊天室时，清除未读消息计数
          this.markRoomAsRead(roomId);
          
        return;
      }
      
        const apiBaseUrl = getApiBaseUrl();
        const response = await axios.get(`${apiBaseUrl}/api/v1/chatroom/rooms/${roomId}/messages`);
        
        if (response.data) {
          // 确保聊天室消息数组已初始化
        if (!this.messages[roomId]) {
          this.messages[roomId] = [];
        }
        
          // 更新聊天室消息
          this.messages[roomId] = response.data;
          
          console.log(`成功加载聊天室 ${roomId} 的消息，数量:`, response.data.length);
          
          // 进入聊天室时，清除未读消息计数
          this.markRoomAsRead(roomId);
          
          // 在下次DOM更新后滚动到底部
          setTimeout(() => {
          this.scrollToBottom();
          }, 100);
        }
      } catch (error) {
        console.error(`加载聊天室 ${roomId} 的消息失败:`, error);
      }
    },

    // 加载用户加入的聊天室列表
    async fetchUserRooms() {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.error('用户未登录，无法加载聊天室列表');
        return;
      }
      
      try {
        const apiBaseUrl = getApiBaseUrl();
        const response = await axios.get(`${apiBaseUrl}/api/v1/chatroom/rooms`, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        // 统一属性名格式，将snake_case转为camelCase
        this.rooms = response.data.map((room: ChatRoomData) => ({
          ...room,
          // 保留原始属性的同时，添加驼峰式命名的别名
          isPublic: room.is_public,
          isOfficial: room.is_official,
          isMember: room.is_member,
          isAdmin: room.is_admin,
          memberCount: room.member_count,
          onlineUsers: room.online_users,
          maxMembers: room.max_members,
          // 转换创建者信息
          creator: room.creator ? {
            ...room.creator,
            avatarUrl: room.creator.avatar_url
          } : null
        }));
        
        // 更新已加入的聊天室ID列表
        this.joinedRoomIds = this.rooms
          .filter((room: ChatRoomData) => room.is_member)
          .map((room: ChatRoomData) => room.id);
          
        console.log('已加载聊天室列表:', this.rooms.length, '个聊天室');
      } catch (error) {
        console.error('加载聊天室列表失败:', error);
      }
    },

    // 加入聊天室
    async joinRoom(roomId: number) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.error('用户未登录，无法加入聊天室');
        return;
      }
      
      try {
        const apiBaseUrl = getApiBaseUrl();
        await axios.post(`${apiBaseUrl}/api/v1/chatroom/rooms/${roomId}/join`, {}, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        // 刷新用户的聊天室列表，确保获取最新的聊天室信息
        await this.fetchUserRooms();
        
        // 更新已加入的聊天室列表
        if (!this.joinedRoomIds.includes(roomId)) {
          this.joinedRoomIds.push(roomId);
        }
        
        // 更新当前选中的聊天室
        this.currentRoomId = roomId;
        
        // 确保消息数组已初始化，即使loadRoomMessages失败也能接收消息
        if (!this.messages[roomId]) {
          this.messages[roomId] = [];
          console.log(`[Chat] 为新加入的聊天室 ${roomId} 初始化消息数组`);
        }
        
        // 加载聊天室消息
        try {
        await this.loadRoomMessages(roomId);
        } catch (error) {
          console.error(`加载聊天室 ${roomId} 的消息失败:`, error);
          // 即使加载消息失败，也能保证消息数组已初始化，可以接收新消息
        }
        
        // 发送聊天室加入通知给WebSocket服务器
        this.sendJoinRoomNotification(roomId);
        
        return true;
      } catch (error) {
        console.error('加入聊天室失败:', error);
        return false;
      }
    },

    // 离开聊天室
    async leaveRoom(roomId: number) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.error('用户未登录，无法离开聊天室');
        return;
      }
      
      try {
        const apiBaseUrl = getApiBaseUrl();
        await axios.post(`${apiBaseUrl}/api/v1/chatroom/rooms/${roomId}/leave`, {}, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        // 从已加入的聊天室列表中移除
        this.joinedRoomIds = this.joinedRoomIds.filter(id => id !== roomId);
        
        // 如果当前选中的是该聊天室，清除选择
        if (this.currentRoomId === roomId) {
          this.currentRoomId = null;
        }
        
        return true;
      } catch (error) {
        console.error('离开聊天室失败:', error);
        return false;
      }
    },
  }
}); 