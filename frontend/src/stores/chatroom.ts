import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import router from '@/router'

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
      const authStore = useAuthStore();
      
      // 如果用户未登录，不进行初始化
      if (!authStore.isAuthenticated) {
        console.log('用户未登录，跳过聊天系统初始化');
        return;
      }
      
      console.log('开始初始化聊天系统...');
      
      // 连接到聊天WebSocket
      this.connectWebSocket();
      
      // 获取用户加入的聊天室列表
      this.fetchUserRooms();
      
      console.log('聊天系统初始化完成');
    },
    
    // 连接到聊天WebSocket
    connectWebSocket() {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated || !authStore.token) {
        console.log('未登录，不能连接聊天WebSocket');
        return;
      }

      // 如果已经连接，先关闭现有连接
      this.closeWebSocket();

      try {
        const wsBaseUrl = getWsBaseUrl();
        const wsUrl = `${wsBaseUrl}/api/v1/chatroom/ws/user/${authStore.token}`;
        
        console.log(`正在连接聊天WebSocket: ${wsUrl.replace(/\/user\/[^/]+/, '/user/***')}`);
        
        this.connectionStatus = 'connecting';
        this.socket = new WebSocket(wsUrl);

        // 连接打开事件
        this.socket.onopen = () => {
          console.log('聊天WebSocket连接已建立');
          this.connectionStatus = 'connected';
          this.reconnectAttempts = 0;
          this.connectionError = null;
          
          // 设置心跳检测
          this.startHeartbeat();
          
          // 重新订阅所有已加入的聊天室
          this.resubscribeToRooms();
          
          // 触发连接成功事件，通知UI更新
          window.dispatchEvent(new Event('chat:websocket-connected'));
        };

        // 连接关闭事件
        this.socket.onclose = (event) => {
          this.connectionStatus = 'disconnected';
          
          // 触发断开连接事件，通知UI更新
          window.dispatchEvent(new Event('chat:websocket-disconnected'));
          
          // 清除心跳检测
          if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
          }
          
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          
          console.log(`聊天WebSocket连接已关闭，代码: ${event.code}，原因: ${event.reason || '未提供原因'}`);
          
          // 记录常见关闭代码的含义，帮助诊断问题
          if (event.code === 1000) {
            console.log('WebSocket正常关闭');
            // 正常关闭，不进行重连
            return;
          } else if (event.code === 1001) {
            console.log('WebSocket关闭: 终端离开');
          } else if (event.code === 1006) {
            console.log('WebSocket关闭: 异常关闭，可能是网络问题或服务器重启');
          } else if (event.code === 1008) {
            console.log('WebSocket关闭: 违反策略，可能是认证问题');
          }
          
          // 认证错误时的处理
          if (event.code === 1008) {
            console.log('认证问题，可能是token过期');
            
            // 检查用户是否仍然登录
            if (!authStore.isAuthenticated || !authStore.token) {
              console.log('用户已登出，不尝试重连，重置状态');
              this.socket = null;
              this.resetState();
              return;
            }
            
            // 重要：尝试刷新token
            console.log('尝试刷新token并重连');
            authStore.refreshAccessToken(true).then(success => {
              if (success) {
                console.log('Token刷新成功，尝试重新连接');
                setTimeout(() => {
                  this.connectWebSocket();
                }, 1000); // 等待1秒确保token已传播到后端
              } else {
                console.log('Token刷新失败，不尝试重连，重置状态');
                this.socket = null;
                this.resetState();
              }
            });
            return;
          }
          
          // 检查用户是否仍然登录
          if (!authStore.isAuthenticated || !authStore.token) {
            console.log('用户已登出，不尝试重连');
            // 清理socket相关资源
            this.socket = null;
            // 重置状态
            this.resetState();
            return;
          }
          
          // 只有在非正常关闭且未超过最大重连次数时尝试重连
          if (event.code !== 1000 && event.code !== 1001 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };

        // 连接错误事件
        this.socket.onerror = (error) => {
          console.error('聊天WebSocket连接出错:', error);
          this.connectionError = '聊天WebSocket连接出错';
          
          // 在错误发生时不立即尝试重连，让onclose事件处理重连逻辑
        };

        // 收到消息事件
        this.socket.onmessage = (event) => {
          // 处理消息
          this.handleWebSocketMessage(event);
        };
      } catch (error) {
        console.error('创建聊天WebSocket连接失败:', error);
        this.connectionError = '创建聊天WebSocket连接失败';
        
        // 如果创建WebSocket对象失败，直接尝试重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        }
      }
    },

    // 尝试重新连接WebSocket
    attemptReconnect() {
      this.reconnectAttempts++;
      
      // 清理之前的重连定时器
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
      
      // 使用指数退避策略，增加重连间隔
      const delay = this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);
      
      console.log(`尝试重新连接聊天WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...将在 ${delay/1000} 秒后尝试`);
      
      this.reconnectTimeout = window.setTimeout(() => {
        // 检查登录状态再尝试重连
        const authStore = useAuthStore();
        if (authStore.isAuthenticated && authStore.token) {
          console.log(`正在执行第 ${this.reconnectAttempts} 次重连尝试...`);
          this.connectWebSocket();
        } else {
          console.log('用户已登出，取消重连');
        }
      }, delay);
    },

    // 关闭WebSocket连接
    closeWebSocket() {
      // 清除所有心跳相关定时器
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // 关闭重连定时器
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
      
      // 关闭WebSocket连接
      if (this.socket) {
        try {
          this.socket.onopen = null;
          this.socket.onmessage = null;
          this.socket.onerror = null;
          this.socket.onclose = null;
          this.socket.close();
        } catch (e) {
          console.error('[Chat] 关闭WebSocket连接失败:', e);
        }
        this.socket = null;
      }
      
      this.connectionStatus = 'disconnected';
    },

    // 处理WebSocket收到的消息
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
            // 收到服务器pong响应，清除心跳超时
            if (this.heartbeatTimeout) {
              clearTimeout(this.heartbeatTimeout);
              this.heartbeatTimeout = null;
            }
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

    // 发送pong响应
    sendPong() {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = JSON.stringify({ type: 'pong' });
        this.socket.send(message);
        console.debug('[Chat] 发送pong响应');
      }
    },

    // 发送ping请求
    sendPing() {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        const message = JSON.stringify({ type: 'ping' });
        this.socket.send(message);
        console.debug('[Chat] 发送ping请求');
      }
    },

    // 启动心跳检测
    startHeartbeat() {
      // 清除现有的心跳计时器
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
      }
      
      // 每30秒发送一次ping
      this.heartbeatInterval = window.setInterval(() => {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          // 发送ping
          const message = JSON.stringify({ type: 'ping' });
          this.socket.send(message);
          console.debug('[Chat] 发送ping心跳');
          
          // 设置10秒超时等待pong响应
          this.heartbeatTimeout = window.setTimeout(() => {
            console.warn('[Chat] 心跳检测失败: 未收到pong响应');
            // 关闭连接并触发重连
            this.closeWebSocket();
            this.attemptReconnect();
          }, 10000); // 10秒超时
        }
      }, 30000); // 30秒间隔
    },

    // 发送聊天消息
    sendChatMessage(content: string) {
      const authStore = useAuthStore();
      
      // 首先检查用户是否已登录，这是最重要的安全检查
      if (!authStore.isAuthenticated || !authStore.token) {
        console.error('[Chat] 无法发送消息：用户未登录或没有有效token');
        return;
      }
      
      // 其次检查WebSocket连接状态
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN || !this.currentRoomId) {
        console.error('[Chat] 无法发送消息：WebSocket未连接或未选择聊天室');
        return;
      }
      
      // 确保已经向WebSocket服务器发送了聊天室订阅通知
      if (this.currentRoomId && this.joinedRoomIds.includes(this.currentRoomId)) {
        // 发送订阅通知以确保WebSocket服务器知道用户在这个聊天室
        this.sendJoinRoomNotification(this.currentRoomId);
      }
      
      const message = JSON.stringify({
        type: 'message',
        room_id: this.currentRoomId,
        content: content
      });
      
      this.socket.send(message);
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

    // 重置状态
    resetState() {
      // 关闭WebSocket连接
      this.closeWebSocket();
      
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

    // 清除指定聊天室的消息
    clearRoomMessages(roomId: number) {
      if (roomId && this.messages[roomId]) {
        console.log(`清除聊天室 ${roomId} 的所有消息`);
        // 删除该聊天室的所有消息
        delete this.messages[roomId];
      }
    },

    // 发送聊天室加入通知给WebSocket服务器
    sendJoinRoomNotification(roomId: number) {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        console.error('[Chat] 无法发送加入通知：WebSocket未连接');
        return;
      }
      
      // 发送订阅消息，通知WebSocket服务器用户加入了此聊天室
      const message = JSON.stringify({
        type: 'subscribe',
        room_id: roomId
      });
      
      console.log(`[Chat] 发送聊天室 ${roomId} 加入通知到WebSocket服务器`);
      this.socket.send(message);
    },
    
    // 重新订阅所有已加入的聊天室（在连接或重连后调用）
    resubscribeToRooms() {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        console.error('[Chat] 无法重新订阅聊天室：WebSocket未连接');
        return;
      }
      
      if (this.joinedRoomIds.length > 0) {
        console.log(`[Chat] 重新订阅 ${this.joinedRoomIds.length} 个聊天室`);
        
        // 对每个已加入的聊天室发送订阅消息
        this.joinedRoomIds.forEach(roomId => {
          this.sendJoinRoomNotification(roomId);
        });
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
  }
}); 