import axios from 'axios'
import tokenManager from './tokenManager'
import { useAuthStore } from '@/stores/auth'

// 創建API實例
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1',
  headers: {
    'Content-Type': 'application/json'
  }
})

// 請求攔截器
api.interceptors.request.use(
  (config) => {
    // 使用TokenManager獲取授權頭
    const authHeader = tokenManager.getAuthorizationHeader()
    if (authHeader) {
      config.headers.Authorization = authHeader
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 響應攔截器
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // 如果請求失敗是因為認證錯誤（401）
    if (error.response?.status === 401) {
      try {
        // 檢查錯誤訊息是否與時間同步相關
        const errorDetail = error.response.data?.detail || '';
        if (errorDetail.includes('時間同步') || 
            errorDetail.includes('時鐘') || 
            errorDetail.includes('clock') || 
            errorDetail.includes('time sync')) {
          
          console.warn('伺服器時間同步問題:', errorDetail);
          
          // 顯示友好的錯誤訊息，但不清除身份驗證
          window.dispatchEvent(new CustomEvent('time-sync-error', { 
            detail: { message: '伺服器時間同步問題，請稍後再試' } 
          }));
          
          // 創建特定的錯誤對象
          const timeError = new Error('伺服器時間同步問題');
          timeError.name = 'TimeSync';
          return Promise.reject(timeError);
        }
        
        // 嘗試刷新令牌
        const refreshSuccess = await tokenManager.refreshAccessToken()
        
        if (refreshSuccess) {
          // 更新授權頭
          const config = error.config
          const authHeader = tokenManager.getAuthorizationHeader()
          if (authHeader) {
            config.headers.Authorization = authHeader
          }
          
          // 重試失敗的請求
          return api(config)
        } else {
          // 刷新失敗，清除認證信息並顯示登入模態框
          const authStore = useAuthStore()
          await authStore.clearAuth()
          
          // 觸發顯示登入模態框事件
          window.dispatchEvent(new CustomEvent('show-login-modal', {
            detail: { reason: '您的登入狀態已失效，請重新登入' }
          }))
          return Promise.reject(error)
        }
      } catch (refreshError) {
        console.error('令牌刷新失敗:', refreshError)
        
        // 清除認證信息並顯示登入模態框
        const authStore = useAuthStore()
        await authStore.clearAuth()
        
        // 觸發顯示登入模態框事件
        window.dispatchEvent(new CustomEvent('show-login-modal', {
          detail: { reason: '登入狀態已過期，請重新登入' }
        }))
        return Promise.reject(error)
      }
    }
    
    // 處理API錯誤
    if (error.response?.data) {
      const responseData = error.response.data;
      
      // 如果API返回詳細錯誤信息，重寫錯誤信息
      if (responseData.detail) {
        error.message = responseData.detail;
      }
      
      // 處理特定類型的錯誤
      if (responseData.code === 'time_sync_error' || 
          (typeof responseData.detail === 'string' && 
           (responseData.detail.includes('時間同步') || 
            responseData.detail.includes('clock')))) {
        
        console.warn('伺服器時間同步問題:', responseData.detail);
        
        // 發送特定的事件
        window.dispatchEvent(new CustomEvent('time-sync-error', { 
          detail: { message: '伺服器時間同步問題，請稍後再試' } 
        }));
        
        // 自定義錯誤
        const timeError = new Error('伺服器時間同步問題');
        timeError.name = 'TimeSync';
        return Promise.reject(timeError);
      }
    }
    
    return Promise.reject(error)
  }
)

// 提供刷新令牌的方法
const refreshToken = async (keepLoggedIn = false) => {
  return tokenManager.refreshAccessToken(keepLoggedIn)
}

// 提供登出方法
const logout = async () => {
  return tokenManager.logout()
}

export { api, refreshToken, logout } 