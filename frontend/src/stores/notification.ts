import { defineStore } from 'pinia'
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
    /**
     * 從WebSocket消息中解析通知數據
     * 支持多種格式的通知數據結構
     */
    parseNotificationFromMessage(data: any): any {
      console.log('嘗試解析通知數據:', data);
      
      // 嘗試不同的數據格式
      if (data.payload && typeof data.payload === 'object') {
        console.log('使用data.payload格式解析通知');
        return {...data.payload, is_read: data.payload.is_read || data.payload.read || false};
      } 
      
      if (data.notification && typeof data.notification === 'object') {
        console.log('使用data.notification格式解析通知');
        return {...data.notification, is_read: data.notification.is_read || data.notification.read || false};
      }
      
      if (data.data && typeof data.data === 'object') {
        console.log('使用data.data格式解析通知');
        return {...data.data, is_read: data.data.is_read || data.data.read || false};
      }
      
      // 如果消息本身就是通知對象
      if (data.id && (data.title || data.message)) {
        console.log('消息本身是通知對象');
        return {...data, is_read: data.is_read || data.read || false};
      }
      
      console.error('無法從消息中解析通知數據:', data);
      return null;
    },

    // 新增：处理WebSocket消息的方法
    handleWebSocketMessage(event: MessageEvent | any): void {
      try {
        // 記錄原始事件物件類型，便於調試
        console.log("收到WebSocket消息，事件類型:", typeof event, event);

        // 處理傳入的消息可能是已解析的對象或字符串的情況
        let data: any;

        // 如果 event 本身就是一個物件且不是 MessageEvent (來自 webSocketManager 的直接調用)
        if (event && typeof event === 'object' && !(event instanceof MessageEvent)) {
          console.log("直接接收到解析後的消息物件");
          data = event;
        }
        // 如果是標準 MessageEvent
        else if (event && event.data !== undefined) {
          console.log("收到標準 MessageEvent 消息:", event.data);
          
          // 如果 data 是字符串，嘗試解析為 JSON
          if (typeof event.data === 'string') {
            try {
              data = JSON.parse(event.data);
            } catch (parseError) {
              console.error("解析 WebSocket 消息失敗:", parseError);
              return;
            }
          } else if (typeof event.data === 'object') {
            // 如果 data 已經是物件，直接使用
            data = event.data;
          } else {
            console.error("未知的 WebSocket 消息格式:", typeof event.data);
            return;
          }
        } else {
          console.error("收到無效的 WebSocket 消息或空消息");
          return;
        }
        
        // 確保 data 不為 undefined
        if (!data) {
          console.error("解析後的消息為空");
          return;
        }
        
        // 增加詳細日誌以進行調試
        console.log("處理 WebSocket 消息:", data);
        console.log("WebSocket 消息類型:", data.type);
        
        // 排除聊天類型的消息
        if (data.type && data.type.startsWith('chat/')) {
          console.log('通知管理器忽略聊天類型的消息:', data.type);
          return;
        }
        
        // 處理不同類型的消息
        switch (data.type) {
          case 'ping':
            // 收到服務器ping，回復pong
            this.sendPong();
            break;
          
          case 'pong':
            // 收到服務器pong響應，不需要處理
            break;

          case 'notification':
            // 添加詳細日誌
            console.log('收到通知消息:', data);
            
            // 解析通知數據
            const notification = this.parseNotificationFromMessage(data);
            
            // 處理通知
            if (notification && notification.id) {
              // 檢查是否已存在相同ID的通知
              if (!this.notifications.some(n => n.id === notification.id)) {
                // 添加新通知
                this.notifications.unshift(notification);
                this.unreadCount++;
                
                // 使用瀏覽器通知API (如果用戶允許)
                this.showDesktopNotification(notification);
                
                console.log("通知已添加到列表，目前有", this.notifications.length, "條通知");
                console.log("未讀通知數:", this.unreadCount);
              } else {
                console.log("忽略重複通知, ID:", notification.id);
              }
            }
            break;
            
          case 'error':
            // 錯誤消息
            console.error('通知WebSocket錯誤:', data.message);
            this.error = data.message || '通知服務發生錯誤';
            break;
            
          default:
            console.log('收到未知類型的WebSocket消息:', data);
        }
      } catch (error) {
        console.error("處理WebSocket消息時出錯:", error);
      }
    },

    // 新增：WebSocket连接成功的处理方法
    onWebSocketConnected(): void {
      console.log('通知WebSocket连接已建立');
      this.websocketConnected = true;
      this.reconnectAttempts = 0;
      this.error = null;
      
      // 连接成功后开始拉取最新通知
      this.fetchNotifications();
      
      // 添加调试信息
      console.log('通知WebSocket连接状态:', {
        连接状态: this.websocketConnected ? '已连接' : '未连接',
        重连次数: this.reconnectAttempts
      });
      
      // 触发连接成功事件，通知UI更新
      window.dispatchEvent(new Event('notification:websocket-connected'));
    },

    // 新增：WebSocket断开连接的处理方法
    onWebSocketDisconnected(): void {
      this.websocketConnected = false;
      
      // 触发断开连接事件，通知UI更新
      window.dispatchEvent(new Event('notification:websocket-disconnected'));
    },

    // 发送pong响应
    sendPong(): void {
      webSocketManager.send({ type: 'pong' });
    },
    
    // 发送ping请求
    sendPing(): void {
      webSocketManager.send({ type: 'ping' });
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
          const userId = localStorage.getItem('userId');
          const username = localStorage.getItem('username');
          const storageKey = getUserNotificationsKey(
            userId ? parseInt(userId) : null, 
            username
          );
          
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
        
        // 準備要保存的數據 - 不再引用 user 屬性
        const storageData: StoredNotificationData = {
          notifications: this.notifications,
          timestamp: Date.now()
        };
        
        // 獲取用戶特定的存儲鍵名，適應現有的 authStore 結構
        const userId = localStorage.getItem('userId');
        const username = localStorage.getItem('username');
        const storageKey = getUserNotificationsKey(
          userId ? parseInt(userId) : null, 
          username
        );
        
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
        
        // 獲取用戶特定的存儲鍵名，適應現有的 authStore 結構
        const userId = localStorage.getItem('userId');
        const username = localStorage.getItem('username');
        const storageKey = getUserNotificationsKey(
          userId ? parseInt(userId) : null, 
          username
        );
        
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
      
      // 不再直接註冊 WebSocket 處理器，完全依賴 authService 進行消息分發
      // 所有通知消息都將通過 authService 分發到 handleWebSocketMessage 方法
      
      // 但需要監聽 WebSocket 的連接和斷開事件，以便更新狀態
      window.addEventListener('websocket:connected', () => {
        this.onWebSocketConnected();
      });
      
      window.addEventListener('websocket:disconnected', () => {
        this.onWebSocketDisconnected();
      });
      
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
      
      // 移除事件监听器
      window.removeEventListener('websocket:connected', () => {
        this.onWebSocketConnected();
      });
      
      window.removeEventListener('websocket:disconnected', () => {
        this.onWebSocketDisconnected();
      });
      
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
    },

    // 兼容方法：提供与旧版API兼容的WebSocket连接方法
    // 此方法仅用于兼容现有代码，不应在新代码中使用
    connectWebSocket(): boolean {
      console.warn('[Notification] connectWebSocket方法已弃用，WebSocket连接现在由WebSocketManager统一管理');
      return webSocketManager.connect() as any;
    },
    
    // 兼容方法：提供与旧版API兼容的WebSocket关闭方法
    // 此方法仅用于兼容现有代码，不应在新代码中使用
    closeWebSocket(): void {
      console.warn('[Notification] closeWebSocket方法已弃用，WebSocket连接现在由WebSocketManager统一管理');
      webSocketManager.disconnect();
    }
  }
}); 