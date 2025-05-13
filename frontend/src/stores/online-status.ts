import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import router from '@/router'
import webSocketManager, { WebSocketType } from '@/services/webSocketService'

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

export const useOnlineStatusStore = defineStore('onlineStatus', {
  state: () => ({
    // WebSocket连接状态
    connectionStatus: 'disconnected' as 'connecting' | 'connected' | 'disconnected',
    reconnectAttempts: 0,
    heartbeatInterval: null as number | null,
    
    // 在线状态数据
    onlineUsers: {} as Record<string, boolean>, // 用户ID -> 在线状态
    lastUpdate: null as Date | null,
    
    // 统计数据
    totalOnline: 0,
  }),
  
  getters: {
    isConnected: (state) => state.connectionStatus === 'connected',
    
    // 检查指定用户是否在线
    isUserOnline: (state) => (userId: number | string) => {
      return !!state.onlineUsers[userId.toString()];
    },
    
    // 获取在线用户ID列表
    onlineUserIds: (state) => {
      return Object.entries(state.onlineUsers)
        .filter(([_, isOnline]) => isOnline)
        .map(([userId]) => userId);
    }
  },
  
  actions: {
    // 初始化在线状态管理
    initialize() {
      const authStore = useAuthStore();
      
      // 如果用户未登录，不初始化
      if (!authStore.isAuthenticated) {
        console.log('用户未登录，跳过在线状态系统初始化');
        return;
      }
      
      console.log('初始化在线状态管理系统...');
      
      // 註冊在線狀態事件監聽器，接收來自主 WebSocket 的在線狀態變更
      this.setupEventListeners();
      
      // 設置定期刷新在線狀態
      this.startPeriodicRefresh();
      
      console.log('在线状态管理系统初始化完成');
    },
    
    // 設置事件監聽器
    setupEventListeners() {
      // 監聽用戶狀態變化事件 (從主 WebSocket 轉發)
      window.addEventListener('online:user-status-changed', (event: CustomEvent) => {
        if (event.detail) {
          const { userId, isOnline } = event.detail;
          console.log(`[Online] 收到用戶狀態變化事件: 用戶 ${userId} 狀態變為 ${isOnline ? '在線' : '離線'}`);
          this.updateUserStatus(userId, isOnline);
        }
      });
      
      console.log('[Online] 事件監聽器設置完成');
    },
    
    // 处理WebSocket消息
    handleWebSocketMessage(event: MessageEvent) {
      try {
        const data = JSON.parse(event.data);
        console.debug('[Online] 收到WebSocket消息:', data);
        
        if (data.type === 'ping') {
          // 收到服务器ping，回复pong
          this.sendPong();
        } else if (data.type === 'pong') {
          // 心跳响应，忽略
        } else if (data.type === 'user_status') {
          // 用户状态变化
          this.updateUserStatus(data.user_id, data.is_online);
        } else if (data.type === 'status_connected') {
          // 连接成功消息
          console.log('在线状态系统连接成功');
        }
      } catch (error) {
        console.error('[Online] 处理WebSocket消息出错:', error);
      }
    },
    
    // 当WebSocket连接成功时的回调
    onWebSocketConnected() {
      console.log('[Online] 在线状态WebSocket连接已建立');
      this.connectionStatus = 'connected';
      this.reconnectAttempts = 0;
      
      // 立即获取最新在线状态
      this.fetchOnlineStatus();
      
      // 触发连接成功事件
      window.dispatchEvent(new Event('online:websocket-connected'));
    },
    
    // 当WebSocket连接断开时的回调
    onWebSocketDisconnected() {
      console.log('[Online] 在线状态WebSocket连接已断开');
      this.connectionStatus = 'disconnected';
      
      // 触发断开连接事件
      window.dispatchEvent(new Event('online:websocket-disconnected'));
    },
    
    // 发送pong响应
    sendPong() {
      webSocketManager.send(WebSocketType.ONLINE_STATUS, { type: 'pong' });
    },
    
    // 发送ping请求
    sendPing() {
      webSocketManager.send(WebSocketType.ONLINE_STATUS, { type: 'ping' });
    },
    
    // 兼容方法：提供与旧版API兼容的WebSocket连接方法
    // 此方法仅用于兼容现有代码，不应在新代码中使用
    connectWebSocket() {
      console.warn('[Online] connectWebSocket方法已弃用，WebSocket连接现在由WebSocketManager统一管理');
      return webSocketManager.connect(WebSocketType.ONLINE_STATUS);
    },
    
    // 兼容方法：提供与旧版API兼容的WebSocket关闭方法
    // 此方法仅用于兼容现有代码，不应在新代码中使用
    closeWebSocket() {
      console.warn('[Online] closeWebSocket方法已弃用，WebSocket连接现在由WebSocketManager统一管理');
      return webSocketManager.disconnect(WebSocketType.ONLINE_STATUS);
    },
    
    // 开始定期刷新在线状态
    startPeriodicRefresh() {
      // 每2分钟刷新一次在线状态
      setInterval(() => {
        this.fetchOnlineStatus();
      }, 120000); // 2分钟
    },
    
    // 获取在线用户状态
    async fetchOnlineStatus(userIds?: number[]) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        return;
      }
      
      try {
        const apiBaseUrl = getApiBaseUrl();
        let url = `${apiBaseUrl}/api/v1/online/users/online`;
        
        // 如果提供了特定用户ID，使用查询参数
        if (userIds && userIds.length > 0) {
          const params = userIds.map(id => `user_ids=${id}`).join('&');
          url = `${url}?${params}`;
        }
        
        const response = await axios.get(url, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        if (response.data) {
          // 更新在线用户状态
          this.onlineUsers = {
            ...this.onlineUsers,
            ...response.data.online_status
          };
          
          this.totalOnline = response.data.total_online;
          this.lastUpdate = new Date();
          
          // 触发在线状态更新事件
          window.dispatchEvent(new CustomEvent('online:status-updated', {
            detail: { onlineUsers: this.onlineUsers }
          }));
        }
      } catch (error) {
        console.error('获取在线用户状态失败:', error);
      }
    },
    
    // 获取特定聊天室的在线用户
    async fetchRoomOnlineUsers(roomId: number) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        return [];
      }
      
      try {
        const apiBaseUrl = getApiBaseUrl();
        const response = await axios.get(`${apiBaseUrl}/api/v1/online/rooms/${roomId}/online`, {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        if (response.data && response.data.online_users) {
          // 返回在线用户列表
          return response.data.online_users;
        }
        return [];
      } catch (error) {
        console.error(`获取聊天室 ${roomId} 的在线用户失败:`, error);
        return [];
      }
    },
    
    // 更新单个用户的在线状态
    updateUserStatus(userId: number | string, isOnline: boolean) {
      const id = userId.toString();
      
      // 如果状态有变化才更新
      if (this.onlineUsers[id] !== isOnline) {
        this.onlineUsers[id] = isOnline;
        
        // 触发用户状态变化事件
        window.dispatchEvent(new CustomEvent('online:user-status-changed', {
          detail: { userId: id, isOnline: isOnline }
        }));
      }
    },
    
    // 重置状态
    resetState() {
      // 不再需要关闭WebSocket连接，由WebSocketManager统一管理
      
      // 清空状态数据
      this.onlineUsers = {};
      this.totalOnline = 0;
      this.lastUpdate = null;
      this.connectionStatus = 'disconnected';
      this.reconnectAttempts = 0;
      
      // 清除心跳检测
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
    }
  }
}); 