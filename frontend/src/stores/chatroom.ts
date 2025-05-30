import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import router from '@/router'
import webSocketManager from '@/services/webSocketService'

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
    // WebSocket连接狀態（僅保留狀態，但實際連接由WebSocketManager管理）
    connectionStatus: 'disconnected' as 'connecting' | 'connected' | 'disconnected',
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectInterval: 3000, // 3秒
    reconnectTimeout: null as number | null,
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
      console.log('[Chat] 初始化聊天系統...');
      
      // 設置聊天相關事件監聽器
      this.setupEventListeners();
      
      // 立即嘗試加載聊天室列表
      this.fetchUserRooms().then(success => {
        if (success) {
          console.log('[Chat] 聊天室列表初始化成功');
          
          // 如果用戶已加入某些聊天室，嘗試訂閱
          if (this.joinedRoomIds.length > 0) {
            console.log('[Chat] 正在訂閱已加入的聊天室:', this.joinedRoomIds);
            this.resubscribeToRooms();
          }
        } else {
          console.warn('[Chat] 聊天室列表初始化失敗，將在WebSocket連接後重試');
        }
      });
      
      // 注意：不再直接连接WebSocket，由authService统一管理
      // WebSocket连接将在authService.initializeWebSockets()中处理
      
      console.log('[Chat] 聊天系統初始化完成');
    },
    
    // 設置事件監聽器
    setupEventListeners() {
      // 監聽聊天消息事件（從主 WebSocket 轉發）
      window.addEventListener('chat:message-received', (event: CustomEvent) => {
        if (event.detail) {
          const { messageId, roomId } = event.detail;
          console.log(`[聊天] 收到聊天消息事件: ID=${messageId}, 聊天室=${roomId}`);
          
          // 如果消息屬於當前聊天室，滾動到底部
          if (roomId === this.currentRoomId) {
            this.scrollToBottom();
          }
        }
      });
      
      console.log('[聊天] 事件監聽器設置完成');
    },
    
    // 處理WebSocket消息 - 由主WebSocket轉發
    handleWebSocketMessage(data: any) {
      try {
        console.debug('[聊天] 收到WebSocket消息:', JSON.stringify(data));

        // 處理不同類型的消息
        const msgType = data.type || '';
        
        if (msgType === 'chat/message') {
          // 處理聊天消息
          console.log('[聊天] 收到聊天消息，完整數據:', JSON.stringify(data));
          
          if (data.room_id) {
            // 確保消息數組已經初始化
            if (!this.messages[data.room_id]) {
              this.messages[data.room_id] = [];
              console.log(`[聊天] 為聊天室 ${data.room_id} 初始化消息數組`);
            }
            this.handleChatMessage(data);
          } else {
            console.error('[聊天] 收到的消息缺少 room_id 欄位:', data);
          }
        } else if (msgType === 'chat/join' || msgType === 'chat/leave') {
          // 用户加入/離開聊天室
          console.log(`[聊天] 收到用戶 ${data.user_id} ${msgType === 'chat/join' ? '加入' : '離開'} 聊天室 ${data.room_id} 的消息`);
          
          if (data.room_id) {
            // 確保消息數組已經初始化
            if (!this.messages[data.room_id]) {
              this.messages[data.room_id] = [];
              console.log(`[聊天] 為聊天室 ${data.room_id} 初始化消息數組`);
            }
            this.handleSystemMessage(data);
          } else {
            console.error('[聊天] 收到的系統消息缺少 room_id 欄位:', data);
          }
        } else if (msgType === 'chat/error') {
          // 錯誤消息
          console.error('[聊天] 收到錯誤消息:', data);
          
          if (data.room_id) {
            // 確保消息數組已經初始化
            if (!this.messages[data.room_id]) {
              this.messages[data.room_id] = [];
              console.log(`[聊天] 為聊天室 ${data.room_id} 初始化消息數組`);
            }
            this.handleErrorMessage(data);
          } else {
            console.error('[聊天] 收到錯誤消息:', data.content || data.message || '未知錯誤');
          }
        } else if (msgType === 'user_status' || msgType === 'online/status') {
          // 用户狀態變化
          console.log('[聊天] 收到用戶狀態變化消息:', data);
          this.handleUserStatusChange(data);
        } else if (msgType === 'ping') {
          // 收到ping，回復pong
          console.log('[聊天] 收到 ping 消息，回復 pong');
          this.sendPong();
        } else if (msgType === 'pong') {
          // 收到pong，不需處理
          console.log('[聊天] 收到 pong 回覆');
        } else {
          console.log('[聊天] 收到未知類型的WebSocket消息:', msgType, data);
        }
      } catch (error) {
        console.error('[聊天] 處理WebSocket消息錯誤:', error);
      }
    },
    
    // 當WebSocket連接成功時的回調
    onWebSocketConnected() {
      console.log('[Chat] 聊天WebSocket連接已建立');
      this.connectionStatus = 'connected';
      this.reconnectAttempts = 0;
      this.connectionError = null;
      
      // 重新訂閱所有已加入的聊天室
      this.resubscribeToRooms();
      
      // 觸發連接成功事件，通知UI更新
      window.dispatchEvent(new Event('chat:websocket-connected'));
    },
    
    // 當WebSocket連接斷開時的回調
    onWebSocketDisconnected() {
      console.log('[Chat] 聊天WebSocket連接已斷開');
      this.connectionStatus = 'disconnected';
      
      // 觸發斷開連接事件，通知UI更新
      window.dispatchEvent(new Event('chat:websocket-disconnected'));
    },
    
    // 發送pong響應
    sendPong() {
      webSocketManager.send({ type: 'pong' });
    },
    
    // 發送ping請求
    sendPing() {
      webSocketManager.send({ type: 'ping' });
    },
    
    // 發送聊天消息
    sendChatMessage(content: string) {
      if (!this.currentRoomId) {
        console.error('[Chat] 嘗試發送消息，但未選擇聊天室');
        return false;
      }
      
      const message = {
        type: 'chat/message',
        room_id: this.currentRoomId,
        content
      };
      
      return webSocketManager.send(message);  // 直接傳遞消息對象
    },
    
    // 重置状态
    resetState() {
      this.connectionStatus = 'disconnected';
      this.reconnectAttempts = 0;
      this.connectionError = null;
      this.rooms = [];
      this.currentRoomId = null;
      this.joinedRoomIds = [];
      this.messages = {};
      this.usersTyping = {};
      this.unreadMessagesByRoom = {};
      
      // 不再需要关闭WebSocket连接，由WebSocketManager统一管理
      console.log('[Chat] 聊天状态已重置');
    },
    
    // 發送聊天室加入通知
    sendJoinRoomNotification(roomId: number) {
      // 发送订阅消息，通知WebSocket服务器用户加入了此聊天室
      const message = {
        type: 'chat/join_room',
        room_id: roomId
      };
      
      console.log(`[Chat] 发送聊天室 ${roomId} 加入通知到WebSocket服务器`);
      webSocketManager.send(message);
    },
    
    // 重新訂閱所有已加入的聊天室
    resubscribeToRooms() {
      // 确保WebSocket已连接
      if (!webSocketManager.isConnected()) {
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
      
      // 確保消息數組已經初始化
      if (!this.messages[roomId]) {
        this.messages[roomId] = [];
        console.log(`[聊天] 為聊天室 ${roomId} 初始化消息數組`);
      }
      
      // 添加時間戳：如果消息沒有帶時間戳，添加當前時間
      const timestamp = data.timestamp || new Date().toISOString();
      
      // 處理頭像URL：確保頭像URL是完整的
      let avatarUrl = data.avatar_url || '';
      // 去除可能存在的時間戳參數，以便緩存可以生效
      if (avatarUrl.includes('?_t=')) {
        avatarUrl = avatarUrl.split('?_t=')[0];
      } else if (avatarUrl.includes('&_t=')) {
        avatarUrl = avatarUrl.split('&_t=')[0];
      }
      
      if (avatarUrl && !avatarUrl.startsWith('http')) {
        const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        avatarUrl = avatarUrl.startsWith('/') 
          ? `${apiBaseUrl}${avatarUrl}` 
          : `${apiBaseUrl}/${avatarUrl}`;
      }
      
      // 檢查是否已經存在相同ID的消息，避免重複添加
      const messageId = data.message_id || `temp-${Date.now()}`;
      console.log(`[聊天] 處理消息: ID=${messageId}, 聊天室=${roomId}, 內容=${data.content}`, data);
      
      const existingMessageIndex = this.messages[roomId].findIndex(msg => msg.id === messageId);
      
      // 如果消息已存在，更新它；否則添加新消息
      const message = {
        id: messageId,
        content: data.content,
        userId: data.user_id || data.userId, // 兼容兩種可能的屬性名
        username: data.username,
        avatar: avatarUrl,
        timestamp: timestamp,
        isSystem: false
      };
      
      if (existingMessageIndex !== -1) {
        // 更新現有消息
        this.messages[roomId][existingMessageIndex] = message;
        console.log(`[聊天] 更新聊天室 ${roomId} 中ID為 ${messageId} 的消息`);
      } else {
        // 添加新消息
        console.log(`[聊天] 添加新消息到聊天室 ${roomId}: ${JSON.stringify(message)}`);
        // 使用響應式API確保更新被檢測到
        this.messages[roomId].push(message);
        
        // 創建一個新的消息對象引用，強制Vue檢測變化
        this.messages = { ...this.messages };
        
        // 如果該用戶正在輸入中，收到消息後移除輸入狀態
        if (data.user_id && this.usersTyping[roomId] && this.usersTyping[roomId].has(data.user_id)) {
          this.usersTyping[roomId].delete(data.user_id);
        }
        
        // 如果消息屬於當前聊天室，滾動到底部
        if (roomId === this.currentRoomId) {
          console.log(`[聊天] 是當前聊天室 ${roomId} 的消息，滾動到底部`);
          this.scrollToBottom();
        }
        
        // 如果消息不是當前用戶發送的，且不是在當前瀏覽的聊天室中，增加未讀消息計數
        const authStore = useAuthStore();
        const currentUserId = authStore.user?.id;
        
        if (data.user_id !== currentUserId && roomId !== this.currentRoomId) {
          // 初始化該聊天室的未讀消息計數（如果不存在）
          if (typeof this.unreadMessagesByRoom[roomId] === 'undefined') {
            this.unreadMessagesByRoom[roomId] = 0;
          }
          
          // 增加未讀消息計數
          this.unreadMessagesByRoom[roomId]++;
          
          // 觸發未讀消息更新事件
          window.dispatchEvent(new CustomEvent('chat:unread-updated', {
            detail: { totalUnread: this.totalUnreadCount }
          }));
          
          // 更新rooms數組中的hasNewMessages標誌
          this.updateRoomNewMessageStatus(roomId, true);
        }
      }
      
      // 強制觸發UI更新
      window.dispatchEvent(new CustomEvent('chat:message-received', {
        detail: { messageId, roomId }
      }));
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
        const apiBaseUrl = getApiBaseUrl();
        // 改為獲取聊天室全部消息，移除分頁參數
        const response = await axios.get(`${apiBaseUrl}/api/v1/chatroom/messages/${roomId}`);
        
        console.log('API返回的消息格式:', JSON.stringify(response.data[0] || {}).substring(0, 300));
        
        if (response.data) {
          // 確保聊天室消息數組已初始化
          if (!this.messages[roomId]) {
            this.messages[roomId] = [];
          }
          
          // 清空並重置消息數組
          this.messages[roomId] = [];
          
          // 處理每條消息，根據API返回格式進行轉換
          response.data.forEach((msg: any) => {
            // 處理頭像URL
            let avatarUrl = '';
            if (msg.user && msg.user.avatar_url) {
              avatarUrl = msg.user.avatar_url;
              // 去除可能存在的時間戳參數，以便緩存可以生效
              if (avatarUrl.includes('?_t=')) {
                avatarUrl = avatarUrl.split('?_t=')[0];
              } else if (avatarUrl.includes('&_t=')) {
                avatarUrl = avatarUrl.split('&_t=')[0];
              }
              
              if (avatarUrl && !avatarUrl.startsWith('http')) {
                const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
                avatarUrl = avatarUrl.startsWith('/') 
                  ? `${apiBaseUrl}${avatarUrl}` 
                  : `${apiBaseUrl}/${avatarUrl}`;
              }
            }
            
            // 將API返回的消息格式轉換為前端使用的格式
            this.messages[roomId].push({
              id: msg.id,
              content: msg.content,
              userId: msg.user_id,
              username: msg.user ? msg.user.username : '未知用戶',
              avatar: avatarUrl,
              timestamp: msg.created_at,
              isSystem: !!msg.is_system
            });
          });
          
          console.log(`成功加載聊天室 ${roomId} 的消息，數量:`, response.data.length);
          
          // 進入聊天室時，清除未讀消息計數
          this.markRoomAsRead(roomId);
          
          // 在下次DOM更新後滾動到底部
          setTimeout(() => {
            this.scrollToBottom();
          }, 100);
        }
      } catch (error) {
        console.error(`加載聊天室 ${roomId} 的消息失敗:`, error);
      }
    },

    // 加载用户加入的聊天室列表
    async fetchUserRooms(retryCount = 0, maxRetries = 3) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.error('用戶未登錄，無法加載聊天室列表');
        return false;
      }
      
      // 檢查令牌有效性
      if (!authStore.token || !authStore.isAuthenticated) {
        console.error('認證令牌無效，無法加載聊天室列表');
        return false;
      }
      
      try {
        console.log(`[Chat] 開始載入聊天室列表 (嘗試 ${retryCount + 1}/${maxRetries + 1})`);
        const apiBaseUrl = getApiBaseUrl();
        const response = await axios.get(`${apiBaseUrl}/api/v1/chatroom/rooms`, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          },
          timeout: 10000 // 10秒超時
        });
        
        // 验证响应数据
        if (!Array.isArray(response.data)) {
          console.error('聊天室列表數據格式錯誤:', response.data);
          return false;
        }
        
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
          
        console.log(`[Chat] 已加載聊天室列表: ${this.rooms.length} 個聊天室，其中已加入 ${this.joinedRoomIds.length} 個`);
        
        // 通知UI聊天室列表已更新
        window.dispatchEvent(new CustomEvent('chat:rooms-updated', { 
          detail: { roomCount: this.rooms.length }
        }));
        
        return true;
      } catch (error) {
        // 詳細記錄錯誤信息
        if (axios.isAxiosError(error)) {
          const statusCode = error.response?.status;
          const errorData = error.response?.data;
          
          if (statusCode === 401 || statusCode === 403) {
            console.error('[Chat] 身份驗證失敗，無法加載聊天室列表:', errorData);
            // 可能需要重新登錄
            return false;
          } else if (statusCode === 429) {
            console.warn('[Chat] 請求過於頻繁，稍後再試:', errorData);
          } else if (statusCode === 500) {
            console.error('[Chat] 服務器錯誤，無法加載聊天室列表:', errorData);
          } else if (error.code === 'ECONNABORTED') {
            console.error('[Chat] 加載聊天室列表超時');
          } else {
            console.error('[Chat] 加載聊天室列表失敗:', error.message, errorData);
          }
        } else {
          console.error('[Chat] 加載聊天室列表失敗:', error);
        }
        
        // 重試機制
        if (retryCount < maxRetries) {
          const retryDelay = Math.pow(2, retryCount) * 1000; // 指數退避策略
          console.log(`[Chat] 將在 ${retryDelay/1000} 秒後重試加載聊天室列表...`);
          
          await new Promise(resolve => setTimeout(resolve, retryDelay));
          return this.fetchUserRooms(retryCount + 1, maxRetries);
        }
        
        return false;
      }
    },

    // 加入聊天室
    async joinRoom(roomId: number) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.error('用户未登錄，無法加入聊天室');
        return;
      }
      
      try {
        const apiBaseUrl = getApiBaseUrl();
        await axios.post(`${apiBaseUrl}/api/v1/chatroom/rooms/${roomId}/join`, {}, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        // 刷新用户的聊天室列表，確保獲取最新的聊天室信息
        await this.fetchUserRooms();
        
        // 更新已加入的聊天室列表
        if (!this.joinedRoomIds.includes(roomId)) {
          this.joinedRoomIds.push(roomId);
        }
        
        // 更新當前選中的聊天室
        this.currentRoomId = roomId;
        
        // 清空並重新初始化消息數組，確保每次加入聊天室時都會重新獲取最新消息
        this.messages[roomId] = [];
        console.log(`[Chat] 為聊天室 ${roomId} 重置消息數組`);
        
        // 加載聊天室消息
        try {
          await this.loadRoomMessages(roomId);
        } catch (error) {
          console.error(`加載聊天室 ${roomId} 的消息失敗:`, error);
          // 即使加載消息失敗，也能保證消息數組已初始化，可以接收新消息
        }
        
        // 發送聊天室加入通知給WebSocket服務器
        this.sendJoinRoomNotification(roomId);
        
        return true;
      } catch (error) {
        console.error('加入聊天室失敗:', error);
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