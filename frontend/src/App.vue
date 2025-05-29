<script setup lang="ts">
import { RouterView } from 'vue-router'
import { computed, ref, onMounted, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import NavBar from '@/components/NavBar.vue'
import Breadcrumb from '@/components/Breadcrumb.vue'
import FloatingChatButton from './components/FloatingChatButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { useChatroomStore } from '@/stores/chatroom'
import { useNotificationStore } from '@/stores/notification.ts'
import { useOnlineStatusStore } from '@/stores/online-status'
import latencyService from '@/services/latencyService'
import authService from '@/services/authService'
import { useUserStore } from '@/stores/user'
import { accountWebSocketService } from '@/services/accountWebSocketService'
import axios from 'axios'

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const themeStore = useThemeStore();
const chatroomStore = useChatroomStore();
const notificationStore = useNotificationStore();
const onlineStatusStore = useOnlineStatusStore();
const userStore = useUserStore();
const isSidebarCollapsed = ref(false);
const notifications = ref();
// 新增：移动设备检测
const isMobile = ref(window.innerWidth < 768);
// 新增：侧边栏可见状态（仅用于移动设备）
const isSidebarVisible = ref(false);

// 新增：服务器时间和WebSocket状态
const serverTime = ref(new Date());
const wsStatus = ref({
  main: false,
  account: false // 添加賬戶WebSocket狀態
});
const wsStatusText = computed(() => {
  return wsStatus.value.main ? '已連線' : '未連線';
});

// 新增：賬戶WebSocket狀態文字
const accountWsStatusText = computed(() => {
  return wsStatus.value.account ? '已連線' : '未連線';
});

// 新增：服务器延迟状态
const serverLatency = ref('--');
const latencyStatus = ref<'excellent' | 'good' | 'fair' | 'poor' | 'failed'>('failed');

// 新增：WebSocket详情弹窗控制
const showWsDetails = ref(false);

// 添加网络测试状态
const networkTestInProgress = ref(false);
const networkTestStartTime = ref(0);
const networkTestProgress = ref(0);
const currentLatency = ref('--'); // 添加当前测量延迟
const networkTestResults = ref<{
  average: string;
  status: 'excellent' | 'good' | 'fair' | 'poor' | 'failed';
  timestamp: number;
} | null>(null);
const lastTestTime = ref(0); // 记录上次测试时间
const cooldownPeriod = 30000; // 限制测试频率（毫秒），设置为30秒冷却期
const cooldownRemaining = ref(0); // 剩余冷却时间（秒）
const cooldownTimer = ref<number | null>(null); // 冷却计时器ID

// 新增：加载状态，用于显示认证加载动画
const authLoading = ref(false);
const authMessage = ref('');

// 根据用户登录状态显示用户名
const username = computed(() => {
  console.log('計算username屬性，當前用戶:', userStore.user?.username || '遊客');
  return userStore.user?.username || '遊客';
});

// Check if user is authenticated
const isAuthenticated = computed(() => {
  return authStore.isAuthenticated;
});

// 根據當前路由確定使用的佈局
const currentLayout = computed(() => {
  return route.meta.layout || 'default';
});

// 控制主内容区域的样式
const mainContentStyle = computed(() => {
  // 如果是auth佈局，不需要sidebar的padding
  if (currentLayout.value === 'auth') {
    return {};
  }
  
  // 根据侧边栏状态和设备类型调整内容区域
  if (isMobile.value) {
    return {}; // 移動設備直接使用中心對齊
  }
  
  // 非移動設備，根據側邊欄狀態調整內容區域
  return {
    marginLeft: isSidebarCollapsed.value 
      ? `calc(var(--sidebar-collapsed-width) + var(--spacing-md))` 
      : `calc(var(--sidebar-width) + var(--spacing-md))`,
    width: isSidebarCollapsed.value
      ? `calc(100% - var(--sidebar-collapsed-width) - var(--spacing-md) * 2)`
      : `calc(100% - var(--sidebar-width) - var(--spacing-md) * 2)`
  };
});

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  if (isMobile.value) {
    // 在移动设备上切换侧边栏可见性
    isSidebarVisible.value = !isSidebarVisible.value;
  } else {
    // 在桌面设备上切换侧边栏折叠状态
    isSidebarCollapsed.value = !isSidebarCollapsed.value;
    localStorage.setItem('sidebarCollapsed', isSidebarCollapsed.value.toString());
  }
};

// 点击主内容区域关闭移动端侧边栏
const closeMenuOnContentClick = () => {
  if (isMobile.value && isSidebarVisible.value) {
    isSidebarVisible.value = false;
  }
};

// 处理登出
const handleLogout = async () => {
  try {
    console.log('處理登出：正在使用authService.logout()');
    // 斷開賬戶WebSocket連接
    accountWebSocketService.disconnect();
    
    // 使用authService.logout()，它會處理主WebSocket關閉和狀態重置
    await authService.logout();
    
    // 触發登出事件
    window.dispatchEvent(new Event('logout-event'));
    
    // 更新WebSocket狀態顯示
    wsStatus.value.main = false;
    wsStatus.value.account = false;
    
    // 跳轉到首頁並刷新頁面
    router.push('/').then(() => {
      // 使用延遲確保路由變更已完成
      setTimeout(() => {
        window.location.reload();
      }, 100);
    });
  } catch (error) {
    console.error('登出處理失敗:', error);
    // 即使失敗也嘗試重定向並刷新
    router.push('/');
    window.location.reload();
  }
};

// 添加 actionLoading 屬性
const actionLoading = ref(false)

// 新增：监听窗口大小变化
const handleResize = () => {
  const newIsMobile = window.innerWidth < 768;
  if (isMobile.value !== newIsMobile) {
    isMobile.value = newIsMobile;
    // 如果从移动端切换到桌面端，确保侧边栏正确显示
    if (!newIsMobile) {
      isSidebarVisible.value = false;
    }
  }
};

// 新增：格式化服务器时间的方法
const formatServerTime = (date: Date) => {
  return new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'Asia/Taipei'
  }).format(date);
};

// 新增：更新服务器时间
const updateServerTime = () => {
  // 实际项目中可能需要从服务器获取时间
  // 这里简单使用本地时间模拟
  serverTime.value = new Date();
};

// 新增：更新WebSocket状态
const updateWebSocketStatus = () => {
  if (authStore.isAuthenticated) {
    // 監控主WebSocket
    import('@/services/webSocketService').then(({ default: mainWebSocketManager }) => {
      wsStatus.value.main = mainWebSocketManager.isConnected();
    });
    
    // 監控賬戶WebSocket
    wsStatus.value.account = accountWebSocketService.isConnected();
  } else {
    wsStatus.value.main = false;
    wsStatus.value.account = false;
  }
};

