<template>
  <div class="auth-callback">
    <div class="loading-container" v-if="loading">
      <div class="loading-spinner"></div>
      <p>正在處理登入...</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import axios from 'axios'
import { tokenService } from '@/services/token'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(true)
const loginEventTriggered = ref(false)

onMounted(async () => {
  try {
    console.log('Auth Callback: 開始處理認證回調')
    console.log('Auth Callback: URL = ', window.location.href)
    
    // 從 URL 參數中獲取令牌信息
    const params = new URLSearchParams(window.location.search)
    console.log('Auth Callback: 所有 URL 參數 = ', Object.fromEntries(params.entries()))
    
    const accessToken = params.get('access_token')
    const tokenType = params.get('token_type')
    const refreshToken = params.get('refresh_token')
    const keepLoggedInStr = params.get('keep_logged_in')
    const keepLoggedIn = keepLoggedInStr === 'true' || keepLoggedInStr === 'True' || keepLoggedInStr === '1' || keepLoggedInStr === 'yes'
    
    console.log('Auth Callback: 訪問令牌 = ', accessToken ? '已獲取' : '未獲取')
    console.log('Auth Callback: 令牌類型 = ', tokenType)
    console.log('Auth Callback: 刷新令牌 = ', refreshToken ? '已獲取' : '未獲取')
    console.log('Auth Callback: 保持登入原始值 = ', keepLoggedInStr)
    console.log('Auth Callback: 保持登入解析後 = ', keepLoggedIn)
    
    if (!accessToken || !tokenType) {
      console.error('Auth Callback: 缺少令牌信息!', { 
        hasAccessToken: !!accessToken, 
        hasTokenType: !!tokenType
      })
      throw new Error('Missing token information')
    }
    
    // 记录令牌前10位（用于调试）
    console.log('Auth Callback: 访问令牌前10位 = ', accessToken.substring(0, 10) + '...')
    if (refreshToken) {
      console.log('Auth Callback: 刷新令牌前10位 = ', refreshToken.substring(0, 10) + '...')
    }
    
    // 保存令牌
    try {
      // 使用 tokenService 保存令牌，而不是直接使用 localStorage
      localStorage.setItem('keepLoggedIn', String(keepLoggedIn))
      
      // 使用 tokenService 設置令牌
      const expiresIn = params.get('expires_in') ? parseInt(params.get('expires_in')!) : undefined;
      const refreshTokenExpiresIn = params.get('refresh_token_expires_in') ? parseInt(params.get('refresh_token_expires_in')!) : expiresIn;
      
      await tokenService.setTokens(
        accessToken,
        '', // 不再傳入 refreshToken，因為它現在由 HTTP-only cookie 管理
        tokenType,
        expiresIn,
        refreshTokenExpiresIn
      );
      
      console.log('Auth Callback: 令牌已保存到 tokenService')
    } catch (storageError) {
      console.error('Auth Callback: 保存令牌時出錯:', storageError)
    }
    
    // 設置 axios 默認 headers
    axios.defaults.headers.common['Authorization'] = `${tokenType} ${accessToken}`
    console.log('Auth Callback: 已設置 axios 授權頭')
    
    // 使用 handleGoogleCallback 處理登入
    console.log('Auth Callback: 處理Google登入回調')
    const expiresIn = params.get('expires_in') ? parseInt(params.get('expires_in')!) : undefined;
    const refreshTokenExpiresIn = params.get('refresh_token_expires_in') ? parseInt(params.get('refresh_token_expires_in')!) : expiresIn;
    
    console.log(`Auth Callback: 調用 handleGoogleCallback 參數:`, {
      accessToken: accessToken ? '已提供' : '未提供',
      refreshToken: refreshToken ? '已提供' : '未提供',
      keepLoggedIn: keepLoggedIn,
      expiresIn: expiresIn,
      refreshTokenExpiresIn: refreshTokenExpiresIn
    });
    
    try {
      // 修改為僅傳入 accessToken，刷新令牌將由 cookie 處理
      const success = await authStore.handleGoogleCallback(
        accessToken, 
        '', // 不再傳入 refreshToken
        keepLoggedIn, 
        expiresIn,
        refreshTokenExpiresIn
      )
      
      if (!success) {
        console.error('Auth Callback: 處理Google登入回調失敗')
        throw new Error('Failed to handle Google callback')
      }
      
      console.log('Auth Callback: 成功處理Google登入回調')
    } catch (callbackError) {
      console.error('Auth Callback: 處理Google登入回調時發生錯誤', callbackError)
      
      // 即使回调处理失败，检查用户是否已经在其他流程中成功登录
      const isAlreadyLoggedIn = await checkIfAlreadyLoggedIn();
      
      if (isAlreadyLoggedIn) {
        console.log('Auth Callback: 雖然回調處理失敗，但用戶已在其他流程中成功登入，繼續執行')
      } else {
        // 真的登录失败了，抛出错误
        throw callbackError;
      }
    }
    
    // 觸發登入成功事件，並設置標記
    if (!loginEventTriggered.value) {
      window.dispatchEvent(new Event('login-authenticated'))
      console.log('Auth Callback: 觸發登入成功事件')
      loginEventTriggered.value = true
    } else {
      console.log('Auth Callback: 登入事件已觸發過，避免重複')
    }
    
    // 清除 URL 參數
    window.history.replaceState({}, document.title, window.location.pathname)
    console.log('Auth Callback: URL 參數已清除')
    
    // 重定向到首頁
    console.log('Auth Callback: 準備重定向到首頁')
    router.push('/')
    console.log('Auth Callback: 已發出重定向請求')
  } catch (error) {
    console.error('Auth Callback: 處理錯誤:', error)
    router.push('/auth/error')
  } finally {
    loading.value = false
  }
})

// 检查用户是否已登录的辅助函数
async function checkIfAlreadyLoggedIn(): Promise<boolean> {
  try {
    console.log('Auth Callback: 检查用户是否已在其他流程中登录')
    
    // 使用 tokenService 檢查是否已經登入
    const isAuthenticated = tokenService.isAuthenticated();
    
    if (!isAuthenticated) {
      console.log('Auth Callback: tokenService 顯示用戶未登入')
      // 再嘗試通過 authStore 檢查認證狀態
      const storeAuthenticated = await authStore.checkAuth();
      console.log(`Auth Callback: authStore.checkAuth結果: ${storeAuthenticated ? '已登录' : '未登录'}`);
      return storeAuthenticated;
    }
    
    console.log('Auth Callback: 用戶已登錄，確保初始化WebSocket連接');
    
    // 如果用户已认证，确保初始化WebSocket连接
    // 只有在主流程未觸發事件的情況下才觸發
    if (!loginEventTriggered.value) {
      setTimeout(() => {
        console.log('Auth Callback: 延迟触发login-authenticated事件');
        window.dispatchEvent(new Event('login-authenticated'));
        loginEventTriggered.value = true;
      }, 500);
    } else {
      console.log('Auth Callback: 主流程已觸發登入事件，不再重複觸發')
    }
    
    return isAuthenticated;
  } catch (error) {
    console.error('Auth Callback: 检查登录状态时出错', error)
    return false;
  }
}
</script>

<style scoped>
.auth-callback {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--surface-color);
}

.loading-container {
  text-align: center;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  margin: 0 auto 1rem;
  border: 4px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-container p {
  color: var(--text-secondary);
  font-size: var(--font-size-md);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style> 