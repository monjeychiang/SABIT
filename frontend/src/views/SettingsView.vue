<template>
  <div class="settings-view">
    <div class="settings-header">
      <h1>帳戶設置</h1>
      <p>管理您的帳戶設置和API配置</p>
    </div>
    
    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>正在載入您的設置...</p>
    </div>
    
    <div v-else class="settings-content">
      <div class="settings-sidebar">
        <div 
          class="sidebar-item" 
          :class="{ active: activeTab === 'profile' }"
          @click="activeTab = 'profile'"
        >
          <span class="item-icon">👤</span>
          <span class="item-text">個人資料</span>
        </div>
        
        <div 
          class="sidebar-item" 
          :class="{ active: activeTab === 'api' }"
          @click="activeTab = 'api'"
        >
          <span class="item-icon">🔑</span>
          <span class="item-text">API設置</span>
        </div>
        
        <div 
          class="sidebar-item" 
          :class="{ active: activeTab === 'notifications' }"
          @click="activeTab = 'notifications'"
        >
          <span class="item-icon">🔔</span>
          <span class="item-text">通知</span>
        </div>
        
        <div 
          class="sidebar-item" 
          :class="{ active: activeTab === 'security' }"
          @click="activeTab = 'security'"
        >
          <span class="item-icon">🔒</span>
          <span class="item-text">安全</span>
        </div>

        <div 
          class="sidebar-item" 
          :class="{ active: activeTab === 'theme' }"
          @click="activeTab = 'theme'"
        >
          <span class="item-icon">🎨</span>
          <span class="item-text">主題</span>
        </div>
      </div>
      
      <div class="settings-panel">
        <!-- 個人資料設置 -->
        <div v-if="activeTab === 'profile'" class="panel-content">
          <h2>個人資料設置</h2>
          <div v-if="profileMessage" :class="profileMessage.type === 'success' ? 'success-message' : 'error-message'">
            {{ profileMessage.text }}
          </div>
          
          <div class="security-tip">
            <strong>安全提示</strong>
            <p>修改個人資料需要驗證您的當前密碼，這是為了保護您的帳戶安全。</p>
          </div>
          
          <form @submit.prevent="updateProfile" class="settings-form">
            <div class="form-group">
              <label for="username">用戶名</label>
              <input type="text" id="username" v-model="profileData.username" required />
            </div>
            
            <div class="form-group">
              <label for="email">電子郵箱</label>
              <input type="email" id="email" v-model="profileData.email" disabled />
              <p class="field-help">電子郵箱地址無法修改</p>
            </div>
            
            <div class="form-group">
              <label for="current_password">當前密碼 <span class="required">*</span></label>
              <div class="password-field">
                <input 
                  :type="showCurrentPassword ? 'text' : 'password'" 
                  id="current_password" 
                  v-model="profileData.currentPassword" 
                  required 
                />
                <button type="button" class="toggle-button" @click="toggleCurrentPasswordVisibility">
                  <span>{{ showCurrentPassword ? '隱藏' : '顯示' }}</span>
                </button>
              </div>
              <p class="field-help">修改任何個人資料都需要驗證當前密碼</p>
            </div>
            
            <div class="form-section">
              <h3>修改密碼</h3>
              <p class="section-description">如果不想修改密碼，請留空</p>
              
              <div class="form-group">
                <label for="new_password">新密碼</label>
                <div class="password-field">
                  <input 
                    :type="showNewPassword ? 'text' : 'password'" 
                    id="new_password" 
                    v-model="profileData.newPassword" 
                    minlength="8" 
                  />
                  <button type="button" class="toggle-button" @click="toggleNewPasswordVisibility" v-if="profileData.newPassword">
                    <span>{{ showNewPassword ? '隱藏' : '顯示' }}</span>
                  </button>
                </div>
              </div>
              
              <div class="form-group">
                <label for="confirm_password">確認新密碼</label>
                <div class="password-field">
                  <input 
                    :type="showConfirmPassword ? 'text' : 'password'" 
                    id="confirm_password" 
                    v-model="profileData.confirmPassword" 
                  />
                  <button type="button" class="toggle-button" @click="toggleConfirmPasswordVisibility" v-if="profileData.confirmPassword">
                    <span>{{ showConfirmPassword ? '隱藏' : '顯示' }}</span>
                  </button>
                </div>
                <p v-if="passwordMismatch" class="field-error">兩次輸入的密碼不匹配</p>
              </div>
            </div>
            
            <div class="form-actions">
              <button type="submit" class="submit-button" :disabled="isProfileUpdating || passwordMismatch">
                {{ isProfileUpdating ? '更新中...' : '更新個人資料' }}
              </button>
            </div>
          </form>
        </div>
        
        <!-- API設置 -->
        <div v-if="activeTab === 'api'" class="panel-content">
          <h2>API設置</h2>
          <p class="panel-description">
            連接您的交易所帳戶以啟用自動交易。您的API密鑰將被安全加密存儲。
          </p>
          
          <div class="security-tip">
            <strong>安全信息</strong>
            <p>您的API密鑰在存儲到我們的數據庫之前會使用AES-256進行加密。</p>
            <p>我們絕不會以明文形式存儲您的API密鑰，包括我們的管理員在內的任何人都無法訪問這些密鑰。</p>
          </div>
          
          <div v-if="apiMessage" :class="apiMessage.type === 'success' ? 'success-message' : 'error-message'">
            {{ apiMessage.text }}
          </div>
          
          <div class="exchange-selector">
            <label for="exchange">選擇交易所</label>
            <el-select v-model="apiData.selectedExchange" class="exchange-select">
              <el-option
                v-for="exchange in exchanges"
                :key="exchange.value"
                :label="exchange.label"
                :value="exchange.value"
              />
            </el-select>
          </div>
          
          <form @submit.prevent="updateApiSettings" class="settings-form">
            <div class="form-group">
              <label for="api_key">API密鑰</label>
              <div class="password-field">
                <input 
                  type="text" 
                  id="api_key" 
                  v-model="apiData.exchanges[apiData.selectedExchange].api_key" 
                  :placeholder="apiData.exchanges[apiData.selectedExchange].api_key ? '••••••••••••••••••••••' : '輸入您的API密鑰'"
                  required 
                  @focus="isEditingKey = true"
                />
                <button type="button" class="toggle-button" @click="clearApiKey" v-if="apiData.exchanges[apiData.selectedExchange].api_key && !isEditingKey">
                  <span>重新輸入</span>
                </button>
              </div>
            </div>
            
            <div class="form-group">
              <label for="api_secret">API密鑰密碼</label>
              <div class="password-field">
                <input 
                  :type="showApiSecret ? 'text' : 'password'" 
                  id="api_secret" 
                  v-model="apiData.exchanges[apiData.selectedExchange].api_secret" 
                  :placeholder="apiData.exchanges[apiData.selectedExchange].api_secret ? '••••••••••••••••••••••••••••••••' : '輸入您的API密鑰密碼'"
                  required 
                  @focus="isEditingSecret = true"
                />
                <button type="button" class="toggle-button" @click="toggleApiSecretVisibility" v-if="isEditingSecret">
                  <span>{{ showApiSecret ? '隱藏' : '顯示' }}</span>
                </button>
                <button type="button" class="toggle-button" @click="clearApiSecret" v-if="apiData.exchanges[apiData.selectedExchange].api_secret && !isEditingSecret">
                  <span>重新輸入</span>
                </button>
              </div>
            </div>
            
            <div class="api-requirements">
              <h4>所需API權限</h4>
              <ul>
                <li>啟用讀取</li>
                <li>啟用現貨和保證金交易</li>
                <li>啟用期貨</li>
              </ul>
            </div>
            
            <div class="form-actions">
              <button type="submit" class="submit-button" :disabled="isApiUpdating">
                {{ isApiUpdating ? '更新中...' : '保存API設置' }}
              </button>
              <button type="button" class="delete-button" @click="deleteApiKeys" :disabled="isApiUpdating">
                刪除API密鑰
              </button>
            </div>
          </form>
          
          <div class="api-guide">
            <h4>如何在{{ exchanges.find(e => e.value === apiData.selectedExchange)?.label }}上創建API密鑰</h4>
            <ol>
              <li>登入您的{{ exchanges.find(e => e.value === apiData.selectedExchange)?.label }}帳戶</li>
              <li>前往帳戶設置中的"API管理"</li>
              <li>創建一個新的API密鑰並設置上述所需權限</li>
              <li>完成安全驗證</li>
              <li>複製API密鑰和密鑰密碼到此表單</li>
            </ol>
            <p>注意：切勿與他人分享您的API密鑰！</p>
          </div>
        </div>
        
        <!-- 通知設置 -->
        <div v-if="activeTab === 'notifications'" class="panel-content">
          <h2>通知設置</h2>
          
          <div v-if="notificationMessage" :class="notificationMessage.type === 'success' ? 'success-message' : 'error-message'">
            {{ notificationMessage.text }}
          </div>
          
          <form @submit.prevent="updateNotificationSettings" class="settings-form">
            <div class="toggle-group">
              <label class="toggle-label">
                <span>電子郵件通知</span>
                <label class="switch">
                  <input type="checkbox" v-model="notificationData.email_notifications">
                  <span class="slider round"></span>
                </label>
              </label>
              <p class="field-help">接收重要事件的電子郵件通知</p>
            </div>
            
            <div class="toggle-group">
              <label class="toggle-label">
                <span>交易通知</span>
                <label class="switch">
                  <input type="checkbox" v-model="notificationData.trade_notifications">
                  <span class="slider round"></span>
                </label>
              </label>
              <p class="field-help">在執行交易時接收通知</p>
            </div>
            
            <div class="toggle-group">
              <label class="toggle-label">
                <span>價格提醒</span>
                <label class="switch">
                  <input type="checkbox" v-model="notificationData.price_alerts">
                  <span class="slider round"></span>
                </label>
              </label>
              <p class="field-help">接收價格變動的通知</p>
            </div>
            
            <div class="form-actions">
              <button type="submit" class="submit-button" :disabled="isNotificationUpdating">
                {{ isNotificationUpdating ? '更新中...' : '保存通知設置' }}
              </button>
            </div>
          </form>
        </div>
        
        <!-- 安全設置 -->
        <div v-if="activeTab === 'security'" class="panel-content">
          <h2>安全設置</h2>
          
          <div class="security-info">
            <h3>登入活動</h3>
            <div class="login-activity">
              <div class="activity-item">
                <div class="activity-icon">💻</div>
                <div class="activity-details">
                  <h4>當前會話</h4>
                  <p>IP: 192.168.1.1</p>
                  <p>瀏覽器: Chrome on Windows</p>
                  <p>上次活動: 剛剛</p>
                </div>
              </div>
              
              <div class="activity-item">
                <div class="activity-icon">📱</div>
                <div class="activity-details">
                  <h4>上次登入</h4>
                  <p>IP: 192.168.1.1</p>
                  <p>瀏覽器: Firefox on Windows</p>
                  <p>日期: 昨天, 15:30</p>
                </div>
              </div>
            </div>
            
            <div class="security-actions">
              <button @click="logout" class="danger-button">
                <span class="button-icon">🚪</span>
                <span>登出所有會話</span>
              </button>
            </div>
          </div>
        </div>
        
        <!-- 主題設置 -->
        <div v-if="activeTab === 'theme'" class="panel-content">
          <h2>主題設置</h2>
          <div class="theme-settings">
            <div class="setting-item">
              <span class="setting-label">深色模式</span>
              <el-switch
                v-model="themeSettings.isDarkMode"
                @change="toggleDarkMode"
              />
            </div>
            <div class="setting-item">
              <span class="setting-label">自動主題</span>
              <el-switch
                v-model="themeSettings.autoTheme"
                @change="toggleAutoTheme"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import { useAuthStore } from '@/stores/auth';
