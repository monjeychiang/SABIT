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
      
      // 如果有緩存用戶，立即同步token到authStore確保UI正確顯示
      if (userStore.token) {
        authStore.token = userStore.token;
        // 設置axios授權頭，確保後續請求帶有授權
        axios.defaults.headers.common['Authorization'] = `Bearer ${userStore.token}`;
      }
      
      // 在後台啟動所有WebSocket連接，不阻塞UI
      setTimeout(async () => {
        try {
          await this.initializeWebSockets();
          console.log('後台WebSocket連接初始化完成');
        } catch (e) {
          console.warn('後台WebSocket連接初始化失敗，但不影響用戶體驗:', e);
        }
      }, 0);
    }
    
    // 非阻塞方式處理令牌驗證
    // 立即返回初始狀態，讓UI可以快速顯示
    // 在後台處理完整的令牌驗證和刷新流程
    setTimeout(async () => {
      try {
        await this._completeInitialization(hasCachedUser);
        console.log('後台完成認證初始化');
      } catch (e) {
        console.warn('後台認證初始化過程發生錯誤，但不影響當前UI:', e);
      }
    }, 0);
    
    // 立即返回初始認證狀態
    return { isAuthenticated: !!userStore.token || !!authStore.token || hasCachedUser };
  },
  
  /**
   * 完成初始化過程（內部方法，由initialize在後台調用）
   * @private
   */
  async _completeInitialization(hasCachedUser: boolean) {
    const authStore = useAuthStore();
    const userStore = useUserStore();
    
    try {
      // 先檢查URL中是否有訪問令牌（登入重定向回調）
      const urlParams = new URLSearchParams(window.location.search);
      const accessToken = urlParams.get('access_token');
      
      // 如果URL中有訪問令牌，優先處理它（來自登入回調）
      if (accessToken) {
        console.log('檢測到URL中的訪問令牌，優先處理');
        const tokenType = urlParams.get('token_type') || 'bearer';
        
        // 更新store中的token
        authStore.token = accessToken;
        userStore.setToken(accessToken);
        
        // 設置axios授權頭
        axios.defaults.headers.common['Authorization'] = `${tokenType} ${accessToken}`;
        
        // 若沒有緩存數據或需要刷新，獲取用戶數據
      if (!hasCachedUser) {
        try {
          await userStore.getUserData();
          } catch (userError) {
            console.error('獲取用戶數據失敗', userError);
          }
        }
        
        // 清除URL參數，避免重新加載時重複處理
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // 初始化WebSocket連接
        await this.initializeWebSockets();
        
        return { isAuthenticated: true };
      }
      
      // 如果URL中沒有訪問令牌，再嘗試刷新流程
      // 嘗試通過刷新令牌 cookie 獲取新的 access token
      const refreshResult = await this.tryRefreshToken();
      
      if (refreshResult.success && refreshResult.accessToken) {
        console.log('通過刷新令牌成功獲取新的訪問令牌');
        
        // 更新 token 到內部狀態
        authStore.token = refreshResult.accessToken;
        userStore.setToken(refreshResult.accessToken);
        
        // 手動設置所需的 axios Authorization 頭
        axios.defaults.headers.common['Authorization'] = `Bearer ${refreshResult.accessToken}`;
        
        // 若沒有緩存數據或需要刷新，獲取用戶數據
        if (!hasCachedUser) {
          try {
            await userStore.getUserData();
          } catch (userError) {
            console.error('獲取用戶數據失敗', userError);
          }
      }
      
      // 用户已登录，初始化WebSocket连接
      await this.initializeWebSockets();
        
        return { isAuthenticated: true };
      }
      
      // 刷新失敗，嘗試從 authStore 初始化
      console.log('刷新令牌失敗，嘗試從 authStore 初始化');
      const authResult = await authStore.initAuth();
      
      if (authResult.authenticated && authStore.token) {
        userStore.setToken(authStore.token);
        
        // 若沒有緩存數據或需要刷新，獲取用戶數據
        if (!hasCachedUser) {
          try {
            await userStore.getUserData();
          } catch (userError) {
            console.error('獲取用戶數據失敗', userError);
          }
        }
        
        // 初始化WebSocket连接
        await this.initializeWebSockets();
        
        return { isAuthenticated: true };
    } else {
      // 嘗試從 user store 初始化令牌
      if (!hasCachedUser) {
        await userStore.initializeToken();
      }
      
      // 如果 user store 有有效令牌，初始化WebSocket連接
      if (userStore.isLoggedIn) {
        await this.initializeWebSockets();
          return { isAuthenticated: true };
        }
        
        return { isAuthenticated: false };
      }
    } catch (error) {
      console.error('認證初始化失敗:', error);
      return { isAuthenticated: false };
    }
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
    console.log('[AuthService] 開始處理登出流程');
    
    try {
      // 獲取需要的 store 引用
    const authStore = useAuthStore();
    const userStore = useUserStore();
    const chatroomStore = useChatroomStore();
    const notificationStore = useNotificationStore();
    
      // 快速重置前端狀態層以便立即反映給使用者
      await this.finalizeLogout(authStore, userStore);
      
      // 診斷信息
      console.log('[AuthService] 登出前檢查 store 狀態:', {
        'authStore 存在': !!authStore,
        'userStore 存在': !!userStore,
        'authStore.token 存在': !!authStore.token,
        'userStore.token 存在': !!userStore.token
      });
      
      // 以下操作將在後台完成，不阻塞 UI
      setTimeout(async () => {
        try {
          // 1. 關閉 WebSocket 連線
          this.closeAllWebSockets();
          console.log('[AuthService] 所有WebSocket連線已關閉');
          
          // 2. 重置聊天室狀態
          chatroomStore.resetState();
          notificationStore.resetState();
          
          // 3. 調用後端登出 API
          try {
            await axios.post('/api/v1/auth/logout', {}, {
              withCredentials: true
            });
            console.log('[AuthService] 登出 API 調用成功');
          } catch (apiError) {
            console.warn('[AuthService] 登出 API 調用失敗', apiError);
          }
          
          console.log('[AuthService] 後台清理操作完成');
        } catch (error) {
          console.error('[AuthService] 後台登出清理操作失敗:', error);
        }
      }, 0);
      
      // 立即返回成功，讓 UI 可以立即響應
      return true;
    } catch (error) {
      // 詳細記錄錯誤信息
      console.error('[AuthService] 登出過程中發生錯誤:', error);
      if (error instanceof Error) {
        console.error('[AuthService] 錯誤類型:', error.name);
        console.error('[AuthService] 錯誤訊息:', error.message);
        console.error('[AuthService] 錯誤堆疊:', error.stack);
      }
      
      // 即使發生錯誤，也確保清除前端狀態
      const authStore = useAuthStore();
      const userStore = useUserStore();
      
      try {
        // 直接清除本地狀態
        console.log('[AuthService] 嘗試手動清除狀態');
        if (authStore) {
          // 手動重置關鍵狀態
          authStore.token = null;
          authStore.refreshToken = null;
          console.log('[AuthService] 手動清除 authStore 狀態完成');
        }
        
        if (userStore) {
          // 手動重置關鍵狀態，只設置那些可寫的屬性
          userStore.user = null;
          userStore.token = null;
          // 移除 isLoggedIn 的賦值，因為它是一個計算屬性
          console.log('[AuthService] 手動清除 userStore 狀態完成');
        }
        
        localStorage.removeItem('keepLoggedIn');
        
        // 清除令牌，使用非阻塞方式
        setTimeout(() => tokenService.clearTokens(), 0);
        
        // 清除 axios 授權標頭
        delete axios.defaults.headers.common['Authorization'];
      } catch (e) {
        console.error('[AuthService] 登出時清除本地狀態失敗:', e);
      }
      
      return false;
    }
  },
  
  /**
   * 完成登出流程的最後步驟 (只處理前端狀態，不呼叫後端 API)
   * @private
   */
  async finalizeLogout(authStore: any, userStore: any): Promise<boolean> {
    try {
      console.log('[AuthService] 開始快速清除前端狀態');
      
      // 完全移除對 $reset() 的嘗試，直接手動重置，減少不必要的等待
      
      // 1. 手動重置 authStore 的狀態
      if (authStore) {
        authStore.token = null;
        authStore.refreshToken = null;
        authStore.error = null;
        console.log('[AuthService] Auth store 狀態已重置');
      }
      
      // 2. 手動重置 userStore 的狀態
      if (userStore) {
        userStore.user = null;
        userStore.token = null;
        console.log('[AuthService] User store 狀態已重置');
      }
      
      // 3. 立即清除本地存儲
      localStorage.removeItem('keepLoggedIn');
      
      // 4. 立即移除授權標頭
      delete axios.defaults.headers.common['Authorization'];
      
      // 5. 啟動令牌清除（不等待其完成）
      // 並行處理令牌清除，不阻塞登出流程完成
      setTimeout(() => {
        try {
          tokenService.clearTokens();
        } catch (tokenError) {
          console.warn('[AuthService] 清除令牌時出現非阻塞錯誤:', tokenError);
        }
      }, 0);
      
      console.log('[AuthService] 前端狀態快速清除完成');
      return true;
    } catch (e) {
      console.error('[AuthService] 清除前端狀態失敗:', e);
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
  },

  /**
   * 嘗試使用 HTTP-only cookie 中的刷新令牌獲取新的訪問令牌
   */
  async tryRefreshToken(): Promise<{ success: boolean, accessToken?: string }> {
    try {
      console.log('[AuthService] 嘗試使用刷新令牌獲取新的訪問令牌');
      
      // 使用統一的tokenService刷新機制，避免重複刷新
      const refreshed = await tokenService.refreshTokenIfNeeded();
      
      if (refreshed) {
        // 獲取刷新後的token
        const accessToken = tokenService.getAccessToken();
        
        if (accessToken) {
          // 安全地顯示 token 部分內容
          const maskToken = (token: string): string => {
            if (token.length <= 8) return '***' + token.substring(token.length - 3);
            return token.substring(0, 4) + '...' + token.substring(token.length - 4);
          };
          
          console.log(`[AuthService] 成功獲取新的訪問令牌: ${maskToken(accessToken)}`);
          return {
            success: true,
            accessToken: accessToken
          };
        }
      }
      
      console.log('[AuthService] 刷新請求未能獲得新的訪問令牌');
      return { success: false };
    } catch (error) {
      console.error('[AuthService] 刷新令牌失敗:', error);
      return { success: false };
    }
  }
};

export default authService; 