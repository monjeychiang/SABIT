import { useAuthStore } from '@/stores/auth';
import { useUserStore } from '@/stores/user';
import { useChatroomStore } from '@/stores/chatroom';
import { useNotificationStore } from '@/stores/notification';
import { useOnlineStatusStore } from '@/stores/online-status';
import mainWebSocketManager from '@/services/webSocketService';
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
 * 用於協調 auth store 和 user store 的狀態
 */
export const authService = {
  /**
   * 初始化認證狀態
   * 將從本地存儲加載令牌，並同步到相應的存儲中
   */
  async initialize() {
    console.log('初始化認證服務...');
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    // 初始化 auth store 身份驗證狀態
    await authStore.initAuth();
    
    // 若 auth store 已登錄，則設置 user store 的令牌
    if (authStore.isAuthenticated && authStore.token) {
      console.log('同步令牌到 user store');
      userStore.setToken(authStore.token);
      
      // 由 user store 負責獲取用戶數據
      try {
        await userStore.getUserData();
      } catch (error) {
        console.error('獲取用戶數據失敗', error);
      }
      
      // 用户已登录，初始化WebSocket连接
      await this.initializeWebSockets();
    } else {
      // 嘗試從 user store 初始化令牌
      await userStore.initializeToken();
      
      // 如果 user store 有有效令牌，初始化WebSocket連接
      if (userStore.isLoggedIn) {
        await this.initializeWebSockets();
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
    if (!this.isAuthenticated()) {
      console.log('[AuthService] 用户未登录，跳过WebSocket初始化');
      return false;
    }
    console.log('[AuthService] 初始化主WebSocket連線');
    const notificationStore = useNotificationStore();
    const chatroomStore = useChatroomStore();
    const onlineStatusStore = useOnlineStatusStore();
    try {
      // 註冊主WebSocket處理器，根據 type 分流
      mainWebSocketManager.register({
        onMessage: (data) => {
          console.log('[AuthService] 收到WebSocket消息:', data);
          if (!data || !data.type) return;
          
          // 根據消息類型分發到不同的處理器
          if (data.type === 'chat/message' || 
              data.type === 'chat/join' || 
              data.type === 'chat/leave' || 
              data.type === 'chat/error') {
            // 聊天相關消息
            chatroomStore.handleWebSocketMessage(data);
          } else if (data.type === 'notification') {
            // 通知消息
            notificationStore.handleWebSocketMessage(data);
          } else if (data.type === 'online/status' || data.type === 'user_status') {
            // 在線狀態消息
            onlineStatusStore.handleWebSocketMessage(data);
          } else if (data.type === 'ping' || data.type === 'pong') {
            // 心跳消息，直接由 chatroom 處理
            chatroomStore.handleWebSocketMessage(data);
          } else {
            console.log('[AuthService] 未處理的消息類型:', data.type);
          }
        },
        onConnect: () => {
          console.log('[AuthService] 主WebSocket已連線');
          chatroomStore.onWebSocketConnected();
          notificationStore.onWebSocketConnected();
          onlineStatusStore.onWebSocketConnected();
        },
        onDisconnect: () => {
          console.log('[AuthService] 主WebSocket已斷線');
          chatroomStore.onWebSocketDisconnected();
          notificationStore.onWebSocketDisconnected();
          onlineStatusStore.onWebSocketDisconnected();
        }
      });
      const result = await mainWebSocketManager.connectAll();
      console.log(`[AuthService] 主WebSocket連線結果: ${result ? '成功' : '失敗'}`);
      return result;
    } catch (error) {
      console.error('[AuthService] 初始化主WebSocket連線時出錯:', error);
      return false;
    }
  },
  
  /**
   * 关闭所有WebSocket连接
   */
  closeAllWebSockets() {
    console.log('[AuthService] 關閉主WebSocket連線');
    mainWebSocketManager.disconnectAll();
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
    
    // 登入成功後，將令牌同步到 user store
    if (authStore.isAuthenticated && authStore.token) {
      // 設置 user store 的令牌
      userStore.setToken(authStore.token);
      
      // 由 user store 直接獲取用戶資料
      await userStore.getUserData(true);
      
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
   * 驗證用戶是否已登入
   */
  isAuthenticated() {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    return authStore.isAuthenticated || userStore.isLoggedIn;
  }
};

export default authService; 