import { useThemeStore } from '@/stores/theme';
import { ElMessage } from 'element-plus';

const authStore = useAuthStore();
const themeStore = useThemeStore();
const router = useRouter();
const activeTab = ref('profile');
const isLoading = ref(true);

// API密鑰顯示控制
const showApiSecret = ref(false);
const isEditingKey = ref(false);
const isEditingSecret = ref(false);
const showCurrentPassword = ref(false);
const showNewPassword = ref(false);
const showConfirmPassword = ref(false);

// 切換密碼可見性
const toggleCurrentPasswordVisibility = () => {
  showCurrentPassword.value = !showCurrentPassword.value;
};

const toggleNewPasswordVisibility = () => {
  showNewPassword.value = !showNewPassword.value;
};

const toggleConfirmPasswordVisibility = () => {
  showConfirmPassword.value = !showConfirmPassword.value;
};

// 切換API密鑰可見性
const toggleApiSecretVisibility = () => {
  showApiSecret.value = !showApiSecret.value;
};

// 清除API密鑰以便重新輸入
const clearApiKey = () => {
  const exchange = apiData.value.selectedExchange;
  apiData.value.exchanges[exchange].api_key = '';
  isEditingKey.value = true;
};

// 清除API密鑰密碼以便重新輸入
const clearApiSecret = () => {
  const exchange = apiData.value.selectedExchange;
  apiData.value.exchanges[exchange].api_secret = '';
  isEditingSecret.value = true;
};

