import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

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
  
  // 直接從API獲取用戶資料
  async function getUserData(forceRefresh = false) {
    try {
      // 如果有快取且未過期且不強制刷新，直接使用快取
      const now = Date.now()
      if (!forceRefresh && 
          user.value && 
          (now - lastFetchTime.value < cacheDuration.value)) {
        return user.value
      }

      // 確保有 token
      const currentToken = token.value || localStorage.getItem('auth_token')
      if (!currentToken) {
        throw new Error('未登入，無法獲取用戶資料')
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
        return formattedUser
      } else {
        throw new Error('獲取用戶資料失敗')
      }
    } catch (error) {
      console.error('獲取用戶資料錯誤:', error)
      userError.value = error instanceof Error ? error.message : '獲取用戶資料失敗'
      throw error
    } finally {
      isUserLoading.value = false
    }
  }
  
  // 登录成功后设置用户信息
  function setUser(userData: User) {
    user.value = userData
  }
  
  // 设置认证令牌
  function setToken(authToken: string) {
    token.value = authToken
    localStorage.setItem('auth_token', authToken)
    isTokenValid.value = true
  }
  
  // 退出登录
  function logout() {
    user.value = null
    token.value = null
    isTokenValid.value = false
    lastFetchTime.value = 0
    localStorage.removeItem('auth_token')
    console.log('用户已登出，所有用户数据和令牌已清除')
  }
  
  // 从本地存储初始化令牌
  async function initializeToken() {
    const storedToken = localStorage.getItem('auth_token')
    if (storedToken) {
      console.log('从本地存储找到令牌，验证其有效性')
      token.value = storedToken
      await validateToken()
    } else {
      console.log('本地存储中没有找到令牌')
      isTokenValid.value = false
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
    setUser, 
    setToken, 
    logout, 
    initializeToken, 
    validateToken, 
    syncWithAuthStore,
    getUserData
  }
}) 