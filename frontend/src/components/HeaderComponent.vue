<template>
  <header class="header">
    <div class="search-bar">
      <input type="text" placeholder="Search type of keywords..." />
      <span class="search-icon">🔍</span>
    </div>
    <div class="user-menu">
      <div class="notification">
        <span class="icon">🔔</span>
      </div>
      <div class="user-profile">
        <div class="avatar">
          <img src="https://via.placeholder.com/40" alt="User Avatar" />
        </div>
        <div class="user-info">
          <h4>Lucas</h4>
          <p>@lucas10</p>
        </div>
        <span class="dropdown-icon">▼</span>
      </div>
    </div>
  </header>
</template>

<script setup>
// Component logic can be added here
</script>

<style scoped lang="scss">
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  background-color: #f8f9fa;
  border-bottom: 1px solid #eaeaea;
  
  .search-bar {
    position: relative;
    width: 300px;
    
    input {
      width: 100%;
      padding: 10px 15px;
      padding-right: 40px;
      border: 1px solid #ddd;
      border-radius: 20px;
      font-size: 14px;
      outline: none;
      
      &:focus {
        border-color: #4B4BFF;
        box-shadow: 0 0 0 2px rgba(75, 75, 255, 0.1);
      }
    }
    
    .search-icon {
      position: absolute;
      right: 15px;
      top: 50%;
      transform: translateY(-50%);
      color: #666;
    }
  }
  
  .user-menu {
    display: flex;
    align-items: center;
    
    .notification {
      margin-right: 20px;
      
      .icon {
        font-size: 20px;
        color: #666;
        cursor: pointer;
      }
    }
    
    .user-profile {
      display: flex;
      align-items: center;
      cursor: pointer;
      
      .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        overflow: hidden;
        margin-right: 10px;
        
        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
      }
      
      .user-info {
        h4 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
        }
        
        p {
          margin: 0;
          font-size: 12px;
          color: #666;
        }
      }
      
      .dropdown-icon {
        margin-left: 10px;
        font-size: 10px;
        color: #666;
      }
    }
  }
}
</style> 