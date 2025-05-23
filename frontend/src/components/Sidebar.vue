<template>
  <transition name="sidebar">
    <aside class="sidebar" :class="{ 
      'sidebar-collapsed': isCollapsed && !isMobile, 
      'mobile': isMobile,
      'visible': isMobile && isVisible 
    }">
      <div class="sidebar-content">
        <nav class="sidebar-menu">
          <router-link to="/" class="menu-item" :class="{ 'active': isActiveRoute('/') && !isActiveRoute('/chat') }" title="Dashboard" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="9"></rect>
                <rect x="14" y="3" width="7" height="5"></rect>
                <rect x="14" y="12" width="7" height="9"></rect>
                <rect x="3" y="16" width="7" height="5"></rect>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">控制面板</span>
          </router-link>
          
          <router-link to="/markets" class="menu-item" :class="{ 'active': isActiveRoute('/markets') }" title="Markets" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M18 20V10"></path>
                <path d="M12 20V4"></path>
                <path d="M6 20v-6"></path>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">市場行情</span>
          </router-link>
          
          <router-link to="/history" class="menu-item" :class="{ 'active': isActiveRoute('/history') }" title="History" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                <line x1="16" y1="2" x2="16" y2="6"></line>
                <line x1="8" y1="2" x2="8" y2="6"></line>
                <line x1="3" y1="10" x2="21" y2="10"></line>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">交易歷史</span>
          </router-link>

          <!-- AI聊天助手链接 -->
          <router-link to="/chat" class="menu-item" :class="{ 'active': isActiveRoute('/chat') }" title="AI Chat" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">AI聊天助手</span>
          </router-link>
        </nav>
        
        <div class="sidebar-section">
          <div class="section-title" v-if="!isCollapsed || (isMobile && isVisible)">MANAGEMENT</div>
          
          <nav class="sidebar-menu">
            <router-link to="/settings" class="menu-item" :class="{ 'active': isActiveRoute('/settings') }" title="Settings" @click="handleMenuItemClick">
              <span class="menu-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="3"></circle>
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z"></path>
                </svg>
              </span>
              <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">Settings</span>
            </router-link>
            
            <!-- 管理員頁面鏈接，僅管理員可見 -->
            <router-link 
              v-if="isAdmin"
              to="/admin" 
              class="menu-item admin-link" 
              :class="{ 'active': isActiveRoute('/admin') }" 
              title="Admin Panel"
              @click="handleMenuItemClick"
            >
              <span class="menu-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                  <circle cx="9" cy="7" r="4"></circle>
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                  <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                </svg>
              </span>
              <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">Admin Panel</span>
            </router-link>
            
            <!-- WebSocket 交易測試頁面鏈接 -->
            <router-link 
              to="/trade-test" 
              class="menu-item" 
              :class="{ 'active': isActiveRoute('/trade-test') }" 
              title="WebSocket 交易測試"
              @click="handleMenuItemClick"
            >
              <span class="menu-icon">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M2 9l10 3 10-3"></path>
                  <path d="M2 12l10 3 10-3"></path>
                  <path d="M2 15l10 3 10-3"></path>
                  <path d="M2 3l10 3 10-3"></path>
                </svg>
              </span>
              <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">WebSocket 交易測試</span>
            </router-link>
          </nav>
        </div>
      </div>
    </aside>
  </transition>
</template>

<script setup>
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { useUserStore } from '@/stores/user';

const props = defineProps({
  isCollapsed: {
    type: Boolean,
    default: false
  },
  isMobile: {
    type: Boolean,
    default: false
  },
  isVisible: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['close-mobile-sidebar']);

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const userStore = useUserStore();

// 計算屬性：是否為管理員
const isAdmin = computed(() => userStore.isAdmin);

// 检查当前路由是否激活
const isActiveRoute = (path) => {
  return route.path === path || route.path.startsWith(`${path}/`);
};

// 处理点击菜单项
const handleMenuItemClick = () => {
  if (props.isMobile && props.isVisible) {
    closeMobileSidebar();
  }
};

// 关闭移动端侧边栏
const closeMobileSidebar = () => {
  emit('close-mobile-sidebar');
};

// 路由变化时关闭移动端侧边栏
watch(() => route.path, () => {
  if (props.isMobile && props.isVisible) {
    closeMobileSidebar();
  }
});

// 登出
const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('tokenType');
  router.push('/login');
};
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  height: 100%;
  background-color: var(--background-color);
  border-right: none;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 50;
  transition: width 0.3s ease, transform 0.3s ease, 
              background-color 0.3s ease, color 0.3s ease, 
              border-color 0.3s ease, box-shadow 0.3s ease;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-top: var(--navbar-height);
}

