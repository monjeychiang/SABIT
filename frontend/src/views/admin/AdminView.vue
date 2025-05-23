<template>
  <div class="admin-page">
    <PageHeader title="管理員面板" />
    
    <!-- 添加儀表板統計信息 -->
    <div class="dashboard-stats">
      <div class="stat-card">
        <div class="stat-icon users-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
          </svg>
        </div>
        <div class="stat-content">
          <h3>註冊用戶數</h3>
          <p class="stat-value">{{ userCount }}</p>
          <p class="stat-description">活躍用戶: {{ activeUserCount }}</p>
        </div>
      </div>

      <!-- 添加在線用戶統計卡片 -->
      <div class="stat-card">
        <div class="stat-icon online-icon">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
            <circle cx="9" cy="7" r="4"></circle>
            <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
            <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
            <circle cx="19" cy="4" r="2" fill="#10b981"></circle>
          </svg>
        </div>
        <div class="stat-content">
          <h3>在線用戶</h3>
          <p class="stat-value">{{ onlineUserCount }}</p>
          <p class="stat-description" v-if="userCount > 0">活躍率: {{ Math.round((onlineUserCount / userCount) * 100) }}%</p>
        </div>
      </div>
      
      <!-- 發送通知按鈕 -->
      <div class="notification-action-card">
        <button class="notification-send-btn" @click="openSendNotificationModal">
          <div class="btn-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 2L11 13"></path>
              <path d="M22 2L15 22L11 13L2 9L22 2Z"></path>
            </svg>
          </div>
          <div class="btn-content">
            <h3>發送通知</h3>
            <p class="btn-description">向指定用戶或全部用戶發送通知</p>
          </div>
        </button>
      </div>
    </div>
    
    <div class="admin-container">
      <div class="admin-section">
        <h2>在線用戶</h2>
        <OnlineUsersWidget :refresh-interval="60000" :max-users="10" />
      </div>
    </div>
    
    <!-- 以下刪除用戶登錄記錄部分 -->
    <div class="admin-container">
      <div class="admin-section">
        <h2>用戶管理</h2>
        
        <div class="search-filter">
          <div class="input-group">
            <label for="search">搜索用戶:</label>
            <input 
              id="search" 
              v-model="searchQuery" 
              type="text" 
              placeholder="輸入用戶名或郵箱..." 
              @keyup.enter="searchUsers"
            >
          </div>
          <button class="btn btn-primary" @click="searchUsers">搜索</button>
        </div>
        
        <div class="table-wrapper" v-if="users.length">
          <table class="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>用戶名</th>
                <th>郵箱</th>
                <th>創建時間</th>
                <th>狀態</th>
                <th>標籤</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td>{{ user.id }}</td>
                <td>{{ user.username }}</td>
                <td>{{ user.email }}</td>
                <td>{{ formatDate(user.created_at) }}</td>
                <td>
                  <span class="tag" :class="user.is_active ? 'is-success' : 'is-danger'">
                    {{ user.is_active ? '啟用' : '禁用' }}
                  </span>
                </td>
                <td>
                  <span class="tag" :class="getUserTagClass(user.user_tag)">
                    {{ getUserTagName(user.user_tag) }}
                  </span>
                </td>
                <td class="actions">
                  <button class="action-btn" title="編輯用戶" @click="editUser(user)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M20 14.66V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5.34"></path>
                      <polygon points="18 2 22 6 12 16 8 16 8 12 18 2"></polygon>
                    </svg>
                  </button>
                  <button 
                    class="action-btn" 
                    :title="getStatusButtonTitle(user)"
                    @click="toggleUserStatus(user)"
                    :disabled="isAdminUser(user)"
                    :class="{ 'disabled-btn': isAdminUser(user) }"
                  >
                    <svg v-if="user.is_active" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="8" y1="12" x2="16" y2="12"></line>
                    </svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="12" y1="8" x2="12" y2="16"></line>
                      <line x1="8" y1="12" x2="16" y2="12"></line>
                    </svg>
                  </button>
                  <!-- 添加用戶詳細資料按鈕 -->
                  <button class="action-btn" title="查看詳細資料" @click="viewUserDetails(user)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="10"></circle>
                      <line x1="12" y1="16" x2="12" y2="12"></line>
                      <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <div class="empty-state" v-else>
          <p>{{ loading ? '正在加載用戶數據...' : '未找到用戶數據' }}</p>
        </div>
        
        <div class="pagination" v-if="totalPages > 1">
          <button 
            class="page-btn" 
            @click="changePage(currentPage - 1)" 
            :disabled="currentPage === 1"
          >
            上一頁
          </button>
          
          <!-- 添加頁碼顯示 -->
          <div class="page-numbers">
            <!-- 首頁按鈕 -->
            <button 
              v-if="currentPage > 3" 
              class="page-number" 
              @click="changePage(1)"
            >
              1
            </button>
            
            <!-- 省略號 -->
            <span v-if="currentPage > 4" class="page-ellipsis">...</span>
            
            <!-- 頁碼按鈕 -->
            <button 
              v-for="page in displayedPages" 
              :key="page" 
              class="page-number" 
              :class="{ 'current': page === currentPage }"
              @click="changePage(page)"
            >
              {{ page }}
            </button>
            
            <!-- 省略號 -->
            <span v-if="currentPage < totalPages - 3" class="page-ellipsis">...</span>
            
            <!-- 最後頁按鈕 -->
            <button 
              v-if="currentPage < totalPages - 2" 
              class="page-number" 
              @click="changePage(totalPages)"
            >
              {{ totalPages }}
            </button>
          </div>
          
          <!-- 添加直接跳轉輸入框 -->
          <div class="page-jump">
            <span>前往</span>
            <input 
              v-model.number="jumpPage" 
              type="number" 
              min="1" 
              :max="totalPages" 
              @keyup.enter="handleJumpPage"
            >
            <span>頁</span>
            <button class="jump-btn" @click="handleJumpPage">確定</button>
          </div>
          
          <button 
            class="page-btn" 
            @click="changePage(currentPage + 1)" 
            :disabled="currentPage === totalPages"
          >
            下一頁
          </button>
        </div>
      </div>
    </div>
    
    <!-- 伺服器狀態區域，移動到最後 -->
    <div class="admin-container">
      <div class="admin-section">
        <h2>伺服器狀態</h2>
        <button class="btn btn-primary" @click="fetchServerStatus">
          <i class="fas fa-sync-alt"></i> 刷新
        </button>
        
        <div class="server-status-content" v-if="serverStatus">
          <div class="status-grid">
            <!-- 系統信息 -->
            <div class="status-card">
              <h4>系統信息</h4>
              <div class="status-info">
                <div class="info-item">
                  <span class="label">操作系統:</span>
                  <span class="value">{{ serverStatus.system.system }} {{ serverStatus.system.version }}</span>
                </div>
                <div class="info-item">
                  <span class="label">處理器:</span>
                  <span class="value">{{ serverStatus.system.processor }}</span>
                </div>
                <div class="info-item">
                  <span class="label">主機名:</span>
                  <span class="value">{{ serverStatus.system.hostname }}</span>
                </div>
                <div class="info-item">
                  <span class="label">IP地址:</span>
                  <span class="value">{{ serverStatus.system.ip }}</span>
                </div>
              </div>
            </div>
            
            <!-- 資源使用情況 -->
            <div class="status-card">
              <h4>資源使用情況</h4>
              <div class="status-info">
                <div class="resource-item">
                  <span class="label">CPU使用率:</span>
                  <div class="progress-container">
                    <div class="progress">
                      <div class="progress-bar" 
                           :class="getResourceClass(serverStatus.resources.cpu_percent)" 
                           :style="{width: `${serverStatus.resources.cpu_percent}%`}">
                      </div>
                    </div>
                    <span class="progress-value">{{ serverStatus.resources.cpu_percent }}%</span>
                  </div>
                </div>
                
                <div class="resource-item">
                  <span class="label">記憶體使用:</span>
                  <div class="progress-container">
                    <div class="progress">
                      <div class="progress-bar" 
                           :class="getResourceClass(serverStatus.resources.memory.percent)" 
                           :style="{width: `${serverStatus.resources.memory.percent}%`}">
                      </div>
                    </div>
                    <span class="progress-value">
                      {{ serverStatus.resources.memory.used.toFixed(2) }}GB / {{ serverStatus.resources.memory.total.toFixed(2) }}GB 
                      ({{ serverStatus.resources.memory.percent }}%)
                    </span>
                  </div>
                </div>
                
                <div class="resource-item">
                  <span class="label">硬碟使用:</span>
                  <div class="progress-container">
                    <div class="progress">
                      <div class="progress-bar" 
                           :class="getResourceClass(serverStatus.resources.disk.percent)" 
                           :style="{width: `${serverStatus.resources.disk.percent}%`}">
                      </div>
                    </div>
                    <span class="progress-value">
                      {{ serverStatus.resources.disk.used.toFixed(2) }}GB / {{ serverStatus.resources.disk.total.toFixed(2) }}GB 
                      ({{ serverStatus.resources.disk.percent }}%)
                    </span>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- 時間信息 -->
            <div class="status-card">
              <h4>時間信息</h4>
              <div class="status-info">
                <div class="info-item">
                  <span class="label">伺服器時間:</span>
                  <span class="value">{{ serverStatus.time.server_time }}</span>
                </div>
                <div class="info-item">
                  <span class="label">啟動時間:</span>
                  <span class="value">{{ serverStatus.time.start_time }}</span>
                </div>
                <div class="info-item">
                  <span class="label">運行時長:</span>
                  <span class="value">{{ formatUptime(serverStatus.time.uptime) }}</span>
                </div>
                <div class="info-item">
                  <span class="label">狀態:</span>
                  <span class="tag is-success">{{ serverStatus.status }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <div class="loading" v-else-if="loadingServerStatus">
          <div class="loader"></div>
        </div>
        
        <div class="error-message" v-else>
          <p>無法獲取伺服器狀態信息</p>
          <button class="btn btn-danger" @click="fetchServerStatus">重試</button>
        </div>
      </div>
    </div>
    
    <!-- 用戶編輯模態框 -->
    <div class="modal" v-if="showEditModal">
      <div class="modal-overlay" @click="showEditModal = false"></div>
      <div class="modal-container">
        <div class="modal-header">
          <h3>編輯用戶</h3>
          <button class="close-btn" @click="showEditModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="updateUser">
            <div class="form-group">
              <label for="username">用戶名</label>
              <input 
                id="username" 
                v-model="editingUser.username" 
                type="text" 
                required
              >
            </div>
            <div class="form-group">
              <label for="email">郵箱</label>
              <input 
                id="email" 
                v-model="editingUser.email" 
                type="email" 
                required
              >
            </div>
            
            <!-- 添加用戶標籤選擇 -->
            <div class="form-group">
              <label>用戶標籤</label>
              <div class="tag-selector">
                <div 
                  v-for="(name, tag) in userTags" 
                  :key="tag"
                  class="tag-option"
                  :class="{ 
                    'selected': editingUser.user_tag === tag,
                    [tag]: true,
                    'disabled': isOriginalAdminUser && tag !== 'admin'
                  }"
                  @click="handleTagSelection(tag)"
                >
                  {{ name }}
                </div>
              </div>
              <div v-if="isOriginalAdminUser" class="admin-warning">
                管理員用戶不能被移除管理員權限
              </div>
            </div>
            
            <!-- 添加管理員密碼驗證 -->
            <div class="form-group admin-password-section">
              <div class="security-tip">
                <strong>安全驗證</strong>
                <p>為了保護用戶資料安全，請輸入您的管理員密碼以確認此次修改。</p>
              </div>
              <label for="admin_password">管理員密碼 <span class="required">*</span></label>
              <div class="password-field">
                <input 
                  :type="showAdminPassword ? 'text' : 'password'" 
                  id="admin_password" 
                  v-model="adminPassword" 
                  placeholder="請輸入您的管理員密碼"
                  required
                >
                <button type="button" class="toggle-button" @click="toggleAdminPasswordVisibility">
                  <span>{{ showAdminPassword ? '隱藏' : '顯示' }}</span>
                </button>
              </div>
              <div v-if="adminPasswordError" class="form-error">{{ adminPasswordError }}</div>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" @click="showEditModal = false">取消</button>
              <button type="submit" class="btn btn-primary" :disabled="isSubmitting">
                {{ isSubmitting ? '保存中...' : '保存' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
    
    <!-- 添加發送通知模態框 -->
    <div class="modal" v-if="showNotificationModal">
      <div class="modal-overlay" @click="showNotificationModal = false"></div>
      <div class="modal-container">
        <div class="modal-header">
          <h3>發送通知</h3>
          <button class="close-btn" @click="showNotificationModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="sendNotification">
            <!-- 修改模板選擇區域為下拉選單式 -->
            <div class="form-group">
              <label>選擇通知模板</label>
              <div class="template-select">
                <div 
                  class="template-trigger"
                  @click="toggleTemplateDropdown"
                >
                  <div class="trigger-content">
                    <div v-if="selectedTemplate" class="selected-template">
                      <div class="template-icon" :class="'type-' + selectedTemplate.notification_type">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <template v-if="selectedTemplate.notification_type === 'system'">
                            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                          </template>
                          <template v-else-if="selectedTemplate.notification_type === 'info'">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                          </template>
                          <template v-else-if="selectedTemplate.notification_type === 'warning'">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                          </template>
                          <template v-else-if="selectedTemplate.notification_type === 'success'">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                            <polyline points="22 4 12 14.01 9 11.01"></polyline>
                          </template>
                        </svg>
                      </div>
                      <div class="selected-info">
                        <span class="template-name">{{ selectedTemplate.name }}</span>
                        <span class="template-type">{{ getNotificationTypeName(selectedTemplate.notification_type) }}</span>
                      </div>
                    </div>
                    <div v-else class="placeholder">
                      請選擇通知模板
                    </div>
                    <div class="dropdown-arrow" :class="{ 'open': showTemplateDropdown }">
                      <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="6 9 12 15 18 9"></polyline>
                      </svg>
                    </div>
                  </div>
                </div>
                
                <div v-if="showTemplateDropdown" class="template-dropdown">
                  <div class="template-search">
                    <input 
                      type="text" 
                      v-model="templateSearchQuery" 
                      placeholder="搜尋模板..."
                      @click.stop
                    >
                  </div>
                  <div class="template-list">
                    <div 
                      v-for="template in filteredTemplates" 
                      :key="template.id"
                      class="template-option"
                      :class="{ 
                        'selected': selectedTemplate?.id === template.id,
                        ['type-' + template.notification_type]: true
                      }"
                      @click="selectTemplate(template)"
                    >
                      <div class="template-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <template v-if="template.notification_type === 'system'">
                            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                            <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                          </template>
                          <template v-else-if="template.notification_type === 'info'">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="16" x2="12" y2="12"></line>
                            <line x1="12" y1="8" x2="12.01" y2="8"></line>
                          </template>
                          <template v-else-if="template.notification_type === 'warning'">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                          </template>
                          <template v-else-if="template.notification_type === 'success'">
                            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                            <polyline points="22 4 12 14.01 9 11.01"></polyline>
                          </template>
                        </svg>
                      </div>
                      <div class="template-info">
                        <span class="template-name">{{ template.name }}</span>
                        <span class="template-description">{{ template.title }}</span>
                      </div>
                      <div v-if="selectedTemplate?.id === template.id" class="selected-check">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 模板變量輸入區域 -->
            <div class="form-group" v-if="Object.keys(templateVariables).length > 0">
              <label>填寫模板變量</label>
              <div class="template-variables">
                <div 
                  v-for="(value, key) in templateVariables" 
                  :key="key" 
                  class="variable-input"
                >
                  <label :for="'var-' + key">{{ key }}</label>
                  <input 
                    :id="'var-' + key"
                    v-model="templateVariables[key]"
                    type="text"
                    :placeholder="'請輸入' + key"
                  >
                </div>
              </div>
            </div>

            <div class="form-group">
              <label for="notification-title">通知標題</label>
              <input 
                id="notification-title" 
                v-model="notificationForm.title" 
                type="text" 
                required
                placeholder="輸入通知標題..."
              >
            </div>
            
            <div class="form-group">
              <label for="notification-message">通知內容</label>
              <textarea 
                id="notification-message" 
                v-model="notificationForm.message" 
                required
                placeholder="輸入通知內容..."
                rows="4"
              ></textarea>
            </div>
            
            <!-- 添加通知類型選擇 -->
            <div class="form-group">
              <label for="notification-type">通知類型</label>
              <div class="notification-type-selector">
                <div 
                  v-for="(type, key) in notificationTypes" 
                  :key="key"
                  class="notification-type-option"
                  :class="{ 
                    'selected': notificationForm.notification_type === key.toLowerCase(), 
                    ['type-' + key.toLowerCase()]: true 
                  }"
                  @click="selectNotificationType(key)"
                >
                  <div class="type-icon" :class="'icon-' + key.toLowerCase()">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <!-- INFO 圖標 -->
                      <template v-if="key.toLowerCase() === 'info'">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                      </template>
                      <!-- SUCCESS 圖標 -->
                      <template v-else-if="key.toLowerCase() === 'success'">
                        <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                        <polyline points="22 4 12 14.01 9 11.01"></polyline>
                      </template>
                      <!-- WARNING 圖標 -->
                      <template v-else-if="key.toLowerCase() === 'warning'">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                      </template>
                      <!-- ERROR 圖標 -->
                      <template v-else-if="key.toLowerCase() === 'error'">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="15" y1="9" x2="9" y2="15"></line>
                        <line x1="9" y1="9" x2="15" y2="15"></line>
                      </template>
                      <!-- SYSTEM 圖標 -->
                      <template v-else-if="key.toLowerCase() === 'system'">
                        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
                        <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
                      </template>
                    </svg>
                  </div>
                  <div class="type-label">{{ getNotificationTypeName(key) }}</div>
                </div>
              </div>
            </div>
            
            <div class="form-group">
              <div class="checkbox-wrapper">
                <input 
                  id="is-global" 
                  v-model="notificationForm.is_global" 
                  type="checkbox"
                  @change="handleGlobalChange"
                >
                <label for="is-global">發送給所有用戶</label>
              </div>
            </div>
            
            <div class="form-group" v-if="!notificationForm.is_global">
              <label for="selected-users">選擇接收者</label>
              <div class="selected-users-list">
                <div v-if="selectedUsers.length === 0" class="empty-selection">
                  未選擇任何用戶
                </div>
                <div v-else class="selected-user-tags">
                  <div v-for="user in selectedUsers" :key="user.id" class="user-tag">
                    {{ user.username }}
                    <button type="button" class="remove-tag" @click="removeSelectedUser(user.id)">×</button>
                  </div>
                </div>
              </div>
              
              <div class="users-selector">
                <input 
                  type="text" 
                  v-model="userSearchQuery" 
                  placeholder="搜索用戶..." 
                  @input="searchSelectableUsers"
                >
                <div class="selectable-users-dropdown" v-if="showUserSelector">
                  <div v-if="filteredSelectableUsers.length === 0" class="empty-users">
                    無匹配用戶
                  </div>
                  <div 
                    v-for="user in filteredSelectableUsers" 
                    :key="user.id" 
                    class="selectable-user"
                    @click="selectUser(user)"
                  >
                    {{ user.username }} ({{ user.email }})
                  </div>
                </div>
              </div>
            </div>
            
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" @click="showNotificationModal = false">取消</button>
              <button 
                type="submit" 
                class="btn btn-primary" 
                :disabled="isSendingNotification || (!notificationForm.is_global && selectedUsers.length === 0)"
              >
                {{ isSendingNotification ? '發送中...' : '發送通知' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 管理員面板主體內容 -->
    <div class="admin-panel-content">
      <!-- 通知發送部分保持不變 -->
    </div>
    
    <!-- 用戶詳細資料模態框 -->
    <div class="modal user-details-modal" v-if="showUserDetailsModal">
      <div class="modal-overlay" @click="showUserDetailsModal = false"></div>
      <div class="modal-container">
        <div class="modal-header">
          <h3>用戶詳細資料</h3>
          <button class="close-btn" @click="showUserDetailsModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div v-if="loadingUserDetails" class="loading-container">
            <div class="loader"></div>
          </div>
          
          <div v-else-if="userDetails" class="user-details-content">
            <div class="user-details-flex-container">
              <!-- 用戶基本資訊 -->
              <div class="details-section user-info-section">
                <h4>基本資訊</h4>
                <!-- 添加用戶頭像顯示 -->
                <div class="user-avatar-container">
                  <UserAvatar 
                    :username="userDetails.user_info.username"
                    :avatar-url="userDetails.user_info.avatar_url"
                    size="medium"
                    :no-cache="false"
                  />
                  <h3 class="user-fullname">
                    {{ userDetails.user_info.full_name || userDetails.user_info.username }}
                  </h3>
                </div>
                <div class="details-grid">
                  <div class="details-item">
                    <span class="label">用戶ID:</span>
                    <span class="value">{{ userDetails.user_info.id }}</span>
                  </div>
                  <div class="details-item">
                    <span class="label">用戶名:</span>
                    <span class="value">{{ userDetails.user_info.username }}</span>
                  </div>
                  <div class="details-item">
                    <span class="label">郵箱:</span>
                    <span class="value">{{ userDetails.user_info.email }}</span>
                  </div>
                  <div class="details-item">
                    <span class="label">創建時間:</span>
                    <span class="value">{{ userDetails.user_info.created_at }}</span>
                  </div>
                  <div class="details-item">
                    <span class="label">用戶類型:</span>
                    <span class="value">
                      <span class="tag" :class="getUserTagClass(userDetails.user_info.user_tag)">
                        {{ getUserTagName(userDetails.user_info.user_tag) }}
                      </span>
                    </span>
                  </div>
                  <div class="details-item">
                    <span class="label">狀態:</span>
                    <span class="value">
                      <span class="tag" :class="userDetails.user_info.is_active ? 'is-success' : 'is-danger'">
                        {{ userDetails.user_info.is_active ? '啟用' : '禁用' }}
                      </span>
                    </span>
                  </div>
                  <div class="details-item">
                    <span class="label">郵箱驗證:</span>
                    <span class="value">
                      <span class="tag" :class="userDetails.user_info.is_verified ? 'is-success' : 'is-warning'">
                        {{ userDetails.user_info.is_verified ? '已驗證' : '未驗證' }}
                      </span>
                    </span>
                  </div>
                </div>
              </div>
              
              <!-- 用戶登入記錄 -->
              <div class="details-section login-history-section">
                <h4>登入記錄</h4>
                <div v-if="userDetails.login_history.length" class="login-history">
                  <table class="data-table">
                    <thead>
                      <tr>
                        <th>登入時間</th>
                        <th>IP地址</th>
                        <th>狀態</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(login, index) in userDetails.login_history" :key="index">
                        <td>{{ login.login_time }}</td>
                        <td>{{ login.login_ip }}</td>
                        <td>
                          <span class="tag is-success" v-if="login.is_current">當前</span>
                          <span class="tag is-default" v-else>歷史</span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="empty-state">
                  <p>無登入記錄</p>
                </div>
              </div>
            </div>
            
            <div class="details-actions">
              <button class="btn btn-secondary" @click="showUserDetailsModal = false">
                關閉
              </button>
            </div>
          </div>
          
          <div v-else class="error-message">
            <p>無法載入用戶資料。請重試。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, onUnmounted } from 'vue';
import axios from 'axios';
import PageHeader from '@/components/PageHeader.vue';
import { useToast } from '@/composables/useToast';
import { useAuthStore } from '@/stores/auth';
import OnlineUsersWidget from '@/components/OnlineUsersWidget.vue';
import UserAvatar from '@/components/UserAvatar.vue';

defineOptions({
  name: 'AdminView'
});

const { showToast } = useToast();
const authStore = useAuthStore();

// 統計相關變量
const userCount = ref(0);
const activeUserCount = ref(0);
const notificationCount = ref(0);
const globalNotificationCount = ref(0);

// 用戶數據相關
const users = ref([]);
const loading = ref(false);
const searchQuery = ref('');
const currentPage = ref(1);
const totalPages = ref(1);
const perPage = ref(10);  // 確保每頁顯示10條記錄

// 用戶編輯相關
const showEditModal = ref(false);
const editingUser = ref({
  id: null,
  username: '',
  email: '',
  user_tag: 'regular'
});

// 載入相關變量
const serverStatusLoadStartTime = ref(0);
const userDetailsLoadStartTime = ref(0);

// 計算總頁數
const totalItems = ref(0);

// 通知相關
const showNotificationModal = ref(false);
const isSendingNotification = ref(false);
const notificationForm = ref({
  title: '',
  message: '',
  is_global: false,
  user_ids: [],
  notification_type: 'info'
});

// 添加常用通知模板
const notificationTemplates = ref([
  {
    id: 1,
    name: '系統維護通知',
    title: '系統維護通知',
    message: '親愛的用戶，系統將於 {date} {time} 進行維護升級，預計維護時間為 {duration} 小時。維護期間將暫停服務，造成不便敬請見諒。',
    notification_type: 'system',
    variables: ['date', 'time', 'duration']
  },
  {
    id: 2,
    name: '功能更新通知',
    title: '新功能上線通知',
    message: '我們很高興地通知您，{feature} 功能已正式上線！{description}',
    notification_type: 'info',
    variables: ['feature', 'description']
  },
  {
    id: 3,
    name: '安全警告通知',
    title: '安全提醒',
    message: '我們檢測到您的帳戶於 {time} 從 {location} 進行登入。如非本人操作，請立即修改密碼並聯繫客服。',
    notification_type: 'warning',
    variables: ['time', 'location']
  },
  {
    id: 4,
    name: '交易提醒',
    title: '交易狀態更新',
    message: '您的訂單 {order_id} 已{status}。{details}',
    notification_type: 'success',
    variables: ['order_id', 'status', 'details']
  }
]);

// 當前選中的模板變量值
const templateVariables = ref({});

// 選擇通知模板
const selectTemplate = (template) => {
  selectedTemplate.value = template;
  showTemplateDropdown.value = false;
  
  // 重置模板變量
  templateVariables.value = {};
  template.variables.forEach(variable => {
    templateVariables.value[variable] = '';
  });
  
  // 設置表單初始值
  notificationForm.value.title = template.title;
  notificationForm.value.message = template.message;
  notificationForm.value.notification_type = template.notification_type;
};

// 更新模板內容
const updateTemplateContent = () => {
  const selectedTemplate = notificationTemplates.value.find(t => 
    t.title === notificationForm.value.title
  );
  
  if (!selectedTemplate) return;
  
  let message = selectedTemplate.message;
  Object.entries(templateVariables.value).forEach(([key, value]) => {
    message = message.replace(`{${key}}`, value || `{${key}}`);
  });
  
  notificationForm.value.message = message;
};

// 監聽模板變量變化
watch(templateVariables, () => {
  updateTemplateContent();
}, { deep: true });

// 初始化通知類型和樣式為具體值，避免引用問題
const notificationTypes = ref({
  INFO: 'info',       // 一般信息
  SUCCESS: 'success', // 成功信息
  WARNING: 'warning', // 警告信息
  ERROR: 'error',     // 错误信息
  SYSTEM: 'system'    // 系统通知
});

const notificationStyles = ref({
  'info': {
    icon: 'info-circle',
    color: '#1677ff',
    bgColor: '#e6f7ff'
  },
  'success': {
    icon: 'check-circle',
    color: '#52c41a',
    bgColor: '#f6ffed'
  },
  'warning': {
    icon: 'warning',
    color: '#faad14',
    bgColor: '#fffbe6'
  },
  'error': {
    icon: 'close-circle',
    color: '#ff4d4f',
    bgColor: '#fff2f0'
  },
  'system': {
    icon: 'bell',
    color: '#722ed1',
    bgColor: '#f9f0ff'
  }
});

// 確保通知樣式已正確加載
console.log('通知樣式：', notificationStyles.value);

// 獲取通知類型的中文名稱
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

// 選擇通知類型
const selectNotificationType = (type) => {
  notificationForm.value.notification_type = type.toLowerCase();
  console.log('選擇通知類型:', notificationForm.value.notification_type);
};

const selectableUsers = ref([]); // 可選擇的用戶列表
const selectedUsers = ref([]); // 已選擇的用戶
const userSearchQuery = ref(''); // 用戶搜索關鍵字
const showUserSelector = ref(false); // 是否顯示用戶選擇器
const filteredSelectableUsers = computed(() => {
  if (!userSearchQuery.value) return selectableUsers.value;
  
  return selectableUsers.value.filter(user => 
    user.username.toLowerCase().includes(userSearchQuery.value.toLowerCase()) ||
    user.email.toLowerCase().includes(userSearchQuery.value.toLowerCase())
  );
});

// 用戶標籤定義
const userTags = {
  'admin': '管理員',
  'regular': '一般用戶',
  'premium': '高級用戶'
};

// 添加管理員密碼相關變量
const adminPassword = ref('');
const adminPasswordError = ref('');
const showAdminPassword = ref(false);
const isSubmitting = ref(false);

// 切換管理員密碼可見性
const toggleAdminPasswordVisibility = () => {
  showAdminPassword.value = !showAdminPassword.value;
};

// 清空管理員密碼和錯誤提示
const resetAdminPassword = () => {
  adminPassword.value = '';
  adminPasswordError.value = '';
};

// 用戶標籤樣式類
const getUserTagClass = (tag) => {
  const tagClasses = {
    'admin': 'is-danger',
    'regular': 'is-info',
    'premium': 'is-warning'
  };
  return tagClasses[tag] || 'is-default';
};

// 獲取用戶標籤名稱
const getUserTagName = (tag) => {
  return userTags[tag] || '未知';
};

// 伺服器狀態相關變量
const serverStatus = ref(null);
const loadingServerStatus = ref(false);
const usersLoginHistory = ref([]);
const loadingLoginHistory = ref(false);

// 在線用戶統計
const onlineUserCount = ref(0);
const onlineUserRefreshInterval = ref(null);

// 獲取在線用戶數
const fetchOnlineUserCount = async () => {
  try {
    // 獲取token
    const token = authStore.token || localStorage.getItem('token');
    
    // 設置請求頭
    const headers = token ? { 'Authorization': `bearer ${token}` } : {};
    
    const response = await axios.get('/api/v1/users/active-users-count', { headers });
    
    onlineUserCount.value = response.data.active_users || 0;
  } catch (error) {
    console.error('獲取在線用戶數失敗:', error);
  }
};

// 獲取伺服器狀態信息
const fetchServerStatus = async () => {
  loadingServerStatus.value = true;
  serverStatusLoadStartTime.value = Date.now(); // 記錄載入開始時間
  
  try {
    const response = await axios.get('/api/v1/system/status', {
      headers: { 'Authorization': `Bearer ${authStore.token}` }
    });
    serverStatus.value = response.data;
    console.log('伺服器狀態:', serverStatus.value);
    
    // 確保載入動畫至少顯示0.5秒
    const loadingDuration = Date.now() - serverStatusLoadStartTime.value;
    if (loadingDuration < 500) {
      setTimeout(() => {
        loadingServerStatus.value = false;
      }, 500 - loadingDuration);
    } else {
      loadingServerStatus.value = false;
    }
  } catch (error) {
    console.error('獲取伺服器狀態失敗:', error);
    showToast('獲取伺服器狀態失敗', 'error');
    
    // 確保載入動畫至少顯示0.5秒
    const loadingDuration = Date.now() - serverStatusLoadStartTime.value;
    if (loadingDuration < 500) {
      setTimeout(() => {
        loadingServerStatus.value = false;
      }, 500 - loadingDuration);
    } else {
      loadingServerStatus.value = false;
    }
  }
};

// 根據資源使用百分比獲取相應的樣式類
const getResourceClass = (percent) => {
  if (percent >= 80) return 'is-danger';
  if (percent >= 60) return 'is-warning';
  return 'is-success';
};

// 格式化伺服器運行時間
const formatUptime = (uptime) => {
  if (!uptime) return '未知';
  
  const days = uptime.days;
  const hours = uptime.hours;
  const minutes = uptime.minutes;
  const seconds = uptime.seconds;
  
  let result = '';
  
  if (days > 0) result += `${days}天 `;
  result += `${hours}小时 ${minutes}分钟 ${seconds}秒`;
  
  return result;
};

// 獲取用戶登入歷史記錄
const fetchUserLoginHistory = async () => {
  // 此函數已被廢棄，用戶登入歷史現在通過用戶詳情頁面查看
  console.log('此函數已被廢棄，用戶登入歷史現在通過用戶詳情頁面查看');
};

// 頁面加載時獲取用戶數據和系統統計信息
onMounted(() => {
  // 加載用戶數據
  fetchUsers();
  
  // 獲取系統統計數據
  fetchStatistics();
  
  // 獲取伺服器狀態
  fetchServerStatus();
  
  // 獲取在線用戶數並定期刷新
  fetchOnlineUserCount();
  onlineUserRefreshInterval.value = setInterval(fetchOnlineUserCount, 60000); // 每1分鐘刷新
  
  // 設置監聽器處理選擇器的點擊外部事件
  document.addEventListener('click', handleDocumentClick);
});

// 添加 onUnmounted 鉤子清理資源
onUnmounted(() => {
  // 清除刷新計時器
  if (onlineUserRefreshInterval.value) {
    clearInterval(onlineUserRefreshInterval.value);
  }
  
  // 移除事件監聽器
  document.removeEventListener('click', handleDocumentClick);
});

// 獲取系統統計數據
const fetchStatistics = async () => {
  try {
    // 獲取用戶總數和活躍用戶數
    const usersResponse = await axios.get('/api/v1/admin/users', {
      params: { page: 1, per_page: 1 },
      headers: { 'Authorization': `Bearer ${authStore.token}` }
    });
    
    userCount.value = usersResponse.data.total || 0;
    
    // 計算活躍用戶數
    const activeUsersResponse = await axios.get('/api/v1/admin/users', {
      params: { page: 1, per_page: 100, is_active: true },
      headers: { 'Authorization': `Bearer ${authStore.token}` }
    });
    
    activeUserCount.value = activeUsersResponse.data.total || 0;
    
    // 獲取通知數量 - 移除API調用，使用固定值
    notificationCount.value = 0;
    globalNotificationCount.value = 0;
  } catch (error) {
    console.error('獲取統計數據失敗:', error);
  }
};

// 獲取用戶列表
const fetchUsers = async () => {
  loading.value = true;
  try {
    const response = await axios.get(`/api/v1/admin/users`, {
      params: {
        page: currentPage.value,
        per_page: perPage.value,
        search: searchQuery.value || undefined
      },
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    });
    
    users.value = response.data.items;
    totalItems.value = response.data.total;
    currentPage.value = response.data.page;
    totalPages.value = Math.ceil(response.data.total / perPage.value) || 1;
    
    // 更新用戶總數
    userCount.value = response.data.total;
    
    // 估算活躍用戶數量
    activeUserCount.value = users.value.filter(user => user.is_active).length;
    
    if (users.value.length === 0 && totalPages.value > 0 && currentPage.value > 1) {
      // 如果當前頁沒有數據但總數大於0，回到第一頁
      currentPage.value = 1;
      await fetchUsers();
    }
  } catch (error) {
    console.error('獲取用戶列表失敗:', error);
    showToast('獲取用戶列表失敗，請重試', 'error');
  } finally {
    loading.value = false;
  }
};

// 搜索用戶
const searchUsers = async () => {
  currentPage.value = 1;
  await fetchUsers();
};

// 分頁切換
const changePage = async (page) => {
  if (page < 1 || page > totalPages.value) return;
  currentPage.value = page;
  await fetchUsers();
};

// 編輯用戶
const editUser = (user) => {
  editingUser.value = { ...user };
  resetAdminPassword();
  showEditModal.value = true;
};

// 更新用戶信息
const updateUser = async () => {
  if (!adminPassword.value) {
    adminPasswordError.value = '請輸入管理員密碼以確認此操作';
    return;
  }
  
  try {
    isSubmitting.value = true;
    adminPasswordError.value = '';
    
    // 如果用戶是管理員，確保保持管理員權限和活躍狀態
    const originalUser = users.value.find(u => u.id === editingUser.value.id);
    const wasAdmin = originalUser && (originalUser.user_tag === 'admin' || originalUser.is_admin);
    
    // 根據用戶標籤設置相應的權限
    const isAdmin = editingUser.value.user_tag === 'admin';
    
    // 如果用戶原本是管理員，但嘗試移除管理員權限，顯示警告並保持管理員權限
    if (wasAdmin && !isAdmin) {
      showToast('不能移除管理員用戶的管理員權限', 'warning');
      editingUser.value.user_tag = 'admin';
      return;
    }
    
    // 確保管理員用戶始終處於活躍狀態
    const isActive = wasAdmin ? true : (editingUser.value.user_tag !== 'disabled');
    
    // 先驗證管理員密碼
    const verifyResponse = await axios.post(
      '/api/v1/auth/verify-admin', 
      { password: adminPassword.value },
      { headers: { 'Authorization': `Bearer ${authStore.token}` } }
    );
    
    if (!verifyResponse.data.success) {
      adminPasswordError.value = '管理員密碼不正確';
      return;
    }
    
    // A驗證成功後更新用戶信息
    await axios.put(`/api/v1/admin/users/${editingUser.value.id}`, {
      username: editingUser.value.username,
      email: editingUser.value.email,
      is_active: isActive,
      is_admin: isAdmin,
      admin_password: adminPassword.value  // 傳遞管理員密碼用於後端二次驗證
    }, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    });
    
    // 更新用戶標籤
    await axios.put(`/api/v1/admin/users/${editingUser.value.id}/tag`, {
      user_tag: editingUser.value.user_tag,
      admin_password: adminPassword.value  // 傳遞管理員密碼用於後端二次驗證
    }, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    });

    showToast('用戶信息已更新', 'success');
    showEditModal.value = false;
    // 清空管理員密碼
    adminPassword.value = '';
    await fetchUsers();
  } catch (error) {
    console.error('更新用戶失敗:', error);
    if (error.response) {
      if (error.response.status === 401 || 
          (error.response.status === 400 && error.response.data.detail?.includes('password'))) {
        adminPasswordError.value = '管理員密碼驗證失敗';
      } else if (error.response.status === 400) {
        showToast(error.response.data.detail || '更新失敗', 'error');
      } else {
        showToast('更新用戶失敗，請重試', 'error');
      }
    } else {
      showToast('更新用戶失敗，請重試', 'error');
    }
  } finally {
    isSubmitting.value = false;
  }
};