// 個人資料數據
const profileData = ref({
  username: '',
  email: '',
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
});
const isProfileUpdating = ref(false);
const profileMessage = ref(null);

// API設置數據
const apiData = ref({
  selectedExchange: 'binance',
  exchanges: {
    binance: { api_key: '', api_secret: '' },
    okx: { api_key: '', api_secret: '' },
    bybit: { api_key: '', api_secret: '' },
    gate: { api_key: '', api_secret: '' },
    mexc: { api_key: '', api_secret: '' }
  }
});
const isApiUpdating = ref(false);
const apiMessage = ref(null);

// 通知設置
const notificationData = ref({
  email_notifications: true,
  trade_notifications: true,
  price_alerts: false
});
const isNotificationUpdating = ref(false);
const notificationMessage = ref(null);

// 密碼驗證
const passwordMismatch = computed(() => {
  return profileData.value.newPassword && 
         profileData.value.confirmPassword && 
         profileData.value.newPassword !== profileData.value.confirmPassword;
});

// 交易所列表
const exchanges = [
  { value: 'binance', label: 'Binance' },
  { value: 'okx', label: 'OKX' },
  { value: 'bybit', label: 'Bybit' },
  { value: 'gate', label: 'Gate.io' },
  { value: 'mexc', label: 'MEXC' }
];

