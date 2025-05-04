import { defineStore } from 'pinia'
import { ref, computed, inject } from 'vue'
import axios from 'axios'
// 移除直接導入，改用全局實例
// import tokenManager from '@/utils/tokenManager'
import type { TokenManager } from '@/utils/tokenManager'
// 引入TokenService单例
import { getTokenManager } from '@/services/tokenService'
import router from '@/router'

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

interface User {
  id: number
  username: string
  email: string
  is_active: boolean
  is_verified: boolean
  is_admin: boolean
  created_at: string
  phone?: string
  bio?: string
  full_name?: string
  avatar_url?: string
  oauth_provider?: string
  user_tag?: string
  referral_code?: string
  referrer_id?: number
  notifications?: {
    emailNotifications: boolean
    priceAlerts: boolean
    tradeNotifications: boolean
  }
}

interface ProfileUpdateData {
  username?: string
  email?: string
  phone?: string
  bio?: string
}

interface PasswordUpdateData {
  current_password: string
  new_password: string
}

interface NotificationSettings {
  emailNotifications: boolean
  priceAlerts: boolean
  tradeNotifications: boolean
}

export const useAuthStore = defineStore('auth', () => {
  // 获取TokenManager单例，不再从依赖注入获取
  const tokenManager = getTokenManager();

  const token = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const user = ref<User | null>(null)
  const loading = ref<boolean>(false)
  const error = ref<string | null>(null)
  
  // 用户数据缓存控制变量
  const lastUserFetchTime = ref<number>(0)
  const userCacheDuration = ref<number>(60000) // 用户数据缓存时间，默认1分钟
  const isUserProfileFetching = ref<boolean>(false) // 请求锁，防止并发请求
  
  // 令牌传播延迟参数 - 令牌获取后多久可以安全地用于获取用户数据
  const tokenPropagationDelay = ref<number>(800) // 默认800毫秒，确保令牌在后端完成传播
  
  // 認證狀態計算屬性
  const isAuthenticated = computed(() => !!token.value)
  
  // 檢查用戶是否為管理員
  const isAdmin = computed(() => !!user.value?.is_admin)

  // 設置axios授權頭的統一方法
  const setAxiosAuthHeader = (authToken: string) => {
    axios.defaults.headers.common['Authorization'] = `Bearer ${authToken}`
    console.log('已設置axios授權頭：', `Bearer ${authToken}`)
  }

  // 等待令牌传播的辅助函数
  const waitForTokenPropagation = async (customDelay?: number) => {
    const delay = customDelay || tokenPropagationDelay.value;
    console.log(`等待令牌传播到后端服务，延迟${delay}毫秒...`);
    await new Promise(resolve => setTimeout(resolve, delay));
    console.log('令牌传播等待完成，可以安全使用令牌');
  }

  // 設置認證資訊
  const setAuth = (newToken: string, newRefreshToken: string, newUser: User) => {
    token.value = newToken
    refreshToken.value = newRefreshToken
    user.value = newUser
    
    // 更新用户数据缓存时间
    lastUserFetchTime.value = Date.now()
    
    // 保存到 localStorage
    localStorage.setItem('token', newToken)
    localStorage.setItem('refreshToken', newRefreshToken)
    
    // 設置 tokenManager
    tokenManager.setTokens(newToken, newRefreshToken)
    
    // 設置axios授權頭
    setAxiosAuthHeader(newToken)
  }

  // 清除認證資訊
  const clearAuth = () => {
    const now = new Date();
    console.log('======【清除認證資訊】======');
    console.log(`清除開始時間: ${now.toLocaleString()} (${now.toISOString()})`);
    
    // 記錄當前狀態
    console.log(`當前認證狀態: ${token.value ? '已登入' : '未登入'}`);
    console.log(`是否有刷新令牌: ${refreshToken.value ? '是' : '否'}`);
    
    // 清除store中的令牌
    token.value = null;
    refreshToken.value = null;
    user.value = null;
    lastUserFetchTime.value = 0;
    
    // 清除axios的Authorization header
    console.log('清除axios授權頭');
    delete axios.defaults.headers.common['Authorization'];
    
    console.log(`======【清除認證資訊完成】======`);
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
      
      console.debug('發送登錄請求', { 
        username: credentials.username, 
        keepLoggedIn: credentials.keepLoggedIn 
      });
      
      const response = await axios.post('/api/v1/auth/login', formData)
      
      // 從響應中獲取token
      const authToken = response.data.access_token
      const newRefreshToken = response.data.refresh_token
      const expiresIn = response.data.expires_in
      
      console.debug('收到登錄響應', { 
        hasToken: !!authToken, 
        hasRefreshToken: !!newRefreshToken,
        expiresIn: expiresIn
      });
      
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
      
      // 等待token在后端服务传播
      await waitForTokenPropagation()
      
      // 獲取用戶資料
      await getUserProfile(true)
      
      // 触发登录成功事件，初始化聊天和通知系统
      window.dispatchEvent(new Event('login-authenticated'))
      console.log('普通登录成功，已触发login-authenticated事件')

      // 发送登录成功通知
      try {
        // 动态导入通知store，避免循环依赖
        const { useNotificationStore } = await import('./notification.ts')
        const notificationStore = useNotificationStore()
        
        // 确保通知store已初始化，并发送登录成功通知
        if (user.value) {
          // 使用setTimeout确保WebSocket有足够时间连接
          setTimeout(() => {
            notificationStore.sendLoginSuccessNotification(user.value?.username)
          }, 1500) // 延迟1.5秒，确保WebSocket连接已建立
        }
      } catch (notifyError) {
        console.error('发送登录成功通知失败:', notifyError)
        // 不影响登录流程，仅记录错误
      }
      
      return {
        success: true,
        user: user.value
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
      console.log('======【Google登錄回調處理】======');
      console.log('處理Google登錄回調', {
        keepLoggedIn: keepLoggedIn ? '是' : '否',
        hasExpiresIn: expiresIn ? `有(${expiresIn}秒)` : '無',
        hasRefreshTokenExpiresIn: refreshTokenExpiresIn ? `有(${refreshTokenExpiresIn}秒)` : '無'
      });
      console.log('刷新令牌值 (前10位):', refreshTokenParam ? refreshTokenParam.substring(0, 10) + '...' : '空');
      
      // 儲存keepLoggedIn狀態
      localStorage.setItem('keepLoggedIn', keepLoggedIn ? 'true' : 'false')
      
      // 保存token到store
      token.value = accessTokenParam
      refreshToken.value = refreshTokenParam
      
      // 确保刷新令牌正确保存到localStorage
      localStorage.setItem('token', accessTokenParam);
      localStorage.setItem('refreshToken', refreshTokenParam);
      localStorage.setItem('tokenType', 'bearer');
      console.log('已直接存储到localStorage:', {
        token前10位: accessTokenParam ? accessTokenParam.substring(0, 10) + '...' : '空',
        refreshToken前10位: refreshTokenParam ? refreshTokenParam.substring(0, 10) + '...' : '空'
      });
      
      // 先手动设置axios授权头，确保后续API请求带有token
      setAxiosAuthHeader(accessTokenParam)
      
      // 关键优化：使用统一的令牌传播等待函数，Google登录使用更长的延迟
      // 因为涉及第三方认证，可能需要更长时间在后端系统中传播
      await waitForTokenPropagation(1000);
      
      // 再使用tokenManager统一管理令牌
      // 让tokenManager根据keepLoggedIn状态决定过期时间
      try {
        const tokensSetResult = await tokenManager.setTokens(
          accessTokenParam, 
          refreshTokenParam, 
          'bearer', 
          expiresIn,
          refreshTokenExpiresIn
        )
        console.log('tokenManager.setTokens结果:', tokensSetResult ? '成功' : '失败');
        
        // 再次检查tokenManager中的令牌
        console.log('tokenManager中的刷新令牌:', tokenManager.getRefreshToken() ? '已设置' : '未设置');
        
        // 如果tokenManager中没有设置刷新令牌或与localStorage中不一致，则尝试强制同步
        if (!tokenManager.getRefreshToken() || tokenManager.getRefreshToken() !== refreshTokenParam) {
          console.warn('检测到tokenManager中的刷新令牌与localStorage不一致，强制同步');
          tokenManager.forceUpdateTokens(accessTokenParam, refreshTokenParam, 'bearer');
        }
      } catch (tokenError) {
        console.error('设置tokenManager时出错:', tokenError);
        // 即使tokenManager设置失败，依然继续流程
      }
      
      try {
        // 獲取用戶信息，强制刷新
        await getUserProfile(true);
        
        // 添加: 发送登录成功通知，类似于login函数中的通知实现
        try {
          // 动态导入通知store，避免循环依赖
          const { useNotificationStore } = await import('./notification.ts')
          const notificationStore = useNotificationStore()
          
          // 确保通知store已初始化，并发送登录成功通知
          if (user.value) {
            // 使用setTimeout确保WebSocket有足够时间连接
            // Google登录可能需要更长时间建立WebSocket连接
            setTimeout(() => {
              notificationStore.sendLoginSuccessNotification(user.value?.username)
              console.log('已发送Google登录成功通知')
            }, 2000) // Google登录使用更长的延迟(2秒)，确保WebSocket连接已建立
          }
        } catch (notifyError) {
          console.error('发送Google登录成功通知失败:', notifyError)
          // 不影响登录流程，仅记录错误
        }
      } catch (userDataError) {
        console.error('获取用户数据失败，但令牌已设置，继续流程:', userDataError);
        
        // 如果获取用户数据失败，但令牌已经设置成功，我们可以返回成功
        // 用户数据会在下一次访问需要时重新获取
        // 检查令牌是否已设置
        if (token.value && refreshToken.value) {
          console.log('虽然获取用户数据失败，但令牌已设置，认为登录成功');
          
          // 尝试从JWT中解析用户名，至少提供基本用户信息
          try {
            const base64Url = accessTokenParam.split('.')[1];
            const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
            const payload = JSON.parse(window.atob(base64));
            const username = payload.sub || 'user';
            
            // 创建基本用户对象
            user.value = {
              id: 0,
              username: username,
              email: '',
              is_active: true,
              is_verified: false,
              is_admin: false,
              created_at: new Date().toISOString()
            };
            
            // 设置短缓存时间
            lastUserFetchTime.value = Date.now();
            userCacheDuration.value = 10000; // 10秒后重试
            
            // 添加: 尝试发送登录成功通知(基于解析的最小用户信息)
            try {
              const { useNotificationStore } = await import('./notification.ts')
              const notificationStore = useNotificationStore()
              
              setTimeout(() => {
                notificationStore.sendLoginSuccessNotification(username)
                console.log('已发送Google登录成功通知(基于最小用户信息)')
              }, 2000)
            } catch (notifyError) {
              console.error('发送Google登录成功通知失败(最小用户信息):', notifyError)
            }
          } catch (parseError) {
            console.error('解析JWT令牌失败:', parseError);
          }
        } else {
          // 如果连令牌都没设置成功，才算真正失败
          throw userDataError;
        }
      }
      
      console.log('======【Google登錄回調處理完成】======');
      return true
    } catch (error: any) {
      console.error('Google回調處理錯誤:', error);
      
      // 检查令牌是否设置成功，以便调用者判断登录状态
      const hasTokensSet = !!(token.value && refreshToken.value);
      console.log(`Google回调处理出错，但令牌状态: ${hasTokensSet ? '已设置' : '未设置'}`);
      
      // 即使出错也确保状态被清除，但只在令牌未设置成功时清除
      if (!hasTokensSet) {
        token.value = null;
        refreshToken.value = null;
        user.value = null;
        lastUserFetchTime.value = 0;
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
      
      // 准备注册数据，包含推荐码
      const registerData = {
        username: data.username,
        email: data.email,
        password: data.password,
        confirm_password: data.confirm_password
      }
      
      // 如果提供了推荐码，添加到请求数据中
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

  // 獲取用戶資料
  const getUserProfile = async (forceRefresh: boolean = false, retryCount = 3) => {
    try {
      // 檢查是否有缓存，且缓存未过期，且不是强制刷新
      const now = Date.now()
      if (
        !forceRefresh && 
        user.value && 
        (now - lastUserFetchTime.value < userCacheDuration.value)
      ) {
        console.debug('直接使用缓存的用户数据，距上次获取:', 
          Math.round((now - lastUserFetchTime.value)/1000), '秒');
        return user.value
      }
      
      // 如果已经有请求在进行中，等待该请求完成而不是发起新请求
      if (isUserProfileFetching.value) {
        console.debug('已有获取用户数据的请求在进行中，等待该请求完成...');
        // 等待当前请求完成后再返回用户数据
        // 这里简单实现为轮询等待锁释放
        return new Promise((resolve, reject) => {
          const checkInterval = setInterval(() => {
            if (!isUserProfileFetching.value) {
              clearInterval(checkInterval);
              if (user.value) {
                console.debug('等待中的getUserProfile获取到了用户数据');
                resolve(user.value);
              } else {
                reject(new Error('获取用户数据失败'));
              }
            }
          }, 50); // 每50ms检查一次
          
          // 设置超时
          setTimeout(() => {
            clearInterval(checkInterval);
            reject(new Error('获取用户数据超时'));
          }, 5000); // 5秒超时
        });
      }
      
      // 设置加载状态和锁定标志
      loading.value = true
      isUserProfileFetching.value = true
      
      // 確保有token
      const currentToken = token.value || localStorage.getItem('token')
      if (!currentToken) {
        throw new Error('未登錄，無法獲取用戶資料')
      }
      
      console.debug('发起获取用户数据请求');
      
      // 設置請求頭
      const headers = {
        'Authorization': `Bearer ${currentToken}`
      }
      
      try {
        const response = await axios.get('/api/v1/auth/me', { headers })
        user.value = response.data
        
        // 更新獲取時間
        lastUserFetchTime.value = now
        
        console.debug('成功获取用户数据，更新缓存时间');
        
        return response.data
      } catch (apiError) {
        console.error('API调用获取用户数据失败:', apiError);
        
        // 检查是否有其他地方已经成功获取了用户数据
        if (user.value) {
          console.debug('虽然API调用失败，但用户数据已被其他流程设置，使用现有数据');
          return user.value;
        }
        
        throw apiError; // 重新抛出以便上层处理
      }
    } catch (error: any) {
      console.error('獲取用戶資料錯誤:', error)
      
      // 添加重试机制
      if (retryCount > 0) {
        console.log(`嘗試重新獲取用戶資料，剩餘重試次數: ${retryCount - 1}`);
        // 短暫延遲後重試，指數級增加延遲時間
        const delay = 1000 * Math.pow(2, 3 - retryCount); // 1秒, 2秒, 4秒
        await new Promise(resolve => setTimeout(resolve, delay));
        return getUserProfile(forceRefresh, retryCount - 1);
      }
      
      error.value = error.response?.data?.detail || '獲取用戶資料失敗'
      throw new Error(error.response?.data?.detail || '獲取用戶資料失敗')
    } finally {
      loading.value = false
      isUserProfileFetching.value = false
    }
  }

  // 刷新令牌
  const refreshAccessToken = async (keepLoggedIn = false) => {
    try {
      loading.value = true
      const startTime = new Date();
      console.log('======【AUTH STORE - 開始刷新令牌】======');
      console.log(`刷新開始時間: ${startTime.toLocaleString()} (${startTime.toISOString()})`);
      console.log(`保持登入狀態: ${keepLoggedIn ? '是' : '否'}`);
      console.log(`當前token過期時間: ${localStorage.getItem('tokenExpiry') || '未設置'}`);
      
      // 使用tokenManager處理刷新邏輯，確保只有一套刷新邏輯
      const refreshSuccess = await tokenManager.refreshAccessToken(keepLoggedIn);
      
      const endTime = new Date();
      const duration = endTime.getTime() - startTime.getTime();
      
      if (!refreshSuccess) {
        console.error(`令牌刷新失敗 (耗時: ${duration}ms)`);
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
      
      // 等待令牌传播
      await waitForTokenPropagation();
      
      console.log(`======【AUTH STORE - 令牌刷新成功】(耗時: ${duration}ms)======`);
      console.log(`完成時間: ${endTime.toLocaleString()} (${endTime.toISOString()})`);
      console.log(`新token過期時間: ${tokenStatus.expiresAt?.toLocaleString() || '未知'}`);
      console.log(`保持登入狀態: ${keepLoggedIn ? '是' : '否'}`);
      
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
      // 防止重复调用
      if (loading.value) {
        console.log('登出操作已在进行中，忽略重复调用');
        return true;
      }
      
      loading.value = true
      console.debug('開始登出流程');
      
      // 使用tokenManager作为唯一的登出实现者
      // 它会处理API调用、令牌清除和事件触发
      const success = await tokenManager.logout();
      
      // 只更新本地状态，不进行重复的令牌清除
      token.value = null;
      refreshToken.value = null;
      user.value = null;
      lastUserFetchTime.value = 0;
      
      // 清除axios授權頭
      console.debug('清除axios授權頭');
      delete axios.defaults.headers.common['Authorization'];
      
      console.debug('登出成功');
      return success;
    } catch (error: any) {
      console.error('登出錯誤:', error);
      
      // 即使出错也确保状态被清除
      token.value = null;
      refreshToken.value = null;
      user.value = null;
      lastUserFetchTime.value = 0;
      delete axios.defaults.headers.common['Authorization'];
      
      return true;
    } finally {
      loading.value = false;
    }
  }

  // 初始化認證狀態
  const initAuth = async () => {
    const startTime = new Date();
    console.log('======【初始化認證狀態】======');
    console.log(`初始化開始時間: ${startTime.toLocaleString()} (${startTime.toISOString()})`);
    
    const savedToken = localStorage.getItem('token')
    const savedRefreshToken = localStorage.getItem('refreshToken')
    
    if (savedToken && savedRefreshToken) {
      console.log('本地存儲中找到令牌');
      token.value = savedToken
      refreshToken.value = savedRefreshToken
      
      // 檢查令牌是否過期
      const tokenExpiry = localStorage.getItem('tokenExpiry')
      const keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true'
      
      if (tokenExpiry) {
        const expiryDate = new Date(tokenExpiry)
        const now = new Date()
        const timeUntilExpiry = expiryDate.getTime() - now.getTime();
        
        console.log('令牌狀態檢查', {
          現在: now.toLocaleString(),
          過期時間: expiryDate.toLocaleString(),
          剩餘時間: `${Math.round(timeUntilExpiry/1000)}秒 (${Math.round(timeUntilExpiry/60000)}分鐘)`,
          已過期: expiryDate <= now,
          保持登入: keepLoggedIn
        });
        
        // 檢查令牌是否有效
        let isTokenValid = expiryDate > now;
        
        // 如果令牌已過期
        if (!isTokenValid) {
          // 只有在保持登入狀態下才嘗試刷新
          if (keepLoggedIn) {
            console.log(`令牌已過期，保持登入狀態下嘗試刷新... (過期時間: ${expiryDate.toLocaleString()})`);
            const refreshSuccess = await refreshAccessToken(keepLoggedIn)
            
            if (!refreshSuccess) {
              console.warn('令牌刷新失敗，清除認證狀態');
              clearAuth()
              
              const endTime = new Date();
              const duration = endTime.getTime() - startTime.getTime();
              console.log(`初始化完成: 已登出 (耗時: ${duration}ms)`);
              return false
            } else {
              console.log('令牌刷新成功');
              isTokenValid = true;
            }
          } else {
            // 非保持登入狀態下，令牌過期直接登出
            console.log(`令牌已過期，非保持登入狀態，直接登出 (過期時間: ${expiryDate.toLocaleString()})`);
            clearAuth();
            
            const endTime = new Date();
            const duration = endTime.getTime() - startTime.getTime();
            console.log(`初始化完成: 已登出 (耗時: ${duration}ms)`);
            return false;
          }
        } else if (timeUntilExpiry < 5 * 60 * 1000) {
          // 令牌即將過期（小於5分鐘）
          if (keepLoggedIn) {
            // 保持登入狀態下，提前刷新令牌
            console.log(`令牌即將過期，保持登入狀態下提前刷新... (剩餘時間: ${Math.round(timeUntilExpiry/1000)}秒)`);
            const refreshSuccess = await refreshAccessToken(keepLoggedIn);
            if (!refreshSuccess) {
              console.warn('令牌刷新失敗，清除認證狀態');
              clearAuth();
              return false;
            } else {
              console.log('令牌提前刷新成功');
              isTokenValid = true;
            }
          } else {
            // 非保持登入狀態下，設置過期後自動登出
            console.log(`令牌即將過期，非保持登入狀態下等待過期 (剩餘時間: ${Math.round(timeUntilExpiry/1000)}秒)`);
            // 不做任何操作，讓TokenManager處理過期登出
          }
        } else {
          // 令牌未過期，設置全局授權頭
          console.log(`令牌有效，設置授權頭 (剩餘時間: ${Math.round(timeUntilExpiry/1000)}秒)`);
          setAxiosAuthHeader(savedToken);
        }
        
        // 令牌有效，強制預加載用戶數據
        if (isTokenValid) {
          // 獲取用戶資料
          try {
            console.log('強制預加載用戶數據...');
            await getUserProfile(true); // 強制從API獲取最新數據，忽略緩存
            
            const endTime = new Date();
            const duration = endTime.getTime() - startTime.getTime();
            console.log(`======【初始化認證狀態完成: 已登入】(耗時: ${duration}ms)======`);
            return true
          } catch (error) {
            console.error('初始化用戶資料失敗:', error)
            clearAuth()
            
            const endTime = new Date();
            const duration = endTime.getTime() - startTime.getTime();
            console.log(`初始化完成: 已登出 (耗時: ${duration}ms)`);
            return false
          }
        }
      } else {
        console.warn('找不到令牌過期時間，無法判斷令牌是否有效');
        clearAuth();
        
        const endTime = new Date();
        const duration = endTime.getTime() - startTime.getTime();
        console.log(`初始化完成: 已登出 (耗時: ${duration}ms)`);
        return false;
      }
    }
    
    const endTime = new Date();
    const duration = endTime.getTime() - startTime.getTime();
    console.log(`======【初始化認證狀態完成: 未登入】(耗時: ${duration}ms)======`);
    return false
  }

  // 檢查認證狀態
  const checkAuth = async () => {
    const startTime = new Date();
    console.log('======【檢查認證狀態】======');
    console.log(`檢查開始時間: ${startTime.toLocaleString()} (${startTime.toISOString()})`);
    
    const savedToken = localStorage.getItem('token')
    if (!savedToken) {
      console.log('未找到令牌，清除認證狀態');
      clearAuth()
      
      const endTime = new Date();
      const duration = endTime.getTime() - startTime.getTime();
      console.log(`======【認證狀態檢查完成: 未登入】(耗時: ${duration}ms)======`);
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
      
      console.log('令牌狀態檢查', {
        現在: now.toLocaleString(),
        過期時間: expiryDate.toLocaleString(),
        剩餘時間: `${Math.round(timeUntilExpiry/1000)}秒 (${Math.round(timeUntilExpiry/60000)}分鐘)`,
        已過期: expiryDate <= now,
        剩餘分鐘: Math.round(timeUntilExpiry/60000),
        保持登入: keepLoggedIn
      });
      
      // 如果令牌已過期或即將過期
      if (expiryDate <= now) {
        // 只有在保持登入狀態下才嘗試刷新
        if (keepLoggedIn) {
          console.log(`令牌已過期，保持登入狀態下嘗試刷新... (過期時間: ${expiryDate.toLocaleString()})`);
          const refreshSuccess = await refreshAccessToken(keepLoggedIn);
          if (!refreshSuccess) {
            console.warn('令牌刷新失敗，清除認證狀態');
            clearAuth();
            
            const endTime = new Date();
            const duration = endTime.getTime() - startTime.getTime();
            console.log(`======【認證狀態檢查完成: 登出】(耗時: ${duration}ms)======`);
            return false;
          }
        } else {
          // 非保持登入狀態下，令牌過期直接登出
          console.log(`令牌已過期，非保持登入狀態下直接登出 (過期時間: ${expiryDate.toLocaleString()})`);
          clearAuth();
          
          const endTime = new Date();
          const duration = endTime.getTime() - startTime.getTime();
          console.log(`======【認證狀態檢查完成: 登出】(耗時: ${duration}ms)======`);
          return false;
        }
      } else if (timeUntilExpiry < 5 * 60 * 1000) {
        // 令牌即將過期（小於5分鐘）
        if (keepLoggedIn) {
          // 保持登入狀態下，提前刷新令牌
          console.log(`令牌即將過期，保持登入狀態下提前刷新... (剩餘時間: ${Math.round(timeUntilExpiry/1000)}秒)`);
          const refreshSuccess = await refreshAccessToken(keepLoggedIn);
          if (!refreshSuccess) {
            console.warn('令牌刷新失敗，清除認證狀態');
            clearAuth();
            return false;
          }
        } else {
          // 非保持登入狀態下，等待過期
          console.log(`令牌即將過期，非保持登入狀態下等待過期 (剩餘時間: ${Math.round(timeUntilExpiry/1000)}秒)`);
          // 不做任何操作，讓TokenManager處理過期登出
        }
      }
    }
    
    try {
      console.log('檢查用戶資料...');
      // 使用缓存机制获取用户资料，避免不必要的API调用
      try {
        await getUserProfile();
      
      const endTime = new Date();
      const duration = endTime.getTime() - startTime.getTime();
      console.log(`======【認證狀態檢查完成: 已登入】(耗時: ${duration}ms)======`);
        return true;
      } catch (error) {
        // 获取用户数据失败，但令牌可能仍然有效
        console.warn('獲取用戶資料失敗，但令牌可能仍有效:', error);
        
        // 检查令牌是否真的无效（通过TokenManager）
        const isTokenStillValid = tokenManager.isAuthenticated() && !tokenManager.isTokenExpired();
        
        if (isTokenStillValid) {
          console.log('令牌仍然有效，使用基本用户信息保持登录状态');
          
          // 如果没有用户信息，创建一个基本的用户对象
          if (!user.value) {
            // 尝试从JWT中解析用户名
            try {
              const base64Url = savedToken.split('.')[1];
              const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
              const payload = JSON.parse(window.atob(base64));
              const username = payload.sub || 'user';
              
              // 创建基本用户对象
              user.value = {
                id: 0,
                username: username,
                email: '',
                is_active: true,
                is_verified: false,
                is_admin: false,
                created_at: new Date().toISOString()
              };
              
              // 设置短缓存时间，以便尽快重试获取完整用户数据
              lastUserFetchTime.value = Date.now();
              userCacheDuration.value = 10000; // 10秒
            } catch (parseError) {
              console.error('解析JWT令牌失败:', parseError);
            }
          }
          
          const endTime = new Date();
          const duration = endTime.getTime() - startTime.getTime();
          console.log(`======【認證狀態檢查完成: 已登入(基本狀態)】(耗時: ${duration}ms)======`);
          return true;
        }
        
        // 令牌确实无效，清除认证状态
        console.error('認證檢查失敗:', error);
        clearAuth();
        
        const endTime = new Date();
        const duration = endTime.getTime() - startTime.getTime();
        console.log(`======【認證狀態檢查完成: 已登出】(耗時: ${duration}ms)======`);
        return false;
      }
    } catch (error) {
      console.error('認證檢查失敗:', error);
      clearAuth();
      
      const endTime = new Date();
      const duration = endTime.getTime() - startTime.getTime();
      console.log(`======【認證狀態檢查完成: 已登出】(耗時: ${duration}ms)======`);
      return false;
    }
  }

  // 添加令牌過期事件監聽
  window.addEventListener('auth:token-expired', () => {
    console.log('收到令牌過期事件，執行登出流程');
    // 使用tokenManager.clearTokens代替clearAuth
    // 确保只有一个地方负责清除令牌
    tokenManager.clearTokens();
    // 更新本地状态
    token.value = null;
    refreshToken.value = null;
    user.value = null;
    lastUserFetchTime.value = 0;
    delete axios.defaults.headers.common['Authorization'];
    
    // 可以在這裡添加通知用戶的邏輯
    router.push('/auth/login?expired=true');
  });

  return {
    token,
    refreshToken,
    user,
    loading,
    error,
    isAuthenticated,
    isAdmin,
    login,
    loginWithGoogle,
    handleGoogleCallback,
    register,
    logout,
    initAuth,
    checkAuth,
    refreshAccessToken,
    getUserProfile,
    clearAuth,
    // 导出配置参数，允许应用层面调整
    userCacheDuration,
    tokenPropagationDelay
  }
}) 