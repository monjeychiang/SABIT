import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUserStore } from '@/stores/user'
import GridTrading from '@/views/GridTrading.vue'

// 定義路由配置
export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { 
      layout: 'default',
      keepAlive: false,
      reload: true,
      breadcrumb: '控制面板'
    }
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { 
      layout: 'default',
      requiresAuth: true,
      breadcrumb: 'AI聊天助手'
    }
  },
  {
    path: '/history',
    name: 'history',
    component: () => import('@/views/HistoryView.vue'),
    meta: { 
      layout: 'default',
      breadcrumb: '交易歷史'
    }
  },
  {
    path: '/users',
    name: 'users',
    component: () => import('@/views/UserView.vue'),
    meta: { 
      layout: 'default',
      requiresAuth: true,
      breadcrumb: '用戶總覽'
    }
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { 
      layout: 'default',
      breadcrumb: '設置'
    }
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/admin/AdminView.vue'),
    meta: { 
      requiresAuth: true, 
      requiresAdmin: true,
      layout: 'default',
      breadcrumb: '管理員面板'
    }
  },
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { 
      layout: 'default',
      requiresAuth: true,
      breadcrumb: '個人資料'
    }
  },
  {
    path: '/auth/error',
    name: 'auth-error',
    component: () => import('@/views/AuthError.vue'),
    meta: { 
      requiresAuth: false,
      layout: 'auth'
    }
  },
  {
    path: '/theme-test',
    name: 'theme-test',
    component: () => import('@/views/ThemeTest.vue'),
    meta: { 
      layout: 'default',
      breadcrumb: '主題測試'
    }
  },
  {
    path: '/account',
    name: 'account',
    component: () => import('@/views/AccountView.vue'),
    meta: { 
      layout: 'default',
      requiresAuth: true,
      breadcrumb: '帳戶管理'
    }
  },
  {
    path: '/trade-test',
    name: 'trade-test',
    component: () => import('@/views/TradeTestView.vue'),
    meta: { 
      layout: 'default',
      requiresAuth: true,
      breadcrumb: 'WebSocket 交易測試'
    }
  },
  {
    path: '/grid-trading',
    name: 'GridTrading',
    component: GridTrading,
    meta: {
      layout: 'default',
      requiresAuth: true,
      breadcrumb: '網格交易'
    }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

// 創建路由實例
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 全局前置守衛
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  const userStore = useUserStore()
  
  // 只檢查管理員頁面的權限
  if (to.meta.requiresAdmin) {
    if (!authStore.isAuthenticated) {
      window.dispatchEvent(new CustomEvent('show-login-modal'))
      next('/')
      return
    }
    
    if (!userStore.isAdmin) {
      window.dispatchEvent(new CustomEvent('show-toast', { 
        detail: { 
          type: 'error',
          message: '需要管理員權限訪問此頁面'
        }
      }))
      next('/')
      return
    }
  }
  
  next()
})

export default router 