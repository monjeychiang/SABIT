import { defineStore } from 'pinia'
import { ref, reactive, computed } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import router from '@/router'

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
    socket: null as WebSocket | null,
    connectionStatus: 'disconnected' as 'connecting' | 'connected' | 'disconnected',
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectInterval: 3000, // 3秒
    reconnectTimeout: null as number | null,
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
      
      // 连接WebSocket
      this.connectWebSocket();
      
      // 设置定期刷新在线状态
      this.startPeriodicRefresh();
      
      console.log('在线状态管理系统初始化完成');
    },
    
    // 连接WebSocket
    connectWebSocket() {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated || !authStore.token) {
        console.log('未登录，不能连接在线状态WebSocket');
        return;
      }
      
      // 如果已连接，先关闭
      this.closeWebSocket();
      
      try {
        const wsBaseUrl = getWsBaseUrl();
        const wsUrl = `${wsBaseUrl}/api/v1/online/ws/status/${authStore.token}`;
        
        console.log(`正在连接在线状态WebSocket: ${wsUrl.replace(/\/status\/[^/]+/, '/status/***')}`);
        
        this.connectionStatus = 'connecting';
        this.socket = new WebSocket(wsUrl);
        
        // 连接打开事件
        this.socket.onopen = () => {
          console.log('在线状态WebSocket连接已建立');
          this.connectionStatus = 'connected';
          this.reconnectAttempts = 0;
          
          // 设置心跳检测
          this.startHeartbeat();
          
          // 立即获取最新在线状态
          this.fetchOnlineStatus();
          
          // 触发连接成功事件
          window.dispatchEvent(new Event('online:websocket-connected'));
        };
        
        // 连接关闭事件
        this.socket.onclose = (event) => {
          this.connectionStatus = 'disconnected';
          
          // 触发断开连接事件
          window.dispatchEvent(new Event('online:websocket-disconnected'));
          
          // 清除心跳检测
          if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
          }
          
          console.log(`在线状态WebSocket连接已关闭，代码: ${event.code}，原因: ${event.reason || '未提供原因'}`);
          
          // 检查是否需要重连
          const authStore = useAuthStore();
          if (!authStore.isAuthenticated) {
            console.log('用户已登出，不尝试重连');
            return;
          }
          
          // 只有在非正常关闭且未超过最大重连次数时尝试重连
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          }
        };
        
        // 连接错误事件
        this.socket.onerror = (error) => {
          console.error('在线状态WebSocket连接出错:', error);
        };
        
        // 收到消息事件
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'pong') {
              // 心跳响应，忽略
            } else if (data.type === 'user_status') {
              // 用户状态变化
              this.updateUserStatus(data.user_id, data.is_online);
            } else if (data.type === 'status_connected') {
              // 连接成功消息
              console.log('在线状态系统连接成功');
            }
          } catch (error) {
            console.error('处理在线状态WebSocket消息出错:', error);
          }
        };
      } catch (error) {
        console.error('创建在线状态WebSocket连接失败:', error);
        
        // 如果创建失败，尝试重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        }
      }
    },
    
    // 尝试重连
    attemptReconnect() {
      this.reconnectAttempts++;
      
      // 清理之前的重连定时器
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
      
      // 使用指数退避策略
      const delay = this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);
      
      console.log(`尝试重新连接在线状态WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...将在 ${delay/1000} 秒后尝试`);
      
      this.reconnectTimeout = window.setTimeout(() => {
        // 检查登录状态再尝试重连
        const authStore = useAuthStore();
        if (authStore.isAuthenticated && authStore.token) {
          console.log(`正在执行第 ${this.reconnectAttempts} 次在线状态重连尝试...`);
          this.connectWebSocket();
        } else {
          console.log('用户已登出，取消重连');
        }
      }, delay);
    },
    
    // 关闭WebSocket连接
    closeWebSocket() {
      // 清除心跳检测
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      // 清除重连定时器
      if (this.reconnectTimeout) {
        clearTimeout(this.reconnectTimeout);
        this.reconnectTimeout = null;
      }
      
      // 关闭WebSocket
      if (this.socket) {
        try {
          this.socket.onopen = null;
          this.socket.onmessage = null;
          this.socket.onerror = null;
          this.socket.onclose = null;
          this.socket.close();
        } catch (e) {
          console.error('关闭在线状态WebSocket连接失败:', e);
        }
        this.socket = null;
      }
      
      this.connectionStatus = 'disconnected';
    },
    
    // 启动心跳检测
    startHeartbeat() {
      // 清除现有心跳
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
      }
      
      // 每30秒发送一次心跳
      this.heartbeatInterval = window.setInterval(() => {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
          // 发送心跳
          this.socket.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30000); // 30秒
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
      // 关闭WebSocket
      this.closeWebSocket();
      
      // 清空状态数据
      this.onlineUsers = {};
      this.totalOnline = 0;
      this.lastUpdate = null;
      this.connectionStatus = 'disconnected';
      this.reconnectAttempts = 0;
    }
  }
}); 