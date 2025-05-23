<template>
  <div class="navbar">
    <div class="left">
      <button class="menu-button" @click="$emit('toggle-sidebar')">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
          <path fill="none" d="M0 0h24v24H0z" />
          <path d="M3 4h18v2H3V4zm0 7h18v2H3v-2zm0 7h18v2H3v-2z" fill="currentColor" />
        </svg>
      </button>
      <img 
        src="/sabit_embedded_image.svg" 
        alt="Logo" 
        class="logo-image" 
      />
    </div>
    
    <!-- 添加搜索框 -->
    <div class="search-container">
      <div class="search-box">
        <input 
          type="text" 
          placeholder="搜索..." 
          class="search-input" 
          v-model="searchQuery"
        />
        <button class="search-button">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
            <path fill="none" d="M0 0h24v24H0z"/>
            <path d="M18.031 16.617l4.283 4.282-1.415 1.415-4.282-4.283A8.96 8.96 0 0 1 11 20c-4.968 0-9-4.032-9-9s4.032-9 9-9 9 4.032 9 9a8.96 8.96 0 0 1-1.969 5.617zm-2.006-.742A6.977 6.977 0 0 0 18 11c0-3.868-3.133-7-7-7-3.868 0-7 3.132-7 7 0 3.867 3.132 7 7 7a6.977 6.977 0 0 0 4.875-1.975l.15-.15z" fill="currentColor"/>
          </svg>
        </button>
      </div>
    </div>
    
    <div class="right">
      <!-- 未登录时显示登录按钮 -->
      <template v-if="!isAuthenticated">
        <button class="login-button" @click="showLoginModal = true">
          登入
        </button>
      </template>

      <!-- 已登录时显示的内容 -->
      <template v-else>
        <div class="notification-dropdown">
          <button class="notification-button" @click="toggleNotifications">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
              <path fill="none" d="M0 0h24v24H0z" />
              <path d="M20 17h2v2H2v-2h2v-7a8 8 0 1 1 16 0v7zm-2 0v-7a6 6 0 1 0-12 0v7h12zm-9 4h6v2H9v-2z" fill="currentColor" />
            </svg>
            <span v-if="unreadNotifications > 0" class="notification-badge">{{ unreadNotifications }}</span>
          </button>
          <transition name="dropdown">
            <div v-if="showNotifications" class="notifications-panel">
              <div class="notifications-header">
                <h3>通知</h3>
                <div class="notification-actions">
                  <button v-if="hasNotifications" class="clear-all" @click="clearAllNotifications">全部清除</button>
                </div>
              </div>
              <div class="notification-local-info" v-if="hasNotifications">
                <small>已读状态和清除操作仅保存在本地，其他用户不受影响</small>
              </div>
              <div v-if="notificationStore.loading" class="loading-notifications">
                <div class="loading-spinner"></div>
                <p>載入中...</p>
              </div>
              <div v-else-if="hasNotifications" class="notifications-list">
                <div 
                  v-for="notification in filteredNotifications" 
                  :key="notification.id" 
                  class="notification-item"
                  :class="{ 'unread': !notification.is_read }"
                  :data-type="notification.notification_type || 'info'"
                  @click="markAsRead(notification.id)"
                >
                  <div class="notification-icon" :style="{
                    backgroundColor: getNotificationStyle(notification.notification_type).bgColor,
                    color: getNotificationStyle(notification.notification_type).color
                  }">
                    {{ getNotificationStyle(notification.notification_type).icon }}
                  </div>
                  <div class="notification-content">
                    <div class="notification-type-badge" :style="{
                      color: getNotificationStyle(notification.notification_type).color,
                      backgroundColor: getNotificationStyle(notification.notification_type).bgColor
                    }">
                      {{ getNotificationTypeName(notification.notification_type) }}
                    </div>
                    <h4>{{ notification.title }}</h4>
                    <p>{{ notification.message }}</p>
                    <span class="notification-time">{{ formatTime(notification.created_at) }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="empty-notifications">
                <p>目前沒有通知</p>
              </div>
              
            </div>
          </transition>
        </div>
        
        <div class="user-dropdown">
          <button class="user-button" @click="toggleUserDropdown">
            <UserAvatar 
              :username="username"
              :avatar-url="avatarUrl"
              size="medium"
              :no-cache="false"
            />
            <span class="username">{{ fullName || username }}</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18">
              <path fill="none" d="M0 0h24v24H0z" />
              <path d="M12 16l-6-6h12z" fill="currentColor" />
            </svg>
          </button>
          <transition name="dropdown">
            <div v-if="showUserDropdown" class="user-dropdown-menu">
              <div class="user-info">
                <div class="user-name">{{ username }}</div>
                <div class="user-email">{{ email }}</div>
                <div class="user-tag" :class="getUserTagClass(userTag)">
                  {{ getUserTagName(userTag) }}
                </div>
              </div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-item" @click="goToProfile">
                <span class="item-icon">👤</span>
                <span>個人資料</span>
              </div>
              <div class="dropdown-item" @click="goToUsersList">
                <span class="item-icon">👥</span>
                <span>用戶總覽</span>
              </div>
              <div class="dropdown-item" @click="goToSettings">
                <span class="item-icon">⚙️</span>
                <span>設置</span>
              </div>
              <div class="dropdown-item" @click="showReferralModal = true">
                <span class="item-icon">🔗</span>
                <span>推薦碼</span>
              </div>
              <div class="dropdown-divider"></div>
              <div class="dropdown-item" @click="logout">
                <span class="item-icon">🚪</span>
                <span>登出</span>
              </div>
            </div>
          </transition>
        </div>
      </template>
      
      <!-- 垂直分隔線 -->
      <div class="vertical-divider"></div>
      
      <!-- 添加GitHub圖標 -->
      <button class="icon-button" @click="goToGitHub" title="前往GitHub倉庫">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
          <path fill="none" d="M0 0h24v24H0z"/>
          <path d="M12 2C6.475 2 2 6.475 2 12a9.994 9.994 0 0 0 6.838 9.488c.5.087.687-.213.687-.476 0-.237-.013-1.024-.013-1.862-2.512.463-3.162-.612-3.362-1.175-.113-.288-.6-1.175-1.025-1.413-.35-.187-.85-.65-.013-.662.788-.013 1.35.725 1.538 1.025.9 1.512 2.338 1.087 2.912.825.088-.65.35-1.087.638-1.337-2.225-.25-4.55-1.113-4.55-4.938 0-1.088.387-1.987 1.025-2.688-.1-.25-.45-1.275.1-2.65 0 0 .837-.262 2.75 1.026a9.28 9.28 0 0 1 2.5-.338c.85 0 1.7.112 2.5.337 1.912-1.3 2.75-1.024 2.75-1.024.55 1.375.2 2.4.1 2.65.637.7 1.025 1.587 1.025 2.687 0 3.838-2.337 4.688-4.562 4.938.362.312.675.912.675 1.85 0 1.337-.013 2.412-.013 2.75 0 .262.188.574.688.474A10.016 10.016 0 0 0 22 12c0-5.525-4.475-10-10-10z" fill="currentColor"/>
        </svg>
      </button>
      
      <!-- 添加問號圖標 -->
      <button class="icon-button" @click="showHelp" title="幫助中心">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
          <path fill="none" d="M0 0h24v24H0z"/>
          <path d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-2a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm-1-5h2v2h-2v-2zm2-1.645V14h-2v-1.5a1 1 0 0 1 1-1 1.5 1.5 0 1 0-1.471-1.794l-1.962-.393A3.501 3.501 0 1 1 13 13.355z" fill="currentColor"/>
        </svg>
      </button>
      
      <!-- 垂直分隔線 -->
      <div class="vertical-divider"></div>
      
      <!-- 深色模式切換按鈕 - 移動到這裡作為最右側元素 -->
      <button class="theme-toggle-button" @click="toggleDarkMode" aria-label="Toggle dark mode">
        <svg v-if="isDarkMode" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
          <path fill="none" d="M0 0h24v24H0z"/>
          <path d="M12 18C8.68629 18 6 15.3137 6 12C6 8.68629 8.68629 6 12 6C15.3137 6 18 8.68629 18 12C18 15.3137 15.3137 18 12 18ZM12 16C14.2091 16 16 14.2091 16 12C16 9.79086 14.2091 8 12 8C9.79086 8 8 9.79086 8 12C8 14.2091 9.79086 16 12 16ZM11 1H13V4H11V1ZM11 20H13V23H11V20ZM3.51472 4.92893L4.92893 3.51472L7.05025 5.63604L5.63604 7.05025L3.51472 4.92893ZM16.9497 18.364L18.364 16.9497L20.4853 19.0711L19.0711 20.4853L16.9497 18.364ZM19.0711 3.51472L20.4853 4.92893L18.364 7.05025L16.9497 5.63604L19.0711 3.51472ZM5.63604 16.9497L7.05025 18.364L4.92893 20.4853L3.51472 19.0711L5.63604 16.9497ZM23 11V13H20V11H23ZM4 11V13H1V11H4Z" fill="currentColor"/>
        </svg>
        <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
          <path fill="none" d="M0 0h24v24H0z"/>
          <path d="M10 7C10 10.866 13.134 14 17 14C18.9584 14 20.729 13.1957 21.9995 11.8995C22 11.933 22 11.9665 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C12.0335 2 12.067 2 12.1005 2.00049C10.8043 3.27098 10 5.04157 10 7ZM4 12C4 16.4183 7.58172 20 12 20C15.0583 20 17.7158 18.2839 19.062 15.7621C18.3945 15.9522 17.7035 16.0603 16.9931 16.0603C12.2157 16.0603 8.34282 12.1874 8.34282 7.41001C8.34282 6.26347 8.56410 5.17549 8.97108 4.18773C6.14571 5.17935 4 8.34752 4 12Z" fill="currentColor"/>
        </svg>
      </button>
    </div>

    <!-- 登录对话框 -->
    <transition name="modal">
      <div v-if="showLoginModal" class="login-modal-overlay" @click="showLoginModal = false">
        <div class="login-modal" @click.stop>
          <div class="login-modal-header">
            <h2>歡迎回來</h2>
            <button class="close-button" @click="showLoginModal = false">×</button>
          </div>
          
          <div class="login-modal-body">
            <div v-if="loginError" class="login-error">
              {{ loginError }}
            </div>
            
            <form @submit.prevent="handleLogin" class="login-form">
              <div class="form-group">
                <label for="email">用戶名</label>
                <input 
                  type="text" 
                  id="email" 
                  v-model="loginForm.email" 
                  required 
                  placeholder="請輸入用戶名"
                />
              </div>
              
              <div class="form-group">
                <label for="password">密碼</label>
                <div class="password-input">
                  <input 
                    :type="showPassword ? 'text' : 'password'" 
                    id="password" 
                    v-model="loginForm.password" 
                    required
                    placeholder="請輸入密碼"
                  />
                  <button 
                    type="button" 
                    class="toggle-password"
                    @click="showPassword = !showPassword"
                  >
                    <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                      <path d="M12 3c5.392 0 9.878 3.88 10.819 9-.94 5.12-5.427 9-10.819 9-5.392 0-9.878-3.88-10.819-9C2.121 6.88 6.608 3 12 3zm0 16c3.691 0 6.915-2.534 7.736-6C18.915 9.534 15.691 7 12 7c-3.691 0-6.915 2.534-7.736 6 .82 3.466 4.045 6 7.736 6zm0-10c2.21 0 4 1.791 4 4s-1.79 4-4 4c-2.21 0-4-1.791-4-4s1.79-4 4-4zm0 6c1.105 0 2-.895 2-2s-.895-2-2-2c-1.105 0-2 .895-2 2s.895 2 2 2z"/>
                    </svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                      <path d="M9.342 18.782l-1.931-.518.787-2.939a10.988 10.988 0 01-3.237-1.872l-2.153 2.154-1.415-1.415 2.154-2.153a10.957 10.957 0 01-2.371-5.07l1.968-.359C3.903 10.812 7.579 14 12 14c4.42 0 8.097-3.188 8.856-7.39l1.968.358a10.957 10.957 0 01-2.37 5.071l2.153 2.153-1.415 1.415-2.153-2.154a10.988 10.988 0 01-3.237 1.872l.787 2.94-1.931.517-.788-2.94a11.072 11.072 0 01-3.74 0l-.788 2.94z"/>
                    </svg>
                  </button>
                </div>
              </div>
              
              <div class="login-options">
                <label class="custom-checkbox">
                  <input type="checkbox" v-model="loginForm.rememberMe">
                  <span class="checkmark"></span>
                  <span class="checkbox-label">記住用戶名</span>
                </label>
                
                <label class="custom-checkbox">
                  <input type="checkbox" v-model="loginForm.keepLoggedIn">
                  <span class="checkmark"></span>
                  <span class="checkbox-label">保持登入狀態</span>
                </label>
              </div>
              
              <button type="submit" class="login-submit-button" :disabled="isLoading">
                {{ isLoading ? '登入中...' : '登入' }}
              </button>
              
              <div class="login-divider">
                <span>或</span>
              </div>
              
              <button 
                type="button" 
                class="google-login-button" 
                @click="handleGoogleLogin"
              >
                <img 
                  src="/google-icon.svg" 
                  alt="Google" 
                  class="google-icon"
                />
                使用 Google 帳號登入
              </button>
              
              <div class="register-link">
                還沒有帳號？ <a href="#" @click.prevent="showRegisterModal = true; showLoginModal = false">立即註冊</a>
              </div>
            </form>
          </div>
        </div>
      </div>
    </transition>
    
    <!-- 注册对话框 -->
    <transition name="modal">
      <div v-if="showRegisterModal" class="register-modal-overlay" @click="showRegisterModal = false">
        <div class="register-modal" @click.stop>
          <div class="register-modal-header">
            <h2>加入我們</h2>
            <button class="close-button" @click="showRegisterModal = false">×</button>
          </div>
          
          <div class="register-modal-body">
            <div v-if="registerError" class="register-error">
              {{ registerError }}
            </div>
            
            <form @submit.prevent="handleRegister" class="register-form">
              <div class="form-group">
                <label for="register-username">用戶名</label>
                <input 
                  type="text" 
                  id="register-username" 
                  v-model="registerForm.username" 
                  required 
                  placeholder="請輸入用戶名"
                />
              </div>
              
              <div class="form-group">
                <label for="register-email">電子郵件</label>
                <input 
                  type="email" 
                  id="register-email" 
                  v-model="registerForm.email" 
                  required 
                  placeholder="請輸入電子郵件"
                />
              </div>
              
              <div class="form-group">
                <label for="register-password">密碼</label>
                <div class="password-input">
                  <input 
                    :type="showRegisterPassword ? 'text' : 'password'" 
                    id="register-password" 
                    v-model="registerForm.password" 
                    required
                    placeholder="請輸入密碼"
                  />
                  <button 
                    type="button" 
                    class="toggle-password"
                    @click="showRegisterPassword = !showRegisterPassword"
                  >
                    <svg v-if="!showRegisterPassword" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                      <path d="M12 3c5.392 0 9.878 3.88 10.819 9-.94 5.12-5.427 9-10.819 9-5.392 0-9.878-3.88-10.819-9C2.121 6.88 6.608 3 12 3zm0 16c3.691 0 6.915-2.534 7.736-6C18.915 9.534 15.691 7 12 7c-3.691 0-6.915 2.534-7.736 6 .82 3.466 4.045 6 7.736 6zm0-10c2.21 0 4 1.791 4 4s-1.79 4-4 4c-2.21 0-4-1.791-4-4s1.79-4 4-4zm0 6c1.105 0 2-.895 2-2s-.895-2-2-2c-1.105 0-2 .895-2 2s.895 2 2 2z"/>
                    </svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                      <path d="M9.342 18.782l-1.931-.518.787-2.939a10.988 10.988 0 01-3.237-1.872l-2.153 2.154-1.415-1.415 2.154-2.153a10.957 10.957 0 01-2.371-5.07l1.968-.359C3.903 10.812 7.579 14 12 14c4.42 0 8.097-3.188 8.856-7.39l1.968.358a10.957 10.957 0 01-2.37 5.071l2.153 2.153-1.415 1.415-2.153-2.154a10.988 10.988 0 01-3.237 1.872l.787 2.94-1.931.517-.788-2.94a11.072 11.072 0 01-3.74 0l-.788 2.94z"/>
                    </svg>
                  </button>
                </div>
              </div>
              
              <div class="form-group">
                <label for="register-confirm-password">確認密碼</label>
                <div class="password-input">
                  <input 
                    :type="showRegisterPassword ? 'text' : 'password'" 
                    id="register-confirm-password" 
                    v-model="registerForm.confirmPassword" 
                    required
                    placeholder="請再次輸入密碼"
                  />
                </div>
              </div>
              
              <!-- 添加推荐码字段 -->
              <div class="form-group">
                <label for="register-referral-code">推薦碼 <span class="optional">(選填)</span></label>
                <input 
                  type="text" 
                  id="register-referral-code" 
                  v-model="registerForm.referralCode" 
                  placeholder="如有推薦碼請輸入"
                />
                <div class="field-hint">填寫推薦者的推薦碼</div>
              </div>
              
              <button type="submit" class="register-submit" :disabled="isRegisterLoading">
                {{ isRegisterLoading ? '註冊中...' : '註冊' }}
              </button>
              
              <div class="login-link-container">
                <span>已有帳號？</span>
                <a href="#" @click.prevent="showLoginModal = true; showRegisterModal = false">立即登入</a>
              </div>
            </form>
          </div>
        </div>
      </div>
    </transition>
    
    <!-- 推薦碼模態框 -->
    <transition name="modal">
      <div v-if="showReferralModal" class="modal-overlay" @click="showReferralModal = false">
        <div class="modal-container" @click.stop>
          <div class="modal-header">
            <h2>我的推薦碼</h2>
            <button class="close-button" @click="showReferralModal = false">×</button>
          </div>
          
          <div class="modal-body">
            <div v-if="loadingReferralData" class="loading-container">
              <div class="loading-spinner"></div>
              <p>載入中...</p>
            </div>
            
            <div v-else class="referral-content">
              <!-- 顶部信息板块：横向布局的邀请码和邀请人 -->
              <div class="referral-top-section">
                <!-- 邀请码区域 -->
                <div class="referral-code-section">
                  <h3>您的推薦碼</h3>
                  <div class="code-display">
                    <span class="code">{{ referralData.referralCode || '無推薦碼' }}</span>
                    <button v-if="referralData.referralCode" class="copy-button" @click="copyReferralCode" title="複製推薦碼">
                      <span v-if="codeCopied">已複製!</span>
                      <span v-else>複製</span>
                    </button>
                  </div>
                  <div class="referral-benefits">
                    <h4>推薦好友的好處:</h4>
                    <ul>
                      <li>幫助朋友加入我們的平台</li>
                      <li>追蹤被推薦用戶的活動</li>
                      <li>建立您的用戶網絡</li>
                    </ul>
                  </div>
                </div>
                
                <!-- 邀请人信息区域 -->
                <div class="referrer-section">
                  <h3>邀請人信息</h3>
                  <div v-if="referralData.referrerInfo" class="referrer-info">
                    <p><strong>用戶名:</strong> {{ referralData.referrerInfo.username }}</p>
                    <p><strong>邀請時間:</strong> {{ formatDate(referralData.referrerInfo.inviteDate) }}</p>
                  </div>
                  <p v-else class="no-referrer">您沒有邀請人</p>
                </div>
              </div>
              
              <!-- 使用說明 -->
              <div class="referral-instructions">
                <h3>如何使用推薦碼</h3>
                <ol>
                  <li>複製您的推薦碼</li>
                  <li>分享給朋友或在社交媒體上發布</li>
                  <li>當新用戶註冊時，讓他們在註冊表單中輸入您的推薦碼</li>
                </ol>
              </div>
              
              <!-- 推薦列表區域 -->
              <div class="referrals-list-section">
                <h3>我的推薦列表</h3>
                <div v-if="referralData.referralsList && referralData.referralsList.length > 0" class="referrals-list">
                  <div class="referrals-header">
                    <span class="header-username">用戶名</span>
                    <span class="header-email">電子郵件</span>
                    <span class="header-date">註冊時間</span>
                    <span class="header-status">狀態</span>
                  </div>
                  <div v-for="(referral, index) in referralData.referralsList" :key="index" class="referral-item">
                    <span class="item-username">{{ referral.username }}</span>
                    <span class="item-email">{{ referral.email }}</span>
                    <span class="item-date">{{ formatDate(referral.created_at) }}</span>
                    <span class="item-status" :class="{'status-active': referral.is_active, 'status-inactive': !referral.is_active}">
                      {{ referral.is_active ? '活躍' : '未活躍' }}
                      {{ referral.is_verified ? '(已驗證)' : '(未驗證)' }}
                    </span>
                  </div>
                </div>
                <p v-else class="no-referrals">您還沒有推薦任何用戶</p>
              </div>
            </div>
          </div>
          
          <div class="modal-footer">
            <button class="btn btn-primary" @click="showReferralModal = false">關閉</button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, h, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';
import { UserOutlined, LogoutOutlined } from '@ant-design/icons-vue';
import { useNotificationStore, NotificationType, NotificationStyles } from '@/stores/notification.ts';
import { useChatroomStore } from '@/stores/chatroom';
import { useAuthStore } from '@/stores/auth';
import { useUserStore } from '@/stores/user';
import { useThemeStore } from '@/stores/theme';
import UserAvatar from '@/components/UserAvatar.vue';
import authService from '@/services/authService';

const notificationStore = useNotificationStore();
const chatroomStore = useChatroomStore();
const authStore = useAuthStore();
const userStore = useUserStore();
const themeStore = useThemeStore();

const renderIcon = (icon) => {
  return () => h(icon);
};

const props = defineProps({
  username: {
    type: String,
    default: 'User'
  },
  notifications: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(['toggle-sidebar', 'logout']);

const route = useRoute();
const router = useRouter();

const showNotifications = ref(false);
const showUserDropdown = ref(false);
const showLoginModal = ref(false);
const showPassword = ref(false);
const isLoading = ref(false);
const loginError = ref('');
const notificationInterval = ref(null);
const loginForm = ref({
  email: '',
  password: '',
  rememberMe: false,
  keepLoggedIn: false
});

const showRegisterModal = ref(false);
const showRegisterPassword = ref(ref(false));
const isRegisterLoading = ref(false);
const registerError = ref('');
const registerForm = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  referralCode: ''
});

const username = ref('');
const email = ref('');
const userTag = ref('regular');
const avatarUrl = ref('');
const fullName = ref('');
const oauthProvider = ref('');

// 推薦碼相關狀態變數
const showReferralModal = ref(false);
const loadingReferralData = ref(false);
const referralData = ref({
  referralCode: '',
  referrerInfo: null,
  referralsList: []
});
const codeCopied = ref(false);

// 添加 searchQuery 變量
const searchQuery = ref('');

onMounted(async () => {
  themeStore.initTheme();
  
  document.addEventListener('click', handleClickOutside);

  const savedEmail = localStorage.getItem('savedEmail');
  if (savedEmail) {
    loginForm.value.email = savedEmail;
    loginForm.value.rememberMe = true;
  }

  window.addEventListener('show-login-modal', () => {
    showLoginModal.value = true;
  });

  window.addEventListener('logout-event', () => {
    console.log('收到登出事件，更新导航栏状态');
    username.value = '';
    email.value = '';
    userTag.value = 'regular';
  });

  // 监听通知状态变化事件
  window.addEventListener('notification:state-changed', () => {
    console.log('检测到通知状态变化，更新UI');
    // 直接从store获取最新的未读通知数量
    if (notificationStore) {
      console.log('当前未读通知数：', notificationStore.unreadCount);
    }
  });

  // 监听未读通知计数更新事件
  window.addEventListener('notification:unread-updated', (event) => {
    console.log('收到未读通知计数更新事件:', event.detail?.count);
    // 可以直接使用事件中的计数，或者触发一个UI刷新
    if (notificationStore) {
      // 确保store的计数也是最新的
      notificationStore.updateUnreadCount();
    }
  });
  
  // 初始化認證狀態
  console.log('NavBar 組件掛載，初始化認證狀態...');
  await authService.initialize();
  
  // 如果已登錄，加載用戶資料
  if (authStore.isAuthenticated) {
    console.log('使用者已登錄，加載用戶資料');
    await loadUserData();
    
    // 设置通知回调
    notificationStore.setNewNotificationCallback((notification) => {
      console.log('收到新通知回调:', notification);
      playNotificationSound(notification.notification_type);
      showNotificationToast(notification);
    });
    
    // 初始化通知系统
    console.log('初始化通知系统...');
    notificationStore.initialize();
    console.log('通知系统初始化完成，WebSocket状态:', notificationStore.websocketConnected ? '已连接' : '未连接');
    
    // 初始化聊天系统
    console.log('初始化聊天系统...');
    chatroomStore.initialize();
    console.log('聊天系统初始化完成');
    
    // 额外检查：3秒后再次检查WebSocket连接状态
    setTimeout(() => {
      console.log('WebSocket连接状态检查:', 
        notificationStore.websocketConnected ? '已连接' : '未连接',
        '通知数量:', notificationStore.notifications.length
      );
      
      // 如果连接断开，尝试重新连接
      if (!notificationStore.websocketConnected) {
        console.log('检测到WebSocket未连接，尝试重新连接...');
        // 注意：此方法内部已更新为使用WebSocketManager，保留调用是为了兼容现有代码
        notificationStore.connectWebSocket();
        
        // 如果需要同时重连所有WebSocket，可以使用以下代码
        // import('@/services/webSocketService').then(({ default: webSocketManager }) => {
        //   webSocketManager.connectAll();
        // });
      }
    }, 3000);
  }

  if (window.location.pathname === '/auth/google/callback') {
    handleGoogleCallback();
  }
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
  window.removeEventListener('show-login-modal', () => {
    showLoginModal.value = true;
  });
  window.removeEventListener('logout-event', () => {});
  
  // 移除通知状态事件监听器
  window.removeEventListener('notification:state-changed', () => {});
  window.removeEventListener('notification:unread-updated', () => {});
  
  // 注意：以下closeWebSocket方法调用已经被更新，现在内部使用WebSocketManager管理连接
  // 这些兼容方法保留是为了确保现有代码继续正常工作，它们会将请求委托给WebSocketManager
  
  // 关闭通知WebSocket连接
  notificationStore.closeWebSocket();
  
  // 关闭聊天WebSocket连接
  chatroomStore.closeWebSocket();
  
  if (notificationInterval.value) {
    clearInterval(notificationInterval.value);
    notificationInterval.value = null;
  }
});

const isDarkMode = computed(() => themeStore.isDarkMode);

const toggleDarkMode = () => {
  themeStore.toggleTheme();
};

const hasNotifications = computed(() => notificationStore.notifications.length > 0);
const unreadNotifications = computed(() => notificationStore.unreadCount);
const sortedNotifications = computed(() => notificationStore.sortedNotifications);
const filteredNotifications = computed(() => notificationStore.filteredNotifications);

const usernameInitial = computed(() => 
  props.username ? props.username.charAt(0).toUpperCase() : 'U'
);

const toggleNotifications = () => {
  showNotifications.value = !showNotifications.value;
  if (showNotifications.value) {
    showUserDropdown.value = false;
  }
};

const toggleUserDropdown = () => {
  showUserDropdown.value = !showUserDropdown.value;
  if (showUserDropdown.value) {
    showNotifications.value = false;
  }
};

const markAsRead = async (id) => {
  await notificationStore.markAsRead(id);
  showNotifications.value = false;
};

const markAllAsRead = async () => {
  await notificationStore.markAllAsRead();
  showNotifications.value = false;
};

const clearAllNotifications = async () => {
  await notificationStore.clearAllNotifications();
  showNotifications.value = false;
};

const formatTime = (dateString) => {
  if (!dateString) return '-';

  try {
    const date = new Date(dateString);
    
    if (isNaN(date.getTime())) {
      return '无效日期';
    }
    
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date >= today) {
      return `今天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else if (date >= yesterday) {
      return `昨天 ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    } else {
      return new Intl.DateTimeFormat('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      }).format(date);
    }
  } catch (error) {
    console.error('日期格式化错误:', error);
    return dateString;
  }
};

const goToProfile = () => {
  router.push('/profile');
  showUserDropdown.value = false;
};

const goToSettings = () => {
  router.push('/settings');
  showUserDropdown.value = false;
};

const goToUsersList = () => {
  router.push('/users');
  showUserDropdown.value = false;
};

const logout = () => {
  showUserDropdown.value = false;
  handleLogout();
};

const handleClickOutside = (event) => {
  const notificationDropdown = document.querySelector('.notification-dropdown');
  const userDropdown = document.querySelector('.user-dropdown');
  
  if (notificationDropdown && !notificationDropdown.contains(event.target)) {
    showNotifications.value = false;
  }
  
  if (userDropdown && !userDropdown.contains(event.target)) {
    showUserDropdown.value = false;
  }
};

watch(() => route.path, () => {
  showNotifications.value = false;
  showUserDropdown.value = false;
});

const isAuthenticated = computed(() => {
  return authStore.isAuthenticated;
});

const handleLogin = async () => {
  if (isLoading.value) return;
  
  isLoading.value = true;
  loginError.value = '';
  
  try {
    // 触发全局加载动画
    window.dispatchEvent(new CustomEvent('auth-loading-start', { 
      detail: { message: '正在处理登入...' }
    }));
    
    // 準備登入憑證
    const credentials = {
      username: loginForm.value.email,
      password: loginForm.value.password,
      keepLoggedIn: loginForm.value.keepLoggedIn
    };
    
    // 使用 authService 進行登入
    await authService.login(credentials);
    
    // 登入成功後自動加載用戶資料
    if (authStore.isAuthenticated) {
      await loadUserData();
    }
    
    // 關閉登入對話框
    showLoginModal.value = false;
    
  } catch (error) {
    console.error('登入失敗:', error);
    
    // 根據錯誤類型顯示不同的錯誤消息
    if (error.code === 'ECONNABORTED') {
      loginError.value = '連接超時，請檢查伺服器是否正在運行';
    } else if (authStore.error) {
      loginError.value = authStore.error;
    } else {
      loginError.value = '登入失敗，請稍後再試';
    }
  } finally {
    isLoading.value = false;
    
    // 无论成功或失败，关闭全局加载动画
    window.dispatchEvent(new CustomEvent('auth-loading-end'));
  }
};

const handleRegister = async () => {
  try {
    isRegisterLoading.value = true;
    registerError.value = '';
    
    if (registerForm.value.password !== registerForm.value.confirmPassword) {
      registerError.value = '兩次輸入的密碼不匹配';
      return;
    }
    
    // 使用 auth store 處理註冊
    await authStore.register({
      username: registerForm.value.username,
      email: registerForm.value.email,
      password: registerForm.value.password,
      confirm_password: registerForm.value.confirmPassword,
      referral_code: registerForm.value.referralCode
    });
    
    showRegisterModal.value = false;
    showLoginModal.value = true;
    // 修改为填入用户名，而不是电子邮箱
    loginForm.value.email = registerForm.value.username;
    registerForm.value = { username: '', email: '', password: '', confirmPassword: '', referralCode: '' };
    
  } catch (error) {
    console.error('Registration error:', error);
    if (error.code === 'ECONNABORTED') {
      registerError.value = '連接超時，請檢查伺服器是否正在運行';
    } else if (authStore.error) {
      registerError.value = authStore.error;
    } else {
      registerError.value = '註冊失敗，請稍後再試';
    }
  } finally {
    isRegisterLoading.value = false;
  }
};

const goToRegister = () => {
  showLoginModal.value = false;
  showRegisterModal.value = true;
};

const userMenuOptions = [
  {
    label: '个人资料',
    key: 'profile',
    icon: renderIcon(UserOutlined)
  },
  {
    label: '退出登录',
    key: 'logout',
    icon: renderIcon(LogoutOutlined)
  }
]

const handleUserMenuSelect = (key) => {
  switch (key) {
    case 'profile':
      router.push('/profile')
      break
    case 'logout':
      handleLogout()
      break
  }
}

const getNotificationStyle = (type) => {
  const styles = {
    'info': { icon: 'ℹ️', color: '#1677ff', bgColor: '#e6f7ff' },
    'success': { icon: '✅', color: '#52c41a', bgColor: '#f6ffed' },
    'warning': { icon: '⚠️', color: '#faad14', bgColor: '#fffbe6' },
    'error': { icon: '❌', color: '#ff4d4f', bgColor: '#fff2f0' },
    'system': { icon: '🔔', color: '#722ed1', bgColor: '#f9f0ff' }
  };
  return styles[type] || styles['info'];
};

const getNotificationTypeName = (type) => {
  const typeNames = {
    'info': '信息',
    'success': '成功',
    'warning': '警告',
    'error': '错误',
    'system': '系统'
  };
  return typeNames[type] || '信息';
};

const playNotificationSound = (type) => {
  try {
    let soundPath;
    
    switch(type) {
      case 'error':
        soundPath = '/sounds/error.mp3';
        break;
      case 'warning':
        soundPath = '/sounds/warning.mp3';
        break;
      case 'success':
        soundPath = '/sounds/success.mp3';
        break;
      case 'system':
        soundPath = '/sounds/system.mp3';
        break;
      default:
        soundPath = '/sounds/notification.mp3';
    }
    
    const audio = new Audio(soundPath);
    audio.volume = 0.5;
    audio.play().catch(e => console.log('无法播放通知音效:', e));
  } catch (e) {
    console.error('播放通知提示音失败:', e);
  }
};

const showNotificationToast = (notification) => {
  const style = getNotificationStyle(notification.notification_type);
  
  const toast = document.createElement('div');
  toast.className = 'notification-toast';
  toast.style.backgroundColor = style.bgColor;
  toast.style.color = '#333';
  toast.style.borderLeft = `4px solid ${style.color}`;
  
  toast.innerHTML = `
    <div class="notification-toast-title">${notification.title}</div>
    <div class="notification-toast-message">${notification.message}</div>
  `;
  
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('show');
  }, 10);
  
  setTimeout(() => {
    toast.classList.remove('show');
    setTimeout(() => {
      document.body.removeChild(toast);
    }, 300);
  }, 5000);
};