// 判斷當前編輯的用戶是否原本就是管理員
const isOriginalAdminUser = computed(() => {
  const originalUser = users.value.find(u => u.id === editingUser.value.id);
  return originalUser && (originalUser.user_tag === 'admin' || originalUser.is_admin);
});

// 處理標籤選擇
const handleTagSelection = (tag) => {
  // 如果用戶原本是管理員，不允許切換為非管理員標籤
  if (isOriginalAdminUser.value && tag !== 'admin') {
    showToast('不能移除管理員用戶的管理員權限', 'warning');
    return;
  }
  editingUser.value.user_tag = tag;
};

// 切換用戶狀態（啟用/禁用）
const toggleUserStatus = async (user) => {
  // 如果是管理員用戶，直接返回並提示
  if (isAdminUser(user)) {
    showToast('管理員用戶不能被禁用', 'warning');
    return;
  }
  
  try {
    await axios.put(`/api/v1/admin/users/${user.id}/status`, 
      { is_active: !user.is_active },
      {
        headers: {
          'Authorization': `Bearer ${authStore.token}`
        }
      }
    );
    
    showToast(`用戶 ${user.username} 已${user.is_active ? '禁用' : '啟用'}`, 'success');
    await fetchUsers();
  } catch (error) {
    console.error('更新用戶狀態失敗:', error);
    if (error.response && error.response.status === 400) {
      showToast(error.response.data.detail || '操作失敗', 'error');
    } else {
      showToast('更新用戶狀態失敗，請重試', 'error');
    }
  }
};

