import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface User {
  id: number
  username: string
  avatar?: string
  email: string
  role: string // 'admin', 'regular', 'premium'
  lastLogin?: string
  createdAt: string
}

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const isTokenValid = ref<boolean>(false)
  const isLoggedIn = computed(() => !!user.value && !!token.value && isTokenValid.value)
  
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
    }
  }
  
  return { 
    user, 
    token, 
    isTokenValid, 
    isLoggedIn, 
    setUser, 
    setToken, 
    logout, 
    initializeToken, 
    validateToken, 
    syncWithAuthStore 
  }
}) 