const handleLogout = async () => {
  try {
    console.log('正在登出...');
    // 使用 authService 登出，它會處理 auth store 和 user store 的同步
    await authService.logout();
    
    // 清空本地用戶信息變量
    username.value = '';
    email.value = '';
    userTag.value = 'regular';
    avatarUrl.value = '';
    fullName.value = '';
    oauthProvider.value = '';
    
    // 關閉用戶下拉菜單
    showUserDropdown.value = false;
    
    // 清除通知
    notificationStore.clearAllNotifications();
    
    console.log('登出成功');
    
    // 可選：重定向到登錄頁面
    router.push('/login');
  } catch (error) {
    console.error('登出出錯:', error);
  }
};

const handleGoogleLogin = async () => {
  try {
    // 获取登录表单中的保持登录状态
    const keepLoggedIn = loginForm.value.keepLoggedIn;
    console.log(`Google登入請求，保持登入狀態: ${keepLoggedIn}`);
    
    // 触发全局加载动画
    window.dispatchEvent(new CustomEvent('auth-loading-start', { 
      detail: { message: '正在准备Google登入...' }
    }));
    
    const authUrl = await authStore.loginWithGoogle(keepLoggedIn);
    if (authUrl) {
      window.location.href = authUrl;
    } else {
      // 如果获取URL失败，关闭加载动画
      window.dispatchEvent(new CustomEvent('auth-loading-end'));
      loginError.value = '無法啟動 Google 登入';
    }
  } catch (error) {
    console.error('Google login error:', error);
    loginError.value = '無法啟動 Google 登入';
    
    // 发生错误时关闭加载动画
    window.dispatchEvent(new CustomEvent('auth-loading-end'));
  }
};