// 判斷用戶是否為管理員
const isAdminUser = (user) => {
  return user.user_tag === 'admin' || user.is_admin;
};

// 獲取狀態按鈕的提示文本
const getStatusButtonTitle = (user) => {
  if (isAdminUser(user)) {
    return '管理員用戶不能被禁用';
  }
  return user.is_active ? '禁用用戶' : '啟用用戶';
};

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

// 打開發送通知模態框
const openSendNotificationModal = () => {
  console.log('Opening notification modal'); // 添加調試日誌
  notificationForm.value = {
    title: '',
    message: '',
    is_global: false,
    user_ids: [],
    notification_type: 'info' // 確保使用小寫字符串
  };
  selectedUsers.value = [];
  userSearchQuery.value = '';
  
  fetchSelectableUsers();
  showNotificationModal.value = true;
  console.log('Modal state:', showNotificationModal.value);
  console.log('Notification form:', notificationForm.value);
};

// 获取可选择的用户列表
const fetchSelectableUsers = async () => {
  try {
    const response = await axios.get('/api/v1/admin/users', {
      params: {
        page: 1,
        per_page: 100 // 获取更多用户，实际项目中可能需要分页加载
      },
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    });
    
    selectableUsers.value = response.data.items.filter(user => user.is_active);
  } catch (error) {
    console.error('获取用户列表失败:', error);
    showToast('获取用户列表失败', 'error');
  }
};

