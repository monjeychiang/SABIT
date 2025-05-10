import { useAuthStore } from '@/stores/auth';
import { useUserStore } from '@/stores/user';
import { useChatroomStore } from '@/stores/chatroom';
import { useNotificationStore } from '@/stores/notification';
import { useOnlineStatusStore } from '@/stores/online-status';
import webSocketManager, { WebSocketType } from '@/services/webSocketService';
import type { User } from '@/stores/user';

// 定義登入憑證介面
interface LoginCredentials {
  username: string;
  password: string;
  keepLoggedIn?: boolean;
}

// 定義類型轉換函數，將 authStore.user 轉換為 User 類型
function convertToUserType(authUser: any): User {
  return {
    id: authUser.id,
    username: authUser.username,
    email: authUser.email,
    role: authUser.is_admin ? 'admin' : 'regular',
    createdAt: authUser.created_at,
    avatar: authUser.avatar_url
  };
}

/**
 * 認證服務 - 提供統一的認證相關功能
 * 用於同步 auth store 和 user store 的狀態
 */
export const authService = {
  /**
   * 初始化認證狀態
   * 將從本地存儲加載令牌，並同步到兩個存儲中
   */
  async initialize() {
    console.log('初始化認證服務...');
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    // 初始化 auth store 身份驗證狀態
    await authStore.initAuth();
    
    // 如果 auth store 已登錄，將數據同步到 user store
    if (authStore.isAuthenticated && authStore.user && authStore.token) {
      console.log('從 auth store 同步用戶數據到 user store');
      const convertedUser = convertToUserType(authStore.user);
      userStore.syncWithAuthStore(authStore.token, convertedUser);
      
      // 用户已登录，初始化WebSocket连接
      await this.initializeWebSockets();
    } else {
      // 嘗試從 user store 初始化令牌
      await userStore.initializeToken();
      
      // 如果 user store 有有效令牌但沒有用戶數據，嘗試獲取用戶資料
      if (userStore.token && userStore.isTokenValid && !userStore.user) {
        console.log('user store 有有效令牌但沒有用戶數據，嘗試獲取');
        await this.fetchUserData();
        
        // 如果获取到了用户数据，初始化WebSocket连接
        if (userStore.isLoggedIn) {
          await this.initializeWebSockets();
        }
      }
    }
    
    console.log('認證狀態初始化完成', {
      authStore: authStore.isAuthenticated,
      userStore: userStore.isLoggedIn
    });
    
    return {
      isAuthenticated: authStore.isAuthenticated || userStore.isLoggedIn
    };
  },
  
  /**
   * 初始化WebSocket连接
   */
  async initializeWebSockets() {
    // 如果用户未登录，不初始化连接
    if (!this.isAuthenticated()) {
      console.log('[AuthService] 用户未登录，跳过WebSocket初始化');
      return false;
    }
    
    console.log('[AuthService] 开始初始化WebSocket连接');
    
    const notificationStore = useNotificationStore();
    const chatroomStore = useChatroomStore();
    const onlineStatusStore = useOnlineStatusStore();
    
    try {
      // 确保authStore中的token是最新的
      const authStore = useAuthStore();
      const token = authStore.token || localStorage.getItem('token');
      
      if (!token) {
        console.warn('[AuthService] 没有有效的认证令牌，无法初始化WebSocket');
        return false;
      }
      
      console.log('[AuthService] 已获取有效的认证令牌，准备注册WebSocket处理器');
      
      // 注册各类型的WebSocket连接
      webSocketManager.register(WebSocketType.NOTIFICATION, {
        onMessage: (event) => notificationStore.handleWebSocketMessage(event),
        onConnect: () => {
          console.log('通知WebSocket已连接');
          notificationStore.onWebSocketConnected();
        },
        onDisconnect: () => {
          console.log('通知WebSocket已断开');
          notificationStore.onWebSocketDisconnected();
        }
      });
      
      webSocketManager.register(WebSocketType.CHATROOM, {
        onMessage: (event) => chatroomStore.handleWebSocketMessage(event),
        onConnect: () => {
          console.log('聊天WebSocket已连接');
          chatroomStore.onWebSocketConnected();
        },
        onDisconnect: () => {
          console.log('聊天WebSocket已断开');
          chatroomStore.onWebSocketDisconnected();
        }
      });
      
      webSocketManager.register(WebSocketType.ONLINE_STATUS, {
        onMessage: (event) => onlineStatusStore.handleWebSocketMessage(event),
        onConnect: () => {
          console.log('在线状态WebSocket已连接');
          onlineStatusStore.onWebSocketConnected();
        },
        onDisconnect: () => {
          console.log('在线状态WebSocket已断开');
          onlineStatusStore.onWebSocketDisconnected();
        }
      });
      
      console.log('[AuthService] 已注册所有WebSocket处理器，开始连接...');
      
      // 连接所有注册的WebSocket
      const result = await webSocketManager.connectAll();
      console.log(`[AuthService] WebSocket连接结果: ${result ? '成功' : '失败'}`);
      return result;
    } catch (error) {
      console.error('[AuthService] 初始化WebSocket连接时出错:', error);
      return false;
    }
  },
  
  /**
   * 关闭所有WebSocket连接
   */
  closeAllWebSockets() {
    console.log('[AuthService] 关闭所有WebSocket连接');
    webSocketManager.disconnectAll();
  },
  
  /**
   * 登入用戶
   * @param credentials 登入憑證（用戶名/密碼）
   */
  async login(credentials: LoginCredentials) {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    // 使用 auth store 進行登入
    const result = await authStore.login(credentials);
    
    // 登入成功後，將數據同步到 user store
    if (authStore.isAuthenticated && authStore.user && authStore.token) {
      const convertedUser = convertToUserType(authStore.user);
      userStore.syncWithAuthStore(authStore.token, convertedUser);
      
      // 登录成功后初始化WebSocket连接
      await this.initializeWebSockets();
    }
    
    return result;
  },
  
  /**
   * 登出用戶
   */
  async logout() {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    const chatroomStore = useChatroomStore();
    const notificationStore = useNotificationStore();
    
    // 先关闭所有WebSocket连接
    this.closeAllWebSockets();
    
    // 重置聊天室状态
    chatroomStore.resetState();
    notificationStore.resetState();
    
    // 先登出 auth store
    await authStore.logout();
    
    // 再登出 user store
    userStore.logout();
    
    return true;
  },
  
  /**
   * 獲取用戶數據
   */
  async fetchUserData() {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    try {
      // 嘗試通過 auth store 獲取用戶資料
      if (authStore.isAuthenticated) {
        await authStore.getUserProfile();
        
        // 如果獲取成功，同步到 user store
        if (authStore.user && authStore.token) {
          const convertedUser = convertToUserType(authStore.user);
          userStore.syncWithAuthStore(authStore.token, convertedUser);
          return authStore.user;
        }
      }
      
      // 如果 auth store 沒有獲取成功，但 user store 有令牌，直接獲取
      if (userStore.token && userStore.isTokenValid) {
        const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${apiUrl}/api/v1/users/me`, {
          headers: {
            'Authorization': `Bearer ${userStore.token}`
          }
        });
        
        if (response.ok) {
          const userData = await response.json();
          // 將 API 返回的數據轉換為 User 類型
          const convertedUser: User = {
            id: userData.id,
            username: userData.username,
            email: userData.email,
            role: userData.is_admin ? 'admin' : 'regular',
            createdAt: userData.created_at,
            avatar: userData.avatar_url
          };
          userStore.setUser(convertedUser);
          return userData;
        } else {
          throw new Error(`無法獲取用戶數據: ${response.status}`);
        }
      }
      
      return null;
    } catch (error: unknown) {
      console.error('獲取用戶數據失敗:', error);
      
      // 如果是認證錯誤，清除令牌
      if (
        typeof error === 'object' && 
        error !== null && 
        'response' in error && 
        typeof error.response === 'object' && 
        error.response && 
        'status' in error.response && 
        error.response.status === 401
      ) {
        // 處理 axios 錯誤格式
        authStore.token = null;
        userStore.logout();
      } else if (
        error instanceof Error && 
        error.message.includes('401')
      ) {
        // 處理一般 Error 物件
        authStore.token = null;
        userStore.logout();
      }
      
      return null;
    }
  },
  
  /**
   * 驗證用戶是否已登入
   */
  isAuthenticated() {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    return authStore.isAuthenticated || userStore.isLoggedIn;
  }
};

export default authService; 