const handleGoogleCallback = () => {
  const urlParams = new URLSearchParams(window.location.search);
  const accessToken = urlParams.get('access_token');
  const refreshToken = urlParams.get('refresh_token');
  const error = urlParams.get('error');
  const errorDescription = urlParams.get('error_description');
  const keepLoggedInStr = urlParams.get('keep_logged_in');
  const keepLoggedIn = keepLoggedInStr === 'true' || keepLoggedInStr === 'True' || keepLoggedInStr === '1' || keepLoggedInStr === 'yes';
  
  console.log('Google Callback: 參數解析', {
    accessToken: accessToken ? '已獲取' : '未獲取',
    refreshToken: refreshToken ? '已獲取' : '未獲取',
    keepLoggedInStr: keepLoggedInStr,
    keepLoggedIn: keepLoggedIn
  });
  
  if (error) {
    console.error('Google login error:', error, errorDescription);
    
    // 處理特定錯誤
    if (error === 'token_verification_failed' || error.includes('time') || error.includes('clock')) {
      loginError.value = '伺服器時間同步問題，您的登入請求已被接收，但由於技術原因無法完成。請稍後再試。';
    } else {
      loginError.value = errorDescription || `Google 登入失敗: ${error}`;
    }
    
    showLoginModal.value = true;
    return;
  }
  
  if (accessToken && refreshToken) {
    // 使用 auth store 處理 Google 回調
    authStore.handleGoogleCallback(accessToken, refreshToken, keepLoggedIn)
      .then(success => {
        if (success) {
          // 先初始化WebSocket连接
          console.log('Google回调处理成功，初始化WebSocket连接');
          import('@/services/authService').then(async ({ authService }) => {
            // 先初始化WebSocket连接
            await authService.initializeWebSockets();
            // 再加载用户数据
            await loadUserData();
            
            // 觸發登入事件
            window.dispatchEvent(new Event('login-authenticated'));
            
            // 清除 URL 參數
            window.history.replaceState({}, document.title, window.location.pathname);
            router.push('/');
          });
        } else {
          loginError.value = '處理您的Google登入時發生問題，請稍後再試。';
          showLoginModal.value = true;
        }
      })
      .catch(err => {
        console.error('Error processing Google callback:', err);
        
        // 更友好的錯誤信息
        if (err.message && (err.message.includes('time') || err.message.includes('clock') || err.message.includes('sync'))) {
          loginError.value = '伺服器時間同步問題，您的登入請求已被接收，但由於技術原因無法完成。請稍後再試。';
        } else {
          loginError.value = '處理Google登入時發生錯誤，請稍後再試。';
        }
        
        showLoginModal.value = true;
      });
  } else {
    // 处理没有令牌参数的情况
    console.warn('没有收到令牌信息');
    
    // 提取錯誤信息（如果有）
    const errorFromQuery = urlParams.get('error');
    if (errorFromQuery) {
      loginError.value = `Google登入失敗: ${errorFromQuery}`;
    } else {
      loginError.value = '無法完成Google登入，未接收到認證信息';
    }
    
    showLoginModal.value = true;
  }
};

