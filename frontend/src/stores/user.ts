import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import { tokenService } from '@/services/token'

export interface User {
  id: number
  username: string
  avatar?: string
  email: string
  role: string // 'admin', 'regular', 'premium'
  lastLogin?: string
  createdAt: string
  referralCode?: string  // 用戶推薦碼
  referrerId?: number    // 推薦人ID
}

// 常量，用於localStorage鍵名
const USER_DATA_CACHE_KEY = 'user_data_cache';
const USER_CACHE_TIMESTAMP_KEY = 'user_cache_timestamp';

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const isTokenValid = ref<boolean>(false)
  const isLoggedIn = computed(() => !!user.value && !!token.value && isTokenValid.value)
  const isAdmin = computed(() => !!user.value && user.value.role === 'admin')
  const isUserLoading = ref<boolean>(false)
  const userError = ref<string | null>(null)
  const lastFetchTime = ref<number>(0)
  const cacheDuration = ref<number>(60000) // 1分鐘快取
  const persistentCacheDuration = ref<number>(24 * 60 * 60 * 1000) // 24小時持久化緩存
  const maxRetries = ref<number>(3) // 最大重試次數
  
  // 緩存版本控制，用於緩存失效
  const CACHE_VERSION = '1.0.1'
  const USER_CACHE_VERSION_KEY = 'user_cache_version'
  
  // 從localStorage載入用戶資料緩存
  function loadUserFromCache() {
    try {
      // 檢查緩存版本，如果版本不一致則不使用緩存
      const cacheVersion = localStorage.getItem(USER_CACHE_VERSION_KEY)
      if (cacheVersion !== CACHE_VERSION) {
        console.log('用戶緩存版本已更新，清除舊緩存')
        localStorage.removeItem(USER_DATA_CACHE_KEY)
        localStorage.removeItem(USER_CACHE_TIMESTAMP_KEY)
        localStorage.setItem(USER_CACHE_VERSION_KEY, CACHE_VERSION)
        return false
      }
      
      const cachedUserJson = localStorage.getItem(USER_DATA_CACHE_KEY);
      const cachedTimestamp = localStorage.getItem(USER_CACHE_TIMESTAMP_KEY);
      
      if (cachedUserJson && cachedTimestamp) {
        const cachedUser = JSON.parse(cachedUserJson) as User;
        const timestamp = parseInt(cachedTimestamp);
        
        // 如果緩存未過期，使用緩存數據
        const now = Date.now();
        if (now - timestamp < persistentCacheDuration.value) { // 使用持久化緩存期限
          user.value = cachedUser;
          lastFetchTime.value = timestamp;
          // 加載緩存用戶數據時也更新令牌狀態，確保立即顯示已登錄
          isTokenValid.value = true;
          
          // 優先級提示
          const freshness = now - timestamp < cacheDuration.value ? '新鮮' : '過期但可用';
          console.log(`從持久化緩存載入用戶資料(${freshness}):`, cachedUser.username);
          
          // 在後台自動刷新過期但仍可用的緩存
          if (now - timestamp > cacheDuration.value) {
            setTimeout(() => {
              console.log('緩存資料已過期，在後台自動更新...');
              getUserData(true).catch(err => console.warn('後台更新緩存失敗:', err));
            }, 0);
          }
          
          return true;
        } else {
          console.log('持久化緩存已完全過期，需要重新獲取用戶資料');
        }
      }
    } catch (error) {
      console.error('載入用戶緩存失敗:', error);
    }
    return false;
  }
  
  // 將用戶資料保存到持久化緩存
  function saveUserToCache(userData: User) {
    try {
      localStorage.setItem(USER_DATA_CACHE_KEY, JSON.stringify(userData));
      localStorage.setItem(USER_CACHE_TIMESTAMP_KEY, lastFetchTime.value.toString());
      localStorage.setItem(USER_CACHE_VERSION_KEY, CACHE_VERSION);
      console.log('用戶資料已保存到持久化緩存');
    } catch (error) {
      console.error('保存用戶緩存失敗:', error);
    }
  }
  
  // 監視用戶資料變化，自動更新緩存
  watch(user, (newUserData) => {
    if (newUserData) {
      saveUserToCache(newUserData);
    }
  });
  
  // 從多個來源嘗試獲取有效令牌
  function getEffectiveToken() {
    // 首先嘗試使用組件內的 token
    if (token.value) {
      return token.value;
    }
    
    // 使用導入的 tokenService 獲取令牌 (如果可用)
    try {
      const accessToken = tokenService.getAccessToken();
      if (accessToken) {
        return accessToken;
      }
    } catch (e) {
      console.warn('嘗試從 tokenService 獲取令牌失敗', e);
    }
    
    // 最後才考慮使用 localStorage (向後兼容)
    return null;
  }
  
  // 直接從API獲取用戶資料
  async function getUserData(forceRefresh = false, retryCount = 0) {
    try {
      // 如果有快取且未過期且不強制刷新，直接使用快取
      const now = Date.now()
      if (!forceRefresh && 
          user.value && 
          (now - lastFetchTime.value < cacheDuration.value)) {
        return user.value
      }

      // 獲取有效令牌
      const currentToken = getEffectiveToken();
      if (!currentToken) {
        throw new Error('未登入，無法獲取用戶資料')
      }

      // 更新 store 中的令牌
      if (token.value !== currentToken) {
        token.value = currentToken;
      }

      isUserLoading.value = true
      userError.value = null

      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const response = await axios.get(`${apiUrl}/api/v1/auth/me`, {
        headers: {
          'Authorization': `Bearer ${currentToken}`
        }
      })

      if (response.status === 200) {
        // 將API回傳的數據轉換為User格式
        const userData = response.data
        const formattedUser: User = {
          id: userData.id,
          username: userData.username,
          email: userData.email,
          role: userData.is_admin ? 'admin' : 'regular',
          createdAt: userData.created_at,
          avatar: userData.avatar_url,
          referralCode: userData.referral_code,
          referrerId: userData.referrer_id
        }

        // 更新用戶資料和快取時間
        user.value = formattedUser
        lastFetchTime.value = now
        isTokenValid.value = true
        
        // 將用戶資料保存到持久化緩存
        saveUserToCache(formattedUser);
        
        return formattedUser
      } else {
        throw new Error('獲取用戶資料失敗')
      }
    } catch (error) {
      console.error('獲取用戶資料錯誤:', error)
      userError.value = error instanceof Error ? error.message : '獲取用戶資料失敗'
      
      // 添加重試邏輯，在網絡問題或令牌剛設置時有用
      if (retryCount < maxRetries.value) {
        console.log(`嘗試重新獲取用戶資料，重試次數: ${retryCount + 1}/${maxRetries.value}`)
        // 延遲重試，給系統一些時間傳播令牌
        await new Promise(resolve => setTimeout(resolve, 800 * (retryCount + 1)));
        return getUserData(forceRefresh, retryCount + 1);
      }
      
      throw error
    } finally {
      if (retryCount === 0 || retryCount >= maxRetries.value) {
        isUserLoading.value = false
      }
    }
  }
  
  // 登录成功后设置用户信息
  function setUser(userData: User) {
    user.value = userData
    lastFetchTime.value = Date.now() // 更新快取時間
    // 將用戶資料保存到持久化緩存
    saveUserToCache(userData);
  }
  
  // 设置认证令牌
  function setToken(authToken: string) {
    token.value = authToken
    // 不再保存令牌到 localStorage
    isTokenValid.value = true
  }
  
  // 退出登录
  function logout() {
    user.value = null
    token.value = null
    isTokenValid.value = false
    lastFetchTime.value = 0
    // 不再從 localStorage 中移除令牌，僅清除用戶資料緩存
    localStorage.removeItem(USER_DATA_CACHE_KEY)
    localStorage.removeItem(USER_CACHE_TIMESTAMP_KEY)
    console.log('用户已登出，所有用户数据和令牌已清除')
  }
  
  // 从本地存储初始化令牌
  async function initializeToken() {
    // 先嘗試從緩存載入用戶資料
    const hasCachedUser = loadUserFromCache();
    
    // 獲取有效令牌
    const storedToken = getEffectiveToken();
    if (storedToken) {
      console.log('找到有效令牌，正在驗證...')
      token.value = storedToken
      await validateToken()
    } else {
      console.log('無法獲取有效令牌')
      isTokenValid.value = false
      
      // 如果沒有令牌但有緩存用戶，清除緩存
      if (hasCachedUser) {
        user.value = null;
        localStorage.removeItem(USER_DATA_CACHE_KEY);
        localStorage.removeItem(USER_CACHE_TIMESTAMP_KEY);
      }
    }
  }
  
  // 验证令牌是否有效
  async function validateToken() {
    if (!token.value) {
      isTokenValid.value = false
      return false
    }

    try {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
      const response = await fetch(`${apiUrl}/api/v1/auth/verify-token`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token.value}`
        }
      })

      if (response.ok) {
        console.log('令牌验证成功')
        isTokenValid.value = true
        
        // 令牌有效，自動獲取用戶資料
        try {
          await getUserData(true)
        } catch (err) {
          // 獲取資料失敗不影響令牌驗證結果
          console.error('令牌驗證成功但獲取用戶資料失敗', err)
        }
        
        return true
      } else {
        console.log('令牌无效或已过期')
        isTokenValid.value = false
        // 如果令牌无效，清除它
        logout()
        return false
      }
    } catch (error) {
      console.error('令牌验证错误:', error)
      isTokenValid.value = false
      return false
    }
  }
  
  // 同步认证状态，从 auth store 同步令牌和用户数据
  function syncWithAuthStore(authToken: string, userData: User | null) {
    if (authToken) {
      token.value = authToken
      isTokenValid.value = true
    }
    
    if (userData) {
      user.value = userData
      lastFetchTime.value = Date.now()
      // 將用戶資料保存到持久化緩存
      saveUserToCache(userData);
    }
  }
  
  return { 
    user, 
    token, 
    isTokenValid, 
    isLoggedIn,
    isAdmin, 
    isUserLoading,
    userError,
    cacheDuration,
    persistentCacheDuration,
    maxRetries,
    setUser, 
    setToken, 
    logout, 
    initializeToken, 
    validateToken, 
    syncWithAuthStore,
    getUserData,
    getEffectiveToken,
    loadUserFromCache
  }
}) 