// 帶認證的API請求
const createAuthenticatedRequest = () => {
  const token = localStorage.getItem('token');
  const tokenType = localStorage.getItem('tokenType') || 'bearer';
  
  if (!token) {
    router.push('/login');
    return null;
  }
  
  return axios.create({
    baseURL: 'http://localhost:8000',
    headers: {
      'Authorization': `${tokenType} ${token}`
    }
  });
};

// 載入用戶設置
const loadUserSettings = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isLoading.value = true;
    
    // 獲取用戶個人資料信息
    try {
      // 使用authStore獲取用戶資料，利用緩存機制
      const userData = await authStore.getUserProfile();
      if (userData) {
        profileData.value = {
          username: userData.username,
          email: userData.email,
          currentPassword: '',
          newPassword: '',
          confirmPassword: ''
        };
      }
    } catch (profileError) {
      console.error('載入用戶資料失敗:', profileError);
    }
    
    // 獲取API密鑰設置狀態
    try {
      const apiResponse = await api.get('/api/v1/api-keys');
      if (apiResponse.data && Array.isArray(apiResponse.data)) {
        const apiKeys = apiResponse.data;
        
        // 初始化默認結構
        const exchangeData = {
          selectedExchange: 'binance',
          exchanges: {
            binance: { api_key: '', api_secret: '' },
            okx: { api_key: '', api_secret: '' },
            bybit: { api_key: '', api_secret: '' },
            gate: { api_key: '', api_secret: '' },
            mexc: { api_key: '', api_secret: '' }
          }
        };
        
        // 填充已存在的 API 密鑰數據
        apiKeys.forEach(apiKey => {
          if (exchangeData.exchanges[apiKey.exchange]) {
            exchangeData.exchanges[apiKey.exchange] = {
              api_key: apiKey.api_key ? '••••••••••••••••••••••' : '',
              api_secret: apiKey.api_key ? '••••••••••••••••••••••••••••••••' : ''
            };
          }
        });
        
        apiData.value = exchangeData;
      }
    } catch (apiError) {
      console.error('載入API設置失敗:', apiError);
      // 設置默認空值
      apiData.value = {
        selectedExchange: 'binance',
        exchanges: {
          binance: { api_key: '', api_secret: '' },
          okx: { api_key: '', api_secret: '' },
          bybit: { api_key: '', api_secret: '' },
          gate: { api_key: '', api_secret: '' },
          mexc: { api_key: '', api_secret: '' }
        }
      };
    }
    
    // 載入通知設置
    // 在實際應用中，您應該從API獲取這些設置
    notificationData.value = {
      email_notifications: true,
      trade_notifications: true,
      price_alerts: false
    };
    
  } catch (error) {
    console.error('載入用戶設置失敗:', error);
    if (error.response && error.response.status === 401) {
      router.push('/login');
    }
  } finally {
    isLoading.value = false;
  }
};

