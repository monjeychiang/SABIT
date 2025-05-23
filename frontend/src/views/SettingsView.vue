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
          
          <!-- 添加头像上传区域 -->
          <div class="avatar-upload-section">
            <h3>個人頭像</h3>
            <div class="avatar-container">
              <div class="avatar-preview">
                <img 
                  v-if="avatarPreview" 
                  :src="avatarPreview" 
                  alt="頭像預覽" 
                  class="avatar-image"
                />
                <div v-else class="avatar-placeholder">
                  {{ profileData.username ? profileData.username.charAt(0).toUpperCase() : 'U' }}
                </div>
              </div>
              <div class="avatar-actions">
                <input 
                  type="file" 
                  id="avatar-upload" 
                  ref="avatarInput" 
                  @change="onAvatarSelected" 
                  accept="image/png, image/jpeg, image/gif" 
                  class="avatar-input"
                />
                <button type="button" class="avatar-upload-button" @click="triggerAvatarUpload">
                  {{ profileData.avatar_url ? '更換頭像' : '上傳頭像' }}
                </button>
                <button 
                  v-if="profileData.avatar_url" 
                  type="button" 
                  class="avatar-delete-button" 
                  @click="deleteAvatar"
                >
                  刪除頭像
                </button>
              </div>
            </div>
            <p class="field-help">
              支持的格式: JPG, JPEG, PNG, GIF。最大文件大小: 5MB
            </p>
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

          <!-- API密鑰類型切換 -->
          <div class="api-type-selector">
            <label>API密鑰類型</label>
            <div class="api-type-options">
              <el-radio-group v-model="apiData.activeApiType">
                <el-radio-button label="hmac">HMAC-SHA256</el-radio-button>
                <el-radio-button label="ed25519">Ed25519</el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="api-info-box">
            <div v-if="apiData.activeApiType === 'hmac'">
              <div class="api-type-description">
                <i class="el-icon-info"></i>
                <span>HMAC-SHA256 是傳統的API認證方式，由API密鑰和密鑰密碼組成。</span>
              </div>
            </div>
            <div v-else>
              <div class="api-type-description">
                <i class="el-icon-info"></i>
                <span>Ed25519 是一種較新的加密簽名算法，提供更高的安全性和更快的性能。</span>
              </div>
            </div>
          </div>
          
          <!-- API 密鑰狀態顯示 -->
          <div class="api-status-box">
            <h4>API密鑰狀態</h4>
            <div class="api-status-info">
              <div class="api-status-item" :class="{ active: apiData.exchanges[apiData.selectedExchange].has_hmac }">
                <i :class="apiData.exchanges[apiData.selectedExchange].has_hmac ? 'el-icon-check' : 'el-icon-close'"></i>
                <span>HMAC-SHA256：{{ apiData.exchanges[apiData.selectedExchange].has_hmac ? '已設置' : '未設置' }}</span>
              </div>
              <div class="api-status-item" :class="{ active: apiData.exchanges[apiData.selectedExchange].has_ed25519 }">
                <i :class="apiData.exchanges[apiData.selectedExchange].has_ed25519 ? 'el-icon-check' : 'el-icon-close'"></i>
                <span>Ed25519：{{ apiData.exchanges[apiData.selectedExchange].has_ed25519 ? '已設置' : '未設置' }}</span>
              </div>
            </div>
          </div>
          
          <form @submit.prevent="updateApiSettings" class="settings-form">
            <!-- HMAC-SHA256 密鑰表單 -->
            <div v-if="apiData.activeApiType === 'hmac'">
              <div class="form-group">
                <label for="api_key">API密鑰 <span class="required">*</span></label>
                <div class="password-field">
                  <input 
                    type="text" 
                    id="api_key" 
                    v-model="apiData.exchanges[apiData.selectedExchange].hmac.api_key" 
                    :placeholder="apiData.exchanges[apiData.selectedExchange].hmac.api_key ? '••••••••••••••••••••••' : '輸入您的API密鑰'"
                    required 
                    @focus="isEditingHmacKey = true"
                  />
                  <button type="button" class="toggle-button" @click="clearHmacKey" v-if="apiData.exchanges[apiData.selectedExchange].hmac.api_key && !isEditingHmacKey">
                    <span>重新輸入</span>
                  </button>
                </div>
              </div>
              
              <div class="form-group">
                <label for="api_secret">API密鑰密碼 <span class="required">*</span></label>
                <div class="password-field">
                  <input 
                    :type="showHmacSecret ? 'text' : 'password'" 
                    id="api_secret" 
                    v-model="apiData.exchanges[apiData.selectedExchange].hmac.api_secret" 
                    :placeholder="apiData.exchanges[apiData.selectedExchange].hmac.api_secret ? '••••••••••••••••••••••••••••••••' : '輸入您的API密鑰密碼'"
                    required 
                    @focus="isEditingHmacSecret = true"
                  />
                  <button type="button" class="toggle-button" @click="toggleHmacSecretVisibility" v-if="isEditingHmacSecret">
                    <span>{{ showHmacSecret ? '隱藏' : '顯示' }}</span>
                  </button>
                  <button type="button" class="toggle-button" @click="clearHmacSecret" v-if="apiData.exchanges[apiData.selectedExchange].hmac.api_secret && !isEditingHmacSecret">
                    <span>重新輸入</span>
                  </button>
                </div>
              </div>
            </div>

            <!-- Ed25519 密鑰表單 -->
            <div v-else>
              <div class="form-group">
                <label for="ed25519_key">Ed25519 公鑰 <span class="required">*</span></label>
                <div class="password-field">
                  <input 
                    type="text" 
                    id="ed25519_key" 
                    v-model="apiData.exchanges[apiData.selectedExchange].ed25519.public_key" 
                    :placeholder="apiData.exchanges[apiData.selectedExchange].ed25519.public_key ? '••••••••••••••••••••••' : '輸入您的Ed25519公鑰'"
                    required 
                    @focus="isEditingEd25519Key = true"
                  />
                  <button type="button" class="toggle-button" @click="clearEd25519Key" v-if="apiData.exchanges[apiData.selectedExchange].ed25519.public_key && !isEditingEd25519Key">
                    <span>重新輸入</span>
                  </button>
                </div>
              </div>
              
              <div class="form-group">
                <label for="ed25519_secret">Ed25519 私鑰 <span class="required">*</span></label>
                <div class="password-field">
                  <input 
                    :type="showEd25519Secret ? 'text' : 'password'" 
                    id="ed25519_secret" 
                    v-model="apiData.exchanges[apiData.selectedExchange].ed25519.private_key" 
                    :placeholder="apiData.exchanges[apiData.selectedExchange].ed25519.private_key ? '••••••••••••••••••••••••••••••••' : '輸入您的Ed25519私鑰'"
                    required 
                    @focus="isEditingEd25519Secret = true"
                  />
                  <button type="button" class="toggle-button" @click="toggleEd25519SecretVisibility" v-if="isEditingEd25519Secret">
                    <span>{{ showEd25519Secret ? '隱藏' : '顯示' }}</span>
                  </button>
                  <button type="button" class="toggle-button" @click="clearEd25519Secret" v-if="apiData.exchanges[apiData.selectedExchange].ed25519.private_key && !isEditingEd25519Secret">
                    <span>重新輸入</span>
                  </button>
                </div>
              </div>
            </div>

            <div class="form-group">
              <label for="api_description">API密鑰描述（選填）</label>
              <input 
                type="text" 
                id="api_description" 
                v-model="apiData.exchanges[apiData.selectedExchange].description" 
                placeholder="為這組API密鑰添加描述（例如：主要交易帳戶）"
              />
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
          <p class="panel-description">
            自定义您希望接收的通知类型。这些设置将保存在浏览器Cookie中。
          </p>
          
          <div class="security-tip">
            <strong>提示</strong>
            <p>通知设置存储在您的浏览器中，清除浏览器数据会重置这些设置。</p>
          </div>
          
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
                <span>系統通知</span>
                <label class="switch">
                  <input type="checkbox" v-model="notificationData.system_notifications">
                  <span class="slider round"></span>
                </label>
              </label>
              <p class="field-help">接收系統狀態和更新的通知</p>
            </div>
            
            <div class="toggle-group">
              <label class="toggle-label">
                <span>桌面通知</span>
                <label class="switch">
                  <input type="checkbox" v-model="notificationData.desktop_notifications">
                  <span class="slider round"></span>
                </label>
              </label>
              <p class="field-help">允許在桌面顯示通知彈窗（需要瀏覽器權限）</p>
            </div>
            
            <div class="toggle-group">
              <label class="toggle-label">
                <span>聲音通知</span>
                <label class="switch">
                  <input type="checkbox" v-model="notificationData.sound_notifications">
                  <span class="slider round"></span>
                </label>
              </label>
              <p class="field-help">收到重要通知時播放提示音</p>
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
import { useUserStore } from '@/stores/user';
import { useNotificationStore } from '@/stores/notification';
import { ElMessage } from 'element-plus';
import { NTabs, NTabPane, NForm, NFormItem, NInput, NButton, NSwitch, NCard, NSelect, NDivider } from 'naive-ui';