// 獲取用戶標籤樣式
const getUserTagClass = (tag) => {
  switch (tag) {
    case 'admin':
      return 'tag-admin';
    case 'premium':
      return 'tag-premium';
    case 'regular':
    default:
      return 'tag-regular';
  }
};

// 獲取用戶標籤名稱
const getUserTagName = (tag) => {
  switch (tag) {
    case 'admin':
      return '管理員';
    case 'premium':
      return '高級用戶';
    case 'regular':
    default:
      return '一般用戶';
  }
};

// 載入用戶數據
const loadUserData = async (retryCount = 3) => {
  try {
    // 嘗試獲取用戶數據
    await userStore.getUserData();
    
    if (userStore.user) {
      username.value = userStore.user.username;
      email.value = userStore.user.email;
      userTag.value = userStore.user.role || 'regular';
      avatarUrl.value = userStore.user.avatar || '';
      fullName.value = userStore.user.fullName || '';
      oauthProvider.value = userStore.user.oauthProvider || '';
      console.log('用戶數據已通過 API 更新');
    }
  } catch (error) {
    console.error('Error loading user data:', error);
    if (retryCount > 0) {
      console.log(`重試加載用戶數據，剩餘重試次數: ${retryCount - 1}`);
      setTimeout(() => loadUserData(retryCount - 1), 1000);
    }
  }
};