// 处理全局通知切换
const handleGlobalChange = () => {
  if (notificationForm.value.is_global) {
    selectedUsers.value = [];
    notificationForm.value.user_ids = [];
  }
};

// 搜索可选择的用户
const searchSelectableUsers = () => {
  showUserSelector.value = true;
};

// 选择用户
const selectUser = (user) => {
  if (!selectedUsers.value.some(u => u.id === user.id)) {
    selectedUsers.value.push(user);
    notificationForm.value.user_ids.push(user.id);
  }
  userSearchQuery.value = '';
  showUserSelector.value = false;
};

// 移除已选择的用户
const removeSelectedUser = (userId) => {
  selectedUsers.value = selectedUsers.value.filter(user => user.id !== userId);
  notificationForm.value.user_ids = notificationForm.value.user_ids.filter(id => id !== userId);
};

// 点击外部关闭用户选择器
watch(userSearchQuery, (newVal) => {
  if (newVal) {
    showUserSelector.value = true;
  }
});

// 发送通知
const sendNotification = async () => {
  if (!notificationForm.value.is_global && selectedUsers.value.length === 0) {
    showToast('请选择至少一个接收者或设为全局通知', 'warning');
    return;
  }
  
  isSendingNotification.value = true;
  
  // 确保将当前用户IDs复制到一个新数组
  const userIds = notificationForm.value.is_global ? [] : [...notificationForm.value.user_ids];
  
  try {
    console.log('发送通知数据:', {
      title: notificationForm.value.title,
      message: notificationForm.value.message,
      is_global: notificationForm.value.is_global,
      notification_type: notificationForm.value.notification_type,
      user_ids: notificationForm.value.is_global ? [] : userIds
    });
    
    const response = await axios.post('/api/v1/notifications', {
      title: notificationForm.value.title,
      message: notificationForm.value.message,
      is_global: notificationForm.value.is_global,
      notification_type: notificationForm.value.notification_type,
      user_ids: notificationForm.value.is_global ? [] : userIds
    }, {
      headers: {
        'Authorization': `Bearer ${authStore.token}`
      }
    });
    
    showToast(
      notificationForm.value.is_global 
        ? '全局通知发送成功' 
        : `已成功发送通知给 ${selectedUsers.value.length} 名用户`,
      'success'
    );
    
    showNotificationModal.value = false;
  } catch (error) {
    console.error('发送通知失败:', error);
    
    // 更详细的错误处理
    let errorMsg = '发送通知失败，请重试';
    if (error.response) {
      console.log('错误响应详情:', error.response.data);
      // 处理422错误
      if (error.response.status === 422) {
        if (error.response.data && error.response.data.detail) {
          // 如果是数组形式的验证错误
          if (Array.isArray(error.response.data.detail)) {
            errorMsg = error.response.data.detail.map(err => `${err.loc.join('.')}：${err.msg}`).join('\n');
          } else {
            errorMsg = `验证错误: ${error.response.data.detail}`;
          }
        }
      } else if (error.response.status === 400) {
        errorMsg = `请求错误: ${error.response.data.detail || '必须指定用户ID列表或设置为全局通知'}`;
      } else if (error.response.status === 401) {
        errorMsg = '未授权，请重新登录';
        // 可以选择重定向到登录页面
        // router.push('/login');
      }
    }
    
    showToast(errorMsg, 'error');
  } finally {
    isSendingNotification.value = false;
  }
};