// 新增：更新服务器延迟
const updateServerLatency = () => {
  // 获取最新的延迟测量结果
  const result = latencyService.getLatestResult();
  if (result) {
    serverLatency.value = result.text;
    latencyStatus.value = result.status;
  }
};

// 新增：重连WebSocket的方法
const reconnectWebSockets = () => {
  if (authStore.isAuthenticated) {
    // 重連主WebSocket
    import('@/services/webSocketService').then(({ default: mainWebSocketManager }) => {
      mainWebSocketManager.connectAll().then(result => {
        console.log('主WebSocket重連結果:', result ? '成功' : '失敗');
      }).catch(error => {
        console.error('主WebSocket重連失敗:', error);
      });
    });
    
    // 重連賬戶WebSocket
    if (!accountWebSocketService.isConnected()) {
      // 检查是否有API密钥
      accountWebSocketService.hasExchangeApiKey('binance').then(hasApiKey => {
        if (hasApiKey) {
          accountWebSocketService.connect('binance').then(result => {
            console.log('賬戶WebSocket重連結果:', result ? '成功' : '失敗');
          }).catch(error => {
            console.error('賬戶WebSocket重連失敗:', error);
          });
        } else {
          console.log('用戶沒有binance的API密鑰，跳過WebSocket重連');
        }
      });
    }
    
    setTimeout(() => {
      showWsDetails.value = false;
    }, 500);
  }
};

// 计算按钮文本
const testButtonText = computed(() => {
  if (networkTestInProgress.value) {
    return '测试中...';
  } else if (cooldownRemaining.value > 0) {
    return `冷却中 (${cooldownRemaining.value}秒)`;
  } else {
    return '15秒延迟测试';
  }
});

// 计算按钮是否禁用
const testButtonDisabled = computed(() => {
  return networkTestInProgress.value || cooldownRemaining.value > 0;
});

// 更新冷却计时器
const updateCooldown = () => {
  if (lastTestTime.value === 0) return;
  
  const now = Date.now();
  const elapsed = now - lastTestTime.value;
  
  if (elapsed < cooldownPeriod) {
    cooldownRemaining.value = Math.ceil((cooldownPeriod - elapsed) / 1000);
    
    // 如果没有活跃的计时器，创建一个
    if (cooldownTimer.value === null) {
      cooldownTimer.value = window.setInterval(() => {
        updateCooldown();
        
        // 如果冷却结束，清除计时器
        if (cooldownRemaining.value <= 0) {
          if (cooldownTimer.value !== null) {
            clearInterval(cooldownTimer.value);
            cooldownTimer.value = null;
          }
        }
      }, 1000);
    }
  } else {
    cooldownRemaining.value = 0;
    
    // 清除计时器
    if (cooldownTimer.value !== null) {
      clearInterval(cooldownTimer.value);
      cooldownTimer.value = null;
    }
  }
};

// 新增：执行15秒网络测试
const runNetworkTest = async () => {
  // 检查是否在冷却期内
  const now = Date.now();
  const timeSinceLastTest = now - lastTestTime.value;
  
  if (timeSinceLastTest < cooldownPeriod && lastTestTime.value > 0) {
    // 冷却中，使用计算属性显示状态
    return;
  }
  
  try {
    networkTestInProgress.value = true;
    networkTestStartTime.value = now;
    networkTestProgress.value = 0;
    currentLatency.value = '--';
    
    // 清除之前的测试结果
    networkTestResults.value = null;
    
    // 创建进度条更新定时器
    const progressInterval = setInterval(() => {
      // 计算当前进度百分比
      const elapsed = Date.now() - networkTestStartTime.value;
      networkTestProgress.value = Math.min(100, (elapsed / 15000) * 100);
      
      // 当进度达到100%时停止更新
      if (networkTestProgress.value >= 100) {
        clearInterval(progressInterval);
      }
    }, 100); // 更频繁更新以获得更平滑的进度条
    
    // 优化的测量策略：前5秒每秒测量一次，之后每2秒测量一次，总共约10次请求
    // 这样仍保持15秒的测试时间，但减少请求次数
    const result = await latencyService.measureAverage(15000, (elapsed) => {
      // 前5秒每秒一次，之后每2秒一次
      return elapsed <= 5000 ? 1000 : 2000;
    }, (latency) => {
      // 更新当前测量结果
      currentLatency.value = `${latency}ms`;
    });
    
    // 清除进度条更新定时器
    clearInterval(progressInterval);
    networkTestProgress.value = 100; // 确保进度显示为完成
    
    // 存储测试结果
    networkTestResults.value = {
      average: result.text,
      status: result.status,
      timestamp: result.timestamp
    };
    
    // 更新最后测试时间
    lastTestTime.value = Date.now();
    
    // 启动冷却计时
    updateCooldown();
  } catch (error) {
    console.error('网络测试失败:', error);
  } finally {
    networkTestInProgress.value = false;
  }
};

// 格式化测试时间
const formatTestTime = (timestamp: number): string => {
  const date = new Date(timestamp);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
};

// 獲取系統性能狀態文本
const getPerformanceStatusText = (status: string): string => {
  const statusTexts: Record<string, string> = {
    'excellent': '極佳',
    'good': '良好',
    'fair': '一般',
    'poor': '較差',
    'unknown': '未知'
  };
  return statusTexts[status] || '未知';
};

