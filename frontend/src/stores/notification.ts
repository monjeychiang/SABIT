import { defineStore } from 'pinia'
import axios from 'axios'
import { useAuthStore } from './auth'

// 通知类型枚举
export const NotificationType = {
  INFO: 'info',       // 一般信息
  SUCCESS: 'success', // 成功信息
  WARNING: 'warning', // 警告信息
  ERROR: 'error',     // 错误信息
  SYSTEM: 'system'    // 系统通知
} as const;

// 通知类型的类型定义
export type NotificationTypeValue = typeof NotificationType[keyof typeof NotificationType];

// 通知样式接口
export interface NotificationStyle {
  icon: string;
  color: string;
  bgColor: string;
}

// 通知对象接口
export interface Notification {
  id: number | string;
  title: string;
  message: string;
  notification_type: NotificationTypeValue;
  is_read: boolean;
  created_at: string;
  updated_at?: string;
  is_global?: boolean;
  link?: string;
  user_id?: number;
  sender_id?: number;
  sender_name?: string;
  data?: Record<string, any>;
}

// 通知类型对应的前端样式配置
export const NotificationStyles: Record<NotificationTypeValue, NotificationStyle> = {
  [NotificationType.INFO]: {
    icon: 'info-circle',
    color: '#1677ff',
    bgColor: '#e6f7ff'
  },
  [NotificationType.SUCCESS]: {
    icon: 'check-circle',
    color: '#52c41a',
    bgColor: '#f6ffed'
  },
  [NotificationType.WARNING]: {
    icon: 'warning',
    color: '#faad14',
    bgColor: '#fffbe6'
  },
  [NotificationType.ERROR]: {
    icon: 'close-circle',
    color: '#ff4d4f',
    bgColor: '#fff2f0'
  },
  [NotificationType.SYSTEM]: {
    icon: 'bell',
    color: '#722ed1',
    bgColor: '#f9f0ff'
  }
};

// 获取API基础URL，默认为本地开发环境
const getApiBaseUrl = (): string => {
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
};

// 本地存储相关常量
const LOCAL_STORAGE_NOTIFICATIONS_KEY = 'app_notifications';
const LOCAL_STORAGE_NOTIFICATIONS_MAX = 30; // 最多保存多少条通知
const LOCAL_STORAGE_NOTIFICATIONS_EXPIRY = 7 * 24 * 60 * 60 * 1000; // 7天后过期

// 获取用户特定的通知存储键名
const getUserNotificationsKey = (userId?: number | null, username?: string | null): string => {
  // 优先使用用户ID，因为更稳定；如果没有ID则使用用户名
  const userIdentifier = userId || username || 'anonymous';
  return `${LOCAL_STORAGE_NOTIFICATIONS_KEY}_${userIdentifier}`;
};

// 存储在localStorage的通知数据接口
interface StoredNotificationData {
  notifications: Notification[];
  timestamp: number;
  userId?: number | null;
  username?: string | null;
}

// 通知Store的状态接口
interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  loading: boolean;
  error: string | null;
  lastFetchTime: Date | null;
  filterType: NotificationTypeValue | null;
  websocket: WebSocket | null;
  websocketConnected: boolean;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  reconnectInterval: number;
  reconnectPauseTime: number;
  reconnectPaused: boolean;
  heartbeatTimeout: number | null;
  newNotificationCallback: ((notification: Notification) => void) | null;
  refreshTimer: number | null;
  heartbeatInterval: number | null;
  useLocalStorage: boolean;
}

