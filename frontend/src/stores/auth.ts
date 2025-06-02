import { defineStore } from 'pinia'
import { ref, computed, inject } from 'vue'
import axios from 'axios'
// 移除直接導入，改用全域實例
// import tokenManager from '@/utils/tokenManager'
import type { TokenManager } from '@/utils/tokenManager'
// 引入TokenService單例
import { getTokenManager } from '@/services/tokenService'
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

export const useAuthStore = defineStore('auth', () => {
  // 獲取TokenManager單例，不再從依賴注入獲取
  const tokenManager = getTokenManager();

  const token = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)
  
  // 令牌傳播延遲參數 - 令牌獲取後多久可以安全地用於獲取用戶數據
  const tokenPropagationDelay = ref<number>(1500) // 增加到1500毫秒，確保令牌在後端完成傳播
  
  // 認證狀態計算屬性
  const isAuthenticated = computed(() => !!token.value)

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
      
      const response = await axios.post('/api/v1/auth/login', formData)
      
      // 從響應中獲取token
      const authToken = response.data.access_token
      const newRefreshToken = response.data.refresh_token
      const expiresIn = response.data.expires_in
      
      if (!authToken || !newRefreshToken) {
        throw new Error('登錄響應中沒有找到token')
      }
      
      // 儲存keepLoggedIn狀態
      localStorage.setItem('keepLoggedIn', credentials.keepLoggedIn ? 'true' : 'false')
      
      // 保存token到store
      token.value = authToken
      refreshToken.value = newRefreshToken
      
      // 使用tokenManager統一管理令牌
      tokenManager.setTokens(
        authToken, 
        newRefreshToken, 
        'bearer', 
        expiresIn
      )
      
      // 設置axios授權頭
      setAxiosAuthHeader(authToken)
      
      // 等待token在後端服務傳播
      await waitForTokenPropagation()
      
      // 同步用戶資料 - 新增代碼
      const userStore = useUserStore()
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
  const loginWithGoogle = async (keepLoggedIn: boolean = false) => {
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
    keepLoggedIn: boolean = false, 
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
      
      // 確保刷新令牌正確保存到localStorage
      localStorage.setItem('token', accessTokenParam);
      localStorage.setItem('refreshToken', refreshTokenParam);
      localStorage.setItem('tokenType', 'bearer');
      
      // 先手動設置axios授權頭，確保後續API請求帶有token
      setAxiosAuthHeader(accessTokenParam)
      
      // 關鍵優化：使用統一的令牌傳播等待函數，Google登錄使用更長的延遲
      // 因為涉及第三方認證，可能需要更長時間在後端系統中傳播
      await waitForTokenPropagation(2000); // 增加到2000毫秒
      
      // 再使用tokenManager統一管理令牌
      // 讓tokenManager根據keepLoggedIn狀態決定過期時間
      try {
        const tokensSetResult = await tokenManager.setTokens(
          accessTokenParam, 
          refreshTokenParam, 
          'bearer', 
          expiresIn,
          refreshTokenExpiresIn
        )
        
        // 如果tokenManager中沒有設置刷新令牌或與localStorage中不一致，則嘗試強制同步
        if (!tokenManager.getRefreshToken() || tokenManager.getRefreshToken() !== refreshTokenParam) {
          tokenManager.forceUpdateTokens(accessTokenParam, refreshTokenParam, 'bearer');
        }
      } catch (tokenError) {
        console.error('設置tokenManager時出錯:', tokenError);
        // 即使tokenManager設置失敗，依然繼續流程
      }
      
      // 同步用戶資料並強制獲取 - 新增代碼
      try {
        const userStore = useUserStore()
        userStore.setToken(accessTokenParam)
        // 確保 auth_token 也被正確設置
        localStorage.setItem('auth_token', accessTokenParam)
        await userStore.getUserData(true)
      } catch (userError) {
        console.error('Google登錄成功但獲取用戶資料失敗:', userError)
        // 繼續流程，不影響登錄結果
      }
      
      return true
    } catch (error: any) {
      console.error('Google回調處理錯誤:', error);
      
      // 檢查令牌是否設置成功，以便調用者判斷登錄狀態
      const hasTokensSet = !!(token.value && refreshToken.value);
      
      // 即使出錯也確保狀態被清除，但只在令牌未設置成功時清除
      if (!hasTokensSet) {
        token.value = null;
        refreshToken.value = null;
        delete axios.defaults.headers.common['Authorization'];
      }
      
      return hasTokensSet;
    } finally {
      loading.value = false
    }
  }

  // 註冊
  const register = async (data: RegisterData) => {
    try {
      loading.value = true
      error.value = null
      
      // 準備註冊數據，包含推薦碼
      const registerData = {
        username: data.username,
        email: data.email,
        password: data.password,
        confirm_password: data.confirm_password
      }
      
      // 如果提供了推薦碼，添加到請求數據中
      if (data.referral_code) {
        Object.assign(registerData, { referral_code: data.referral_code })
      }
      
      const response = await axios.post('/api/v1/auth/register', registerData)
      
      return response.data
    } catch (error: any) {
      console.error('註冊錯誤:', error)
      error.value = error.response?.data?.detail || '註冊失敗'
      throw new Error(error.response?.data?.detail || '註冊失敗')
    } finally {
      loading.value = false
    }
  }

  // 刷新令牌
  const refreshAccessToken = async (keepLoggedIn = false) => {
    try {
      loading.value = true
      
      // 使用tokenManager處理刷新邏輯，確保只有一套刷新邏輯
      const refreshSuccess = await tokenManager.refreshAccessToken(keepLoggedIn);
      
      if (!refreshSuccess) {
        clearAuth();
        error.value = '令牌刷新失敗，請重新登錄';
        return false;
      }
      
      // 從tokenManager獲取更新後的令牌狀態
      const tokenStatus = tokenManager.getTokenStatus();
      
      // 更新store中的令牌
      if (tokenStatus.accessToken) {
        token.value = tokenStatus.accessToken;
        setAxiosAuthHeader(tokenStatus.accessToken);
      }
      
      if (tokenStatus.refreshToken) {
        refreshToken.value = tokenStatus.refreshToken;
      }
      
      // 等待令牌傳播
      await waitForTokenPropagation();
      
      return true;
    } catch (error: any) {
      console.error('刷新令牌錯誤:', error);
      clearAuth();
      error.value = '令牌刷新失敗，請重新登錄';
      return false;
    } finally {
      loading.value = false;
    }
  }

  // 登出
  const logout = async () => {
    try {
      // 防止重複調用
      if (loading.value) {
        return true;
      }
      
      loading.value = true
      
      // 使用tokenManager作為唯一的登出實現者
      // 它會處理API調用、令牌清除和事件觸發
      const success = await tokenManager.logout();
      
      // 只更新本地狀態，不進行重複的令牌清除
      token.value = null;
      refreshToken.value = null;
      
      // 清除axios授權頭
      delete axios.defaults.headers.common['Authorization'];
      
      return success;
    } catch (error: any) {
      console.error('登出錯誤:', error);
      
      // 即使出錯也確保狀態被清除
      token.value = null;
      refreshToken.value = null;
      delete axios.defaults.headers.common['Authorization'];
      
      return true;
    } finally {
      loading.value = false;
    }
  }

  // 初始化認證狀態
  const initAuth = async () => {
    const savedToken = localStorage.getItem('token')
    const savedRefreshToken = localStorage.getItem('refreshToken')
    
    if (savedToken && savedRefreshToken) {
      token.value = savedToken
      refreshToken.value = savedRefreshToken
      
      // 確保 auth_token 和 token 保持一致
      localStorage.setItem('auth_token', savedToken)
      
      // 檢查令牌是否過期
      const tokenExpiry = localStorage.getItem('tokenExpiry')
      const keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true'
      
      if (tokenExpiry) {
        const expiryDate = new Date(tokenExpiry)
        const now = new Date()
        const timeUntilExpiry = expiryDate.getTime() - now.getTime();
        
        // 檢查令牌是否有效
        let isTokenValid = expiryDate > now;
        
        // 如果令牌已過期
        if (!isTokenValid) {
          // 只有在保持登入狀態下才嘗試刷新
          if (keepLoggedIn) {
            const refreshSuccess = await refreshAccessToken(keepLoggedIn)
            
            if (!refreshSuccess) {
              clearAuth()
              return false
            } else {
              isTokenValid = true;
            }
          } else {
            // 非保持登入狀態下，令牌過期直接登出
            clearAuth();
            return false;
          }
        } else if (timeUntilExpiry < 5 * 60 * 1000) {
          // 令牌即將過期（小於5分鐘）
          if (keepLoggedIn) {
            // 保持登入狀態下，提前刷新令牌
            const refreshSuccess = await refreshAccessToken(keepLoggedIn);
            if (!refreshSuccess) {
              clearAuth();
              return false;
            } else {
              isTokenValid = true;
            }
          }
          // 非保持登入狀態下，讓TokenManager處理過期登出
        } else {
          // 令牌未過期，設置全局授權頭
          setAxiosAuthHeader(savedToken);
        }
        
        // 如果令牌有效，同步並獲取用戶資料 - 新增代碼
        if (isTokenValid) {
          try {
            const userStore = useUserStore()
            userStore.setToken(savedToken)
            await userStore.getUserData(true)
          } catch (error) {
            console.error('令牌有效但獲取用戶資料失敗:', error)
          }
        }
        
        return isTokenValid;
      } else {
        clearAuth();
        return false;
      }
    }
    
    return false
  }

  // 檢查認證狀態
  const checkAuth = async () => {
    const savedToken = localStorage.getItem('token')
    if (!savedToken) {
      clearAuth()
      return false
    }

    token.value = savedToken
    // 設置默認的Authorization header
    setAxiosAuthHeader(savedToken)
    
    // 檢查令牌是否過期
    const tokenExpiry = localStorage.getItem('tokenExpiry')
    const keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true'
    
    if (tokenExpiry) {
      const expiryDate = new Date(tokenExpiry)
      const now = new Date()
      const timeUntilExpiry = expiryDate.getTime() - now.getTime();
      
      // 如果令牌已過期或即將過期
      if (expiryDate <= now) {
        // 只有在保持登入狀態下才嘗試刷新
        if (keepLoggedIn) {
          const refreshSuccess = await refreshAccessToken(keepLoggedIn);
          if (!refreshSuccess) {
            clearAuth();
            return false;
          }
        } else {
          // 非保持登入狀態下，令牌過期直接登出
          clearAuth();
          return false;
        }
      } else if (timeUntilExpiry < 5 * 60 * 1000) {
        // 令牌即將過期（小於5分鐘）
        if (keepLoggedIn) {
          // 保持登入狀態下，提前刷新令牌
          const refreshSuccess = await refreshAccessToken(keepLoggedIn);
          if (!refreshSuccess) {
            clearAuth();
            return false;
          }
        }
        // 非保持登入狀態下，讓TokenManager處理過期登出
      }
    }
    
    // 檢查令牌是否真的有效（通過TokenManager）
        const isTokenStillValid = tokenManager.isAuthenticated() && !tokenManager.isTokenExpired();
        
        if (isTokenStillValid) {
          return true;
    } else {
      clearAuth();
      return false;
    }
  }

  // 添加令牌過期事件監聽
  window.addEventListener('auth:token-expired', () => {
    // 使用tokenManager.clearTokens代替clearAuth
    // 確保只有一個地方負責清除令牌
    tokenManager.clearTokens();
    // 更新本地狀態
    token.value = null;
    refreshToken.value = null;
    delete axios.defaults.headers.common['Authorization'];
    
    // 可以在這裡添加通知用戶的邏輯
    router.push('/auth/login?expired=true');
  });

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
    initAuth,
    checkAuth,
    refreshAccessToken,
    clearAuth,
    // 導出配置參數，允許應用層面調整
    tokenPropagationDelay
  };
}); 