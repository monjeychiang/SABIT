import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import webSocketManager, { WebSocketType } from '@/services/webSocketService'

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
  isLoading: boolean;
  error: string | null;
  lastNotificationId: number | null;
  connectionStatus: 'connecting' | 'connected' | 'disconnected';
  filterType: NotificationTypeValue | null;
  refreshTimer: number | null;
  heartbeatTimeout: number | null;
  heartbeatInterval: number | null;
  useLocalStorage: boolean;
  newNotificationCallback: ((notification: Notification) => void) | null;
}

export const useNotificationStore = defineStore('notification', {
  state: (): NotificationState => ({
    notifications: [],
    unreadCount: 0,
    isLoading: false,
    error: null,
    lastNotificationId: null,
    connectionStatus: 'disconnected',
    filterType: null,
    refreshTimer: null,
    heartbeatTimeout: null,
    heartbeatInterval: null,
    useLocalStorage: true,
    newNotificationCallback: null
  }),

  getters: {
    getUnreadCount: (state): number => state.unreadCount,
    getNotifications: (state): Notification[] => state.notifications,
    hasUnreadNotifications: (state): boolean => state.unreadCount > 0,
    isConnected: (state): boolean => state.connectionStatus === 'connected'
  },

  actions: {
    initialize() {
      console.log('[Notification] 初始化通知系统...');
      
      this.setupEventListeners();
      
      this.fetchNotifications();
      
      console.log('[Notification] 通知系统初始化完成');
    },
    
    setupEventListeners() {
      window.addEventListener('websocket:connected', this.onWebSocketConnected.bind(this));
      window.addEventListener('websocket:disconnected', this.onWebSocketDisconnected.bind(this));
      
      console.log('[Notification] 事件监听器设置完成');
    },
    
    handleWebSocketMessage(data: any) {
      if (data.type === 'notification') {
        console.log('[Notification] 收到通知消息:', data);
        
        this.addNotification({
          id: data.id || Date.now(),
          message: data.content,
          title: data.title || '系统通知',
          type: data.notification_type || 'info',
          read: false,
          created_at: data.timestamp || new Date().toISOString()
        });
        
        this.triggerNotificationEvent(data);
      }
    },
    
    onWebSocketConnected() {
      console.log('[Notification] WebSocket连接已建立');
      this.connectionStatus = 'connected';
    },
    
    onWebSocketDisconnected() {
      console.log('[Notification] WebSocket连接已断开');
      this.connectionStatus = 'disconnected';
    },
    
    setTypeFilter(type: string) {
      this.filterType = type;
    },
    
    clearTypeFilter() {
      this.filterType = null;
    },
    
    startPeriodicRefresh() {
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
      
      this.refreshTimer = window.setInterval(() => {
        if (this.connectionStatus !== 'connected') {
          this.fetchNotifications();
        }
      }, 5 * 60 * 1000);
    },
    
    triggerNotificationEvent(data: any) {
      const event = new CustomEvent('notification:received', {
        detail: data
      });
      
      window.dispatchEvent(event);
      
      this.showBrowserNotification(data);
    },
    
    showBrowserNotification(data: any) {
      if (!('Notification' in window)) {
        console.log('[Notification] 此浏览器不支持桌面通知');
        return;
      }
      
      if (Notification.permission === 'granted') {
        const notification = new Notification(data.title || '系统通知', {
          body: data.content,
          icon: '/favicon.ico'
        });
        
        notification.onclick = () => {
            window.focus();
          notification.close();
        };
      } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
          if (permission === 'granted') {
            this.showBrowserNotification(data);
          }
        });
      }
    },
    
    async fetchNotifications() {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) return;
      
      this.isLoading = true;
      this.error = null;
      
      try {
        const response = await axios.get('/api/v1/notifications', {
          headers: { Authorization: `Bearer ${authStore.token}` }
        });
        
        this.notifications = response.data.notifications || [];
        this.unreadCount = response.data.unread_count || 0;
        
        if (this.notifications.length > 0) {
          this.lastNotificationId = this.notifications[0].id;
        }
        
        console.log(`[Notification] 成功获取${this.notifications.length}条通知，未读:${this.unreadCount}`);
      } catch (error) {
          this.error = '获取通知失败';
        console.error('[Notification] 获取通知失败:', error);
      } finally {
        this.isLoading = false;
      }
    },
    
    async markAsRead(id: number) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) return;
      
      try {
        await axios.post(`/api/v1/notifications/${id}/read`, {}, {
          headers: { Authorization: `Bearer ${authStore.token}` }
        });
        
        const notification = this.notifications.find(n => n.id === id);
        if (notification && !notification.is_read) {
          notification.is_read = true;
          this.unreadCount = Math.max(0, this.unreadCount - 1);
        }
        
        console.log(`[Notification] 已标记通知${id}为已读`);
      } catch (error) {
        console.error(`[Notification] 标记通知${id}为已读失败:`, error);
      }
    },
    
    async markAllAsRead() {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) return;
      
      try {
        await axios.post('/api/v1/notifications/read-all', {}, {
          headers: { Authorization: `Bearer ${authStore.token}` }
        });
        
        this.notifications.forEach(n => n.is_read = true);
        this.unreadCount = 0;
        
        console.log('[Notification] 已标记所有通知为已读');
      } catch (error) {
        console.error('[Notification] 标记所有通知为已读失败:', error);
      }
    },
    
    async deleteNotification(id: number) {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) return;
      
      try {
        await axios.delete(`/api/v1/notifications/${id}`, {
          headers: { Authorization: `Bearer ${authStore.token}` }
        });
        
        const index = this.notifications.findIndex(n => n.id === id);
        if (index !== -1) {
          const wasUnread = !this.notifications[index].is_read;
          this.notifications.splice(index, 1);
          if (wasUnread) {
            this.unreadCount = Math.max(0, this.unreadCount - 1);
          }
        }
        
        console.log(`[Notification] 已删除通知${id}`);
      } catch (error) {
        console.error(`[Notification] 删除通知${id}失败:`, error);
      }
    },
    
    async clearAllNotifications() {
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated) return;
      
      try {
        await axios.delete('/api/v1/notifications/all', {
          headers: { Authorization: `Bearer ${authStore.token}` }
        });
        
        this.notifications = [];
        this.unreadCount = 0;
        
        console.log('[Notification] 已清空所有通知');
      } catch (error) {
        console.error('[Notification] 清空所有通知失败:', error);
      }
    },
    
    addNotification(notification: any) {
      const existingIndex = this.notifications.findIndex(n => n.id === notification.id);
      
      if (existingIndex !== -1) {
        this.notifications[existingIndex] = { ...notification };
      } else {
        this.notifications.unshift(notification);
        
        if (!notification.is_read) {
          this.unreadCount++;
        }
      }
    },
    
    resetState() {
      this.notifications = [];
      this.unreadCount = 0;
      this.isLoading = false;
      this.error = null;
      this.lastNotificationId = null;
      this.connectionStatus = 'disconnected';
      this.filterType = null;
      
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
      
      console.log('[Notification] 通知状态已重置');
    }
  }
}); 