import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import axios from 'axios'
import { useAuthStore } from './auth'
import webSocketManager, { WebSocketType } from '@/services/webSocketService'
import { useUserStore } from './user'

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
  source?: 'admin' | 'system'; // 添加通知來源字段，用於區分管理員通知和系統事件通知
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
const LOCAL_STORAGE_NOTIFICATIONS_MAX = 100; // 增加最大存儲通知數量
const LOCAL_STORAGE_NOTIFICATIONS_EXPIRY = 30 * 24 * 60 * 60 * 1000; // 延長為30天後過期

// 添加一個新常量用於儲存清空通知的標記
const LOCAL_STORAGE_CLEAR_FLAG_KEY = 'app_notifications_clear_flag';

// 獲取用戶特定的通知清空標記鍵名
const getUserClearFlagKey = (userId?: number | null, username?: string | null): string => {
  const userIdentifier = userId || username || 'anonymous';
  return `${LOCAL_STORAGE_CLEAR_FLAG_KEY}_${userIdentifier}`;
};

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
  localStorageLoaded: boolean; // 新增標誌，表示是否已從LocalStorage加載
  // 添加新的状态
  clearFlag: number | null; // 通知清空标记时间戳
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
    useLocalStorage: true, // 確保默認啟用本地存儲
    newNotificationCallback: null,
    localStorageLoaded: false, // 新增標誌，表示是否已從LocalStorage加載
    clearFlag: null // 初始化为null，表示没有清空标记
  }),

  getters: {
    getUnreadCount: (state): number => state.unreadCount,
    getNotifications: (state): Notification[] => state.notifications,
    hasUnreadNotifications: (state): boolean => state.unreadCount > 0,
    isConnected: (state): boolean => state.connectionStatus === 'connected',
    
    // 按時間排序的通知
    sortedNotifications: (state): Notification[] => {
      return [...state.notifications].sort((a, b) => {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
    },
    
    // 根據過濾類型篩選的通知
    filteredNotifications: (state): Notification[] => {
      if (!state.filterType) {
        return state.notifications;
      }
      return state.notifications.filter(notification => 
        notification.notification_type === state.filterType
      );
    }
  },

  actions: {
    initialize() {
      console.log('[Notification] 初始化通知系统...');
      
      // 首先從LocalStorage加載通知
      const loadedFromStorage = this.loadNotificationsFromLocalStorage();
      
      // 無論是否從LocalStorage成功加載，都設置事件監聽器
      this.setupEventListeners();
      
      // 如果沒有從LocalStorage加載成功，才從服務器獲取
      if (!loadedFromStorage) {
      this.fetchNotifications();
      } else {
        console.log('[Notification] 已從本地存儲加載通知，跳過從服務器獲取');
      }
      
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
        
        // 檢查數據結構，支持多種可能的格式
        const notificationData = data.notification || data.payload || data;
        
        // 創建規範化的通知對象
        const normalizedNotification: Notification = {
          id: notificationData.id || Date.now(),
          title: notificationData.title || '系统通知',
          message: notificationData.message || notificationData.content || '',
          notification_type: notificationData.notification_type || NotificationType.INFO,
          is_read: notificationData.is_read || false,
          created_at: notificationData.created_at || notificationData.timestamp || new Date().toISOString(),
          is_global: notificationData.is_global || false,
          user_id: notificationData.user_id
        };
        
        // 如果消息內容存在於主數據對象中，優先使用它
        if (data.content && typeof data.content === 'string' && !normalizedNotification.message) {
          normalizedNotification.message = data.content;
        }
        
        console.log('[Notification] 已標準化通知數據:', normalizedNotification);
        
        // 確保消息內容不為空
        if (!normalizedNotification.message && !normalizedNotification.title) {
          console.warn('[Notification] 警告: 通知內容為空');
          normalizedNotification.message = '收到一條新通知';
        }
        
        // 添加到通知列表
        this.addNotification(normalizedNotification);
        
        // 觸發通知事件
        this.triggerNotificationEvent(normalizedNotification);
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
    
    setTypeFilter(type: NotificationTypeValue | null) {
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
      
      const title = data.title || '系统通知';
      const body = data.message || data.content || '您有一條新通知';
      
      if (Notification.permission === 'granted') {
        const notification = new Notification(title, {
          body: body,
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
        // 載入清空標記
        this.loadClearFlag();
        
        // 只在登入後首次獲取管理員通知（數據庫通知）
        const response = await axios.get('/api/v1/notifications', {
          headers: { Authorization: `Bearer ${authStore.token}` }
        });
        
        // 將從服務器獲取的通知標記為 'admin' 來源
        const adminNotifications = (response.data.items || []).map((notification: any) => ({
          ...notification,
          source: 'admin' // 標記為管理員通知
        }));
        
        // 根據清空標記過濾通知
        const filteredNotifications = this.clearFlag !== null 
          ? adminNotifications.filter((notification: any) => {
              // 將創建時間轉換為時間戳
              const notificationTime = new Date(notification.created_at).getTime();
              // 只保留清空標記之後的通知
              return notificationTime > this.clearFlag!; // 使用非空斷言，因為前面已經檢查過了
            })
          : adminNotifications;
        
        console.log(`[Notification] 過濾前通知數: ${adminNotifications.length}, 過濾後: ${filteredNotifications.length}`);
        
        // 獲取現有通知，構建ID映射以避免重複
        const existingIds = new Set(this.notifications.map(n => n.id));
        
        // 合併新獲取的管理員通知（避免添加重複）
        for (const notification of filteredNotifications) {
          if (!existingIds.has(notification.id)) {
            this.notifications.push(notification);
            existingIds.add(notification.id);
          }
        }
        
        // 重新計算未讀通知數
        this.updateUnreadCount();
        
        // 保存到本地
        this.saveNotificationsToLocalStorage();
        
        console.log(`[Notification] 成功获取${filteredNotifications.length}条有效管理员通知，目前共有 ${this.notifications.length} 条通知`);
      } catch (error) {
          this.error = '获取通知失败';
        console.error('[Notification] 获取通知失败:', error);
      } finally {
        this.isLoading = false;
      }
    },
    
    // 修改為只在前端更新已讀狀態，不觸發API
    markAsRead(id: number | string) {      
      // 查找通知
        const notification = this.notifications.find(n => n.id === id);
        if (notification && !notification.is_read) {
          notification.is_read = true;
          this.unreadCount = Math.max(0, this.unreadCount - 1);
        
        // 更新本地存儲
        if (this.useLocalStorage) {
          this.saveNotificationsToLocalStorage();
        }
        
        console.log(`[Notification] 已標記通知 ${id} 為已讀（僅前端）`);
      }
    },
    
    // 修改為只在前端更新所有通知的已讀狀態
    markAllAsRead() {
      // 更新所有未讀通知為已讀
      let updatedCount = 0;
      this.notifications.forEach(notification => {
        if (!notification.is_read) {
          notification.is_read = true;
          updatedCount++;
        }
      });
      
      // 更新未讀計數
        this.unreadCount = 0;
        
      // 更新本地存儲
      if (this.useLocalStorage) {
        this.saveNotificationsToLocalStorage();
      }
      
      console.log(`[Notification] 已標記所有通知為已讀（僅前端），更新了 ${updatedCount} 條通知`);
    },
    
    // 修改为只清除前端内存和本地存储的通知，不触发API
    clearAllNotifications() {
      const authStore = useAuthStore();
      const userStore = useUserStore();
      
      try {
        // 清空前端通知列表
        const oldCount = this.notifications.length;
        this.notifications = [];
        this.unreadCount = 0;
        
        // 設定清空標記（當前時間戳）
        this.clearFlag = Date.now();
        
        if (authStore.isAuthenticated && userStore.user) {
          // 清空本地存储的通知
          const key = getUserNotificationsKey(userStore.user.id, userStore.user.username);
          localStorage.removeItem(key);
          
          // 設置清空通知的時間標記
          const clearFlagKey = getUserClearFlagKey(userStore.user.id, userStore.user.username);
          localStorage.setItem(clearFlagKey, this.clearFlag.toString());
          
          console.log(`[Notification] 已清空本地存储中的通知，設置清空標記: ${this.clearFlag}`);
        }
        
        console.log(`[Notification] 已清空所有通知 (${oldCount} 條)`);
      } catch (error) {
        console.error('[Notification] 清空通知失败:', error);
      }
    },
    
    addNotification(notification: Notification) {
      // 檢查是否已經存在相同ID的通知
      const existingIndex = this.notifications.findIndex(n => n.id === notification.id);
      
      if (existingIndex !== -1) {
        // 更新現有通知，但保留已讀狀態
        const isReadStatus = this.notifications[existingIndex].is_read;
        this.notifications[existingIndex] = { 
          ...notification,
          is_read: isReadStatus // 保留原來的已讀狀態
        };
      } else {
        // 添加新通知到列表最前面
        this.notifications.unshift(notification);
        
        // 如果是未讀通知，增加未讀計數
        if (!notification.is_read) {
          this.unreadCount++;
        }
        
        // 通知回調
        if (this.newNotificationCallback && typeof this.newNotificationCallback === 'function') {
          this.newNotificationCallback(notification);
        }
        
        // 限制本地儲存的通知數量
        if (this.notifications.length > LOCAL_STORAGE_NOTIFICATIONS_MAX) {
          // 移除最舊的通知
          this.notifications = this.notifications.slice(0, LOCAL_STORAGE_NOTIFICATIONS_MAX);
        }
      }
      
      // 更新未讀計數
      this.updateUnreadCount();
      
      // 保存到本地存儲
      if (this.useLocalStorage) {
        this.saveNotificationsToLocalStorage();
      }
    },
    
    // 更新未讀通知計數
    updateUnreadCount() {
      const newUnreadCount = this.notifications.filter(n => !n.is_read).length;
      if (this.unreadCount !== newUnreadCount) {
        this.unreadCount = newUnreadCount;
        
        // 觸發未讀計數更新事件
        window.dispatchEvent(new CustomEvent('notification:unread-updated', {
          detail: { count: this.unreadCount }
        }));
      }
    },
    
    // 保存通知到本地存儲
    saveNotificationsToLocalStorage() {
      const authStore = useAuthStore();
      const userStore = useUserStore();
      
      // 檢查用戶是否登入和是否有用戶數據
      if (!authStore.isAuthenticated || !userStore.user) return;
      
      try {
        const key = getUserNotificationsKey(userStore.user.id, userStore.user.username);
        const data: StoredNotificationData = {
          notifications: this.notifications.slice(0, LOCAL_STORAGE_NOTIFICATIONS_MAX),
          timestamp: Date.now(),
          userId: userStore.user.id,
          username: userStore.user.username
        };
        
        localStorage.setItem(key, JSON.stringify(data));
      } catch (error) {
        console.error('[Notification] 保存通知到本地存儲失敗:', error);
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
      this.clearFlag = null; // 重置清空標記
      
      if (this.refreshTimer) {
        clearInterval(this.refreshTimer);
        this.refreshTimer = null;
      }
      
      console.log('[Notification] 通知状态已重置');
    },
    
    // 設置新通知回調函數
    setNewNotificationCallback(callback: (notification: Notification) => void) {
      this.newNotificationCallback = callback;
      console.log('[Notification] 已設置新通知回調函數');
    },
    
    // 從LocalStorage加載通知
    loadNotificationsFromLocalStorage() {
      try {
        const authStore = useAuthStore();
        const userStore = useUserStore();
        
        if (!authStore.isAuthenticated) return false;
        
        // 嘗試獲取用戶ID
        let userId = userStore.user?.id;
        let username = userStore.user?.username;
        
        // 如果沒有用戶數據，嘗試從authStore獲取
        if (!userId && !username) {
          console.log('[Notification] 未找到用戶數據，嘗試從其他來源獲取...');
          
          // 可以添加其他獲取用戶ID的邏輯...
          if (!userId && !username) {
            console.warn('[Notification] 無法獲取用戶ID，無法加載本地通知');
            return false;
          }
        }
        
        // 首先載入清空標記
        this.loadClearFlag();
        
        const key = getUserNotificationsKey(userId, username);
        const storedData = localStorage.getItem(key);
        
        if (storedData) {
          try {
            const data: StoredNotificationData = JSON.parse(storedData);
            
            // 檢查數據是否過期
            const now = Date.now();
            if (now - data.timestamp <= LOCAL_STORAGE_NOTIFICATIONS_EXPIRY) {
              this.notifications = data.notifications;
              
              // 計算未讀通知數
              this.unreadCount = data.notifications.filter(n => !n.is_read).length;
              
              // 更新狀態標誌
              this.localStorageLoaded = true;
              
              console.log(`[Notification] 從本地存儲加載了 ${this.notifications.length} 條通知，未讀數: ${this.unreadCount}`);
              return true;
            } else {
              // 數據已過期，刪除
              localStorage.removeItem(key);
              console.log('[Notification] 本地通知數據已過期，已刪除');
            }
          } catch (parseError) {
            console.error('[Notification] 解析本地存儲通知失敗:', parseError);
            localStorage.removeItem(key);
          }
        } else {
          console.log('[Notification] 本地存儲中沒有通知數據');
        }
        
        return false;
      } catch (error) {
        console.error('[Notification] 從本地存儲加載通知時出錯:', error);
        return false;
      }
    },
    
    // 新增：從LocalStorage加載清空標記
    loadClearFlag() {
      try {
        const authStore = useAuthStore();
        const userStore = useUserStore();
        
        if (!authStore.isAuthenticated || !userStore.user) return;
        
        const clearFlagKey = getUserClearFlagKey(userStore.user.id, userStore.user.username);
        const storedClearFlag = localStorage.getItem(clearFlagKey);
        
        if (storedClearFlag) {
          this.clearFlag = parseInt(storedClearFlag);
          console.log(`[Notification] 從本地存儲加載清空標記: ${this.clearFlag}`);
        } else {
          this.clearFlag = null;
          console.log('[Notification] 未找到清空標記');
        }
      } catch (error) {
        console.error('[Notification] 加載清空標記時出錯:', error);
        this.clearFlag = null;
      }
    },
    
    // 當用戶登出時調用此方法
    handleLogout() {
      // 保存最後活動時間（用於下次登入獲取離線通知）
      localStorage.setItem('last_active_time', new Date().toISOString());
      
      // 重置通知狀態
      this.resetState();
      
      // 關閉WebSocket連接
      webSocketManager.disconnect();
      
      console.log('[Notification] 已處理用戶登出');
    }
  }
}); 