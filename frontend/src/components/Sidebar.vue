<template>
  <transition name="sidebar">
    <aside class="sidebar" :class="{ 
      'sidebar-collapsed': isCollapsed && !isMobile, 
      'mobile': isMobile,
      'visible': isMobile && isVisible 
    }">
      <div class="sidebar-content">
        <nav class="sidebar-menu">
          <router-link to="/" class="menu-item" :class="{ 'active': isActiveRoute('/') }" title="Dashboard" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="3" width="7" height="9"></rect>
                <rect x="14" y="3" width="7" height="5"></rect>
                <rect x="14" y="12" width="7" height="9"></rect>
                <rect x="3" y="16" width="7" height="5"></rect>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">Dashboard</span>
          </router-link>
          
          <router-link to="/grid/new" class="menu-item" :class="{ 'active': isActiveRoute('/grid/new') }" title="Create Grid" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">Create Grid</span>
          </router-link>
          
          <router-link to="/markets" class="menu-item" :class="{ 'active': isActiveRoute('/markets') }" title="Markets" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="22,7 13.5,15.5 8.5,10.5 2,17"></polyline>
                <polyline points="16,7 22,7 22,13"></polyline>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">Markets</span>
          </router-link>
          
          <router-link to="/history" class="menu-item" :class="{ 'active': isActiveRoute('/history') }" title="History" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">History</span>
          </router-link>

          <!-- AI聊天助手链接 -->
          <router-link to="/chat" class="menu-item" :class="{ 'active': isActiveRoute('/chat') }" title="AI Chat" @click="handleMenuItemClick">
            <span class="menu-icon">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                <path d="M8 10h.01"></path>
                <path d="M12 10h.01"></path>
                <path d="M16 10h.01"></path>
              </svg>
            </span>
            <span v-if="!isCollapsed || (isMobile && isVisible)" class="menu-text">AI Chat</span>
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

// 計算屬性：是否為管理員
const isAdmin = computed(() => authStore.isAdmin);

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
  background-color: var(--surface-color);
  border-right: 1px solid var(--border-color);
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 50;
  transition: width 0.3s ease, transform 0.3s ease;
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
}

.sidebar-menu {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.menu-item {
  display: flex;
  align-items: center;
  padding: var(--spacing-sm) var(--spacing-md);
  color: var(--text-primary);
  text-decoration: none;
  border-radius: var(--border-radius-md);
  margin: 0 var(--spacing-sm);
  transition: all 0.2s ease;
  gap: var(--spacing-md);
  cursor: pointer;
  border: none;
  background: none;
  text-align: left;
  font-size: var(--font-size-sm);
  position: relative;
  overflow: hidden;
}

.menu-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background-color: var(--primary-color);
  opacity: 0;
  transition: opacity var(--transition-fast) ease;
}

.menu-item:hover {
  transform: translateX(4px);
  background-color: rgba(var(--primary-color-rgb), 0.1);
}

.menu-item:active {
  transform: translateX(2px);
}

.menu-item.active {
  background-color: var(--primary-color);
  color: var(--text-light);
}

.menu-item.active::before {
  opacity: 1;
}

.menu-item.active .menu-icon {
  color: var(--text-light);
}

.menu-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all var(--transition-fast) ease;
  width: 24px;
  height: 24px;
}

.menu-text {
  white-space: nowrap;
  font-weight: 500;
  transition: opacity 0.2s ease;
}

.sidebar.sidebar-collapsed .menu-text {
  opacity: 0;
}

.sidebar-section {
  margin-top: var(--spacing-lg);
  margin-bottom: var(--spacing-md);
}

.section-title {
  padding: 0 var(--spacing-md);
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: opacity var(--transition-normal) ease;
}

.sidebar.sidebar-collapsed .section-title {
  opacity: 0;
}

.sidebar-footer {
  margin-top: auto;
  border-top: 1px solid var(--border-color);
  padding-top: var(--spacing-md);
}

.logout {
  color: var(--danger-color);
}

.logout .menu-icon {
  color: var(--danger-color);
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
}

.sidebar.mobile.visible {
  transform: translateX(0);
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    box-shadow: var(--box-shadow-lg);
    width: 280px;
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
  transition: width 0.3s ease, transform 0.3s ease;
}

.sidebar-collapsed {
  width: var(--sidebar-collapsed-width);
}

/* 侧边栏显示/隐藏动画 */
.sidebar-enter-active,
.sidebar-leave-active {
  transition: transform 0.3s ease, opacity 0.3s ease;
}

.sidebar-enter-from,
.sidebar-leave-to {
  transform: translateX(-100%);
  opacity: 0;
}

/* 菜单项悬停动画 */
.sidebar-item {
  transition: all 0.2s ease;
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
  transition: transform 0.3s ease;
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