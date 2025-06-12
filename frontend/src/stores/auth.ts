import { defineStore } from 'pinia'
import { ref, computed, inject } from 'vue'
import axios from 'axios'
// 移除舊的 TokenManager 引用
// import type { TokenManager } from '@/utils/tokenManager'
// import { getTokenManager } from '@/services/tokenService'
// 改為引入新的 TokenService
import { tokenService } from '@/services/token'
import router from '@/router'
// 引入 userStore，用於同步用戶資料
import { useUserStore } from '@/stores/user'

interface LoginCredentials {
  username: string
  password: string
  keepLoggedIn?: boolean
}

interface RegisterData {
  username: string
  email: string
  password: string
  confirm_password: string
  referral_code?: string
}

// 令牌刷新的防抖和冷卻控制
const REFRESH_DEBOUNCE_TIME = 2000;  // 2秒內的重複刷新請求會被合併
const REFRESH_COOLDOWN_TIME = 10000; // 10秒冷卻時間，防止頻繁刷新
let refreshPromise: Promise<boolean> | null = null;
let lastRefreshTime = 0;
let refreshInProgress = false;

export const useAuthStore = defineStore('auth', () => {
  // 不再獲取 TokenManager 單例
  // const tokenManager = getTokenManager();
  // 直接使用 tokenService

  // 引入userStore
  const userStore = useUserStore();
  
  // 初始化token，嘗試從userStore獲取
  const token = ref<string | null>(userStore.token);
  const refreshToken = ref<string | null>(null);
  const loading = ref<boolean>(false);
  const error = ref<string | null>(null);
  
  // 令牌傳播延遲參數 - 令牌獲取後多久可以安全地用於獲取用戶數據
  const tokenPropagationDelay = ref<number>(1500); // 增加到1500毫秒，確保令牌在後端完成傳播
  
  // 認證狀態計算屬性 - 同時考慮userStore的登入狀態
  const isAuthenticated = computed(() => !!token.value || userStore.isLoggedIn);

  // 設置axios授權頭的統一方法
  const setAxiosAuthHeader = (authToken: string) => {
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`
  }

  // 等待令牌傳播的輔助函數
  const waitForTokenPropagation = async (customDelay?: number) => {
    const delay = customDelay || tokenPropagationDelay.value;
    await new Promise(resolve => setTimeout(resolve, delay));
  }

  // 清除認證資訊
  const clearAuth = () => {
    // 清除store中的令牌
    token.value = null;
    refreshToken.value = null;
    
    // 清除axios的Authorization header
    delete axios.defaults.headers.common['Authorization'];
  }

  // 登錄
  const login = async (credentials: LoginCredentials) => {
    try {
      loading.value = true
      error.value = null
      
      // 準備FormData
      const formData = new FormData()
      formData.append('username', credentials.username)
      formData.append('password', credentials.password)
      
      if (credentials.keepLoggedIn !== undefined) {
        formData.append('keep_logged_in', credentials.keepLoggedIn.toString())
      }
      
      const response = await axios.post('/api/v1/auth/login', formData, {
        withCredentials: true  // 確保能接收 HTTP-only cookie
      })
      
      // 從響應中獲取token
      const authToken = response.data.access_token
      const expiresIn = response.data.expires_in
      
      if (!authToken) {
        throw new Error('登錄響應中沒有找到token')
      }
      
      // 安全地顯示 token 部分內容
      const maskToken = (token: string): string => {
        if (token.length <= 8) return '***' + token.substring(token.length - 3);
        return token.substring(0, 4) + '...' + token.substring(token.length - 4);
      };
      
      console.log(`【AUTH】登入成功獲取的 access token: ${maskToken(authToken)}`);
      
      // 儲存keepLoggedIn狀態
      localStorage.setItem('keepLoggedIn', credentials.keepLoggedIn ? 'true' : 'false')
      
      // 保存token到store
      token.value = authToken
      
      // 使用 tokenService 統一管理令牌
      tokenService.setTokens(
        authToken, 
        '',        // 不再使用 refreshToken (由 HTTP-only cookie 管理)
        'bearer', 
        expiresIn
      )
      
      // 設置axios授權頭
      setAxiosAuthHeader(authToken)
      
      // 等待token在後端服務傳播
      await waitForTokenPropagation()
      
      // 同步用戶資料 - 新增代碼
      userStore.setToken(authToken)
      
      // 觸發登錄成功事件，初始化聊天和通知系統
      window.dispatchEvent(new Event('login-authenticated'))
      
      // 強制獲取用戶資料 - 新增代碼
      try {
        await userStore.getUserData(true)
      } catch (err) {
        console.error('登錄成功但獲取用戶資料失敗:', err)
      }
      
      return {
        success: true,
        token: authToken
      }
    } catch (error: any) {
      console.error('登錄錯誤:', error)
      error.value = error.response?.data?.detail || '登錄失敗，請檢查用戶名和密碼'
      throw new Error(error.response?.data?.detail || '登錄失敗，請檢查用戶名和密碼')
    } finally {
      loading.value = false
    }
  }

  // 使用Google登錄
  const loginWithGoogle = async (keepLoggedIn: boolean = true) => {
    try {
      loading.value = true
      const response = await axios.get('/api/v1/auth/google/login', {
        params: { keep_logged_in: keepLoggedIn }
      })
      return response.data.authorization_url
    } catch (error: any) {
      console.error('Google登錄錯誤:', error)
      error.value = '無法啟動Google登錄'
      throw new Error('無法啟動Google登錄')
    } finally {
      loading.value = false
    }
  }

  // 處理Google登錄回調
  const handleGoogleCallback = async (
    accessTokenParam: string, 
    refreshTokenParam: string, 
    keepLoggedIn: boolean = true, 
    expiresIn?: number,
    refreshTokenExpiresIn?: number
  ) => {
    try {
      loading.value = true
      
      // 儲存keepLoggedIn狀態
      localStorage.setItem('keepLoggedIn', keepLoggedIn ? 'true' : 'false')
      
      // 保存token到store
      token.value = accessTokenParam
      refreshToken.value = refreshTokenParam
      
      // 先手動設置axios授權頭，確保後續API請求帶有token
      setAxiosAuthHeader(accessTokenParam)
      
      // 關鍵優化：使用統一的令牌傳播等待函數，Google登錄使用更長的延遲
      // 因為涉及第三方認證，可能需要更長時間在後端系統中傳播
      await waitForTokenPropagation(2000); // 增加到2000毫秒
      
      // 使用 tokenService 統一管理令牌
      try {
        const tokensSetResult = await tokenService.setTokens(
          accessTokenParam, 
          '', // 不再使用 refreshToken，由 HTTP-only cookie 管理
          'bearer', 
          expiresIn,
          refreshTokenExpiresIn
        )
        
        // 檢查是否成功設置令牌
        if (!tokensSetResult) {
          console.error('設置令牌失敗');
        }
      } catch (tokenError) {
        console.error('設置 tokenService 時出錯:', tokenError);
      }
      
      // 等待Google令牌在後端服務傳播（需要更長的時間）
      await waitForTokenPropagation(2000);
      
      try {
        console.log('嘗試獲取用戶資料');
        userStore.setToken(accessTokenParam)
        await userStore.getUserData(true)
        console.log('成功獲取用戶資料')
        
        // 觸發認證事件
        window.dispatchEvent(new Event('login-authenticated'))
        
        return {
          success: true,
          token: accessTokenParam
        }
      } catch (error) {
        console.error('獲取用戶資料失敗:', error)
        throw new Error('獲取用戶資料失敗')
      }
    } catch (error: any) {
      console.error('處理Google回調錯誤:', error)
      error.value = error.response?.data?.detail || '處理Google登錄失敗'
      throw new Error(error.response?.data?.detail || '處理Google登錄失敗')
    } finally {
      loading.value = false
    }
  }

  // 注冊
  const register = async (data: RegisterData) => {
    try {
      loading.value = true
      error.value = null
      
      const response = await axios.post('/api/v1/auth/register', data)
      
      return {
        success: true,
        message: '註冊成功，請登錄'
      }
    } catch (error: any) {
      console.error('註冊錯誤:', error)
      error.value = error.response?.data?.detail || '註冊失敗，請檢查輸入信息'
      throw new Error(error.response?.data?.detail || '註冊失敗，請檢查輸入信息')
    } finally {
      loading.value = false
    }
  }

  // 刷新訪問令牌 - 帶有防抖和冷卻機制
  const refreshAccessToken = async (keepLoggedIn = true) => {
    try {
      // 檢查是否有刷新正在進行
      if (refreshPromise) {
        console.log('[AuthStore] 已有刷新請求進行中，使用現有請求');
        return refreshPromise;
      }
      
      // 檢查冷卻時間
      const now = Date.now();
      if (refreshInProgress || (now - lastRefreshTime < REFRESH_COOLDOWN_TIME && lastRefreshTime > 0)) {
        console.log(`[AuthStore] 刷新操作在冷卻中，剩餘時間: ${(REFRESH_COOLDOWN_TIME - (now - lastRefreshTime)) / 1000}秒`);
        // 返回上次刷新的結果
        return !!token.value;
      }
      
      console.log('[AuthStore] 開始刷新訪問令牌');
      refreshInProgress = true;
      
      // 創建一個新的刷新請求
      refreshPromise = (async () => {
        try {
          // 使用統一的tokenService刷新機制，避免重複刷新
          localStorage.setItem('keepLoggedIn', keepLoggedIn.toString());
          const refreshed = await tokenService.refreshTokenIfNeeded();
          
          if (refreshed) {
            // 獲取刷新後的token
            const newAccessToken = tokenService.getAccessToken();
            
            if (newAccessToken) {
              // 更新本地token
              token.value = newAccessToken;
              
              // 更新 axios 授權頭
              setAxiosAuthHeader(newAccessToken);
              
              // 更新用戶store的token
              userStore.setToken(newAccessToken);
              
              console.log('[AuthStore] 訪問令牌刷新成功');
              lastRefreshTime = Date.now();
              return true;
            }
          }
          
          console.log('[AuthStore] 令牌刷新失敗');
          return false;
        } catch (error) {
          console.error('[AuthStore] 刷新令牌錯誤:', error);
          return false;
        } finally {
          // 重置刷新狀態
          refreshInProgress = false;
          
          // 延遲重置 refreshPromise，以便在防抖時間內的請求可以復用
          setTimeout(() => {
            refreshPromise = null;
          }, REFRESH_DEBOUNCE_TIME);
        }
      })();
      
      return refreshPromise;
    } catch (error) {
      console.error('[AuthStore] 刷新令牌過程中發生意外錯誤:', error);
      refreshInProgress = false;
      refreshPromise = null;
      return false;
    }
  }

  // 登出
  const logout = async () => {
    try {
      loading.value = true
      
      // 檢查是否由 authService.logout() 調用
      const isCalledFromAuthService = new Error().stack?.includes('authService');
      
      // 如果是從 authService 調用的，則不再呼叫後端 API
      if (!isCalledFromAuthService) {
        // 呼叫登出 API，清除 HTTP-only cookie
        try {
          await axios.post('/api/v1/auth/logout', {}, {
            withCredentials: true  // 確保發送 cookie
          });
          console.log('[AuthStore] 登出 API 調用成功');
        } catch (logoutError) {
          console.warn('[AuthStore] 登出 API 調用失敗，繼續本地登出流程', logoutError);
        }
      } else {
        console.log('[AuthStore] 從 authService 調用，跳過 API 請求');
      }
      
      // 清除 tokenService 中的令牌
      tokenService.clearTokens();
      
      // 清除本地存儲的令牌
      clearAuth();
      
      // 分發登出事件
      window.dispatchEvent(new Event('auth:logout'));
      
      // 將用戶重定向到首頁，而非直接使用特定的路由名稱
      try {
        // 判斷當前路由是否需要認證，如果需要則跳轉到首頁
        const currentRoute = router.currentRoute.value;
        if (currentRoute.meta.requiresAuth === true && currentRoute.path !== '/') {
          await router.push('/');
        }
      } catch (routerError) {
        console.warn('登出後導航失敗，但不影響登出流程', routerError);
      }
      
      return {
        success: true,
        message: '登出成功'
      };
    } catch (error: any) {
      console.error('登出錯誤:', error);
      error.value = '登出發生錯誤';
      
      // 即使出錯也嘗試清除令牌
      try {
        tokenService.clearTokens();
        clearAuth();
      } catch {}
      
      return {
        success: false,
        message: '登出發生錯誤'
      };
    } finally {
      loading.value = false;
    }
  }

  // 初始化認證狀態（應用啟動時調用）
  const initAuth = async () => {
    try {
      // 檢查 tokenService 中是否有有效令牌
      if (tokenService.isAuthenticated()) {
        token.value = tokenService.getAccessToken()
        refreshToken.value = tokenService.getRefreshToken()
        
        // 設置 axios 授權頭
        if (token.value) {
          setAxiosAuthHeader(token.value)
          
          try {
            // 同步用戶資料
            userStore.setToken(token.value)
            await userStore.getUserData(true)
            
            return { authenticated: true }
          } catch (e) {
            console.error('初始化認證時獲取用戶資料失敗：', e)
            
            // 檢查是否可以刷新令牌
            if (tokenService.isTokenExpired() && refreshToken.value) {
              // 嘗試刷新令牌並重新獲取用戶資料
              const keepLoggedIn = localStorage.getItem('keepLoggedIn') !== 'false'; // 默認為 true
              const refreshed = await refreshAccessToken(keepLoggedIn)
              if (refreshed) {
                // 再次嘗試獲取用戶資料
                userStore.setToken(token.value!)
                await userStore.getUserData(true)
                return { authenticated: true }
              } else {
                // 刷新失敗，清除認證狀態
                await logout()
                return { authenticated: false, reason: 'refresh_failed' }
              }
            } else {
              // 令牌未過期但仍無法獲取用戶資料，可能是令牌已被撤銷
              await logout()
              return { authenticated: false, reason: 'token_revoked' }
            }
          }
        }
      }
      
      // 沒有有效令牌
      return { authenticated: false, reason: 'no_token' }
    } catch (error) {
      console.error('初始化認證狀態錯誤:', error)
      // 發生錯誤，清除可能損壞的認證狀態
      clearAuth()
      return { authenticated: false, reason: 'error' }
    }
  }

  // 檢查認證狀態
  const checkAuth = async () => {
    try {
      // 使用 tokenService 檢查令牌狀態
      const tokenStatus = tokenService.getTokenStatus()
      
      // 如果沒有令牌或令牌已過期，返回 false
      if (!tokenStatus.isAuthenticated) {
        // 嘗試刷新令牌
        if (tokenStatus.refreshToken && (tokenStatus.isExpired || tokenStatus.isExpiringSoon)) {
          const keepLoggedIn = localStorage.getItem('keepLoggedIn') !== 'false'; // 默認為 true
          const refreshed = await refreshAccessToken(keepLoggedIn)
          return refreshed
        }
        return false
      }
      
      return true
    } catch (error) {
      console.error('檢查認證狀態錯誤:', error)
      return false
    }
  }
  
  // 預熱CCXT連接 - 在用戶登錄後調用，減少首次交易的延遲
  const preheatCcxtConnections = async () => {
    try {
      if (!tokenService.isAuthenticated()) {
        console.log('用戶未登錄，不需要預熱CCXT連接')
        return false
      }
      
      console.log('預熱CCXT連接...')
      await axios.post('/api/v1/trading/preheat')
      console.log('CCXT連接預熱成功')
      return true
    } catch (error) {
      console.error('預熱CCXT連接失敗:', error)
      // 預熱失敗不影響用戶使用，只是可能會有首次交易延遲
      return false
    }
  }

  return {
    token,
    refreshToken,
    loading,
    error,
    isAuthenticated,
    login,
    loginWithGoogle,
    handleGoogleCallback,
    register,
    logout,
    refreshAccessToken,
    initAuth,
    checkAuth,
    clearAuth,
    preheatCcxtConnections
  }
}) 