// 更新個人資料
const updateProfile = async () => {
  // 驗證是否輸入了當前密碼
  if (!profileData.value.currentPassword) {
    profileMessage.value = {
      type: 'error',
      text: '請輸入當前密碼以驗證身份'
    };
    return;
  }
  
  // 驗證密碼
  if (profileData.value.newPassword && passwordMismatch.value) {
    profileMessage.value = {
      type: 'error',
      text: '兩次輸入的新密碼不匹配'
    };
    return;
  }
  
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isProfileUpdating.value = true;
    profileMessage.value = null;
    
    // 準備帶有當前密碼的載荷
    const payload = {
      username: profileData.value.username,
      current_password: profileData.value.currentPassword,
      new_password: profileData.value.newPassword || undefined
    };
    
    // 發送當前密碼進行驗證
    const response = await api.post('/api/v1/settings/profile', payload);
    
    if (response.data && response.data.success) {
      profileMessage.value = {
        type: 'success',
        text: '個人資料更新成功'
      };
      
      // 清空密碼欄位
      profileData.value.currentPassword = '';
      profileData.value.newPassword = '';
      profileData.value.confirmPassword = '';
    } else {
      throw new Error(response.data?.message || '更新個人資料失敗');
    }
    
  } catch (error) {
    console.error('更新個人資料時出錯:', error);
    profileMessage.value = {
      type: 'error',
      text: error.response?.data?.detail 
        ? error.response.data.detail 
        : (error.message || '更新個人資料失敗，請稍後重試')
    };
  } finally {
    isProfileUpdating.value = false;
  }
};

// 更新API設置
const updateApiSettings = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isApiUpdating.value = true;
    apiMessage.value = null;
    
    const exchange = apiData.value.selectedExchange;
    const { api_key, api_secret } = apiData.value.exchanges[exchange];
    
    // 檢查交易所名稱
    if (!exchange || !['binance', 'okx', 'bybit', 'gate', 'mexc'].includes(exchange)) {
      throw new Error('無效的交易所名稱');
    }
    
    // 檢查是否已有API密鑰
    const apiKeyExists = await checkApiKeyExists(exchange);
    
    let response;
    if (apiKeyExists) {
      // 更新現有API密鑰
      response = await api.put(`/api/v1/api-keys/${exchange}`, {
        api_key,
        api_secret
      });
    } else {
      // 創建新的API密鑰
      response = await api.post('/api/v1/api-keys', {
        exchange,
        api_key,
        api_secret
      });
    }
    
    if (response.data.success) {
      apiMessage.value = {
        type: 'success',
        text: response.data.message || 'API設置已成功更新'
      };
      
      // 清除表單
      apiData.value.exchanges[exchange] = {
        api_key: '••••••••••••••••••••••',
        api_secret: '••••••••••••••••••••••••••••••••'
      };
      isEditingKey.value = false;
      isEditingSecret.value = false;
    } else {
      throw new Error(response.data.detail || '更新API設置失敗');
    }
    
  } catch (error) {
    console.error('更新API設置時出錯:', error);
    apiMessage.value = {
      type: 'error',
      text: error.response?.data?.detail 
        ? error.response.data.detail 
        : '更新API設置失敗，請稍後重試'
    };
  } finally {
    isApiUpdating.value = false;
  }
};

