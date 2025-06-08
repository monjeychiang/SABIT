import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import axios from 'axios'
// 引入新的 TokenService
import { tokenService } from './services/token'
// 已刪除向後兼容層，移除此引用
import { useAuthStore } from './stores/auth'
import { useChatroomStore } from './stores/chatroom'
import { useOnlineStatusStore } from './stores/online-status'

// 從環境變數獲取 API 配置
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';

// 初始化深色模式
const initTheme = () => {
  const savedTheme = localStorage.getItem('theme')
  
  if (savedTheme === 'dark') {
    document.body.classList.add('dark-theme')
  } else if (savedTheme === 'light') {
    document.body.classList.remove('dark-theme')
  } else {
    // 如果没有保存的主题，检查系统偏好
    const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches
    if (prefersDarkMode) {
      document.body.classList.add('dark-theme')
      localStorage.setItem('theme', 'dark')
    } else {
      document.body.classList.remove('dark-theme')
      localStorage.setItem('theme', 'light')
    }
  }
}

// 初始化應用
const initApp = async () => {
  console.log('======【應用初始化開始】======');
  
  // 設置axios基礎URL（在開發環境中，Vite處理代理）
  axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || '';
  
  // 初始化 TokenService 並設置 axios 攔截器
  console.log('初始化 Token 服務');
  tokenService.setupAxiosInterceptors(axios);
  
  // 創建Vue應用實例
  const app = createApp(App);
  
  // 註冊全局屬性 - 使用新的 tokenService
  app.provide('tokenService', tokenService);
  
  // 使用插件
  const pinia = createPinia();
  app.use(pinia);
  app.use(router);
  
  // 初始化主題
  initTheme()

  // 初始化認證狀態
  const authStore = useAuthStore()
  await authStore.initAuth()

  // 添加系統初始化標記變量
  const systemInitialized = {
    chatroom: false,
    onlineStatus: false,
    notification: false,
    webSocketAttemptTime: 0 // 新增：記錄最後一次WebSocket連接嘗試時間
  };

  // 如果用户已登录，初始化通知和聊天系统
  if (authStore.isAuthenticated) {
    console.log('用户已登录，初始化通知和聊天系统')
    
    // 初始化通知系统
    const { useNotificationStore } = await import('./stores/notification.ts')
    const notificationStore = useNotificationStore()
    notificationStore.initialize()
    systemInitialized.notification = true
    
    // 初始化聊天系统
    const chatroomStore = useChatroomStore()
    chatroomStore.initialize()
    systemInitialized.chatroom = true
    
    // 初始化在线状态系统
    const onlineStatusStore = useOnlineStatusStore()
    onlineStatusStore.initialize()
    systemInitialized.onlineStatus = true
    
    // 記錄初始化時間
    systemInitialized.webSocketAttemptTime = Date.now()
    
    console.log('用户已登录，聊天和在线状态系统已初始化')
  }

  // 监听登录事件
  window.addEventListener('auth:login', () => {
    // 用户登录时初始化
    console.log('收到 auth:login 事件，按需初始化系統')
    const chatroomStore = useChatroomStore()
    const onlineStatusStore = useOnlineStatusStore()
    
    if (!systemInitialized.chatroom) {
      console.log('初始化聊天系统')
      chatroomStore.initialize()
      systemInitialized.chatroom = true
    } else {
      console.log('聊天系統已初始化，跳過')
    }
    
    if (!systemInitialized.onlineStatus) {
      console.log('初始化在线状态系统')
      onlineStatusStore.initialize()
      systemInitialized.onlineStatus = true
    } else {
      console.log('在線狀態系統已初始化，跳過')
    }
    
    // 記錄初始化時間
    systemInitialized.webSocketAttemptTime = Date.now()
  })

  // 监听登出事件
  window.addEventListener('auth:logout', () => {
    // 用户登出时重置状态
    const chatroomStore = useChatroomStore();
    const onlineStatusStore = useOnlineStatusStore();
    chatroomStore.resetState()
    onlineStatusStore.resetState()
    // 重置初始化標記
    systemInitialized.chatroom = false
    systemInitialized.onlineStatus = false
    systemInitialized.notification = false
  })
  
  // 監聽登入認證事件 (OAuth相關)
  window.addEventListener('login-authenticated', () => {
    console.log('收到 login-authenticated 事件，按需初始化系統')
    const chatroomStore = useChatroomStore()
    const onlineStatusStore = useOnlineStatusStore()
    
    // 檢查距離上次初始化的時間
    const now = Date.now()
    const timeSinceLastAttempt = now - systemInitialized.webSocketAttemptTime
    const MIN_REINIT_INTERVAL = 5000 // 5秒內不重複初始化
    
    if (timeSinceLastAttempt < MIN_REINIT_INTERVAL) {
      console.log(`忽略短時間內的重複初始化請求 (${timeSinceLastAttempt}ms < ${MIN_REINIT_INTERVAL}ms)`)
      return
    }
    
    if (!systemInitialized.chatroom) {
      console.log('初始化聊天系统')
      chatroomStore.initialize()
      systemInitialized.chatroom = true
    } else {
      console.log('聊天系統已初始化，跳過')
    }
    
    if (!systemInitialized.onlineStatus) {
      console.log('初始化在线状态系统')
      onlineStatusStore.initialize()
      systemInitialized.onlineStatus = true
    } else {
      console.log('在線狀態系統已初始化，跳過')
    }
    
    // 更新初始化時間
    systemInitialized.webSocketAttemptTime = now
  })

  // 掛載應用
  app.mount('#app');
  
  console.log('======【應用初始化完成】======');
}

// 啟動應用
initApp().catch(error => {
  console.error('應用初始化失敗:', error);
});

// 擴展Window接口以支持自定義屬性
declare global {
  interface Window {
    // 已移除 tokenManager，不再使用全局變量
    // 改用 import { tokenService } from '@/services/token'
  }
}