// 載入推薦碼和邀請人信息
const loadReferralData = async (forceRefresh = false) => {
  if (!authStore.isAuthenticated) return;
  
  loadingReferralData.value = true;
  try {
    console.log('開始加載推薦碼和邀請人信息...');
    
    // 使用 userStore.getUserData 獲取用戶信息，包含推薦碼
    const userData = await userStore.getUserData(forceRefresh);
    
    if (userData) {
      console.log('成功獲取用戶信息:', JSON.stringify(userData));
      
      // 從用戶數據中直接獲取推薦碼
      referralData.value.referralCode = userData.referralCode || '';
      console.log('推薦碼:', referralData.value.referralCode);
      
      // 如果有推薦人ID，則嘗試獲取推薦人信息
      if (userData.referrerId) {
        const referrerId = userData.referrerId;
        console.log(`檢測到推薦人ID: ${referrerId}，正在獲取推薦人信息...`);
        
        try {
          // 使用修改後的用戶信息API路徑
          const referrerUrl = `/api/v1/users/user-info/${referrerId}`;
          console.log(`調用推薦人API: ${referrerUrl}`);
          
          const referrerResponse = await axios.get(referrerUrl, {
            headers: {
              'Authorization': `Bearer ${authStore.token}`
            }
          });
          
          console.log('獲取推薦人信息成功:', JSON.stringify(referrerResponse.data));
          
          if (referrerResponse.data) {
            referralData.value.referrerInfo = {
              username: referrerResponse.data.username,
              inviteDate: userData.createdAt // 使用當前用戶的創建時間作為被邀請時間
            };
            console.log('設置推薦人信息成功:', JSON.stringify(referralData.value.referrerInfo));
          }
        } catch (referrerError) {
          console.error('獲取推薦人信息失敗:', referrerError);
          if (referrerError.response) {
            console.error('錯誤詳情:', {
              status: referrerError.response.status,
              data: referrerError.response.data
            });
          }
        }
      } else {
        console.log('用戶沒有推薦人ID，無法顯示推薦人信息');
      }
      
      // 獲取推薦列表
      try {
        console.log('開始獲取推薦列表...');
        const referralsResponse = await axios.get('/api/v1/auth/me/referrals', {
          headers: {
            'Authorization': `Bearer ${authStore.token}`
          }
        });
        
        if (referralsResponse.data) {
          console.log('獲取推薦列表成功:', JSON.stringify(referralsResponse.data));
          referralData.value.referralsList = referralsResponse.data;
        }
      } catch (referralsError) {
        console.error('獲取推薦列表失敗:', referralsError);
        if (referralsError.response) {
          console.error('錯誤詳情:', {
            status: referralsError.response.status,
            data: referralsError.response.data
          });
        }
        referralData.value.referralsList = [];
      }
    }
  } catch (error) {
    console.error('獲取推薦碼信息失敗:', error);
    if (error.response) {
      console.error('錯誤詳情:', {
        status: error.response.status,
        data: error.response.data
      });
    }
    
    // 如果获取数据失败，设置空值防止界面错误
    referralData.value.referralCode = '';
    referralData.value.referrerInfo = null;
    referralData.value.referralsList = [];
  } finally {
    loadingReferralData.value = false;
  }
};