// Ensure we add click outside event listener for the user selector
onMounted(() => {
  document.addEventListener('click', handleDocumentClick);
});

// 處理點擊外部關閉選擇器
const handleDocumentClick = (event) => {
  const selectorElement = document.querySelector('.users-selector');
  if (selectorElement && !selectorElement.contains(event.target)) {
    showUserSelector.value = false;
  }
};

// 添加模板相關狀態
const showTemplateDropdown = ref(false);
const templateSearchQuery = ref('');
const selectedTemplate = ref(null);

// 過濾模板
const filteredTemplates = computed(() => {
  if (!templateSearchQuery.value) return notificationTemplates.value;
  
  const query = templateSearchQuery.value.toLowerCase();
  return notificationTemplates.value.filter(template => 
    template.name.toLowerCase().includes(query) ||
    template.title.toLowerCase().includes(query)
  );
});

// 切換模板下拉選單
const toggleTemplateDropdown = () => {
  showTemplateDropdown.value = !showTemplateDropdown.value;
};

// 點擊外部關閉下拉選單
onMounted(() => {
  document.addEventListener('click', (event) => {
    const templateSelect = document.querySelector('.template-select');
    if (templateSelect && !templateSelect.contains(event.target)) {
      showTemplateDropdown.value = false;
    }
  });
});