// 新增：处理URL中的认证令牌参数
const handleAuthTokensFromUrl = async () => {
  try {
    // 获取URL参数
    const params = new URLSearchParams(window.location.search);
    
    // 检查是否包含访问令牌，如果有说明是从Google认证回调过来的
    const accessToken = params.get('access_token');
    const refreshToken = params.get('refresh_token');
    const tokenType = params.get('token_type');
    const keepLoggedInStr = params.get('keep_logged_in');
    
    // 如果没有令牌参数，直接返回
    if (!accessToken || !tokenType || !refreshToken) {
      return false;
    }
    
    // 显示加载动画（使用事件机制）
    window.dispatchEvent(new CustomEvent('auth-loading-start', { 
      detail: { message: '正在处理登入...' }
    }));
    
    console.log('App: 检测到URL中的认证令牌，开始处理登录');
    
    // 解析保持登录状态参数
    const keepLoggedIn = keepLoggedInStr === 'true' || keepLoggedInStr === 'True' || 
                         keepLoggedInStr === '1' || keepLoggedInStr === 'yes';
    
    // 获取过期时间参数
    const expiresInParam = params.get('expires_in');
    const expiresIn = expiresInParam ? parseInt(expiresInParam) : undefined;
    
    const refreshTokenExpiresInParam = params.get('refresh_token_expires_in');
    const refreshTokenExpiresIn = refreshTokenExpiresInParam 
                              ? parseInt(refreshTokenExpiresInParam) 
                              : expiresIn;
    
    // 处理Google登录回调
    const success = await authStore.handleGoogleCallback(
      accessToken,
      refreshToken,
      keepLoggedIn,
      expiresIn,
      refreshTokenExpiresIn
    );
    
    if (success) {
      // 触发登录成功事件
      window.dispatchEvent(new Event('login-authenticated'));
      console.log('App: 成功处理登录令牌');
      
      // 清除URL参数
      window.history.replaceState({}, document.title, window.location.pathname);
      
      // 如果当前在认证路径下，跳转到首页
      if (route.path.startsWith('/auth/')) {
        router.push('/');
      }
      
      return true;
    } else {
      console.error('App: 处理登录令牌失败');
      return false;
    }
  } catch (error) {
    console.error('App: 处理认证令牌时出错:', error);
    return false;
  } finally {
    // 关闭加载动画（使用事件机制）
    window.dispatchEvent(new CustomEvent('auth-loading-end'));
  }
};

// 定义timeInterval变量，用于在onUnmounted中清除
let timeInterval: number | undefined;

// 新增：添加伺服器公共狀態和在線用戶數
const serverPublicStatus = ref({
  status: 'running',
  cpu_percent: 0,
  performance_status: 'unknown',
  system: { system: '', version: '' }
});

// 在線用戶數
const onlineUserCount = ref(0);

// 新增：獲取伺服器公共狀態
const fetchServerPublicStatus = async () => {
  try {
    if (authStore.isAuthenticated) {
      const response = await axios.get('/api/v1/system/public-status', {
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      });
      serverPublicStatus.value = response.data;
    }
  } catch (error) {
    console.error('獲取伺服器公共狀態失敗:', error);
  }
};

// 新增：獲取在線用戶數
const fetchOnlineUsersCount = async () => {
  try {
    if (authStore.isAuthenticated) {
      const response = await axios.get('/api/v1/online/public-stats', {
        headers: { 'Authorization': `Bearer ${authStore.token}` }
      });
      onlineUserCount.value = response.data.total_online || 0;
    }
  } catch (error) {
    console.error('獲取在線用戶數失敗:', error);
  }
};

// 新增：詳情彈窗的定時器
let detailsUpdateInterval: number | undefined;

// 監聽詳情彈窗的開關狀態
watch(showWsDetails, (newValue) => {
  if (newValue) {
    // 彈窗打開時，立即獲取數據
    fetchServerPublicStatus();
    fetchOnlineUsersCount();
    
    // 設置定時器，每 10 秒更新一次數據
    detailsUpdateInterval = window.setInterval(() => {
      console.log('詳情彈窗開啟中，更新系統狀態和在線用戶數');
      fetchServerPublicStatus();
      fetchOnlineUsersCount();
    }, 10000);
  } else {
    // 彈窗關閉時，清除定時器
    if (detailsUpdateInterval) {
      clearInterval(detailsUpdateInterval);
      detailsUpdateInterval = undefined;
    }
  }
});

// 初始化
onMounted(async () => {
  // 监听加载动画开始和结束事件
  window.addEventListener('auth-loading-start', (event: Event) => {
    authLoading.value = true;
    // 如果事件中提供了消息，则使用它
    const customEvent = event as CustomEvent<{message?: string}>;
    if (customEvent.detail?.message) {
      authMessage.value = customEvent.detail.message;
    } else {
      authMessage.value = '正在处理...';
    }
  });
  
  window.addEventListener('auth-loading-end', () => {
    authLoading.value = false;
    authMessage.value = '';
  });

  // 尝试处理URL中的令牌参数
  const tokenHandled = await handleAuthTokensFromUrl();
  
  // 只有在没有处理令牌参数时才初始化认证
  if (!tokenHandled) {
    try {
      await authStore.initAuth();
      
      // 如果用戶已認證，嘗試連接到賬戶WebSocket
      if (authStore.isAuthenticated) {
        try {
          // 檢查用戶是否有binance的API密鑰
          const hasApiKey = await accountWebSocketService.hasExchangeApiKey('binance');
          if (hasApiKey) {
            accountWebSocketService.connect('binance').catch(error => {
              console.error('連接賬戶WebSocket失敗:', error);
            });
          } else {
            console.log('用戶沒有binance的API密鑰，跳過WebSocket連接');
            wsStatus.value.account = false;
          }
        } catch (error) {
          console.error('檢查API密鑰時出錯:', error);
        }
      }
    } catch (error) {
      console.error('初始化認證失敗:', error);
    }
  }

  // 初始化主题
  themeStore.initTheme();

  // 檢查本地存儲的 token
  const token = localStorage.getItem('token')
  if (token) {
    try {
      actionLoading.value = true
      await authStore.checkAuth()
      
      // 如果認證成功，連接到賬戶WebSocket
      if (authStore.isAuthenticated) {
        try {
          // 檢查用戶是否有binance的API密鑰
          const hasApiKey = await accountWebSocketService.hasExchangeApiKey('binance');
          if (hasApiKey) {
            accountWebSocketService.connect('binance').catch(error => {
              console.error('連接賬戶WebSocket失敗:', error);
            });
          } else {
            console.log('用戶沒有binance的API密鑰，跳過WebSocket連接');
            wsStatus.value.account = false;
          }
        } catch (error) {
          console.error('檢查API密鑰時出錯:', error);
        }
      }
    } catch (error) {
      console.error('認證檢查失敗:', error)
    } finally {
      actionLoading.value = false
    }
  }

  // 從localStorage恢復側邊欄狀態
  const savedState = localStorage.getItem('sidebarCollapsed');
  if (savedState !== null) {
    isSidebarCollapsed.value = savedState === 'true';
  }

  // 监听窗口大小变化
  window.addEventListener('resize', handleResize);
  // 初始化移动设备检测
  handleResize();

  // 监听令牌更新事件，让状态更新更可靠
  window.addEventListener('auth:tokens-updated', async () => {
    console.log('收到令牌更新事件，检查认证状态');
    try {
      actionLoading.value = true;
      // 使用checkAuth更新状态
      await authStore.checkAuth();
    } catch (error) {
      console.error('令牌更新后认证检查失败:', error);
    } finally {
      actionLoading.value = false;
    }
  });

  // 设置定时器，定期更新服务器时间和WebSocket状态
  timeInterval = window.setInterval(() => {
    updateServerTime();
    updateWebSocketStatus();
    updateServerLatency();
  }, 1000);

  // 启动延迟测量服务
  latencyService.addListener((result) => {
    serverLatency.value = result.text;
    latencyStatus.value = result.status;
  });
  latencyService.startAutoMeasurement();

  // 首次獲取公共狀態和在線用戶數（保留一次性初始化）
  fetchServerPublicStatus();
  fetchOnlineUsersCount();

  // 检查是否需要更新冷却倒计时
  if (lastTestTime.value > 0) {
    updateCooldown();
  }

  // 監聽登入事件
  window.addEventListener('login-authenticated', async () => {
    console.log('檢測到登入事件，嘗試連接賬戶WebSocket');
    // 如果用戶已認證，連接到賬戶WebSocket
    if (authStore.isAuthenticated) {
      try {
        // 檢查用戶是否有binance的API密鑰
        const hasApiKey = await accountWebSocketService.hasExchangeApiKey('binance');
        if (hasApiKey) {
          accountWebSocketService.connect('binance').catch(error => {
            console.error('連接賬戶WebSocket失敗:', error);
          });
        } else {
          console.log('用戶沒有binance的API密鑰，跳過WebSocket連接');
          wsStatus.value.account = false;
        }
      } catch (error) {
        console.error('檢查API密鑰時出錯:', error);
      }
      // 前端登入通知已被禁用，僅依賴後端通知
      console.log('用戶已登入，將只接收後端登入通知');
      // notificationStore.sendLoginSuccessNotification(); // 已在 notification.ts 中禁用
    }
  });
  
  // 監聽登出事件
  window.addEventListener('logout-event', () => {
    console.log('檢測到登出事件，斷開賬戶WebSocket');
    accountWebSocketService.disconnect();
    
    // 添加頁面刷新邏輯
    // 使用短暫延遲確保所有登出操作完成
    setTimeout(() => {
      console.log('登出事件處理完成，準備刷新頁面');
      window.location.reload();
    }, 300);
  });
});

