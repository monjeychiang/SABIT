import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import axios from 'axios'
// 引入TokenManager类型，但不直接创建实例
import { TokenManager } from './utils/tokenManager'
// 引入新的TokenService单例
import { getTokenManager, initializeTokenService } from './services/tokenService'
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
  
  // 初始化TokenService（这将只创建一个TokenManager实例）
  await initializeTokenService();
  
  // 获取TokenManager实例
  const tokenManagerInstance = getTokenManager();
  console.log('已獲取TokenManager單例');
  
  // 設置tokenManager為全局可用 (为了向后兼容)
  window.tokenManager = tokenManagerInstance;
  
  console.log('已設置全局axios攔截器');
  
  // 創建Vue應用實例
  const app = createApp(App);
  
  // 註冊全局屬性
  app.provide('tokenManager', tokenManagerInstance);
  app.config.globalProperties.$tokenManager = tokenManagerInstance;
  
  // 使用插件
  const pinia = createPinia();
  app.use(pinia);
  app.use(router);
  
  // 初始化主題
  initTheme()

  // 初始化認證狀態
  const authStore = useAuthStore()
  await authStore.initAuth()

  // 如果用户已登录，初始化通知和聊天系统
  if (authStore.isAuthenticated) {
    console.log('用户已登录，初始化通知和聊天系统')
    
    // 初始化通知系统
    const { useNotificationStore } = await import('./stores/notification.ts')
    const notificationStore = useNotificationStore()
    notificationStore.initialize()
    
    // 初始化聊天系统
    const chatroomStore = useChatroomStore()
    chatroomStore.initialize()
    
    // 初始化在线状态系统
    const onlineStatusStore = useOnlineStatusStore()
    onlineStatusStore.initialize()
    
    console.log('用户已登录，聊天和在线状态系统已初始化')
  }

  // 监听登录事件
  window.addEventListener('auth:login', () => {
    // 用户登录时初始化
    chatroomStore.initialize()
    onlineStatusStore.initialize()
  })

  // 监听登出事件
  window.addEventListener('auth:logout', () => {
    // 用户登出时重置状态
    chatroomStore.resetState()
    onlineStatusStore.resetState()
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
    tokenManager: TokenManager;
  }
}
