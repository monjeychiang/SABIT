import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index'
import axiosPlugin from './plugins/axios'
import { createPinia } from 'pinia'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'

// 导入Element Plus
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// 初始化應用
const initApp = async () => {
  const app = createApp(App)
  const pinia = createPinia()

  // 注册所有Element Plus图标
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

  app.use(pinia)
  app.use(router)
  app.use(axiosPlugin)
  app.use(ElementPlus)

  // 初始化主題
  const themeStore = useThemeStore()
  themeStore.initTheme()

  // 初始化認證狀態
  const authStore = useAuthStore()
  await authStore.initAuth()

  // 掛載應用
  app.mount('#app')
}

// 啟動應用
initApp().catch(error => {
  console.error('應用初始化失敗:', error)
}) 