.sidebar.sidebar-collapsed {
  width: var(--sidebar-collapsed-width);
}

.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: var(--spacing-md) 0;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--text-tertiary) transparent;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.sidebar-content::-webkit-scrollbar {
  width: 6px;
}

.sidebar-content::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-content::-webkit-scrollbar-thumb {
  background-color: var(--text-tertiary);
  border-radius: 3px;
  transition: background-color 0.3s ease;
}

.sidebar-menu {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.menu-item {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  color: var(--text-primary);
  text-decoration: none;
  border-radius: 0 24px 24px 0;
  transition: all 0.3s ease;
  margin-bottom: 4px;
  margin-right: 12px;
}

.menu-item:hover {
  background-color: var(--hover-color);
}

.menu-item.active {
  background-color: var(--primary-hover);
  color: var(--primary-color);
  font-weight: 500;
}

.menu-icon {
  width: 24px;
  height: 24px;
  margin-right: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: inherit;
  transition: color 0.3s ease;
}

.menu-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: opacity 0.3s ease, color 0.3s ease;
}

.sidebar-section {
  margin-top: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
  transition: color 0.3s ease, background-color 0.3s ease;
}

.section-title {
  padding: 0 var(--spacing-md);
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: opacity 0.3s ease, color 0.3s ease;
}

.sidebar.sidebar-collapsed .section-title {
  opacity: 0;
}

.sidebar-footer {
  margin-top: auto;
  border-top: 1px solid var(--border-color);
  padding-top: var(--spacing-md);
  transition: border-color 0.3s ease, background-color 0.3s ease;
}

.logout {
  color: var(--danger-color);
  transition: all 0.3s ease;
}

.logout .menu-icon {
  color: var(--danger-color);
  transition: color 0.3s ease;
}

.logout:hover {
  background-color: rgba(239, 68, 68, 0.1);
}

.logout.active {
  background-color: var(--danger-color);
}

/* 移动端侧边栏样式 */
.sidebar.mobile {
  transform: translateX(-100%);
  width: 280px;
  box-shadow: var(--box-shadow-lg);
  transition: transform 0.3s ease, width 0.3s ease, 
              background-color 0.3s ease, color 0.3s ease,
              box-shadow 0.3s ease, border-color 0.3s ease;
}

.sidebar.mobile.visible {
  transform: translateX(0);
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    box-shadow: var(--box-shadow-lg);
    width: 280px;
    transition: transform 0.3s ease, width 0.3s ease,
                background-color 0.3s ease, color 0.3s ease,
                box-shadow 0.3s ease, border-color 0.3s ease;
  }

  .sidebar.visible {
    transform: translateX(0);
  }
  
  .sidebar-header {
    padding: var(--spacing-sm);
  }
  
  .logo img {
    height: 28px;
    width: 28px;
  }
  
  .menu-item {
    padding: var(--spacing-sm);
    margin: 0 var(--spacing-xs);
  }
  
  .menu-icon {
    width: 20px;
    height: 20px;
  }
}

/* 侧边栏展开/收起动画 */
.sidebar {
  transition: width 0.3s ease, transform 0.3s ease,
              background-color 0.3s ease, color 0.3s ease,
              border-color 0.3s ease, box-shadow 0.3s ease;
}

.sidebar-collapsed {
  width: var(--sidebar-collapsed-width);
}

/* 侧边栏显示/隐藏动画 */
.sidebar-enter-active,
.sidebar-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease, 
              background-color 0.3s ease, color 0.3s ease;
}

.sidebar-enter-from,
.sidebar-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}

/* 菜单项悬停动画 */
.sidebar-item {
  transition: all 0.3s ease;
}

.sidebar-item:hover {
  transform: translateX(4px);
  background-color: rgba(var(--primary-color-rgb), 0.1);
}

.sidebar-item:active {
  transform: translateX(2px);
}

/* 图标旋转动画 */
.collapse-icon {
  transition: transform 0.3s ease, color 0.3s ease;
}

.sidebar-collapsed .collapse-icon {
  transform: rotate(180deg);
}

/* 文字淡入淡出动画 */
.item-text {
  transition: opacity 0.2s ease;
}

.sidebar-collapsed .item-text {
  opacity: 0;
}
</style> 