const authStore = useAuthStore();
const userStore = useUserStore();
const notificationStore = useNotificationStore();
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

// 头像上传相关
const avatarInput = ref(null);
const avatarPreview = ref('');
const isAvatarUploading = ref(false);
const avatarFile = ref(null);

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
  confirmPassword: '',
  avatar_url: ''
});
const isProfileUpdating = ref(false);
const profileMessage = ref(null);

// API設置數據
const apiData = ref({
  selectedExchange: 'binance',
  activeApiType: 'hmac', // 默認顯示 HMAC-SHA256 表單
  exchanges: {
    binance: { 
      hmac: { api_key: '', api_secret: '' },
      ed25519: { public_key: '', private_key: '' },
      description: ''
    },
    okx: { 
      hmac: { api_key: '', api_secret: '' },
      ed25519: { public_key: '', private_key: '' },
      description: ''
    },
    bybit: { 
      hmac: { api_key: '', api_secret: '' },
      ed25519: { public_key: '', private_key: '' },
      description: ''
    },
    gate: { 
      hmac: { api_key: '', api_secret: '' },
      ed25519: { public_key: '', private_key: '' },
      description: ''
    },
    mexc: { 
      hmac: { api_key: '', api_secret: '' },
      ed25519: { public_key: '', private_key: '' },
      description: ''
    }
  }
});
const isApiUpdating = ref(false);
const apiMessage = ref(null);

