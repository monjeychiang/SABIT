<template>
  <div class="main-layout" :class="{ 'sidebar-collapsed': isSidebarCollapsed }">
    <Sidebar 
      class="sidebar" 
      :collapsed="isSidebarCollapsed" 
      @toggle-sidebar="toggleSidebar"
    />
    
    <div class="main-content">
      <NavBar 
        :username="username" 
        :notifications="notifications"
        @logout="handleLogout"
      />
      
      <div class="content-wrapper">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import Sidebar from './Sidebar.vue';
import NavBar from './NavBar.vue';

const router = useRouter();
const username = ref('User');
const isSidebarCollapsed = ref(false);
const notifications = ref([
  {
    id: 1,
    title: '系統通知',
    message: '歡迎使用加密貨幣交易系統',
    time: new Date(),
    read: false
  }
]);

// Toggle sidebar
const toggleSidebar = () => {
  isSidebarCollapsed.value = !isSidebarCollapsed.value;
  // Save preference to localStorage
  localStorage.setItem('sidebarCollapsed', isSidebarCollapsed.value);
};

// Handle logout
const handleLogout = () => {
  // Clear auth tokens
  localStorage.removeItem('token');
  localStorage.removeItem('tokenType');
  
  // Redirect to login page
  router.push('/login');
};

// Load user info
const loadUserInfo = async () => {
  try {
    // Get username from localStorage or from API
    const storedUsername = localStorage.getItem('username');
    if (storedUsername) {
      username.value = storedUsername;
    } else {
      // If API for user info exists, fetch it here
      // For now, we'll use a placeholder
      username.value = 'Trader';
    }
  } catch (error) {
    console.error('Error loading user info:', error);
  }
};

onMounted(() => {
  // Load sidebar state from localStorage
  const savedSidebarState = localStorage.getItem('sidebarCollapsed');
  if (savedSidebarState !== null) {
    isSidebarCollapsed.value = savedSidebarState === 'true';
  }
  
  // Load user info
  loadUserInfo();
});
</script>

<style scoped>
.main-layout {
  display: flex;
  height: 100vh;
  width: 100%;
  background-color: var(--background-color, #f8f9fa);
}

.sidebar {
  height: 100%;
  flex-shrink: 0;
  z-index: 100;
  transition: width 0.3s;
  width: var(--sidebar-width, 260px);
}

.sidebar-collapsed .sidebar {
  width: 80px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: margin-left 0.3s;
}

.content-wrapper {
  flex: 1;
  overflow: auto;
  padding: 20px;
  padding-top: 80px; /* To account for the fixed navbar */
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    top: 0;
    left: 0;
    height: 100%;
    transform: translateX(-100%);
  }
  
  .sidebar-collapsed .sidebar {
    transform: translateX(0);
    width: 80px;
  }
  
  .main-content {
    margin-left: 0 !important;
  }
}
</style> 