// 檢查API密鑰是否存在
const checkApiKeyExists = async (exchange) => {
  const api = createAuthenticatedRequest();
  if (!api) return false;
  
  try {
    const response = await api.get('/api/v1/api-keys');
    if (response.data && Array.isArray(response.data)) {
      return response.data.some(key => key.exchange === exchange);
    }
    return false;
  } catch (error) {
    console.error('檢查API密鑰時出錯:', error);
    return false;
  }
};

// 刪除API密鑰
const deleteApiKeys = async () => {
  // 確認刪除
  if (!confirm(`確定要刪除 ${exchanges.find(e => e.value === apiData.value.selectedExchange)?.label || apiData.value.selectedExchange} 的 API 密鑰嗎？`)) {
    return;
  }

  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isApiUpdating.value = true;
    apiMessage.value = null;
    
    const exchange = apiData.value.selectedExchange;
    
    // 檢查交易所名稱
    if (!exchange || !['binance', 'okx', 'bybit', 'gate', 'mexc'].includes(exchange)) {
      throw new Error('無效的交易所名稱');
    }
    
    const response = await api.delete(`/api/v1/api-keys/${exchange}`);
    
    if (response.data && response.data.success) {
      apiMessage.value = {
        type: 'success',
        text: response.data.message || 'API密鑰已成功刪除'
      };
      
      // 清除表單
      apiData.value.exchanges[exchange] = {
        api_key: '',
        api_secret: ''
      };
      isEditingKey.value = false;
      isEditingSecret.value = false;
      
      ElMessage.success('API密鑰已成功刪除');
    } else {
      throw new Error(response.data.detail || '刪除API密鑰失敗');
    }
    
  } catch (error) {
    console.error('刪除API密鑰時出錯:', error);
    apiMessage.value = {
      type: 'error',
      text: error.response?.data?.detail 
        ? error.response.data.detail 
        : '刪除API密鑰失敗，請稍後重試'
    };
    
    ElMessage.error(error.response?.data?.detail || '刪除API密鑰失敗，請稍後重試');
  } finally {
    isApiUpdating.value = false;
  }
};

// 更新通知設置
const updateNotificationSettings = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isNotificationUpdating.value = true;
    notificationMessage.value = null;
    
    const response = await api.post('/api/settings/notifications', notificationData.value);
    
    notificationMessage.value = {
      type: 'success',
      text: '通知設置更新成功'
    };
    
  } catch (error) {
    console.error('更新通知設置時出錯:', error);
    notificationMessage.value = {
      type: 'error',
      text: error.response && error.response.data.detail 
        ? error.response.data.detail 
        : '更新通知設置失敗'
    };
  } finally {
    isNotificationUpdating.value = false;
  }
};

// 登出
const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('tokenType');
  router.push('/login');
};

// 主題設置
const themeSettings = ref({
  isDarkMode: false,
  autoTheme: false
})

// 切換深色模式
const toggleDarkMode = (value) => {
  themeSettings.value.isDarkMode = value
  themeStore.toggleTheme()
  localStorage.setItem('themeSettings', JSON.stringify(themeSettings.value))
}

// 切換自動主題
const toggleAutoTheme = (value) => {
  themeSettings.value.autoTheme = value
  if (value) {
    // 如果開啟自動主題，則跟隨系統設置
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    themeStore.applyTheme(systemTheme === 'dark')
  }
  localStorage.setItem('themeSettings', JSON.stringify(themeSettings.value))
}