// 通知設置 - 使用cookie存储
const notificationData = ref({
  email_notifications: true,
  trade_notifications: true,
  system_notifications: true,
  desktop_notifications: false,
  sound_notifications: false,
  price_alerts: false,
  notification_preferences: {}
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
  
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  
  return axios.create({
    baseURL: apiBaseUrl,
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
    
    // 使用 userStore 获取用户数据
    const userData = await userStore.getUserData();
    
    if (userData) {
      profileData.value = {
        username: userData.username,
        email: userData.email,
        currentPassword: '',
        newPassword: '',
        confirmPassword: '',
        avatar_url: userData.avatar
      };
      
      // 设置头像预览
      if (userData.avatar) {
        const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        avatarPreview.value = `${apiBaseUrl}${userData.avatar}`;
      } else {
        avatarPreview.value = '';
      }
    }
    
    // 獲取API密鑰設置狀態
    try {
      console.log('開始獲取 API 密鑰設置');
      const apiResponse = await api.get('/api/v1/api-keys');
      console.log('獲取 API 密鑰成功:', apiResponse.data);
      
      if (apiResponse.data && Array.isArray(apiResponse.data)) {
        const apiKeys = apiResponse.data;
        
        // 初始化默認結構
        const exchangeData = initializeExchangeData();
        
        // 填充已存在的 API 密鑰數據
        apiKeys.forEach(apiKey => {
          if (exchangeData.exchanges[apiKey.exchange]) {
            // 設置描述
            exchangeData.exchanges[apiKey.exchange].description = apiKey.description || '';
            
            // 設置密鑰存在狀態
            exchangeData.exchanges[apiKey.exchange].has_hmac = apiKey.has_hmac;
            exchangeData.exchanges[apiKey.exchange].has_ed25519 = apiKey.has_ed25519;
            
            // 設置 HMAC-SHA256 密鑰
            if (apiKey.has_hmac) {
              exchangeData.exchanges[apiKey.exchange].hmac = {
                api_key: '••••••••••••••••••••••',
                api_secret: '••••••••••••••••••••••••••••••••'
              };
            }
            
            // 設置 Ed25519 密鑰
            if (apiKey.has_ed25519) {
              exchangeData.exchanges[apiKey.exchange].ed25519 = {
                public_key: '••••••••••••••••••••••',
                private_key: '••••••••••••••••••••••••••••••••'
              };
            }
            
            // 根據存在的密鑰類型設置默認活動類型
            if (apiKey.has_hmac) {
              exchangeData.activeApiType = 'hmac';
            } else if (apiKey.has_ed25519) {
              exchangeData.activeApiType = 'ed25519';
            }
          }
        });
        
        apiData.value = exchangeData;
      } else {
        console.warn('API 密鑰響應格式不正確:', apiResponse.data);
        apiData.value = initializeExchangeData();
      }
    } catch (apiError) {
      console.error('載入API設置失敗:', apiError);
      // 顯示錯誤信息給用戶
      ElMessage.error('載入API設置失敗，請稍後重試');
      // 設置默認空值
      apiData.value = initializeExchangeData();
    }
    
    // 載入通知設置
    try {
      const notificationResponse = await api.get('/api/v1/notifications');
      if (notificationResponse.data) {
        notificationData.value = {
          ...notificationResponse.data,
          price_alerts: notificationResponse.data.notification_preferences?.price_alerts || false
        };
        console.log('已從cookie載入通知設置');
      }
    } catch (notificationError) {
      console.error('載入通知設置失敗:', notificationError);
    }
    
  } catch (error) {
    console.error('載入用戶設置失敗:', error);
    if (error.response && error.response.status === 401) {
      router.push('/login');
    }
  } finally {
    isLoading.value = false;
  }
};

// 初始化交易所數據結構的輔助函數
const initializeExchangeData = () => {
  return {
    selectedExchange: 'binance',
    activeApiType: 'hmac',
    exchanges: {
      binance: { 
        hmac: { api_key: '', api_secret: '' },
        ed25519: { public_key: '', private_key: '' },
        description: '',
        has_hmac: false,
        has_ed25519: false
      },
      okx: { 
        hmac: { api_key: '', api_secret: '' },
        ed25519: { public_key: '', private_key: '' },
        description: '',
        has_hmac: false,
        has_ed25519: false
      },
      bybit: { 
        hmac: { api_key: '', api_secret: '' },
        ed25519: { public_key: '', private_key: '' },
        description: '',
        has_hmac: false,
        has_ed25519: false
      },
      gate: { 
        hmac: { api_key: '', api_secret: '' },
        ed25519: { public_key: '', private_key: '' },
        description: '',
        has_hmac: false,
        has_ed25519: false
      },
      mexc: { 
        hmac: { api_key: '', api_secret: '' },
        ed25519: { public_key: '', private_key: '' },
        description: '',
        has_hmac: false,
        has_ed25519: false
      }
    }
  };
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

// 触发头像上传弹窗
const triggerAvatarUpload = () => {
  if (avatarInput.value) {
    avatarInput.value.click();
  }
};

// 头像选择处理
const onAvatarSelected = (event) => {
  const file = event.target.files[0];
  if (!file) return;
  
  // 验证文件类型
  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif'];
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('不支持的文件格式，请上传JPG、PNG或GIF图片');
    return;
  }
  
  // 验证文件大小（5MB）
  const maxSize = 5 * 1024 * 1024; // 5MB
  if (file.size > maxSize) {
    ElMessage.error('文件太大，请上传小于5MB的图片');
    return;
  }
  
  // 保存文件引用
  avatarFile.value = file;
  
  // 创建本地预览
  const reader = new FileReader();
  reader.onload = (e) => {
    avatarPreview.value = e.target.result;
    
    // 為了確保GIF預覽能動態顯示，添加隨機參數避免瀏覽器緩存
    if (file.type === 'image/gif') {
      const timestamp = new Date().getTime();
      avatarPreview.value = `${e.target.result}#t=${timestamp}`;
    }
  };
  reader.readAsDataURL(file);
  
  // 自动上传
  uploadAvatar();
};

// 上传头像到服务器
const uploadAvatar = async () => {
  if (!avatarFile.value) return;
  
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isAvatarUploading.value = true;
    
    // 创建FormData对象
    const formData = new FormData();
    formData.append('file', avatarFile.value);
    
    // 上传头像
    const response = await api.post('/api/v1/user/avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    
    if (response.data && response.data.success) {
      // 更新用户头像URL
      profileData.value.avatar_url = response.data.avatar_url;
      
      // 更新预览（使用服务器返回的URL）
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      let newAvatarUrl = `${apiBaseUrl}${response.data.avatar_url}`;
      
      // 如果是GIF，添加時間戳防止瀏覽器緩存
      if (avatarFile.value.type === 'image/gif') {
        const timestamp = new Date().getTime();
        newAvatarUrl += `?_t=${timestamp}`;
      }
      
      avatarPreview.value = newAvatarUrl;
      
      // 通知用户
      ElMessage.success('头像上传成功');
      
      // 更新全局用户信息 - 确保在auth和user store中都正确更新
      if (authStore.user) {
        authStore.user.avatar_url = response.data.avatar_url;
      }
      
      // 同时也更新userStore中的头像信息
      if (userStore.user) {
        userStore.user.avatar = response.data.avatar_url;
      }
    } else {
      throw new Error(response.data?.message || '头像上传失败');
    }
  } catch (error) {
    console.error('上传头像失败:', error);
    ElMessage.error(error.response?.data?.detail || '上传头像失败，请稍后重试');
  } finally {
    isAvatarUploading.value = false;
    // 清空文件输入以允许再次选择相同文件
    if (avatarInput.value) {
      avatarInput.value.value = '';
    }
    avatarFile.value = null;
  }
};

// 删除头像
const deleteAvatar = async () => {
  // 确认删除
  if (!window.confirm('确定要删除您的头像吗？')) {
    return;
  }
  
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    // 删除头像
    const response = await api.delete('/api/v1/user/avatar');
    
    if (response.data && response.data.success) {
      // 清除头像预览
      avatarPreview.value = '';
      
      // 清除头像URL
      profileData.value.avatar_url = null;
      
      // 更新全局用户信息 - authStore
      if (authStore.user) {
        authStore.user.avatar_url = null;
      }
      
      // 同时也更新userStore中的头像信息
      if (userStore.user) {
        userStore.user.avatar = null;
      }
      
      // 通知用户
      ElMessage.success('头像已成功删除');
    } else {
      throw new Error(response.data?.message || '删除头像失败');
    }
  } catch (error) {
    console.error('删除头像失败:', error);
    ElMessage.error(error.response?.data?.detail || '删除头像失败，请稍后重试');
  }
};

// 驗證表單
const validateForm = () => {
  // 重設所有錯誤訊息
  formErrors.value = {
    hmacKey: '',
    hmacSecret: '',
    ed25519Key: '',
    ed25519Secret: ''
  };

  const exchange = apiData.value.selectedExchange;
  let isValid = true;

  if (apiData.value.activeApiType === 'hmac') {
    // 驗證 HMAC-SHA256 密鑰
    if (!apiData.value.exchanges[exchange].hmac.api_key) {
      formErrors.value.hmacKey = 'API 密鑰不能為空';
      isValid = false;
    }
    
    if (!apiData.value.exchanges[exchange].hmac.api_secret) {
      formErrors.value.hmacSecret = 'API 密鑰密碼不能為空';
      isValid = false;
    }
  } else {
    // 驗證 Ed25519 密鑰
    if (!apiData.value.exchanges[exchange].ed25519.public_key) {
      formErrors.value.ed25519Key = 'Ed25519 公鑰不能為空';
      isValid = false;
    }
    
    if (!apiData.value.exchanges[exchange].ed25519.private_key) {
      formErrors.value.ed25519Secret = 'Ed25519 私鑰不能為空';
      isValid = false;
    }
  }

  return isValid;
};

// 更新API設置
const updateApiSettings = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isApiUpdating.value = true;
    apiMessage.value = null;
    
    const exchange = apiData.value.selectedExchange;
    const apiType = apiData.value.activeApiType;
    const description = apiData.value.exchanges[exchange].description;
    
    // 檢查交易所名稱
    if (!exchange || !['binance', 'okx', 'bybit', 'gate', 'mexc'].includes(exchange)) {
      throw new Error('無效的交易所名稱');
    }
    
    // 初始化 payload，只包含共通字段
    let payload = {
      exchange,
      description
    };
    
    // 根據當前選中的API類型添加相應的密鑰
    if (apiType === 'hmac') {
      // 當前修改的是 HMAC 密鑰
      const hmacKey = apiData.value.exchanges[exchange].hmac.api_key;
      const hmacSecret = apiData.value.exchanges[exchange].hmac.api_secret;
      
      // 只有在有值時才添加到 payload
      if (hmacKey && hmacKey !== '••••••••••••••••••••••') {
        payload.api_key = hmacKey;
      }
      
      if (hmacSecret && hmacSecret !== '••••••••••••••••••••••••••••••••') {
        payload.api_secret = hmacSecret;
      }
    } else {
      // 當前修改的是 Ed25519 密鑰
      const ed25519Key = apiData.value.exchanges[exchange].ed25519.public_key;
      const ed25519Secret = apiData.value.exchanges[exchange].ed25519.private_key;
      
      // 只有在有值時才添加到 payload
      if (ed25519Key && ed25519Key !== '••••••••••••••••••••••') {
        payload.ed25519_key = ed25519Key;
      }
      
      if (ed25519Secret && ed25519Secret !== '••••••••••••••••••••••••••••••••') {
        payload.ed25519_secret = ed25519Secret;
      }
    }
    
    // 檢查是否已有API密鑰，決定創建或更新
    const apiKeyExists = await checkApiKeyExists(exchange);
    
    let response;
    if (apiKeyExists) {
      // 更新現有API密鑰
      response = await api.put(`/api/v1/api-keys/${exchange}`, payload);
    } else {
      // 創建新的API密鑰
      response = await api.post('/api/v1/api-keys', payload);
    }
    
    if (response.data.success) {
      apiMessage.value = {
        type: 'success',
        text: response.data.message || 'API設置已成功更新'
      };
      
      // 根據當前操作的 API 類型，重置相應的輸入框
      if (apiType === 'hmac') {
        apiData.value.exchanges[exchange].hmac = {
          api_key: '••••••••••••••••••••••',
          api_secret: '••••••••••••••••••••••••••••••••'
        };
        isEditingHmacKey.value = false;
        isEditingHmacSecret.value = false;
      } else {
        apiData.value.exchanges[exchange].ed25519 = {
          public_key: '••••••••••••••••••••••',
          private_key: '••••••••••••••••••••••••••••••••'
        };
        isEditingEd25519Key.value = false;
        isEditingEd25519Secret.value = false;
      }
    } else {
      throw new Error(response.data.detail || '更新API設置失敗');
    }
    
  } catch (error) {
    console.error('更新API設置時出錯:', error);
    
    // 處理 422 Unprocessable Entity 錯誤 (驗證錯誤)
    if (error.response && error.response.status === 422 && error.response.data) {
      // 嘗試提取錯誤信息並顯示
      const errorDetails = error.response.data;
      if (Array.isArray(errorDetails) && errorDetails.length > 0) {
        apiMessage.value = {
          type: 'error',
          text: errorDetails[0].msg || '表單驗證錯誤，請檢查您輸入的數據'
        };
      } else {
        apiMessage.value = {
          type: 'error',
          text: '表單驗證錯誤，請檢查您輸入的數據'
        };
      }
    } else {
      apiMessage.value = {
        type: 'error',
        text: error.response?.data?.detail 
          ? error.response.data.detail 
          : '更新API設置失敗，請稍後重試'
      };
    }
  } finally {
    isApiUpdating.value = false;
  }
};