// 在组件卸载时清除定时器
onUnmounted(() => {
  if (timeInterval !== undefined) {
    clearInterval(timeInterval);
  }
  
  // 確保清除詳情彈窗定時器
  if (detailsUpdateInterval !== undefined) {
    clearInterval(detailsUpdateInterval);
  }
  
  latencyService.stopAutoMeasurement();
  
  // 斷開賬戶WebSocket連接
  accountWebSocketService.disconnect();
  
  // 清除冷却计时器
  if (cooldownTimer.value !== null) {
    clearInterval(cooldownTimer.value);
    cooldownTimer.value = null;
  }

  // 移除事件监听器
  window.removeEventListener('resize', handleResize);
  window.removeEventListener('auth:tokens-updated', () => {});
  window.removeEventListener('login-authenticated', () => {});
  window.removeEventListener('logout-event', () => {});
  
  // 移除加载动画事件监听器
  window.removeEventListener('auth-loading-start', () => {});
  window.removeEventListener('auth-loading-end', () => {});
});
</script>

<template>
  <div id="app" :class="{ 'loading': actionLoading, 'dark-theme': themeStore.isDarkMode }">
    <!-- 全局认证加载动画，用于处理Google登录回调 -->
    <div class="auth-loading-overlay" v-if="authLoading">
      <div class="loader"></div>
    </div>

    <!-- 默認佈局：有導航欄和側邊欄 -->
    <template v-if="currentLayout === 'default'">
      <div class="default-layout">
        <NavBar 
          :username="username"
          :notifications="notifications"
          @toggle-sidebar="toggleSidebar"
          @logout="handleLogout"
        />
        
        <!-- 調整側邊欄位置，將其移到與 app-content 同級 -->
        <Sidebar 
          :is-collapsed="isSidebarCollapsed" 
          :is-mobile="isMobile"
          :is-visible="isSidebarVisible"
          @close-mobile-sidebar="isSidebarVisible = false"
        />
        
        <div class="app-content">
          <main class="main-content" :style="mainContentStyle" @click="closeMenuOnContentClick">
            <!-- 麵包屑導航 -->
            <div class="main-content-header">
              <Breadcrumb />
            </div>
            
            <!-- 可滾動內容區域 -->
            <div class="content-scrollable">
              <router-view v-slot="{ Component, route }">
                <transition name="fade" mode="out-in">
                  <component 
                    :is="Component" 
                    :key="route.meta.reload ? route.fullPath : route.path"
                  />
                </transition>
              </router-view>
            </div>
          </main>
        </div>
        
        <!-- 确保底部状态栏在侧边栏之外 -->
        <div class="status-bar" :style="mainContentStyle">
          <div class="status-bar-content">
            <div class="status-bar-section">
              <span class="connection-dot" :class="{ 'connected': wsStatus.main, 'disconnected': !wsStatus.main }"></span>
              <span class="status-value clickable" :class="latencyStatus" @click="showWsDetails = !showWsDetails">{{ serverLatency }}</span>
              <div v-if="showWsDetails" class="ws-details-popup">
                <div class="ws-details-header">
                  <h3>系統狀態</h3>
                  <button class="ws-details-close" @click="showWsDetails = false">×</button>
                </div>
                <div class="ws-details-content">
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">伺服器延遲:</span>
                    <span class="ws-detail-status" :class="latencyStatus">{{ serverLatency }}</span>
                  </div>
                  
                  <!-- 添加在線用戶數顯示 -->
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">在線用戶:</span>
                    <span class="ws-detail-status">{{ onlineUserCount }} 人</span>
                  </div>
                  
                  <!-- 添加伺服器狀態顯示 -->
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">伺服器狀態:</span>
                    <span class="ws-detail-status" :class="{ 'excellent': serverPublicStatus.status === 'running', 'poor': serverPublicStatus.status !== 'running' }">
                      {{ serverPublicStatus.status === 'running' ? '運行中' : '異常' }}
                    </span>
                  </div>
                  
                  <!-- 添加CPU使用率顯示 -->
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">系統效能:</span>
                    <div class="progress-container small">
                      <div class="progress-bar">
                        <div class="progress-inner" 
                            :style="{ width: `${serverPublicStatus.cpu_percent}%` }"
                            :class="serverPublicStatus.performance_status">
                        </div>
                      </div>
                      <span class="progress-value">
                        {{ serverPublicStatus.cpu_percent }}% 
                        <span class="status-text">({{ getPerformanceStatusText(serverPublicStatus.performance_status) }})</span>
                      </span>
                    </div>
                  </div>
                  
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">主WebSocket:</span>
                    <span class="connection-dot" :class="{ 'connected': wsStatus.main, 'disconnected': !wsStatus.main }"></span>
                    <span class="ws-detail-status">{{ wsStatus.main ? '已連線' : '未連線' }}</span>
                  </div>
                  
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">賬戶WebSocket:</span>
                    <span class="connection-dot" :class="{ 'connected': wsStatus.account, 'disconnected': !wsStatus.account }"></span>
                    <span class="ws-detail-status">{{ wsStatus.account ? '已連線' : '未連線' }}</span>
                  </div>
                  
                  <!-- 网络测试区域 -->
                  <div class="network-test-section">
                    <h4>網路測試</h4>
                    
                    <!-- 测试按钮 -->
                    <button 
                      class="network-test-button" 
                      @click="runNetworkTest"
                      :disabled="testButtonDisabled"
                      :class="{ 'cooldown': cooldownRemaining > 0 }"
                    >
                      {{ testButtonText }}
                    </button>
                    
                    <!-- 测试中进度条 -->
                    <div v-if="networkTestInProgress" class="network-test-progress">
                      <div class="progress-bar">
                        <div class="progress-inner" :style="{ width: `${networkTestProgress}%` }"></div>
                      </div>
                      <div class="progress-info">
                        <span class="progress-text">正在測量平均延遲... {{ Math.round(networkTestProgress) }}%</span>
                        <span class="current-latency">當前延遲: {{ currentLatency }}</span>
                      </div>
                    </div>
                    
                    <!-- 测试结果 -->
                    <div v-if="networkTestResults" class="network-test-results">
                      <div class="test-result-header">測試結果：</div>
                      <div class="test-result-item">
                        <span class="test-label">平均延遲:</span>
                        <span class="test-value" :class="networkTestResults.status">
                          {{ networkTestResults.average }}
                        </span>
                      </div>
                      <div class="test-result-item">
                        <span class="test-label">測試時間:</span>
                        <span class="test-value">{{ formatTestTime(networkTestResults.timestamp) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="ws-details-footer">
                  <button class="ws-refresh-button" @click="latencyService.measure(); reconnectWebSockets(); fetchServerPublicStatus(); fetchOnlineUsersCount();">刷新狀態</button>
                </div>
              </div>
            </div>
            
            <div class="status-bar-section">
              <span class="status-value">{{ formatServerTime(serverTime) }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
    
    <!-- 認證佈局：沒有導航欄和側邊欄，全屏顯示 -->
    <template v-else-if="currentLayout === 'auth'">
      <div class="auth-layout">
        <div class="auth-content-wrapper">
          <router-view v-slot="{ Component, route }">
            <component 
              :is="Component"
              :key="route.fullPath"
            />
          </router-view>
        </div>
      </div>
      
      <!-- 认证布局也显示底部状态栏 -->
      <div class="status-bar" :style="mainContentStyle">
        <div class="status-bar-content">
          <div class="status-bar-section">
            <span class="connection-dot" :class="{ 'connected': wsStatus.main, 'disconnected': !wsStatus.main }"></span>
            <span class="status-value clickable" :class="latencyStatus" @click="showWsDetails = !showWsDetails">{{ serverLatency }}</span>
            <div v-if="showWsDetails" class="ws-details-popup">
              <div class="ws-details-header">
                <h3>系統狀態</h3>
                <button class="ws-details-close" @click="showWsDetails = false">×</button>
              </div>
              <div class="ws-details-content">
                <div class="ws-detail-item">
                  <span class="ws-detail-label">伺服器延遲:</span>
                  <span class="ws-detail-status" :class="latencyStatus">{{ serverLatency }}</span>
                </div>
                
                <!-- 添加在線用戶數顯示 -->
                <div class="ws-detail-item">
                  <span class="ws-detail-label">在線用戶:</span>
                  <span class="ws-detail-status">{{ onlineUserCount }} 人</span>
                </div>
                
                <!-- 添加伺服器狀態顯示 -->
                <div class="ws-detail-item">
                  <span class="ws-detail-label">伺服器狀態:</span>
                  <span class="ws-detail-status" :class="{ 'excellent': serverPublicStatus.status === 'running', 'poor': serverPublicStatus.status !== 'running' }">
                    {{ serverPublicStatus.status === 'running' ? '運行中' : '異常' }}
                  </span>
                </div>
                
                <!-- 添加CPU使用率顯示 -->
                <div class="ws-detail-item">
                  <span class="ws-detail-label">系統效能:</span>
                  <div class="progress-container small">
                    <div class="progress-bar">
                      <div class="progress-inner" 
                          :style="{ width: `${serverPublicStatus.cpu_percent}%` }"
                          :class="serverPublicStatus.performance_status">
                      </div>
                    </div>
                    <span class="progress-value">
                      {{ serverPublicStatus.cpu_percent }}% 
                      <span class="status-text">({{ getPerformanceStatusText(serverPublicStatus.performance_status) }})</span>
                    </span>
                  </div>
                </div>
                
                <div class="ws-detail-item">
                  <span class="ws-detail-label">主WebSocket:</span>
                  <span class="connection-dot" :class="{ 'connected': wsStatus.main, 'disconnected': !wsStatus.main }"></span>
                  <span class="ws-detail-status">{{ wsStatus.main ? '已連線' : '未連線' }}</span>
                </div>
                
                <div class="ws-detail-item">
                  <span class="ws-detail-label">賬戶WebSocket:</span>
                  <span class="connection-dot" :class="{ 'connected': wsStatus.account, 'disconnected': !wsStatus.account }"></span>
                  <span class="ws-detail-status">{{ wsStatus.account ? '已連線' : '未連線' }}</span>
                </div>
                
                <!-- 网络测试区域 -->
                <div class="network-test-section">
                  <h4>網路測試</h4>
                  
                  <!-- 测试按钮 -->
                  <button 
                    class="network-test-button" 
                    @click="runNetworkTest"
                    :disabled="testButtonDisabled"
                    :class="{ 'cooldown': cooldownRemaining > 0 }"
                  >
                    {{ testButtonText }}
                  </button>
                  
                  <!-- 测试中进度条 -->
                  <div v-if="networkTestInProgress" class="network-test-progress">
                    <div class="progress-bar">
                      <div class="progress-inner" :style="{ width: `${networkTestProgress}%` }"></div>
                    </div>
                    <div class="progress-info">
                      <span class="progress-text">正在測量平均延遲... {{ Math.round(networkTestProgress) }}%</span>
                      <span class="current-latency">當前延遲: {{ currentLatency }}</span>
                    </div>
                  </div>
                  
                  <!-- 测试结果 -->
                  <div v-if="networkTestResults" class="network-test-results">
                    <div class="test-result-header">測試結果：</div>
                    <div class="test-result-item">
                      <span class="test-label">平均延遲:</span>
                      <span class="test-value" :class="networkTestResults.status">
                        {{ networkTestResults.average }}
                      </span>
                    </div>
                    <div class="test-result-item">
                      <span class="test-label">測試時間:</span>
                      <span class="test-value">{{ formatTestTime(networkTestResults.timestamp) }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="ws-details-footer">
                <button class="ws-refresh-button" @click="latencyService.measure(); reconnectWebSockets(); fetchServerPublicStatus(); fetchOnlineUsersCount();">刷新狀態</button>
              </div>
            </div>
          </div>
          
          <div class="status-bar-section">
            <span class="status-value">{{ formatServerTime(serverTime) }}</span>
          </div>
        </div>
      </div>
    </template>
    
    <!-- 其他佈局可以在這裡添加 -->
  </div>
  
  <!-- 在最外层添加浮动聊天按钮，确保它不受布局影响 -->
  <FloatingChatButton />
</template>

<style>
/* 导入全局CSS变量和样式 */
@import './assets/main.css';

#app {
  min-height: 100vh;
  background-color: var(--background-color);
  color: var(--text-primary);
  transition: background-color 0.3s ease, color 0.3s ease;
  padding-bottom: var(--status-bar-height, 24px);
  position: relative;
  font-family: var(--font-family);
  overflow: hidden; /* 禁止整個應用滾動 */
}

/* 添加全局樣式來禁止基本元素滾動 */
html, body {
  overflow: hidden;
  height: 100%;
  margin: 0;
  padding: 0;
  position: fixed;
  width: 100%;
}

.app-content {
  flex: 1;
  display: flex;
  min-height: calc(100vh - var(--navbar-height));
  margin-top: var(--navbar-height);
  /* 添加過渡效果，確保與側邊欄同步 */
  transition: background-color 0.3s ease, color 0.3s ease;
}

.main-content {
  flex: 1;
  padding: var(--content-padding);
  padding-top: calc(var(--navbar-height) + var(--content-padding));
  transition: padding-left 0.3s ease, background-color 0.3s ease, color 0.3s ease;
  width: 100%;
}

/* 確保整個應用有統一的過渡效果 */
#app {
  transition: background-color 0.3s ease, color 0.3s ease;
}

/* 確保深色主題切換更流暢 */
.dark-theme {
  transition: background-color 0.3s ease, color 0.3s ease;
}

/* 側邊欄折疊時調整 app-content */
.app-content.sidebar-collapsed {
  margin-left: 0; /* 移除左側邊距，由內部內容控制 */
}

.main-content {
  flex: 1;
  margin: var(--spacing-md); /* 恢復頂部邊距 */
  margin-bottom: calc(var(--spacing-md) + var(--status-bar-height, 24px) + 8px); /* 增加底部間距，確保不被狀態欄遮擋 */
  border-radius: var(--border-radius-lg);
  transition: all var(--transition-normal) ease;
  max-height: calc(100vh - var(--navbar-height) - var(--spacing-sm) - var(--spacing-md) * 2 - var(--status-bar-height, 24px)); /* 更新高度計算，考慮頂部間距 */
  background-color: var(--card-background);
  position: relative;
  box-shadow: var(--box-shadow-sm);
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 防止整個卡片滾動 */
  height: auto; /* 讓卡片高度根據內容自適應，而不是固定高度 */
  min-height: 300px; /* 設置最小高度，確保卡片不會太小 */
  max-width: calc(100% - var(--spacing-md) * 2); /* 確保卡片寬度不超過可用空間 */
  margin-left: auto;
  margin-right: auto;
  padding-top: var(--spacing-xs); /* 為卡片頂部添加間距 */
}

.main-content-header {
  padding: var(--spacing-xs) 0 0; /* 為頂部添加間距 */
  flex-shrink: 0;
  z-index: 10; /* 確保始終在頂部 */
  position: relative; /* 使z-index生效 */
  background-color: var(--card-background); /* 確保背景色與卡片一致 */
  margin: 0 var(--spacing-sm); /* 左右添加適當外邊距 */
  border-radius: var(--border-radius-lg) var(--border-radius-lg) 0 0; /* 頂部圓角與卡片一致 */
}

.breadcrumb-container {
  margin: 0; /* 移除所有外邊距 */
  position: relative;
  padding: var(--spacing-xs) var(--spacing-sm); /* 調整內邊距，增加頂部和底部空間 */
  background-color: transparent;
  border-bottom: 1px solid var(--border-color-light); /* 添加底部邊框分隔線 */
  margin-bottom: var(--spacing-xs); /* 添加底部外邊距增加與內容的間距 */
}

.content-scrollable {
  flex: 1;
  overflow-y: auto; /* 只有內容區域滾動 */
  overflow-x: hidden; /* 防止水平滾動 */
  padding: var(--spacing-xs) var(--spacing-sm); /* 左右增加間距 */
  position: relative; /* 添加相對定位 */
  -webkit-overflow-scrolling: touch; /* 在iOS上改善滾動體驗 */
  height: calc(100% - var(--breadcrumb-height, 42px)); /* 調整高度計算，考慮增加的麵包屑高度 */
  margin: 0 var(--spacing-sm); /* 增加左右外邊距 */
}

/* 移動設備上的調整 */
@media (max-width: 768px) {
  .app-content {
    margin-top: calc(var(--navbar-height) + var(--spacing-xs)); /* 移動設備上使用更小的間距 */
    padding-top: 0;
  }
  
  .main-content {
    margin: var(--spacing-sm); /* 恢復移動設備上的頂部邊距 */
    margin-bottom: calc(var(--spacing-sm) + var(--status-bar-height-mobile, 20px) + 8px); /* 調整移動設備上的底部間距 */
    min-height: 200px; /* 移動設備上的最小高度可以更小 */
    max-width: calc(100% - var(--spacing-sm) * 2); /* 移動設備上的最大寬度 */
    padding-top: var(--spacing-xs); /* 為卡片頂部添加間距 */
  }
  
  .main-content-header {
    padding: var(--spacing-xs) 0 0; /* 為頂部添加間距 */
    margin: 0 var(--spacing-xs); /* 左右添加適當外邊距 */
  }
  
  .breadcrumb-container {
    padding: var(--spacing-xs) var(--spacing-xs); /* 移動版上使用更小的內邊距 */
    margin-bottom: var(--spacing-xs); /* 添加底部外邊距 */
  }
  
  .content-scrollable {
    padding: var(--spacing-xs) var(--spacing-xs); /* 在移動設備上減少內邊距 */
    margin: 0 var(--spacing-xs); /* 保持一致的外邊距 */
  }
}

/* 更新側邊欄樣式，確保它與導航欄無縫銜接 */
.sidebar {
  position: fixed;
  top: var(--navbar-height);
  left: 0;
  bottom: var(--status-bar-height, 24px); /* 確保不遮擋狀態欄 */
  width: var(--sidebar-width);
  height: calc(100vh - var(--navbar-height) - var(--status-bar-height, 24px));
  z-index: 100;
  transition: width var(--transition-normal) ease, transform var(--transition-normal) ease;
  overflow: hidden;
}

/* 更新側邊欄折疊樣式 */
.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
}

/* 移動設備上的側邊欄樣式 */
@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
  }
  
  .sidebar.visible {
    transform: translateX(0);
  }
}

