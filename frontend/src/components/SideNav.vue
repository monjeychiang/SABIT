<template>
  <div class="v-sidebar" :class="{ 'v-sidebar-collapsed': isCollapsed }">
    <div class="v-logo">
      <!-- Logo section -->
      <span v-if="!isCollapsed">GridTrader</span>
      <span v-else>GT</span>
      <button class="v-collapse-btn" @click="toggleCollapse">
        <span v-if="isCollapsed">›</span>
        <span v-else>‹</span>
      </button>
    </div>
    
    <div class="v-nav">
      <router-link to="/" class="v-nav-link">
        <i class="v-icon fas fa-th-large"></i>
        <span v-if="!isCollapsed">Dashboard</span>
      </router-link>

      <router-link to="/grid/new" class="v-nav-link">
        <i class="v-icon fas fa-plus-circle"></i>
        <span v-if="!isCollapsed">Create Grid</span>
      </router-link>

      <router-link to="/markets" class="v-nav-link">
        <i class="v-icon fas fa-chart-line"></i>
        <span v-if="!isCollapsed">Markets</span>
      </router-link>

      <router-link to="/history" class="v-nav-link">
        <i class="v-icon fas fa-history"></i>
        <span v-if="!isCollapsed">History</span>
      </router-link>
      
      <router-link to="/settings" class="v-nav-link">
        <i class="v-icon fas fa-cog"></i>
        <span v-if="!isCollapsed">Settings</span>
      </router-link>
    </div>
    
    <div class="v-sidebar-footer">
      <!-- Support section with icon -->
      <a href="#" class="v-nav-link">
        <i class="v-icon fas fa-question-circle"></i>
        <span v-if="!isCollapsed">Help & Support</span>
      </a>
    </div>
  </div>
</template>

<script setup>
// Component logic can be added here
</script>

<style scoped lang="scss">
.v-sidebar {
  background-color: #fff;
  width: 200px;
  height: 100vh;
  padding: 20px 0;
  border-right: 1px solid #eaeaea;
  display: flex;
  flex-direction: column;
  
  .v-logo {
    padding: 0 20px;
    margin-bottom: 30px;
    
    h1 {
      font-size: 20px;
      font-weight: 600;
      color: #333;
    }
  }
  
  .v-nav {
    display: flex;
    flex-direction: column;
    flex: 1;
    
    .v-nav-link {
      display: flex;
      align-items: center;
      padding: 12px 20px;
      color: var(--text-color);
      text-decoration: none;
      transition: all 0.3s;
      border-radius: 8px;
      margin-bottom: 5px;
      
      .v-icon {
        margin-right: 10px;
        font-size: 18px;
      }
      
      &:hover, &.active {
        background-color: var(--active-nav-bg);
        color: var(--active-nav-color);
      }
    }
    
    .logout {
      margin-top: auto;
      color: #ff5b5b;
    }
  }
}
</style> 