export const useNotificationStore = defineStore('notification', {
  state: (): NotificationState => ({
    notifications: [],
    unreadCount: 0,
    loading: false,
    error: null,
    lastFetchTime: null,
    filterType: null, // 添加通知类型过滤状态
    websocket: null,
    websocketConnected: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectInterval: 3000, // 重连间隔(毫秒)
    reconnectPauseTime: 60000, // 达到最大重试次数后的暂停时间(毫秒)
    reconnectPaused: false, // 是否处于重连暂停状态
    heartbeatTimeout: null,
    newNotificationCallback: null, // 新通知回调函数
    refreshTimer: null,
    heartbeatInterval: null,
    useLocalStorage: true // 是否使用本地存储
  }),

  getters: {
    hasUnread: (state): boolean => state.unreadCount > 0,
    
    sortedNotifications: (state): Notification[] => {
      return [...state.notifications].sort((a, b) => {
        const dateA = new Date(a.created_at);
        const dateB = new Date(b.created_at);
        return dateB.getTime() - dateA.getTime();
      });
    },
    
    // 根据类型过滤的通知
    filteredNotifications: (state): Notification[] => {
      if (!state.filterType) {
        // 直接使用排序逻辑而不是引用getter
        return [...state.notifications].sort((a, b) => {
          const dateA = new Date(a.created_at);
          const dateB = new Date(b.created_at);
          return dateB.getTime() - dateA.getTime();
        });
      }
      
      // 先过滤再排序
      return state.notifications
        .filter((n: Notification) => n.notification_type === state.filterType)
        .sort((a, b) => {
          const dateA = new Date(a.created_at);
          const dateB = new Date(b.created_at);
          return dateB.getTime() - dateA.getTime();
        });
    },
    
    // 按类型统计通知数量
    notificationCountsByType: (state): Record<NotificationTypeValue, number> => {
      const counts = {
        [NotificationType.INFO]: 0,
        [NotificationType.SUCCESS]: 0,
        [NotificationType.WARNING]: 0,
        [NotificationType.ERROR]: 0,
        [NotificationType.SYSTEM]: 0
      };
      
      state.notifications.forEach(notification => {
        const type = notification.notification_type || NotificationType.INFO;
        counts[type] = (counts[type] || 0) + 1;
      });
      
      return counts;
    },
    
    // 是否连接到WebSocket
    isWebSocketConnected: (state): boolean => state.websocketConnected
  },

  actions: {
    // 连接到通知WebSocket
    connectWebSocket(): void {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated || !authStore.token) {
        console.log('未登录，不能连接WebSocket');
        return;
      }

      // 如果已经连接，先关闭现有连接
      this.closeWebSocket();

      try {
        const apiBaseUrl = getApiBaseUrl();
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsBaseUrl = apiBaseUrl.replace(/^http(s)?:/, wsProtocol);
        
        // 获取上次活动时间
        const lastActivityTime = localStorage.getItem('lastLogoutTime');
        
        // 创建WebSocket连接，包括认证token和上次活动时间
        let wsUrl = `${wsBaseUrl}/api/v1/notifications/ws?token=${authStore.token}`;
        
        // 添加上次活动时间参数（如果有）
        if (lastActivityTime) {
          const lastActivityDate = new Date(parseInt(lastActivityTime));
          if (!isNaN(lastActivityDate.getTime())) {
            wsUrl += `&last_activity=${lastActivityDate.toISOString()}`;
          }
        }
        
        console.log(`正在连接通知WebSocket: ${wsUrl.replace(/token=[^&]+/, 'token=***')}`);
        
        this.websocket = new WebSocket(wsUrl);

        // 连接打开事件
        this.websocket.onopen = (): void => {
          console.log('通知WebSocket连接已建立');
          this.websocketConnected = true;
          this.reconnectAttempts = 0;
          this.error = null;
          
          // 连接建立后清除上次活动时间
          if (lastActivityTime) {
            localStorage.removeItem('lastLogoutTime');
          }
          
          // 设置心跳检测
          this.startHeartbeat();
          
          // 添加调试信息
          console.log('通知WebSocket连接状态:', {
            连接状态: this.websocketConnected ? '已连接' : '未连接',
            重连次数: this.reconnectAttempts,
            用户ID: authStore.user?.id
          });
          
          // 触发连接成功事件，通知UI更新
          window.dispatchEvent(new Event('notification:websocket-connected'));
        };

        // 连接关闭事件
        this.websocket.onclose = (event: CloseEvent): void => {
          this.websocketConnected = false;
          
          // 触发断开连接事件，通知UI更新
          window.dispatchEvent(new Event('notification:websocket-disconnected'));
          
          // 清除心跳检测
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
          }
          
          console.log(`通知WebSocket连接已关闭，代码: ${event.code}，原因: ${event.reason || '未提供原因'}`);
          
          // 记录常见关闭代码的含义，帮助诊断问题
          if (event.code === 1000) {
            console.log('WebSocket正常关闭');
            // 正常关闭，不进行重连
            return;
          } else if (event.code === 1001) {
            console.log('WebSocket关闭: 终端离开');
          } else if (event.code === 1005) {
            console.log('WebSocket关闭: 无状态码接收');
          } else if (event.code === 1006) {
            console.log('WebSocket关闭: 异常关闭，可能是网络问题或服务器重启');
          } else if (event.code === 1008) {
            console.log('WebSocket关闭: 违反策略，可能是认证问题');
          } else if (event.code === 1011) {
            console.log('WebSocket关闭: 服务器内部错误');
          }
          
          // 认证错误不尝试重连
          if (event.code === 1008) {
            console.log('认证问题，不进行重连');
            // 可能需要刷新令牌或重新登录
            console.log('可能需要重新登录或刷新令牌');
            return;
          }
          
          // 只有在非正常关闭且未超过最大重连次数时尝试重连
          if (event.code !== 1000 && event.code !== 1001 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.attemptReconnect();
          } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('已达到最大重连尝试次数，停止重连');
            // 达到最大重试次数后，尝试使用HTTP轮询作为备用
            this.fetchNotifications();
            
            // 5分钟后尝试重新连接
            setTimeout(() => {
              console.log('重置重连计数器，再次尝试连接');
              this.reconnectAttempts = 0;
              this.connectWebSocket();
            }, 5 * 60 * 1000);
          }
        };

        // 连接错误事件
        this.websocket.onerror = (error: Event): void => {
          console.error('通知WebSocket连接出错:', error);
          this.error = '通知WebSocket连接出错';
          
          // 在错误发生时不立即尝试重连，让onclose事件处理重连逻辑
          // 因为onerror事件后通常会触发onclose事件
        };

        // 收到消息事件
        this.websocket.onmessage = (event: MessageEvent): void => {
          // 接收消息时重置心跳检测
          if (this.heartbeatTimeout) {
            clearTimeout(this.heartbeatTimeout);
          }
          this.startHeartbeat();
          
          // 处理消息
          this.handleWebSocketMessage(event);
        };
      } catch (error) {
        console.error('创建通知WebSocket连接失败:', error);
        this.error = '创建通知WebSocket连接失败';
        
        // 如果创建WebSocket对象失败，直接尝试重连
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        }
      }
    },

    // 尝试重新连接WebSocket
    attemptReconnect(): void {
      this.reconnectAttempts++;
      
      // 确保不超过最大重连次数
      if (this.reconnectAttempts > this.maxReconnectAttempts) {
        console.log('已达到最大重连尝试次数，停止重连');
        return;
      }
      
      // 使用指数退避策略，增加重连间隔
      const delay = this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);
      
      console.log(`尝试重新连接WebSocket (${this.reconnectAttempts}/${this.maxReconnectAttempts})...将在 ${delay/1000} 秒后尝试`);
      
      setTimeout(() => {
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
    closeWebSocket(): void {
      // 清除所有心跳相关定时器
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // 关闭WebSocket连接
      if (this.websocket) {
        try {
          // 先移除所有事件监听器
          this.websocket.onopen = null;
          this.websocket.onmessage = null;
          this.websocket.onerror = null;
          this.websocket.onclose = null;
          
          // 如果连接仍处于打开状态，则关闭连接
          if (this.websocket.readyState === WebSocket.OPEN || 
              this.websocket.readyState === WebSocket.CONNECTING) {
            this.websocket.close();
          }
        } catch (e) {
          console.error('关闭WebSocket连接失败:', e);
        }
        this.websocket = null;
      }
      
      this.websocketConnected = false;
    },

    // 处理WebSocket收到的消息
    handleWebSocketMessage(event: MessageEvent): void {
      try {
        const data = JSON.parse(event.data);
        console.debug('收到WebSocket消息:', data);

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

          case 'notification':
            // 添加详细日志
            console.log('收到通知消息:', data);
            
            // 检查消息格式，兼容两种可能的数据结构
            if (data.data) {
              // 将后端的read属性映射为is_read
              const notification = { ...data.data, is_read: data.data.read || false };
              console.log('处理data.data格式的通知:', notification);
              this.handleNewNotification(notification);
            } else if (data.notification) {
              const notification = { ...data.notification, is_read: data.notification.read || false };
              console.log('处理data.notification格式的通知:', notification);
              this.handleNewNotification(notification);
            } else {
              console.error('收到的通知消息格式不正确:', data);
            }
            break;
            
          case 'error':
            // 错误消息
            console.error('通知WebSocket错误:', data.message);
            this.error = data.message || '通知服务发生错误';
            break;
            
          default:
            console.log('收到未知类型的WebSocket消息:', data);
        }
      } catch (error) {
        console.error('处理WebSocket消息错误:', error);
      }
    },

    // 处理新通知
    handleNewNotification(notification: Notification): void {
      // 如果不存在或已经存在相同ID的通知，则不处理
      if (!notification || this.notifications.some(n => n.id === notification.id)) {
        return;
      }
      
      // 添加通知到列表
      this.addNotification(notification);
      
      // 更新未读计数
      this.updateUnreadCount();
      
      // 显示桌面通知（如果支持）
      this.showDesktopNotification(notification);
      
      // 如果设置了新通知回调函数，则调用
      if (this.newNotificationCallback) {
        try {
          this.newNotificationCallback(notification);
        } catch (error) {
          console.error('调用新通知回调函数失败:', error);
        }
      }
    },

    // 发送pong响应
    sendPong(): void {
      if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) return;
      
      try {
        this.websocket.send(JSON.stringify({ type: 'pong' }));
      } catch (error) {
        console.error('发送pong响应失败:', error);
      }
    },

    // 发送ping请求
    sendPing(): void {
      if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) return;
      
      try {
        this.websocket.send(JSON.stringify({ type: 'ping' }));
        console.debug('发送ping请求');
      } catch (error) {
        console.error('发送ping请求失败:', error);
      }
    },

    // 设置心跳检测
    startHeartbeat(): void {
      // 清除现有的心跳计时器
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
      }
      
      // 每30秒发送一次ping
      this.heartbeatInterval = window.setInterval(() => {
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) return;
        
        try {
          // 发送ping
          this.websocket.send(JSON.stringify({ type: 'ping' }));
          
          // 设置10秒超时等待pong响应
          this.heartbeatTimeout = window.setTimeout(() => {
            console.warn('心跳检测失败: 未收到pong响应');
            // 关闭连接并触发重连
            this.closeWebSocket();
            this.attemptReconnect();
          }, 10000);
        } catch (error) {
          console.error('发送ping心跳失败:', error);
          this.closeWebSocket();
          this.attemptReconnect();
        }
      }, 30000);
    },

    // 显示桌面通知
    showDesktopNotification(notification: Notification): void {
      // 如果浏览器不支持通知，直接返回
      if (!('Notification' in window)) {
        return;
      }
      
      // 如果已经获得了通知权限，直接显示通知
      if (Notification.permission === 'granted') {
        try {
          // 创建通知
          const title = notification.title || '新通知';
          const options = {
            body: notification.message,
            icon: '/favicon.ico', // 使用应用的图标
            tag: `notification-${notification.id}`, // 使用通知ID作为标签
            data: notification
          };
          
          const notificationObj = new Notification(title, options);
          
          // 点击通知事件
          notificationObj.onclick = function() {
            // 如果通知有链接，点击时跳转到该链接
            if (notification.link) {
              window.open(notification.link, '_blank');
            }
            // 聚焦窗口
            window.focus();
            // 关闭通知
            this.close();
          };
          
          // 5秒后自动关闭通知
          setTimeout(() => {
            notificationObj.close();
          }, 5000);
        } catch (error) {
          console.error('显示桌面通知失败:', error);
        }
      } 
      // 如果还没有请求通知权限，请求权限
      else if (Notification.permission !== 'denied') {
        this.requestNotificationPermission();
      }
    },
    
    // 请求通知权限
    requestNotificationPermission(): void {
      if (!('Notification' in window)) {
        return;
      }
      
      Notification.requestPermission().then((permission) => {
        if (permission === 'granted') {
          console.log('已获得通知权限');
        }
      }).catch((error) => {
        console.error('请求通知权限失败:', error);
      });
    },
    
    // 设置新通知回调函数
    setNewNotificationCallback(callback: ((notification: Notification) => void) | null): void {
      this.newNotificationCallback = callback;
    },
    
    // 从服务器获取通知
    async fetchNotifications(type: NotificationTypeValue | null = null, since: Date | null = null): Promise<void> {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.log('用户未登录，不能获取通知');
        return;
      }
      
      // 如果正在加载，不重复请求
      if (this.loading) {
        return;
      }
      
      this.loading = true;
      this.error = null;
      
      try {
        // 构建查询参数
        const params: Record<string, any> = {};
        
        if (type) {
          params.type = type;
        }
        
        if (since) {
          params.since = since.toISOString();
        } else if (this.lastFetchTime) {
          // 如果没有指定since参数，但有上次获取时间，则使用上次获取时间
          params.since = this.lastFetchTime.toISOString();
        }
        
        const apiBaseUrl = getApiBaseUrl();
        const response = await axios.get(`${apiBaseUrl}/api/v1/notifications`, {
          params,
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        // 更新最后获取时间
        this.lastFetchTime = new Date();
        
        // 处理新通知
        if (response.data.notifications && Array.isArray(response.data.notifications)) {
          this.mergeNotifications(response.data.notifications);
        }
        
        // 保存到本地存储
        if (this.useLocalStorage) {
          this.saveNotificationsToLocalStorage();
        }
        
        // 更新未读计数
        this.updateUnreadCount();
        
        return response.data;
      } catch (error) {
        console.error('获取通知失败:', error);
        if (error instanceof Error) {
          this.error = error.message;
        } else {
          this.error = '获取通知失败';
        }
        throw error;
      } finally {
        this.loading = false;
      }
    },
    
    // 获取自上次登出后的错过通知 (添加缺失的方法)
    async fetchMissedNotifications(lastLogoutDate: Date): Promise<void> {
      console.log(`获取自 ${lastLogoutDate.toISOString()} 以来的错过通知`);
      return this.fetchNotifications(null, lastLogoutDate);
    },
    
    // 合并新通知到现有列表
    mergeNotifications(newNotifications: Notification[]): void {
      if (!newNotifications || !Array.isArray(newNotifications)) {
        return;
      }
      
      // 合并通知，避免重复
      newNotifications.forEach(notification => {
        // 如果通知已存在，不再添加
        if (!this.notifications.some(n => n.id === notification.id)) {
          this.notifications.push(notification);
        }
      });
      
      // 限制通知数量，避免过多
      if (this.notifications.length > LOCAL_STORAGE_NOTIFICATIONS_MAX) {
        // 按时间排序，保留最新的通知
        const sortedNotifications = [...this.notifications].sort((a, b) => {
          const dateA = new Date(a.created_at);
          const dateB = new Date(b.created_at);
          return dateB.getTime() - dateA.getTime();
        });
        this.notifications = sortedNotifications.slice(0, LOCAL_STORAGE_NOTIFICATIONS_MAX);
      }
    },
    
    // 标记通知为已读
    async markAsRead(notificationId: number | string): Promise<void> {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) {
        console.log('用户未登录，不能标记通知');
        return;
      }
      
      // 尝试在本地标记通知为已读
      const notification = this.notifications.find(n => n.id === notificationId);
      if (notification) {
        notification.is_read = true;
        
        // 更新未读计数
        this.updateUnreadCount();
        
        // 保存到本地存储
        if (this.useLocalStorage) {
          this.saveNotificationsToLocalStorage();
        }
        
        console.log(`已在本地将通知(ID:${notificationId})标记为已读，未读通知数量:${this.unreadCount}`);
      }
      
      // 不再与后端通信，所有已读状态只在本地处理
    },
    
    // 添加标记所有通知为已读的方法
    async markAllAsRead(): Promise<void> {
      if (this.notifications.length === 0) return;
      
      // 在本地标记所有通知为已读
      this.notifications.forEach(notification => {
        notification.is_read = true;
      });
      
      // 更新未读计数
      this.updateUnreadCount();
      
      // 保存到本地存储
      if (this.useLocalStorage) {
        this.saveNotificationsToLocalStorage();
      }
      
      console.log(`已在本地将全部${this.notifications.length}条通知标记为已读`);
      
      // 不再需要与服务器通信
    },
    
    // 添加清除所有通知的方法
    clearAllNotifications(): void {
      // 直接清空通知数组
      this.notifications = [];
      
      // 更新未读计数
      this.updateUnreadCount();
      
      // 从本地存储中完全删除通知数据
      if (this.useLocalStorage) {
        try {
          // 获取当前用户的存储键名
          const authStore = useAuthStore();
          const storageKey = getUserNotificationsKey(authStore.user?.id, authStore.user?.username);
          
          // 删除本地存储条目
          localStorage.removeItem(storageKey);
          console.log(`已从本地存储中完全删除通知数据 (键: ${storageKey})`);
        } catch (error) {
          console.error('从本地存储删除通知数据失败:', error);
        }
      }
      
      console.log('已在本地清除所有通知');
    },
    
    // 更新未读通知计数
    updateUnreadCount(): void {
      this.unreadCount = this.notifications.filter(n => !n.is_read).length;
    },
    
    // 添加通知到列表
    addNotification(notification: Notification): void {
      // 如果通知已存在，不再添加
      if (this.notifications.some(n => n.id === notification.id)) {
        return;
      }
      
      // 添加通知
      this.notifications.push(notification);
      
      // 限制通知数量
      if (this.notifications.length > LOCAL_STORAGE_NOTIFICATIONS_MAX) {
        // 按时间排序，保留最新的通知
        const sortedNotifications = [...this.notifications].sort((a, b) => {
          const dateA = new Date(a.created_at);
          const dateB = new Date(b.created_at);
          return dateB.getTime() - dateA.getTime();
        });
        this.notifications = sortedNotifications.slice(0, LOCAL_STORAGE_NOTIFICATIONS_MAX);
      }
      
      // 保存到本地存储
      if (this.useLocalStorage) {
        this.saveNotificationsToLocalStorage();
      }
    },
    
    // 保存通知到本地存储
    saveNotificationsToLocalStorage(): void {
      try {
        // 如果未登录或不使用本地存储，不保存
        const authStore = useAuthStore();
        if (!authStore.isAuthenticated || !this.useLocalStorage) {
          return;
        }
        
        // 准备要保存的数据
        const storageData: StoredNotificationData = {
          notifications: this.notifications,
          timestamp: Date.now(),
          userId: authStore.user?.id,
          username: authStore.user?.username
        };
        
        // 获取用户特定的存储键名
        const storageKey = getUserNotificationsKey(authStore.user?.id, authStore.user?.username);
        
        // 保存到本地存储
        localStorage.setItem(storageKey, JSON.stringify(storageData));
      } catch (error) {
        console.error('保存通知到本地存储失败:', error);
      }
    },
    
    // 从本地存储加载通知
    loadNotificationsFromLocalStorage(): void {
      try {
        // 如果未登录或不使用本地存储，不加载
        const authStore = useAuthStore();
        if (!authStore.isAuthenticated || !this.useLocalStorage) {
          return;
        }
        
        // 获取用户特定的存储键名
        const storageKey = getUserNotificationsKey(authStore.user?.id, authStore.user?.username);
        
        // 从本地存储中获取数据
        const storageItem = localStorage.getItem(storageKey);
        if (!storageItem) {
          return;
        }
        
        // 解析数据
        const storageData = JSON.parse(storageItem) as StoredNotificationData;
        
        // 检查数据是否过期
        const now = Date.now();
        if (now - storageData.timestamp > LOCAL_STORAGE_NOTIFICATIONS_EXPIRY) {
          // 数据已过期，删除
          localStorage.removeItem(storageKey);
          return;
        }
        
        // 检查用户ID是否匹配
        if (storageData.userId && authStore.user?.id && storageData.userId !== authStore.user.id) {
          // 用户ID不匹配，不加载
          return;
        }
        
        // 加载通知到状态
        if (storageData.notifications && Array.isArray(storageData.notifications)) {
          this.notifications = storageData.notifications;
          this.updateUnreadCount();
        }
      } catch (error) {
        console.error('从本地存储加载通知失败:', error);
      }
    },
    
    // 初始化通知系统
    initialize(): void {
      // 加载本地存储的通知
      if (this.useLocalStorage) {
        this.loadNotificationsFromLocalStorage();
      }
      
      // 请求桌面通知权限
      this.requestNotificationPermission();
      
      // 连接到WebSocket
      this.connectWebSocket();
      
      // 设置周期性刷新
      this.startPeriodicRefresh();
      
      // 如果有记录的最后登出时间，加载错过的通知
      const lastLogoutTime = localStorage.getItem('lastLogoutTime');
      if (lastLogoutTime) {
        const lastLogoutDate = new Date(parseInt(lastLogoutTime));
        if (!isNaN(lastLogoutDate.getTime())) {
          this.fetchNotifications(null, lastLogoutDate);
        }
      }
    },
    
    // 设置类型过滤器
    setTypeFilter(type: NotificationTypeValue): void {
      this.filterType = type;
    },
    
    // 清除类型过滤器
    clearTypeFilter(): void {
      this.filterType = null;
    },
    
    // 设置周期性刷新通知
    startPeriodicRefresh(): void {
      // 清除现有的定时器
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
      }
      
      // 每5分钟刷新一次通知
      this.refreshTimer = window.setInterval(() => {
        // 只有在WebSocket未连接时才通过HTTP刷新
        if (!this.websocketConnected) {
          this.fetchNotifications();
        }
      }, 5 * 60 * 1000);
    },
    
    // 重置状态
    resetState(): void {
      // 关闭WebSocket连接
      this.closeWebSocket();
      
      // 清除定时器
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
      
      if (this.heartbeatInterval) {
        clearInterval(this.heartbeatInterval);
        this.heartbeatInterval = null;
      }
      
      if (this.heartbeatTimeout) {
        clearTimeout(this.heartbeatTimeout);
        this.heartbeatTimeout = null;
      }
      
      // 重置状态
      this.notifications = [];
      this.unreadCount = 0;
      this.loading = false;
      this.error = null;
      this.lastFetchTime = null;
      this.filterType = null;
      this.websocketConnected = false;
      this.reconnectAttempts = 0;
      this.newNotificationCallback = null;
    },

    // 发送登录成功通知
    sendLoginSuccessNotification(username?: string): void {
      try {
        const greeting = username ? `欢迎回来，${username}！` : '欢迎回来！';
        
        // 创建通知对象
        const notification: Notification = {
          id: Date.now(), // 使用时间戳作为临时ID
          title: '登录成功',
          message: `${greeting} 您已成功登录系统。`,
          notification_type: NotificationType.SUCCESS,
          is_read: false,
          created_at: new Date().toISOString()
        };
        
        // 添加到通知列表
        this.addNotification(notification);
        
        // 确保手动再次更新未读计数，并放在添加通知之后
        this.unreadCount = this.notifications.filter(n => !n.is_read).length;
        
        // 立即保存到本地存储，确保数据持久化
        if (this.useLocalStorage) {
          this.saveNotificationsToLocalStorage();
        }
        
        // 显示桌面通知
        this.showDesktopNotification(notification);
        
        // 触发一个自定义事件通知UI更新未读计数
        window.dispatchEvent(new CustomEvent('notification:unread-updated', { 
          detail: { count: this.unreadCount } 
        }));
        
        console.log('已发送登录成功通知:', notification, '当前未读通知数:', this.unreadCount);
        
        // 主动触发一个DOM更新事件，确保UI能够立即更新
        setTimeout(() => {
          window.dispatchEvent(new Event('notification:state-changed'));
        }, 0);
      } catch (error) {
        console.error('发送登录成功通知失败:', error);
      }
    }
  }
}); 