// 複製推薦碼到剪貼板
const copyReferralCode = () => {
  if (!referralData.value.referralCode) return;
  
  navigator.clipboard.writeText(referralData.value.referralCode)
    .then(() => {
      codeCopied.value = true;
      setTimeout(() => {
        codeCopied.value = false;
      }, 2000);
    })
    .catch(err => {
      console.error('複製失敗:', err);
    });
};

// 當推薦碼模態框顯示時載入數據
watch(showReferralModal, (newValue) => {
  if (newValue) {
    // 当模态框显示时，默认使用缓存加载数据
    loadReferralData(false);
  }
});

// 手動刷新推薦數據
const refreshReferralData = () => {
  if (loadingReferralData.value) return; // 防止重复请求
  
  // 强制刷新数据，忽略缓存
  loadReferralData(true);
};

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return '未知';
  
  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('zh-TW', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  } catch (error) {
    console.error('日期格式化錯誤:', error);
    return dateString;
  }
};

const goToGitHub = () => {
  // 打開GitHub倉庫頁面
  window.open('https://github.com/monjeychiang/SABIT', '_blank');
};

const showHelp = () => {
  // 顯示幫助中心或文檔
  router.push('/help');
};
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: var(--navbar-height);
  padding: 0 var(--spacing-md);
  background-color: var(--background-color);
  border-bottom: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  /* 添加與側邊欄一致的過渡效果 */
  transition: background-color 0.3s ease, color 0.3s ease, 
              border-color 0.3s ease, box-shadow 0.3s ease;
}

.left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.menu-button {
  background: none;
  border: none;
  padding: var(--spacing-sm);
  cursor: pointer;
  border-radius: var(--border-radius-sm);
  color: var(--text-primary);
  transition: all var(--transition-fast) ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-button:hover {
  background-color: var(--hover-color);
}

.logo-image {
  height: 40px;
  width: auto;
  max-width: 180px;
  object-fit: contain;
  margin-right: var(--spacing-md);
}

.right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.theme-toggle-button {
  background: none;
  border: none;
  padding: var(--spacing-sm);
  cursor: pointer;
  border-radius: var(--border-radius-sm);
  color: var(--text-primary);
  /* 確保過渡效果一致 */
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.theme-toggle-button:hover {
  background-color: var(--hover-color);
}

.login-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background-color: var(--primary-color);
  color: var(--text-light);
  border: none;
  border-radius: var(--border-radius-md);
  cursor: pointer;
  font-weight: 500;
  transition: all var(--transition-fast) ease;
  min-width: 80px;
}

.login-button:hover {
  background-color: var(--primary-dark);
}

.notification-dropdown {
  position: relative;
}

.notification-button {
  background: none;
  border: none;
  padding: var(--spacing-sm);
  cursor: pointer;
  border-radius: var(--border-radius-sm);
  color: var(--text-primary);
  transition: all var(--transition-fast) ease;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.notification-button:hover {
  background-color: var(--hover-color);
}

.notification-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  background-color: var(--danger-color);
  color: var(--text-light);
  font-size: var(--font-size-xs);
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  box-shadow: 0 0 0 2px var(--surface-color);
}

.notifications-panel {
  position: absolute;
  top: calc(100% + 5px);
  left: 50%;
  transform: translateX(-50%);
  width: 380px;
  max-width: 90vw;
  max-height: calc(100vh - 150px);
  overflow-y: auto;
  background-color: var(--background-color);
  border: none;
  border-radius: var(--border-radius-md);
  box-shadow: var(--box-shadow-md);
  z-index: 10;
}

.notifications-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.notifications-header h3 {
  margin: 0;
  font-size: var(--font-size-md);
  color: var(--text-primary);
}

.notification-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.mark-all-read, .clear-all {
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--font-size-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--border-radius-sm);
  transition: all var(--transition-fast) ease;
}

.mark-all-read {
  color: var(--primary-color);
}

.clear-all {
  color: var(--danger-color);
}

.mark-all-read:hover, .clear-all:hover {
  background-color: var(--hover-color);
}