// 用戶詳細資料相關變量
const showUserDetailsModal = ref(false);
const loadingUserDetails = ref(false);
const userDetails = ref(null);

// 獲取用戶詳細資料
const viewUserDetails = async (user) => {
  showUserDetailsModal.value = true;
  loadingUserDetails.value = true;
  userDetailsLoadStartTime.value = Date.now(); // 記錄載入開始時間
  userDetails.value = null;
  
  try {
    // 獲取用戶登錄歷史
    const loginHistoryResponse = await axios.get(`/api/v1/system/user/${user.id}/login-history`, {
      headers: { 'Authorization': `Bearer ${authStore.token}` }
    });
    
    // 設置用戶詳細信息
    userDetails.value = loginHistoryResponse.data;
    console.log('用戶詳細資料:', userDetails.value);
    
    // 確保載入動畫至少顯示0.5秒
    const loadingDuration = Date.now() - userDetailsLoadStartTime.value;
    if (loadingDuration < 500) {
      setTimeout(() => {
        loadingUserDetails.value = false;
      }, 500 - loadingDuration);
    } else {
      loadingUserDetails.value = false;
    }
  } catch (error) {
    console.error('獲取用戶詳細資料失敗:', error);
    showToast('獲取用戶詳細資料失敗', 'error');
    
    // 獲取失敗時，嘗試回退到基本用戶信息
    try {
      const userResponse = await axios.get(`/api/v1/admin/users/${user.id}`, {
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      });
      
      // 創建一個基本的用戶詳情結構
      userDetails.value = {
        user_info: {
          ...userResponse.data,
          created_at: formatDate(userResponse.data.created_at)
        },
        login_history: []
      };
    } catch (fallbackError) {
      console.error('獲取基本用戶信息也失敗:', fallbackError);
    }
    
    // 確保載入動畫至少顯示0.5秒
    const loadingDuration = Date.now() - userDetailsLoadStartTime.value;
    if (loadingDuration < 500) {
      setTimeout(() => {
        loadingUserDetails.value = false;
      }, 500 - loadingDuration);
    } else {
      loadingUserDetails.value = false;
    }
  }
};

// 在script部分添加新的變量和計算屬性
// 在現有變量聲明後添加
const jumpPage = ref(1);

// 在computed部分添加顯示頁碼的計算屬性
const displayedPages = computed(() => {
  // 顯示當前頁附近的頁碼
  const pages = [];
  let startPage = Math.max(1, currentPage.value - 2);
  let endPage = Math.min(totalPages.value, currentPage.value + 2);
  
  // 確保始終顯示5個頁碼（如果有足夠的頁數）
  if (endPage - startPage + 1 < 5 && totalPages.value >= 5) {
    if (startPage === 1) {
      endPage = Math.min(5, totalPages.value);
    } else if (endPage === totalPages.value) {
      startPage = Math.max(1, totalPages.value - 4);
    }
  }
  
  for (let i = startPage; i <= endPage; i++) {
    pages.push(i);
  }
  
  return pages;
});

// 添加跳轉頁面的方法
const handleJumpPage = () => {
  if (jumpPage.value >= 1 && jumpPage.value <= totalPages.value) {
    changePage(jumpPage.value);
  } else {
    // 如果輸入的頁碼超出範圍，重置為當前頁
    jumpPage.value = currentPage.value;
  }
};

// 監聽currentPage變化，同步jumpPage的值
watch(currentPage, (newPage) => {
  jumpPage.value = newPage;
});
</script>

<style scoped>
/* 儀表盤統計卡片樣式 */
.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.stat-card {
  background-color: var(--surface-color);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-sm);
  padding: var(--spacing-md);
  display: flex;
  align-items: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--box-shadow-md);
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--spacing-md);
  flex-shrink: 0;
}