// 初始化主題設置
const initThemeSettings = () => {
  const savedSettings = localStorage.getItem('themeSettings')
  if (savedSettings) {
    themeSettings.value = JSON.parse(savedSettings)
  } else {
    // 如果沒有保存的設置，則使用當前主題
    themeSettings.value.isDarkMode = themeStore.isDarkMode
    themeSettings.value.autoTheme = false
  }
}

onMounted(() => {
  loadUserSettings();
  initThemeSettings();
});
</script>

<style scoped>
.settings-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.settings-header {
  margin-bottom: 30px;
}

.settings-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.settings-header p {
  font-size: 16px;
  color: var(--text-secondary);
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background-color: var(--card-background);
  border-radius: 10px;
  box-shadow: var(--box-shadow-md);
  text-align: center;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-light);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.settings-content {
  display: flex;
  gap: 30px;
}

.settings-sidebar {
  width: 250px;
  flex-shrink: 0;
  background-color: var(--card-background);
  border-radius: 10px;
  box-shadow: var(--box-shadow-md);
  overflow: hidden;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.sidebar-item {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  border-left: 3px solid transparent;
  transition: background-color 0.3s ease;
}

.sidebar-item:hover {
  background-color: var(--hover-color);
}

.sidebar-item.active {
  border-left-color: var(--primary-color);
  background-color: rgba(75, 112, 226, 0.1);
}

body.dark-theme .sidebar-item.active {
  background-color: rgba(91, 129, 255, 0.2);
}

.item-icon {
  margin-right: 12px;
  font-size: 18px;
  color: var(--text-primary);
}

.item-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
}

.settings-panel {
  flex: 1;
  background-color: var(--card-background);
  border-radius: 10px;
  box-shadow: var(--box-shadow-md);
  overflow: hidden;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.panel-content {
  padding: 30px;
}

.panel-content h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.panel-description {
  color: var(--text-secondary);
  margin-bottom: 24px;
}

.success-message, .error-message {
  padding: 12px 16px;
  border-radius: 5px;
  margin-bottom: 20px;
  font-size: 14px;
}

.success-message {
  background-color: rgba(46, 125, 50, 0.1);
  color: #4caf50;
  border-left: 4px solid #4caf50;
}

body.dark-theme .success-message {
  background-color: rgba(76, 175, 80, 0.15);
  color: #81c784;
}

.error-message {
  background-color: rgba(198, 40, 40, 0.1);
  color: #f44336;
  border-left: 4px solid #f44336;
}

body.dark-theme .error-message {
  background-color: rgba(244, 67, 54, 0.15);
  color: #e57373;
}

.settings-form {
  max-width: 600px;
}

.form-group {
  margin-bottom: 24px;
}

.form-section {
  margin-top: 30px;
  margin-bottom: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--border-color);
}

.form-section h3 {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.section-description {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: 20px;
}

label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
}

input[type="text"],
input[type="email"],
input[type="password"] {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--border-color);
  border-radius: 5px;
  font-size: 16px;
  outline: none;
  transition: border-color 0.3s, background-color 0.3s ease;
  background-color: var(--surface-color);
  color: var(--text-primary);
}

input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(75, 112, 226, 0.1);
}

body.dark-theme input:focus {
  box-shadow: 0 0 0 3px rgba(91, 129, 255, 0.2);
}

.field-help {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.field-error {
  color: var(--danger-color);
  font-size: 12px;
  margin-top: 5px;
}

.form-actions {
  margin-top: 30px;
}

.submit-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 5px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.3s;
}

.submit-button:hover {
  background-color: var(--primary-dark);
}

.submit-button:disabled {
  background-color: rgba(75, 112, 226, 0.5);
  cursor: not-allowed;
}

body.dark-theme .submit-button:disabled {
  background-color: rgba(91, 129, 255, 0.5);
}

.api-requirements {
  background-color: var(--hover-color);
  border-radius: 5px;
  padding: 16px;
  margin-bottom: 24px;
}

.api-requirements h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.api-requirements ul {
  padding-left: 20px;
  color: var(--text-secondary);
}

.api-requirements li {
  margin-bottom: 8px;
}