/* 修改路由視圖的包裝方式 */
.router-view-wrapper {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 調整滾動條樣式只針對內容區域 */
.content-scrollable::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.content-scrollable::-webkit-scrollbar-track {
  background-color: transparent;
}

.content-scrollable::-webkit-scrollbar-thumb {
  background-color: var(--border-color);
  border-radius: 3px;
}

.content-scrollable::-webkit-scrollbar-thumb:hover {
  background-color: var(--text-tertiary);
}

/* 底部状态栏样式 */
.status-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  width: 100%; /* 默認全寬 */
  height: var(--status-bar-height, 24px);
  background-color: var(--background-color);
  border-top: none;
  display: flex;
  align-items: center;
  justify-content: flex-end; /* 内容右对齐 */
  padding: 0 var(--spacing-md);
  font-size: 12px;
  color: var(--text-secondary);
  z-index: 50; /* 降低z-index，確保模態對話框覆蓋層能覆蓋狀態欄 */
  transition: all var(--transition-normal) ease;
  box-shadow: 0 -1px 3px rgba(0, 0, 0, 0.05); /* 添加輕微的頂部陰影，使狀態欄更明顯 */
}

/* 認證布局下状态栏样式 */
.auth-layout + .status-bar {
  left: 0 !important;
  width: 100% !important;
  margin-left: 0 !important;
}

