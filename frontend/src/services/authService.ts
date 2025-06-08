import { useAuthStore } from '@/stores/auth';
import { useUserStore, type User } from '@/stores/user';
import { useChatroomStore } from '@/stores/chatroom';
import { useNotificationStore } from '@/stores/notification';
import { useOnlineStatusStore } from '@/stores/online-status';
import mainWebSocketManager from '@/services/webSocketService';
import { accountWebSocketService } from '@/services/accountWebSocketService';
import { tradingService } from '@/services/tradingService';
import axios from 'axios';
import { tokenService } from '@/services/token';

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
    
    // 先嘗試從持久化緩存載入用戶資料
    // 這將確保頁面刷新後立即顯示用戶資料，不需等待API請求
    const hasCachedUser = userStore.loadUserFromCache();
    if (hasCachedUser) {
      console.log('從持久化緩存成功載入用戶資料，無需等待API請求');
    }
    
    // 初始化 auth store 身份驗證狀態
    await authStore.initAuth();
    
    // 若 auth store 已登錄，則設置 user store 的令牌
    if (authStore.isAuthenticated && authStore.token) {
      console.log('同步令牌到 user store');
      userStore.setToken(authStore.token);
      
      // 若沒有緩存數據或需要刷新，再獲取用戶數據
      if (!hasCachedUser) {
        try {
          console.log('從緩存未載入到用戶資料，嘗試從API獲取');
          await userStore.getUserData();
        } catch (error) {
          console.error('獲取用戶數據失敗', error);
        }
      } else {
        console.log('已有緩存用戶資料，背景刷新資料');
        // 在背景刷新用戶資料，但不等待完成
        userStore.getUserData().catch(error => {
          console.error('背景刷新用戶資料失敗', error);
        });
      }
      
      // 用户已登录，初始化WebSocket连接
      await this.initializeWebSockets();
    } else {
      // 嘗試從 user store 初始化令牌
      if (!hasCachedUser) {
        await userStore.initializeToken();
      }
      
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
    // 檢查用戶是否已登入
    if (!this.isAuthenticated()) {
      console.log('[AuthService] 用户未登录，跳过WebSocket初始化');
      return false;
    }
    
    console.log('[AuthService] 開始統一初始化所有WebSocket連線');
    
    try {
      // 檢查現有的WebSocket狀態
      const mainConnected = await this.checkMainWebSocketStatus();
      const accountConnected = await this.checkAccountWebSocketStatus();
      
      if (mainConnected && accountConnected) {
        console.log('[AuthService] 所有WebSocket已連接，跳過初始化');
        return true;
      }

      // 初始化WebSocket連接，紀錄所有步驟
      let mainResult = mainConnected;
      let accountResult = accountConnected;

      // 初始化主WebSocket（如果尚未連接）
      if (!mainConnected) {
        console.log('[AuthService] 初始化主WebSocket連線');
        const notificationStore = useNotificationStore();
        const chatroomStore = useChatroomStore();
        const onlineStatusStore = useOnlineStatusStore();
        
        // 註冊主WebSocket處理器，根據 type 分流
        mainWebSocketManager.register({
          onMessage: (data) => {
            if (!data || !data.type) return;
            
            // 根據消息類型分發到不同的處理器
            if (data.type === 'chat/message' || 
                data.type === 'chat/join' || 
                data.type === 'chat/leave' || 
                data.type === 'chat/error') {
              // 聊天相關消息只傳給聊天室 store 處理
              chatroomStore.handleWebSocketMessage(data);
            } else if (data.type === 'notification') {
              // 通知消息只傳給通知 store 處理
              notificationStore.handleWebSocketMessage(data);
            } else if (data.type === 'online/status' || data.type === 'user_status') {
              // 在線狀態消息只傳給線上狀態 store 處理
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
        
        // 初始化主WebSocket連接
        mainResult = await mainWebSocketManager.connectAll();
        console.log(`[AuthService] 主WebSocket連線結果: ${mainResult ? '成功' : '失敗'}`);
      }
      
      // 初始化賬戶WebSocket連接（如果尚未連接）
      if (!accountConnected) {
        console.log('[AuthService] 初始化賬戶WebSocket連線');
        accountResult = await accountWebSocketService.initializeConnection();
        console.log(`[AuthService] 賬戶WebSocket連線結果: ${accountResult ? '成功' : '失敗'}`);
      }
      
      // 返回整體連接結果（至少有一個成功）
      const result = mainResult || accountResult;
      console.log(`[AuthService] 所有WebSocket初始化完成，總結果: ${result ? '成功' : '失敗'}`);
      return result;
    } catch (error) {
      console.error('[AuthService] 初始化WebSocket連線時出錯:', error);
      return false;
    }
  },
  
  /**
   * 檢查主WebSocket狀態
   */
  async checkMainWebSocketStatus(): Promise<boolean> {
    try {
      const isConnected = mainWebSocketManager.isConnected();
      console.log(`[AuthService] 主WebSocket狀態檢查: ${isConnected ? '已連接' : '未連接'}`);
      return isConnected;
    } catch (error) {
      console.error('[AuthService] 檢查主WebSocket狀態時出錯:', error);
      return false;
    }
  },
  
  /**
   * 檢查賬戶WebSocket狀態
   */
  async checkAccountWebSocketStatus(): Promise<boolean> {
    try {
      const isConnected = accountWebSocketService.isConnected();
      console.log(`[AuthService] 賬戶WebSocket狀態檢查: ${isConnected ? '已連接' : '未連接'}`);
      return isConnected;
    } catch (error) {
      console.error('[AuthService] 檢查賬戶WebSocket狀態時出錯:', error);
      return false;
    }
  },
  
  /**
   * 关闭所有WebSocket连接
   */
  closeAllWebSockets() {
    console.log('[AuthService] 統一關閉所有WebSocket連線');
    
    try {
      // 關閉主WebSocket連線
      console.log('[AuthService] 關閉主WebSocket連線');
      mainWebSocketManager.disconnectAll();
      
      // 關閉賬戶WebSocket連線 - 使用統一接口，強制模式
      console.log('[AuthService] 關閉賬戶WebSocket連線');
      accountWebSocketService.closeConnection(true);
      
      console.log('[AuthService] 所有WebSocket連線已關閉');
      return true;
    } catch (error) {
      console.error('[AuthService] 關閉WebSocket連線時出錯:', error);
      return false;
    }
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
    console.log('[AuthService] 統一關閉所有WebSocket連線');
    // 先关闭所有WebSocket连接
    this.closeAllWebSockets();
    
    console.log('[AuthService] 所有WebSocket連線已關閉');
    
    const authStore = useAuthStore();
    const userStore = useUserStore();
    const chatroomStore = useChatroomStore();
    const notificationStore = useNotificationStore();
    
    // 重置聊天室状态
    chatroomStore.resetState();
    notificationStore.resetState();
    
    try {
      // 從 authStore 獲取當前刷新令牌（而非訪問令牌）
      const currentRefreshToken = authStore.refreshToken;
      
      // 如果用戶已登入且有有效刷新令牌，嘗試調用登出 API
      if (currentRefreshToken) {
        try {
          // 嘗試帶有表單格式的請求，使用正確的參數名稱 'refresh_token'
          try {
            const formData = new FormData();
            formData.append('refresh_token', currentRefreshToken);
            
            await axios.post('/api/v1/auth/logout', formData, {
              headers: {
                'Content-Type': 'multipart/form-data'
              }
            });
            console.log('[AuthService] 登出 API 調用成功 (表單格式)');
            // 如果成功，不再嘗試其他格式
            return await this.finalizeLogout(authStore, userStore);
          } catch (formError) {
            console.warn('[AuthService] 表單格式登出請求失敗:', formError);
            // 即使API調用失敗，也繼續本地登出流程
          }
        } catch (error) {
          // 捕獲但不拋出錯誤，確保登出流程繼續
          console.warn('[AuthService] 登出 API 調用失敗，繼續本地登出流程', error);
        }
      } else {
        console.warn('[AuthService] 沒有刷新令牌可用於登出 API 調用');
      }
      
      // 無論 API 是否成功，都完成本地登出流程
      return await this.finalizeLogout(authStore, userStore);
    } catch (error) {
      console.error('[AuthService] 登出過程中發生錯誤:', error);
      
      // 即使發生錯誤，也確保清除用戶狀態
      try {
        tokenService.clearTokens();
        userStore.logout();
      } catch (e) {
        console.error('[AuthService] 登出時清除用戶狀態失敗:', e);
      }
      
      return false;
    }
  },
  
  /**
   * 完成登出流程的最後步驟
   * @private
   */
  async finalizeLogout(authStore: any, userStore: any): Promise<boolean> {
    try {
      // 先登出 auth store (這會清除令牌)
      await authStore.logout();
      
      // 再登出 user store
      userStore.logout();
      
      console.log('[AuthService] 登出完成');
      return true;
    } catch (e) {
      console.error('[AuthService] 完成登出過程失敗:', e);
      
      // 確保令牌被清除
      tokenService.clearTokens();
      
      return false;
    }
  },
  
  /**
   * 驗證用戶是否已登入
   */
  isAuthenticated() {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    return authStore.isAuthenticated || userStore.isLoggedIn;
  },

  /**
   * 預熱 CCXT 連接
   * 在用戶登入後調用此方法，預先初始化 CCXT 連接，以減少首次交易操作的延遲
   * @returns {Promise<{success: boolean, message: string, exchanges: string[]}>} 預熱結果
   */
  async preheatCcxtConnections() {
    console.log('[AuthService] 開始預熱 CCXT 連接');
    
    try {
      // 檢查用戶是否已登入
      if (!this.isAuthenticated()) {
        console.log('[AuthService] 用户未登录，跳过 CCXT 預熱');
        return {
          success: false,
          message: '用戶未登入，無法預熱連接',
          exchanges: []
        };
      }
      
      // 使用交易服務預熱 Binance 交易所連接
      const result = await tradingService.preheatExchangeConnection('binance');
      
      // 可以根據需求添加更多交易所的預熱
      // const exchanges = ['binance', 'okx', 'bybit', 'gate', 'mexc'];
      // const result = await tradingService.preheatMultipleExchanges(exchanges);
      
      return {
        success: result.success,
        message: result.message,
        exchanges: result.success ? ['binance'] : []
      };
    } catch (error) {
      console.error('[AuthService] 預熱 CCXT 連接失敗:', error);
      return {
        success: false,
        message: `預熱連接失敗: ${error instanceof Error ? error.message : '未知錯誤'}`,
        exchanges: []
      };
    }
  }
};

export default authService; 