.api-guide {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--border-color);
}

.api-guide h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.api-guide ol {
  padding-left: 20px;
  color: var(--text-secondary);
}

.api-guide li {
  margin-bottom: 8px;
}

.toggle-group {
  margin-bottom: 24px;
}

.toggle-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.switch {
  position: relative;
  display: inline-block;
  width: 50px;
  height: 26px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: #ccc;
  transition: .3s;
}

body.dark-theme .slider {
  background-color: #555;
}

.slider:before {
  position: absolute;
  content: "";
  height: 18px;
  width: 18px;
  left: 4px;
  bottom: 4px;
  background-color: white;
  transition: .3s;
}

input:checked + .slider {
  background-color: var(--primary-color);
}

input:focus + .slider {
  box-shadow: 0 0 1px var(--primary-color);
}

input:checked + .slider:before {
  transform: translateX(24px);
}

.slider.round {
  border-radius: 34px;
}

.slider.round:before {
  border-radius: 50%;
}

.security-info {
  max-width: 600px;
}

.login-activity {
  margin-top: 20px;
}

.activity-item {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin-bottom: 16px;
  background-color: var(--surface-color);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.activity-icon {
  font-size: 24px;
  margin-right: 16px;
  color: var(--text-primary);
}

.activity-details h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--text-primary);
}

.activity-details p {
  margin: 4px 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.security-actions {
  margin-top: 30px;
}

.danger-button {
  background-color: var(--surface-color);
  color: var(--danger-color);
  border: 1px solid var(--danger-color);
  border-radius: 5px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.3s, color 0.3s;
  display: flex;
  align-items: center;
}

.danger-button:hover {
  background-color: var(--danger-color);
  color: white;
}

.button-icon {
  margin-right: 8px;
}

@media (max-width: 768px) {
  .settings-content {
    flex-direction: column;
  }
  
  .settings-sidebar {
    width: 100%;
    margin-bottom: 20px;
  }
  
  .sidebar-item {
    padding: 12px 16px;
  }
}

.password-field {
  position: relative;
  display: flex;
  align-items: center;
}

.toggle-button {
  position: absolute;
  right: 10px;
  background: none;
  border: none;
  color: var(--primary-color);
  font-size: 14px;
  cursor: pointer;
  padding: 5px;
  transition: color 0.3s;
}

.toggle-button:hover {
  color: var(--primary-dark);
  text-decoration: underline;
}

input:focus {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(75, 112, 226, 0.1);
}

/* CSRF 加强安全提示 */
.security-tip {
  background-color: rgba(25, 118, 210, 0.1);
  padding: 15px;
  border-radius: 8px;
  border-left: 4px solid #1976d2;
  margin: 16px 0 24px 0;
  font-size: 14px;
  color: var(--text-secondary);
}

body.dark-theme .security-tip {
  background-color: rgba(66, 165, 245, 0.1);
  border-left: 4px solid #42a5f5;
}

.security-tip strong {
  color: var(--text-primary);
  display: block;
  margin-bottom: 8px;
  font-size: 16px;
}

.security-tip p {
  margin: 6px 0;
}

.required {
  color: var(--danger-color);
  margin-left: 4px;
}

.theme-settings {
  padding: 20px;
}

.theme-options {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-top: 20px;
}

.theme-options .el-switch {
  margin-bottom: 10px;
}

.settings-container {
  padding: 20px;
}

.theme-settings {
  max-width: 600px;
  margin: 0 auto;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 0;
  border-bottom: 1px solid var(--el-border-color-light);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-label {
  font-size: 16px;
  color: var(--el-text-color-primary);
}

.exchange-selector {
  margin-bottom: 24px;
}

.exchange-select {
  width: 100%;
  max-width: 300px;
}

.delete-button {
  background-color: var(--surface-color);
  color: var(--danger-color);
  border: 1px solid var(--danger-color);
  border-radius: 5px;
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  margin-left: 16px;
  transition: background-color 0.3s, color 0.3s;
}

.delete-button:hover {
  background-color: var(--danger-color);
  color: white;
}

.delete-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style> 