.status-bar-content {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.status-bar-section {
  display: flex;
  align-items: center;
  gap: 6px;
  position: relative; /* 为弹窗定位提供参考 */
}

.status-label {
  font-weight: 500;
}

.status-value {
  color: var(--text-primary);
}

.status-value.clickable {
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 3px;
}

.status-value.clickable:hover {
  color: var(--primary-color);
}

.connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.2);
}

.connection-dot.connected {
  background-color: #52c41a; /* 绿色 - 已连接 */
}

.connection-dot.disconnected {
  background-color: #ff4d4f; /* 红色 - 未连接 */
}

/* 添加延迟状态相关的样式 */
.status-value.excellent {
  color: #52c41a; /* 绿色 - 优秀延迟 */
}

.status-value.good {
  color: #1890ff; /* 蓝色 - 良好延迟 */
}

.status-value.fair {
  color: #faad14; /* 黄色 - 一般延迟 */
}

.status-value.poor {
  color: #ff4d4f; /* 红色 - 较差延迟 */
}

.status-value.failed {
  color: #d9d9d9; /* 灰色 - 测量失败 */
}

/* WebSocket详情弹窗样式 */
.ws-details-popup {
  position: absolute;
  bottom: calc(var(--status-bar-height) + 5px);
  right: 0;
  width: 250px;
  background-color: var(--background-color);
  border: none;
  border-radius: var(--border-radius-md);
  box-shadow: var(--box-shadow-md);
  z-index: 1000;
  overflow: hidden;
}