.notifications-list {
  max-height: 400px;
  overflow-y: auto;
}

.notification-item {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast) ease;
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.notification-item:hover {
  background-color: var(--hover-color);
}

.notification-item.unread {
  background-color: rgba(var(--primary-color-rgb), 0.05);
}

.notification-item[data-type="info"] {
  border-left-color: #444444; /* 修改藍色為灰色 */
}

.notification-item[data-type="success"] {
  border-left-color: #52c41a;
}

.notification-item[data-type="warning"] {
  border-left-color: #faad14;
}

.notification-item[data-type="error"] {
  border-left-color: #ff4d4f;
}

.notification-item[data-type="system"] {
  border-left-color: #722ed1;
}

.notification-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
}

.notification-content {
  flex: 1;
}

.notification-content h4 {
  margin: 0 0 var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-weight: 600;
}

.notification-content p {
  margin: 0 0 var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.4;
}

.notification-time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.empty-notifications {
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--text-tertiary);
}

.user-dropdown {
  position: relative;
}

.user-button {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  background: none;
  border: none;
  padding: var(--spacing-sm);
  cursor: pointer;
  border-radius: var(--border-radius-md);
  color: var(--text-primary);
  transition: all var(--transition-fast) ease;
  height: 48px;  /* 固定高度以确保一致性 */
}

.user-button:hover {
  background-color: var(--hover-color);
}

.user-button :deep(.user-avatar-component) {
  width: 32px;  /* 设置头像组件的固定宽度 */
  height: 32px;  /* 设置头像组件的固定高度 */
  min-width: 32px; /* 确保最小宽度一致 */
  min-height: 32px; /* 确保最小高度一致 */
  max-width: 32px; /* 确保最大宽度一致 */
  max-height: 32px; /* 确保最大高度一致 */
  flex-shrink: 0;  /* 防止头像被压缩 */
  aspect-ratio: 1/1; /* 确保保持正方形比例 */
}

.username {
  font-size: var(--font-size-sm);
  max-width: 120px;  /* 限制用户名最大宽度 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-dropdown-menu {
  position: absolute;
  top: calc(100% + 5px);
  left: 50%;
  transform: translateX(-50%);
  width: 250px;
  background-color: var(--background-color);
  border: none;
  border-radius: var(--border-radius-md);
  box-shadow: var(--box-shadow-md);
  z-index: 10;
  overflow: hidden;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: none;
  border: none;
  color: var(--text-primary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: all var(--transition-fast) ease;
}

.dropdown-item:hover {
  background-color: var(--hover-color);
}

.dropdown-item.logout {
  color: var(--danger-color);
}

.dropdown-divider {
  height: 1px;
  background-color: var(--border-color);
  margin: var(--spacing-xs) 0;
}

.login-modal-overlay,
.register-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  backdrop-filter: blur(3px);
}

.login-modal,
.register-modal {
  background-color: var(--background-color);
  width: 400px;
  max-width: 90%;
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-lg);
  overflow: hidden;
}

.login-modal-header,
.register-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.login-modal-header h2,
.register-modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.close-button {
  background: none;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  color: var(--text-tertiary);
}

.login-modal-body,
.register-modal-body {
  padding: 20px;
}

.login-error,
.register-error {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
  padding: 10px;
  border-radius: var(--border-radius-sm);
  margin-bottom: 16px;
  font-size: 0.875rem;
}

.login-form,
.register-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-group input[type="email"],
.form-group input[type="password"],
.form-group input[type="text"] {
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background-color: var(--surface-color);
  color: var(--text-primary);
  font-size: 0.875rem;
}

.password-input {
  position: relative;
  display: flex;
}

.password-input input {
  flex: 1;
  padding-right: 40px;
}

.toggle-password {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-tertiary);
  font-size: 1rem;
  padding: 0;
}

.login-options {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.custom-checkbox {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  user-select: none;
}

.custom-checkbox input[type="checkbox"] {
  position: absolute;
  opacity: 0;
  cursor: pointer;
  height: 0;
  width: 0;
}

.checkmark {
  position: relative;
  height: 20px;
  width: 20px;
  background-color: var(--surface-color);
  border: 2px solid var(--border-color);
  border-radius: 4px;
  transition: all var(--transition-fast) ease;
}

.custom-checkbox:hover .checkmark {
  border-color: var(--primary-color);
}

.custom-checkbox input:checked ~ .checkmark {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

.checkmark:after {
  content: "";
  position: absolute;
  display: none;
  left: 6px;
  top: 2px;
  width: 4px;
  height: 8px;
  border: solid white;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.custom-checkbox input:checked ~ .checkmark:after {
  display: block;
}

.checkbox-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.login-submit-button,
.register-submit,
.google-login-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  padding: 12px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: all var(--transition-fast) ease;
  height: 40px;
}

.login-submit-button:hover,
.register-submit:hover,
.google-login-button:hover {
  background-color: var(--primary-dark, #106fbd);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(var(--shadow-color-rgb, 0, 0, 0), 0.15);
}

.login-submit-button:disabled,
.register-submit:disabled,
.google-login-button:disabled {
  background-color: var(--disabled-color);
  cursor: not-allowed;
}

.login-divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: var(--spacing-md) 0;
}

.login-divider::before,
.login-divider::after {
  content: '';
  flex: 1;
  border-bottom: 1px solid var(--border-color);
}

.login-divider span {
  padding: 0 var(--spacing-sm);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

.register-link,
.login-link-container {
  margin-top: 12px;
  text-align: center;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.register-link a,
.login-link-container a {
  color: var(--primary-color);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--transition-fast) ease;
}

.register-link a:hover,
.login-link-container a:hover {
  color: var(--primary-color-hover);
  text-decoration: underline;
}

.google-login-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  width: 100%;
}

.google-icon {
  width: 20px;
  height: 20px;
  object-fit: contain;
  filter: none;
}

.user-tag {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 2px;  /* 改為方框樣式，只保留極小圓角 */
  font-size: 12px;
  font-weight: 500;
  margin-top: 4px;
  text-transform: uppercase;  /* 使文字全部大寫，更具視覺衝擊力 */
  letter-spacing: 0.5px;  /* 增加字母間距，提高可讀性 */
  border: 1px solid transparent;  /* 添加邊框，但設為透明 */
}

.tag-admin {
  background-color: rgba(255, 77, 79, 0.1);  /* 淡化背景色 */
  color: #ff4d4f;  /* 保留原來的紅色，但用於文字 */
  border-color: #ff4d4f;  /* 設置邊框顏色 */
}

.tag-premium {
  background-color: rgba(250, 173, 20, 0.1);  /* 淡化背景色 */
  color: #faad14;  /* 保留原來的黃色，但用於文字 */
  border-color: #faad14;  /* 設置邊框顏色 */
}

.tag-regular {
  background-color: rgba(82, 196, 26, 0.1);  /* 淡化背景色 */
  color: #52c41a;  /* 保留原來的綠色，但用於文字 */
  border-color: #52c41a;  /* 設置邊框顏色 */
}

.user-info {
  padding: 12px 16px;
  width: 100%; /* 确保占据整个容器宽度 */
  box-sizing: border-box;
}

.user-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--text-primary);
  white-space: nowrap; /* 防止文本换行 */
  overflow: hidden; /* 隐藏溢出内容 */
  text-overflow: ellipsis; /* 使用省略号表示被截断的文本 */
  max-width: 100%; /* 限制最大宽度 */
}

.user-email {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 2px;
  white-space: nowrap; /* 防止文本换行 */
  overflow: hidden; /* 隐藏溢出内容 */
  text-overflow: ellipsis; /* 使用省略号表示被截断的文本 */
  max-width: 100%; /* 限制最大宽度 */
}

.vertical-divider {
  height: 24px;
  width: 1px;
  background-color: var(--border-color);
  margin: 0 var(--spacing-sm);
  align-self: center;
}