.users-icon {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.online-icon {
  background-color: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.notifications-icon {
  background-color: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.stat-content {
  flex: 1;
}

.stat-content h3 {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  font-size: var(--font-size-xl);
  font-weight: 700;
  margin: var(--spacing-xs) 0;
  color: var(--text-primary);
}

.stat-description {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: 0;
}

.admin-page {
  padding: var(--spacing-md);
}

.admin-container {
  background-color: var(--surface-color);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-sm);
  margin-top: var(--spacing-md);
  overflow: hidden;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.admin-container:hover {
  box-shadow: var(--box-shadow-md);
}

.admin-section {
  padding: var(--spacing-lg);
}

.admin-section h2 {
  margin-top: 0;
  margin-bottom: var(--spacing-md);
  font-size: var(--font-size-xl);
  color: var(--text-primary);
  position: relative;
  padding-left: var(--spacing-sm);
}

.admin-section h2::before {
  content: '';
  position: absolute;
  left: 0;
  top: 25%;
  height: 50%;
  width: 4px;
  background-color: var(--primary-color);
  border-radius: 2px;
}

.search-filter {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  align-items: flex-end;
}

.input-group {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.table-wrapper {
  overflow-x: auto;
  margin-bottom: var(--spacing-lg);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
}

.data-table th,
.data-table td {
  padding: var(--spacing-sm);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.data-table th {
  background-color: var(--surface-color);
  color: var(--text-secondary);
  font-weight: 600;
  position: sticky;
  top: 0;
}

.data-table tbody tr:hover {
  background-color: var(--hover-color);
}

.tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xs);
  padding: 2px 8px;
  border-radius: var(--border-radius-sm);
  font-weight: 500;
}

.tag.is-success {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.tag.is-danger {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.tag.is-warning {
  background-color: rgba(234, 179, 8, 0.1);
  color: #eab308;
}

.tag.is-info {
  background-color: rgba(14, 165, 233, 0.1);
  color: #0ea5e9;
}

.actions {
  display: flex;
  gap: var(--spacing-xs);
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--border-radius-sm);
  border: none;
  background-color: var(--surface-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast) ease;
}

.action-btn:hover {
  background-color: var(--hover-color);
  color: var(--primary-color);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
  flex-wrap: wrap;
}

.page-btn {
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--border-color);
  background-color: var(--surface-color);
  border-radius: var(--border-radius-sm);
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-fast) ease;
}

.page-btn:hover:not(:disabled) {
  background-color: var(--hover-color);
  border-color: var(--primary-color);
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.page-numbers {
  display: flex;
  align-items: center;
  gap: 6px;
}

.page-number {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-color);
  background-color: var(--surface-color);
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all var(--transition-fast) ease;
}

.page-number:hover {
  background-color: var(--hover-color);
  border-color: var(--primary-color);
}

.page-number.current {
  background-color: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
  cursor: default;
}

.page-ellipsis {
  color: var(--text-secondary);
  margin: 0 4px;
}

.page-jump {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
}

.page-jump input {
  width: 50px;
  text-align: center;
  padding: 4px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
}

.jump-btn {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  background-color: var(--surface-color);
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast) ease;
}

.jump-btn:hover {
  background-color: var(--hover-color);
  border-color: var(--primary-color);
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

/* 模態框樣式 */
.modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 1000;
}

.modal-container {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
  position: relative;
  width: 80%;
  max-width: 900px;
  max-height: 90vh;
  overflow-y: auto;
  margin: auto;
  z-index: 1001;
}

.user-details-modal .modal-container {
  width: 95%;
  max-width: 1200px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e0e0e0;
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  cursor: pointer;
  color: #666;
}

.close-btn:hover {
  color: #333;
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  max-height: calc(90vh - 130px);
}

/* 用户详情模态框专用样式 */
.user-details-modal .modal-container {
  width: 95%;
  max-width: 1400px; /* 更大的宽度 */
}

.user-details-flex-container {
  display: flex;
  flex-direction: row;
  gap: 20px;
  width: 100%;
}

.user-avatar-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding: var(--spacing-sm);
  background-color: rgba(0, 0, 0, 0.03);
  border-radius: var(--border-radius-lg);
}

.user-avatar-container :deep(.user-avatar-component) {
  width: 50px;
  height: 50px;
  min-width: 50px;
  margin-bottom: var(--spacing-sm);
}

.user-fullname {
  margin: var(--spacing-xs) 0;
  font-size: var(--font-size-md);
  font-weight: 600;
  text-align: center;
}

.user-info-section {
  flex: 1;
  min-width: 300px;
}

.login-history-section {
  flex: 2;
  min-width: 600px; /* 确保登录历史区域有足够宽度 */
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.modal-header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-secondary);
}

.form-group {
  margin-bottom: var(--spacing-md);
}