.ws-details-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-color);
}

.ws-details-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
}

.ws-details-close {
  background: none;
  border: none;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  color: var(--text-tertiary);
}

.ws-details-content {
  padding: 10px 12px;
  background-color: var(--card-background);
  border-radius: var(--border-radius-sm);
}

.ws-detail-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 8px;
}

.ws-detail-label {
  min-width: 70px;
  font-weight: 500;
}

.ws-detail-status {
  flex: 1;
}

.ws-details-footer {
  padding: 8px 12px;
  border-top: none;
  display: flex;
  justify-content: flex-end;
  background-color: var(--card-background);
  border-radius: 0 0 var(--border-radius-md) var(--border-radius-md);
}

.ws-reconnect-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.ws-reconnect-button:hover {
  background-color: var(--primary-dark);
}

/* 添加页面过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

/* 侧边栏过渡动画 */
.main-container {
  transition: padding-left 0.3s ease;
}

.sidebar {
  transition: width 0.3s ease, transform 0.3s ease;
}

/* 响应式布局调整 */
@media (max-width: 768px) {
  .status-bar {
    padding: 0 var(--spacing-sm);
    font-size: 10px;
    height: var(--status-bar-height-mobile, 20px);
  }
}

.app.loading {
  cursor: wait;
  pointer-events: none;
  opacity: 0.7;
}

.loading-fallback {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: var(--text-secondary);
}

:root {
  --status-bar-height: 24px;
  --status-bar-height-mobile: 20px;
  --breadcrumb-height: 36px;
}

/* 网络测试区域样式 */
.network-test-section {
  margin-top: 15px;
  padding-top: 10px;
  border-top: 1px solid var(--border-color);
}

.network-test-section h4 {
  font-size: 13px;
  font-weight: 600;
  margin: 0 0 10px 0;
  color: var(--text-primary);
}

.network-test-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  width: 100%;
  margin-bottom: 10px;
}

.network-test-button:hover {
  background-color: var(--primary-dark);
}

.network-test-button:disabled {
  background-color: var(--disabled-color);
  cursor: not-allowed;
}

.network-test-button.cooldown {
  background-color: #8c8c8c;
  position: relative;
  overflow: hidden;
}

.network-test-button.cooldown::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background-color: rgba(255, 255, 255, 0.15);
  animation: cooldown-animation 30s linear forwards;
  z-index: 1;
}

@keyframes cooldown-animation {
  from { width: 100%; }
  to { width: 0%; }
}

.network-test-progress {
  margin: 10px 0;
}

.progress-bar {
  height: 4px;
  background-color: var(--border-color);
  border-radius: 2px;
  overflow: hidden;
}

.progress-inner {
  height: 100%;
  background-color: var(--primary-color);
  border-radius: 2px;
  transition: width 0.1s linear; /* 使用更短的过渡时间，与更新间隔匹配 */
  background-image: linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.15) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 255, 255, 0.15) 50%,
    rgba(255, 255, 255, 0.15) 75%,
    transparent 75%,
    transparent
  );
  background-size: 1rem 1rem;
  animation: progress-bar-stripes 1s linear infinite;
}