@keyframes modalEnter {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@media (max-width: 768px) {
  .navbar {
    padding: 0 var(--spacing-sm);
  }
  
  .logo-image {
    display: none;
  }
  
  .notifications-panel {
    left: auto;
    right: 0;
    transform: none;
    width: 280px;
  }
  
  .user-dropdown-menu {
    left: auto;
    right: 0;
    transform: none;
  }
  
  .login-modal {
    margin: var(--spacing-md);
  }
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.3s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.modal-enter-active,
.modal-leave-active {
  transition: all 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .login-modal,
.modal-enter-from .register-modal,
.modal-leave-to .login-modal,
.modal-leave-to .register-modal {
  transform: scale(0.9);
}

.login-modal,
.register-modal {
  transition: transform 0.3s ease;
}

.login-button,
.theme-toggle-button,
.notification-button,
.user-button,
.dropdown-item {
  transition: all 0.2s ease;
}

.login-button:hover,
.theme-toggle-button:hover,
.notification-button:hover,
.user-button:hover,
.dropdown-item:hover {
  transform: translateY(-1px);
}

.login-button:active,
.theme-toggle-button:active,
.notification-button:active,
.user-button:active,
.dropdown-item:active {
  transform: translateY(0);
}

.form-group input {
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.form-group input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.1);
}

.loading-notifications {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-tertiary);
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: var(--spacing-sm);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.notification-type-badge {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 10px;
  margin-bottom: 4px;
  font-weight: 500;
}

.notification-toast {
  position: fixed;
  top: 20px;
  right: 20px;
  min-width: 300px;
  max-width: 400px;
  padding: 15px;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 9999;
  opacity: 0;
  transform: translateY(-20px);
  transition: opacity 0.3s, transform 0.3s;
  font-family: var(--font-family);
}

.notification-toast.show {
  opacity: 1;
  transform: translateY(0);
}

.notification-toast-title {
  font-weight: bold;
  margin-bottom: 5px;
  font-size: 16px;
  color: #333;
}

.notification-toast-message {
  font-size: 14px;
  color: #666;
  word-break: break-word;
}

.field-hint {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  margin-top: 4px;
}

.optional {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  font-weight: normal;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  backdrop-filter: blur(3px);
}

.modal-container {
  background-color: var(--surface-color);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-lg);
  width: 90%;
  max-width: 800px; /* 增加模态框宽度，以适应横向布局 */
  max-height: 90vh;
  overflow: hidden;
  animation: modal-in 0.3s ease;
}

@keyframes modal-in {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h2 {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}

.close-button {
  background: none;
  border: none;
  font-size: 1.5rem;
  line-height: 1;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 0;
  margin: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.close-button:hover {
  background-color: var(--hover-color);
  color: var(--text-primary);
}

.modal-body {
  padding: var(--spacing-lg);
  overflow-y: auto;
  max-height: 60vh;
}

.modal-footer {
  padding: var(--spacing-md) var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
}

.btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: var(--border-radius-md);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.btn-primary {
  background-color: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  background-color: var(--primary-color-hover);
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-lg);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(var(--primary-color-rgb), 0.3);
  border-radius: 50%;
  border-top-color: var(--primary-color);
  animation: spin 1s linear infinite;
  margin-bottom: var(--spacing-md);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 推薦碼相關樣式 */
.referral-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.referral-top-section {
  display: flex;
  flex-direction: row;
  gap: var(--spacing-lg);
  width: 100%;
}

.referral-code-section,
.referrer-section {
  background-color: var(--surface-color-alt);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-lg);
  border: 1px solid var(--border-color);
}

.referral-code-section {
  flex: 2; /* 占更多空间 */
}

.referrer-section {
  flex: 1; /* 占更少空间 */
}

.referral-code-section h3,
.referrer-section h3 {
  margin-top: 0;
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-md);
  color: var(--text-primary);
}

.code-display {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.code {
  font-family: monospace;
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--primary-color);
  background-color: rgba(var(--primary-color-rgb), 0.1);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--border-radius-md);
  letter-spacing: 1px;
}

.copy-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: all 0.2s ease;
  white-space: nowrap;
}

.copy-button:hover {
  background-color: var(--primary-color-hover);
}

.referrer-info {
  background-color: rgba(var(--primary-color-rgb), 0.05);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-md);
}

.referrer-info p {
  margin: var(--spacing-xs) 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}

.no-referrer {
  color: var(--text-tertiary);
  font-style: italic;
  margin: 0;
}

.referral-instructions {
  background-color: var(--surface-color-alt);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-lg);
  border: 1px solid var(--border-color);
  margin-bottom: var(--spacing-lg);
}

.referral-instructions h3 {
  margin-top: 0;
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-md);
  color: var(--text-primary);
}

.referral-instructions ol {
  padding-left: var(--spacing-lg);
  margin: 0;
}

.referral-instructions ol li {
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding-left: var(--spacing-xs);
}

.referral-benefits h4 {
  margin-top: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}

.referral-benefits ul {
  padding-left: var(--spacing-lg);
  margin: 0;
}

.referral-benefits ul li {
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.referrals-list-section {
  margin-top: var(--spacing-md);
}

.referrals-list {
  background-color: var(--surface-color-alt);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-md);
  border: 1px solid var(--border-color);
  overflow-x: auto; /* 添加水平滚动支持 */
}

.referrals-header {
  display: grid;
  grid-template-columns: 1.5fr 2fr 1.5fr 1.5fr;
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--spacing-xs);
}

.referrals-header span {
  font-weight: 600;
  color: var(--text-primary);
  padding: 0 var(--spacing-xs);
}

.referral-item {
  display: grid;
  grid-template-columns: 1.5fr 2fr 1.5fr 1.5fr;
  padding: var(--spacing-xs) 0;
  border-bottom: 1px solid var(--border-color-light);
  transition: background-color 0.2s;
}

.referral-item:hover {
  background-color: var(--surface-color-hover);
}

.item-username,
.item-email,
.item-date,
.item-status {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  padding: 0 var(--spacing-xs);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.item-status.status-active {
  color: #52c41a;
}

.item-status.status-inactive {
  color: #ff4d4f;
}

.no-referrals {
  color: var(--text-tertiary);
  font-style: italic;
  margin: var(--spacing-md) 0;
}

.notification-local-info {
  padding: 0 var(--spacing-md);
  margin-bottom: var(--spacing-xs);
  text-align: center;
  color: var(--text-tertiary);
  font-size: 0.75rem;
  background-color: var(--bg-secondary);
  padding: 4px 0;
  border-bottom: 1px solid var(--border-color-light);
}

.loading-notifications {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-tertiary);
}

/* 搜索框樣式 */
.search-container {
  flex: 1;
  display: flex;
  justify-content: center;
  max-width: 700px;
  margin: 0 auto;
}

.search-box {
  display: flex;
  align-items: center;
  width: 100%;
  max-width: 700px;
  background-color: var(--hover-color);
  border: none;
  border-radius: 8px;
  padding: 4px 8px;
  transition: background-color 0.3s, box-shadow 0.3s;
}

.search-box:hover {
  background-color: var(--hover-color);
  box-shadow: 0 1px 5px rgba(0, 0, 0, 0.1);
}

.search-box:focus-within {
  background-color: var(--background-color);
  box-shadow: 0 1px 5px rgba(0, 0, 0, 0.2);
  border: 1px solid var(--border-color);
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 8px;
  font-size: 14px;
  color: var(--text-primary);
  outline: none;
}

.search-button {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.search-button:hover {
  color: var(--primary-color);
}

/* 響應式搜索框樣式 */
@media (max-width: 768px) {
  .search-container {
    max-width: 200px;
    margin: 0 10px;
  }
  
  .search-input {
    font-size: 13px;
    padding: 0 10px;
  }
}

@media (max-width: 576px) {
  .search-container {
    display: none; /* 在極小屏幕上隱藏搜索框 */
  }
}

.icon-button {
  background: none;
  border: none;
  padding: var(--spacing-sm);
  cursor: pointer;
  border-radius: var(--border-radius-sm);
  color: var(--text-primary);
  transition: all var(--transition-fast) ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-button:hover {
  background-color: var(--hover-color);
}
</style> 