.form-group label {
  display: block;
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.form-group input[type="text"],
.form-group input[type="email"] {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background-color: var(--input-bg);
  color: var(--text-primary);
}

.checkboxes {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.checkbox-wrapper {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.checkbox-wrapper label {
  margin-bottom: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
}

/* 通知相关样式 */
.notification-actions {
  display: flex;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.btn-primary svg {
  margin-right: var(--spacing-xs);
}

.selected-users-list {
  margin-top: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
  min-height: 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  padding: var(--spacing-xs);
}

.empty-selection {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  padding: var(--spacing-xs);
}

.selected-user-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.user-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  background-color: var(--hover-color);
  padding: 2px 8px;
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-xs);
}

.remove-tag {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-tag:hover {
  color: var(--danger-color);
}

.users-selector {
  position: relative;
}

.selectable-users-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 100%;
  max-height: 200px;
  overflow-y: auto;
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  z-index: 10;
  box-shadow: var(--box-shadow-md);
}

.selectable-user {
  padding: var(--spacing-sm);
  cursor: pointer;
  transition: background-color var(--transition-fast) ease;
}

.selectable-user:hover {
  background-color: var(--hover-color);
}

.empty-users {
  padding: var(--spacing-sm);
  color: var(--text-tertiary);
  text-align: center;
  font-size: var(--font-size-sm);
}

textarea {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background-color: var(--input-bg);
  color: var(--text-primary);
  resize: vertical;
  font-family: inherit;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 添加通知类型选择器样式 */
.notification-type-selector {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.notification-type-option {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 100px;
}

.notification-type-option:hover {
  background-color: var(--hover-color);
}

.notification-type-option.selected {
  border-color: var(--primary-color);
  background-color: rgba(var(--primary-color-rgb), 0.05);
  font-weight: bold;
}

.type-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

/* 为不同类型添加特定颜色 */
.notification-type-option.type-info .type-icon {
  background-color: #e6f7ff;
  color: #1677ff;
}

.notification-type-option.type-success .type-icon {
  background-color: #f6ffed;
  color: #52c41a;
}

.notification-type-option.type-warning .type-icon {
  background-color: #fffbe6;
  color: #faad14;
}

.notification-type-option.type-error .type-icon {
  background-color: #fff2f0;
  color: #ff4d4f;
}

.notification-type-option.type-system .type-icon {
  background-color: #f9f0ff;
  color: #722ed1;
}

.type-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

/* 用户标签选择器样式 */
.tag-selector {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin: var(--spacing-sm) 0;
}

.tag-option {
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-color);
  cursor: pointer;
  font-size: var(--font-size-sm);
  transition: all 0.2s;
}

.tag-option:hover {
  background-color: var(--hover-color);
}

.tag-option.selected {
  border-color: var(--primary-color);
  background-color: rgba(var(--primary-color-rgb), 0.1);
}

/* 用户标签样式 */
.tag-option.admin, .tag.is-danger {
  background-color: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.tag-option.regular, .tag.is-info {
  background-color: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.tag-option.premium, .tag.is-warning {
  background-color: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

/* 服务器状态卡片样式 */
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.status-card {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  padding: 16px;
}

.status-card h4 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.status-info .info-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  align-items: center;
}

.status-info .label {
  font-weight: 500;
  color: #666;
}

.status-info .value {
  font-weight: 400;
  color: #333;
}

/* 资源进度条样式 */
.resource-item {
  margin-bottom: 16px;
}

.resource-item .label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #666;
}

.progress-container {
  display: flex;
  align-items: center;
  gap: 10px;
}

.progress {
  flex: 1;
  height: 8px;
  background-color: #eee;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-bar.is-success {
  background-color: #48c78e;
}

.progress-bar.is-warning {
  background-color: #ffe08a;
}

.progress-bar.is-danger {
  background-color: #f14668;
}

.progress-value {
  min-width: 120px;
  font-size: 14px;
  color: #666;
}

/* 加载动画 */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  margin: 20px 0;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  margin: 10px 0;
}

/* 新的三点加载动画效果 */
.loader {
  width: 55px;
  aspect-ratio: 0.75;
  --c: no-repeat linear-gradient(var(--primary-color) 0 0);
  background: 
    var(--c) 0%   50%,
    var(--c) 50%  50%,
    var(--c) 100% 50%;
  animation: l7 1s infinite linear alternate;
}

@keyframes l7 {
  0%  {background-size: 20% 50%, 20% 50%, 20% 50%}
  20% {background-size: 20% 20%, 20% 50%, 20% 50%}
  40% {background-size: 20% 100%, 20% 20%, 20% 50%}
  60% {background-size: 20% 50%, 20% 100%, 20% 20%}
  80% {background-size: 20% 50%, 20% 50%, 20% 100%}
  100%{background-size: 20% 50%, 20% 50%, 20% 50%}
}

.loading-cell .loader {
  width: 24px;
  aspect-ratio: 0.75;
  margin-bottom: 0;
}

/* 圓形旋轉動畫樣式(保留給表格單元格使用) */
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #48c78e;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 错误信息 */
.error-message {
  text-align: center;
  padding: 30px;
  background-color: #fff3f3;
  border-radius: 8px;
  margin-top: 20px;
}

.error-message p {
  margin-bottom: 16px;
  color: #f14668;
  font-weight: 500;
}

/* 表格单元格样式 */
.loading-cell, .empty-cell {
  text-align: center;
  padding: 20px;
}

.loading-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.loading-cell .loader {
  width: 24px;
  aspect-ratio: .75;
  margin-bottom: 0;
}

.empty-cell {
  color: #888;
  font-style: italic;
}

/* CSS部分添加 */
.disabled-btn {
  opacity: 0.5;
  cursor: not-allowed !important;
  color: var(--text-tertiary) !important;
}

.disabled-btn:hover {
  background-color: var(--surface-color) !important;
  color: var(--text-tertiary) !important;
}

/* 添加管理员密码验证相关样式 */
.required {
  color: #ef4444;
  margin-left: 4px;
}

.form-error {
  color: #ef4444;
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

.admin-password-section {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border-color);
}

.security-tip {
  background-color: rgba(25, 118, 210, 0.1);
  padding: 15px;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
  border-left: 4px solid #1976d2;
}

.security-tip strong {
  color: var(--text-primary);
  display: block;
  margin-bottom: 8px;
}

.password-field {
  position: relative;
}

.toggle-button {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--primary-color);
  font-size: 0.875rem;
  cursor: pointer;
  padding: 5px;
}

.toggle-button:hover {
  text-decoration: underline;
}

.admin-warning {
  color: #ef4444;
  font-size: 0.875rem;
  margin-top: 0.5rem;
}

/* 添加通知按钮卡片样式 */
.notification-action-card {
  display: flex;
  align-items: stretch;
}

.notification-send-btn {
  width: 100%;
  background-color: var(--surface-color);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-sm);
  padding: var(--spacing-md);
  display: flex;
  align-items: center;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.notification-send-btn:hover {
  transform: translateY(-4px);
  box-shadow: var(--box-shadow-md);
  background-color: rgba(59, 130, 246, 0.05);
}

.btn-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: var(--spacing-md);
  flex-shrink: 0;
  background-color: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
}

.btn-content {
  flex: 1;
  text-align: left;
}

.btn-content h3 {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

.btn-description {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: var(--spacing-xs) 0 0 0;
}

/* 添加模板相關樣式 */
.templates-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.template-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-card:hover {
  background-color: var(--hover-color);
  transform: translateY(-2px);
}

.template-card.selected {
  border-color: var(--primary-color);
  background-color: rgba(var(--primary-color-rgb), 0.05);
}

.template-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.template-info {
  flex: 1;
}

.template-info h4 {
  margin: 0;
  font-size: var(--font-size-sm);
  font-weight: 600;
}

.template-info p {
  margin: var(--spacing-xs) 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

/* 模板類型樣式 */
.template-card.type-system .template-icon {
  background-color: #f9f0ff;
  color: #722ed1;
}

.template-card.type-info .template-icon {
  background-color: #e6f7ff;
  color: #1677ff;
}

.template-card.type-warning .template-icon {
  background-color: #fffbe6;
  color: #faad14;
}

.template-card.type-success .template-icon {
  background-color: #f6ffed;
  color: #52c41a;
}

/* 模板變量輸入樣式 */
.template-variables {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.variable-input {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.variable-input label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  text-transform: capitalize;
}

.variable-input input {
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-sm);
}

.variable-input input:focus {
  border-color: var(--primary-color);
  outline: none;
  box-shadow: 0 0 0 2px rgba(var(--primary-color-rgb), 0.1);
}

/* 添加下拉選單相關樣式 */
.template-select {
  position: relative;
  width: 100%;
}

.template-trigger {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  background-color: var(--surface-color);
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-trigger:hover {
  border-color: var(--primary-color);
}

.trigger-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.selected-template {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.selected-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-name {
  font-weight: 500;
  color: var(--text-primary);
}

.template-type {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.placeholder {
  color: var(--text-tertiary);
}

.dropdown-arrow {
  transition: transform 0.2s ease;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

.template-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  width: 100%;
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  box-shadow: var(--box-shadow-md);
  z-index: 1000;
  max-height: 400px;
  display: flex;
  flex-direction: column;
}

.template-search {
  padding: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
}

.template-search input {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-sm);
}

.template-list {
  overflow-y: auto;
  max-height: 350px;
}

.template-option {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  cursor: pointer;
  transition: all 0.2s ease;
}

.template-option:hover {
  background-color: var(--hover-color);
}

.template-option.selected {
  background-color: rgba(var(--primary-color-rgb), 0.05);
}

.template-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.template-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.template-description {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}

.selected-check {
  color: var(--primary-color);
}

/* 模板類型圖標樣式 */
.type-system {
  background-color: #f9f0ff;
  color: #722ed1;
}

.type-info {
  background-color: #e6f7ff;
  color: #1677ff;
}

.type-warning {
  background-color: #fffbe6;
  color: #faad14;
}

.type-success {
  background-color: #f6ffed;
  color: #52c41a;
}

/* 用户详细资料样式 */
.details-section {
  margin-bottom: var(--spacing-lg);
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  padding: 20px;
  background-color: #f9f9f9;
}

.user-details-flex-container {
  display: flex;
  flex-direction: row;
  gap: 20px;
  width: 100%;
}

.user-info-section {
  flex: 1;
  min-width: 300px;
}

.login-history-section {
  flex: 2;
}

.details-section h4 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #333;
  font-weight: 600;
  border-bottom: 1px solid #ddd;
  padding-bottom: 8px;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.details-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xs);
  padding: 8px;
  border-radius: 4px;
  background-color: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.label {
  font-weight: 500;
  color: #666;
}

.value {
  font-weight: 400;
  color: #333;
}

/* 用户登录历史样式 */
.login-history {
  margin-top: var(--spacing-md);
}

.login-history table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.login-history th,
.login-history td {
  padding: var(--spacing-sm);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.login-history th {
  background-color: var(--surface-color);
  color: var(--text-secondary);
  font-weight: 600;
  position: sticky;
  top: 0;
}

.login-history tbody tr:hover {
  background-color: var(--hover-color);
}

.login-history .tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.75rem;
  font-weight: 500;
}

.tag.is-success {
  background-color: rgba(34, 197, 94, 0.1);
  color: #22c55e;
}

.tag.is-default {
  background-color: rgba(14, 165, 233, 0.1);
  color: #0ea5e9;
}

.details-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid #ddd;
}

.btn.btn-primary {
  margin-right: var(--spacing-md);
}

.modal-body {
  padding: var(--spacing-md);
  overflow-y: auto;
  max-height: calc(90vh - 120px); /* 减去标题和底部操作区域的高度 */
}

.user-details-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.details-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.login-history table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-sm);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

/* 响应式调整 */
@media (max-width: 1024px) {
  .user-details-flex-container {
    flex-direction: column;
  }
  
  .user-info-section {
    max-width: 100%;
  }
  
  .login-history-section {
    min-width: 100%;
  }
}

/* 只在宽屏设备上使用多列 */
@media (min-width: 768px) {
  .user-info-section .details-grid {
    grid-template-columns: 1fr;
  }
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 30px;
}

.loader {
  width: 40px;
  height: 40px;
  border: 4px solid #f3f3f3;
  border-top: 4px solid #48c78e;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style> 