@keyframes progress-bar-stripes {
  from { background-position: 1rem 0; }
  to { background-position: 0 0; }
}

.progress-text {
  display: block;
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 5px;
  text-align: center;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 5px;
}

.current-latency {
  font-size: 11px;
  font-weight: 600;
  color: var(--primary-color);
}

.network-test-results {
  margin-top: 10px;
  padding: 8px;
  background-color: var(--background-color);
  border-radius: var(--border-radius-sm);
  border: none;
  box-shadow: var(--box-shadow-sm);
}

.test-result-header {
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 6px;
}

.test-result-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 12px;
}

.test-label {
  color: var(--text-secondary);
}

.test-value {
  font-weight: 600;
}

.test-value.excellent {
  color: #52c41a; /* 绿色 - 优秀延迟 */
}

.test-value.good {
  color: #1890ff; /* 蓝色 - 良好延迟 */
}

.test-value.fair {
  color: #faad14; /* 黄色 - 一般延迟 */
}

.test-value.poor {
  color: #ff4d4f; /* 红色 - 较差延迟 */
}

.test-value.failed {
  color: #d9d9d9; /* 灰色 - 测量失败 */
}

.ws-refresh-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.ws-refresh-button:hover {
  background-color: var(--primary-dark);
}

/* 全局认证加载动画样式 */
.auth-loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(var(--surface-color-rgb), 0.9);
  z-index: 9999; /* 確保這個值比其他模態對話框更高 */
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
}

/* 新的三点加载动画效果 */
.loader {
  width: 45px;
  aspect-ratio: .75;
  --c: no-repeat linear-gradient(var(--primary-color) 0 0);
  background: 
    var(--c) 0%   50%,
    var(--c) 50%  50%,
    var(--c) 100% 50%;
  animation: l7 1s infinite linear alternate;
}

@keyframes l7 {
  0%  {background-size: 20% 50% ,20% 50% ,20% 50% }
  20% {background-size: 20% 20% ,20% 50% ,20% 50% }
  40% {background-size: 20% 100%,20% 20% ,20% 50% }
  60% {background-size: 20% 50% ,20% 100%,20% 20% }
  80% {background-size: 20% 50% ,20% 50% ,20% 100%}
  100%{background-size: 20% 50% ,20% 50% ,20% 50% }
}

/* 隱藏全局滾動條 */
body::-webkit-scrollbar,
#app::-webkit-scrollbar,
.main-content::-webkit-scrollbar,
.sidebar::-webkit-scrollbar,
.sidebar-content::-webkit-scrollbar,
.sidebar-menu::-webkit-scrollbar {
  width: 0;
  background: transparent;
  display: none;
}

body,
#app,
.main-content,
.sidebar,
.sidebar-content,
.sidebar-menu {
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

/* 確保深色模式下也隱藏滾動條 */
:root.dark body::-webkit-scrollbar,
:root.dark #app::-webkit-scrollbar,
:root.dark .main-content::-webkit-scrollbar,
:root.dark .sidebar::-webkit-scrollbar,
:root.dark .sidebar-content::-webkit-scrollbar,
:root.dark .sidebar-menu::-webkit-scrollbar,
:root[data-theme='dark'] body::-webkit-scrollbar,
:root[data-theme='dark'] #app::-webkit-scrollbar,
:root[data-theme='dark'] .main-content::-webkit-scrollbar,
:root[data-theme='dark'] .sidebar::-webkit-scrollbar,
:root[data-theme='dark'] .sidebar-content::-webkit-scrollbar,
:root[data-theme='dark'] .sidebar-menu::-webkit-scrollbar {
  width: 0;
  background: transparent;
  display: none;
}

/* 修改 auth layout 部分的 router-view */
.auth-layout {
  min-height: calc(100vh - var(--status-bar-height, 24px) - 8px); /* 調整高度，增加與狀態欄的間距 */
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: var(--background-color);
  overflow: hidden; /* 防止整體認證佈局滾動 */
  margin-bottom: calc(var(--status-bar-height, 24px) + 8px); /* 增加底部間距 */
}

.auth-content-wrapper {
  max-height: calc(90vh - var(--status-bar-height, 24px) - 16px); /* 調整最大高度，確保不與狀態欄重疊 */
  overflow-y: auto;
  padding: var(--spacing-md);
  -webkit-overflow-scrolling: touch; /* 在iOS上改善滾動體驗 */
}

/* 防止頁面整體滾動的補充樣式 */
.default-layout {
  position: fixed;
  width: 100%;
  height: calc(100% - var(--status-bar-height, 24px)); /* 調整高度，不包含狀態欄 */
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: var(--background-color); /* 使用應用整體背景色，而非卡片背景色 */
}

/* 為組件添加正確的滾動行為 */
.router-view-component {
  height: 100%;
  width: 100%;
  overflow: visible; /* 允許組件內容顯示，但滾動由父容器控制 */
}

/* 新增：確保模態對話框的覆蓋層能覆蓋整個頁面，包括狀態欄 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(var(--surface-color-rgb), 0.8);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
  z-index: 900; /* 比狀態欄的z-index更高 */
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 新增：確保模態對話框本身的z-index比覆蓋層更高 */
.modal-content {
  z-index: 901;
  position: relative;
  background-color: var(--card-background);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-lg);
  max-width: 90%;
  max-height: 90%;
  overflow: hidden;
}

/* 添加小型進度條樣式 */
.progress-container.small {
  display: flex;
  align-items: center;
  flex: 1;
  gap: 8px;
}

.progress-container.small .progress-bar {
  flex: 1;
  height: 6px;
  background-color: var(--border-color);
  border-radius: 3px;
  overflow: hidden;
}

.progress-container.small .progress-inner {
  height: 100%;
  border-radius: 3px;
}

.progress-container.small .progress-value {
  font-size: 12px;
  min-width: 60px;
  text-align: right;
}

.status-text {
  font-size: 10px;
  opacity: 0.8;
}

/* 性能狀態顏色 */
.progress-inner.excellent {
  background-color: #52c41a; /* 绿色 - 优秀性能 */
}

.progress-inner.good {
  background-color: #1890ff; /* 蓝色 - 良好性能 */
}

.progress-inner.fair {
  background-color: #faad14; /* 黄色 - 一般性能 */
}

.progress-inner.poor {
  background-color: #ff4d4f; /* 红色 - 较差性能 */
}

.ws-refresh-button {
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: var(--border-radius-sm);
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
</style>