// 檢查API密鑰是否存在
const checkApiKeyExists = async (exchange) => {
  const api = createAuthenticatedRequest();
  if (!api) return false;
  
  try {
    console.log(`檢查交易所 ${exchange} 的 API 密鑰是否存在`);
    const response = await api.get('/api/v1/api-keys');
    
    if (response.data && Array.isArray(response.data)) {
      // 檢查是否有匹配的交易所
      const exists = response.data.some(key => key.exchange === exchange);
      console.log(`交易所 ${exchange} 的 API 密鑰${exists ? '存在' : '不存在'}`);
      return exists;
    }
    
    console.warn('API 密鑰響應格式不正確:', response.data);
    return false;
  } catch (error) {
    console.error(`檢查 ${exchange} API 密鑰時出錯:`, error);
    
    // 如果是 404 錯誤，表示沒有找到密鑰，返回 false
    if (error.response && error.response.status === 404) {
      return false;
    }
    
    // 對於其他錯誤，默認假設不存在以便創建新密鑰
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
        hmac: { api_key: '', api_secret: '' },
        ed25519: { public_key: '', private_key: '' },
        description: ''
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
    
    // 准备要发送的数据
    const payload = {
      email_notifications: notificationData.value.email_notifications,
      trade_notifications: notificationData.value.trade_notifications,
      system_notifications: notificationData.value.system_notifications || true,
      desktop_notifications: notificationData.value.desktop_notifications || false,
      sound_notifications: notificationData.value.sound_notifications || false,
      notification_preferences: {
        price_alerts: notificationData.value.price_alerts
      }
    };
    
    // 调用API保存设置到cookie
    const response = await api.post('/api/v1/notifications', payload);
    
    if (response.status >= 200 && response.status < 300) {
      notificationMessage.value = {
        type: 'success',
        text: '通知設置更新成功'
      };
      
      ElMessage.success('通知設置已保存到您的瀏覽器中');
    } else {
      throw new Error(response.data?.detail || '更新通知設置失敗');
    }
    
  } catch (error) {
    console.error('更新通知設置時出錯:', error);
    notificationMessage.value = {
      type: 'error',
      text: error.response?.data?.detail 
        ? error.response.data.detail 
        : '更新通知設置失敗，請稍後重試'
    };
    
    ElMessage.error('無法更新通知設置');
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

// HMAC-SHA256 密鑰顯示控制
const showHmacSecret = ref(false);
const isEditingHmacKey = ref(false);
const isEditingHmacSecret = ref(false);

// Ed25519 密鑰顯示控制
const showEd25519Secret = ref(false);
const isEditingEd25519Key = ref(false);
const isEditingEd25519Secret = ref(false);

// 切換 HMAC-SHA256 API密鑰可見性
const toggleHmacSecretVisibility = () => {
  showHmacSecret.value = !showHmacSecret.value;
};

// 切換 Ed25519 密鑰可見性
const toggleEd25519SecretVisibility = () => {
  showEd25519Secret.value = !showEd25519Secret.value;
};

// 清除 HMAC-SHA256 API密鑰以便重新輸入
const clearHmacKey = () => {
  const exchange = apiData.value.selectedExchange;
  apiData.value.exchanges[exchange].hmac.api_key = '';
  isEditingHmacKey.value = true;
};

// 清除 HMAC-SHA256 API密鑰密碼以便重新輸入
const clearHmacSecret = () => {
  const exchange = apiData.value.selectedExchange;
  apiData.value.exchanges[exchange].hmac.api_secret = '';
  isEditingHmacSecret.value = true;
};

// 清除 Ed25519 公鑰以便重新輸入
const clearEd25519Key = () => {
  const exchange = apiData.value.selectedExchange;
  apiData.value.exchanges[exchange].ed25519.public_key = '';
  isEditingEd25519Key.value = true;
};

// 清除 Ed25519 私鑰以便重新輸入
const clearEd25519Secret = () => {
  const exchange = apiData.value.selectedExchange;
  apiData.value.exchanges[exchange].ed25519.private_key = '';
  isEditingEd25519Secret.value = true;
};

onMounted(() => {
  loadUserSettings();
  initThemeSettings();
});

// 計算表單是否有效
const isFormValid = computed(() => {
  const exchange = apiData.value.selectedExchange;
  
  if (apiData.value.activeApiType === 'hmac') {
    // 檢查 HMAC-SHA256 表單是否填寫完整
    return !!apiData.value.exchanges[exchange].hmac.api_key && 
           !!apiData.value.exchanges[exchange].hmac.api_secret;
  } else {
    // 檢查 Ed25519 表單是否填寫完整
    return !!apiData.value.exchanges[exchange].ed25519.public_key && 
           !!apiData.value.exchanges[exchange].ed25519.private_key;
  }
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

.avatar-upload-section {
  margin-bottom: 24px;
}

.avatar-container {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.avatar-preview {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  overflow: hidden;
  margin-right: 16px;
}

.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  image-rendering: auto;
  transform: translateZ(0);
}

.avatar-placeholder {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background-color: var(--surface-color);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: var(--text-secondary);
}

.avatar-actions {
  display: flex;
  align-items: center;
}

.avatar-input {
  display: none;
}

.avatar-upload-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 5px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  margin-left: 8px;
  transition: background-color 0.3s;
}

.avatar-upload-button:hover {
  background-color: var(--primary-dark);
}

.avatar-delete-button {
  background-color: var(--surface-color);
  color: var(--danger-color);
  border: 1px solid var(--danger-color);
  border-radius: 5px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  margin-left: 8px;
  transition: background-color 0.3s, color 0.3s;
}

.avatar-delete-button:hover {
  background-color: var(--danger-color);
  color: white;
}

.api-type-selector {
  margin-bottom: 24px;
}

.api-type-options {
  margin-top: 10px;
}

.api-info-box {
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 5px;
  padding: 16px;
  margin-bottom: 20px;
}

.api-type-description {
  display: flex;
  align-items: flex-start;
  color: var(--text-secondary);
  font-size: 14px;
}

.api-type-description i {
  margin-right: 8px;
  color: var(--primary-color);
  font-size: 16px;
}

.el-radio-button {
  margin-right: 10px;
}

body.dark-theme .api-info-box {
  background-color: rgba(45, 45, 45, 0.5);
}

.api-status-box {
  margin-top: 20px;
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 5px;
  padding: 16px;
  margin-bottom: 20px;
}

.api-status-box h4 {
  margin-top: 0;
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
}

.api-status-info {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.api-status-item {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-radius: 4px;
  background-color: rgba(0, 0, 0, 0.05);
  flex: 1;
  min-width: 200px;
}

.api-status-item i {
  margin-right: 8px;
  font-size: 16px;
}

.api-status-item.active {
  background-color: rgba(76, 175, 80, 0.1);
  color: #4caf50;
}

.api-status-item:not(.active) {
  background-color: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

body.dark-theme .api-status-item.active {
  background-color: rgba(76, 175, 80, 0.2);
}

body.dark-theme .api-status-item:not(.active) {
  background-color: rgba(244, 67, 54, 0.2);
}
</style> 