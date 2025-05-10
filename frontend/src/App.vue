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

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const themeStore = useThemeStore();
const chatroomStore = useChatroomStore();
const notificationStore = useNotificationStore();
const onlineStatusStore = useOnlineStatusStore();
const isSidebarCollapsed = ref(false);
const notifications = ref();
// 新增：移动设备检测
const isMobile = ref(window.innerWidth < 768);
// 新增：侧边栏可见状态（仅用于移动设备）
const isSidebarVisible = ref(false);

// 新增：服务器时间和WebSocket状态
const serverTime = ref(new Date());
const wsStatus = ref({
  chat: false,
  notification: false,
  online: false
});
const wsStatusText = computed(() => {
  if (wsStatus.value.chat && wsStatus.value.notification && wsStatus.value.online) {
    return '全部连接';
  } else if (wsStatus.value.chat || wsStatus.value.notification || wsStatus.value.online) {
    return '部分连接';
  } else {
    return '未连接';
  }
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
  console.log('计算username属性，当前用户:', authStore.user?.username || '游客');
  return authStore.user?.username || '游客';
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
    return { paddingLeft: `var(--content-padding)` };
  }
  
  // 根据侧边栏状态调整内容区域
  return {
    paddingLeft: isSidebarCollapsed.value 
      ? `calc(var(--sidebar-collapsed-width) + var(--content-padding))` 
      : `calc(var(--sidebar-width) + var(--content-padding))`
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
    console.log('处理登出：正在使用authService.logout()');
    // 使用authService.logout()，它会处理WebSocket关闭和状态重置
    await authService.logout();
    
    // 触发登出事件
    window.dispatchEvent(new Event('logout-event'));
    
    // 更新WebSocket状态显示
    wsStatus.value.chat = false;
    wsStatus.value.notification = false;
    wsStatus.value.online = false;
    
    // 跳转到首页而不是刷新页面
    router.push('/');
  } catch (error) {
    console.error('登出处理失败:', error);
    // 即使失败也尝试重定向
    router.push('/');
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
    wsStatus.value.chat = chatroomStore.isConnected;
    wsStatus.value.notification = notificationStore.isWebSocketConnected;
    wsStatus.value.online = onlineStatusStore.isConnected;
  } else {
    wsStatus.value.chat = false;
    wsStatus.value.notification = false;
    wsStatus.value.online = false;
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
    // 使用WebSocketManager重连所有WebSocket连接
    import('@/services/webSocketService').then(({ default: webSocketManager }) => {
      webSocketManager.connectAll().then(result => {
        console.log('WebSocket重连结果:', result ? '成功' : '失败');
        // 短暂延迟后关闭弹窗
        setTimeout(() => {
          showWsDetails.value = false;
        }, 500);
      }).catch(error => {
        console.error('WebSocket重连失败:', error);
      });
    }).catch(error => {
      console.error('导入WebSocketManager失败:', error);
      
      // 如果导入失败，回退到旧方法
      if (!wsStatus.value.chat) {
        chatroomStore.connectWebSocket();
      }
      if (!wsStatus.value.notification) {
        notificationStore.connectWebSocket();
      }
      if (!wsStatus.value.online) {
        onlineStatusStore.connectWebSocket();
      }
      
      // 短暂延迟后关闭弹窗
      setTimeout(() => {
        showWsDetails.value = false;
      }, 500);
    });
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

  // 添加WebSocket连接状态监听器
  window.addEventListener('chat:websocket-connected', () => {
    wsStatus.value.chat = true;
    console.log('聊天WebSocket已连接 - 状态已更新');
  });
  
  window.addEventListener('chat:websocket-disconnected', () => {
    wsStatus.value.chat = false;
    console.log('聊天WebSocket已断开 - 状态已更新');
  });
  
  window.addEventListener('notification:websocket-connected', () => {
    wsStatus.value.notification = true;
    console.log('通知WebSocket已连接 - 状态已更新');
  });
  
  window.addEventListener('notification:websocket-disconnected', () => {
    wsStatus.value.notification = false;
    console.log('通知WebSocket已断开 - 状态已更新');
  });
  
  window.addEventListener('online:websocket-connected', () => {
    wsStatus.value.online = true;
    console.log('在线状态WebSocket已连接 - 状态已更新');
  });
  
  window.addEventListener('online:websocket-disconnected', () => {
    wsStatus.value.online = false;
    console.log('在线状态WebSocket已断开 - 状态已更新');
  });

  // 添加统一的登录成功事件处理器
  window.addEventListener('login-authenticated', async () => {
    console.log('检测到登录成功事件，初始化聊天和通知系统');
    // 初始化通知系统
    notificationStore.initialize();
    // 初始化聊天系统
    chatroomStore.initialize();
    // 初始化在线状态系统
    onlineStatusStore.initialize();
    
    // 确保WebSocket连接被建立 - 添加这一行解决Google登录不初始化WebSocket的问题
    import('@/services/authService').then(async ({ authService }) => {
      console.log('从login-authenticated事件中初始化WebSocket连接');
      await authService.initializeWebSockets();
    });
  });

  // 尝试处理URL中的令牌参数
  const tokenHandled = await handleAuthTokensFromUrl();
  
  // 只有在没有处理令牌参数时才初始化认证
  if (!tokenHandled) {
    try {
      await authStore.initAuth();
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

  // 检查是否需要更新冷却倒计时
  if (lastTestTime.value > 0) {
    updateCooldown();
  }
});

// 在组件卸载时清除定时器
onUnmounted(() => {
  if (timeInterval !== undefined) {
    clearInterval(timeInterval);
  }
  latencyService.stopAutoMeasurement();
  
  // 清除冷却计时器
  if (cooldownTimer.value !== null) {
    clearInterval(cooldownTimer.value);
    cooldownTimer.value = null;
  }

  // 移除事件监听器
  window.removeEventListener('resize', handleResize);
  window.removeEventListener('auth:tokens-updated', () => {});
  
  // 移除加载动画事件监听器
  window.removeEventListener('auth-loading-start', () => {});
  window.removeEventListener('auth-loading-end', () => {});
  
  // 移除WebSocket连接状态监听器
  window.removeEventListener('chat:websocket-connected', () => {});
  window.removeEventListener('chat:websocket-disconnected', () => {});
  window.removeEventListener('notification:websocket-connected', () => {});
  window.removeEventListener('notification:websocket-disconnected', () => {});
  window.removeEventListener('online:websocket-connected', () => {});
  window.removeEventListener('online:websocket-disconnected', () => {});
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
        
        <div class="app-content">
          <Sidebar 
            :is-collapsed="isSidebarCollapsed" 
            :is-mobile="isMobile"
            :is-visible="isSidebarVisible"
            @close-mobile-sidebar="isSidebarVisible = false"
          />
          
          <main class="main-content" :style="mainContentStyle" @click="closeMenuOnContentClick">
            <!-- 添加面包屑导航 -->
            <Breadcrumb />
            
            <router-view v-slot="{ Component, route }">
              <transition name="fade" mode="out-in">
                <component 
                  :is="Component"
                  :key="route.meta.reload ? route.fullPath : route.path"
                />
              </transition>
            </router-view>
          </main>
        </div>
        
        <!-- 确保底部状态栏在侧边栏之外 -->
        <div class="status-bar" :class="{'sidebar-collapsed': isSidebarCollapsed && !isMobile}">
          <div class="status-bar-content">
            <div class="status-bar-section">
              <span class="connection-dot" :class="{ 
                'connected': wsStatus.chat && wsStatus.notification && wsStatus.online, 
                'partial': (wsStatus.chat || wsStatus.notification || wsStatus.online) && !(wsStatus.chat && wsStatus.notification && wsStatus.online),
                'disconnected': !wsStatus.chat && !wsStatus.notification && !wsStatus.online 
              }"></span>
              <span class="status-value clickable" 
                    :class="latencyStatus"
                    @click="showWsDetails = !showWsDetails">{{ serverLatency }}</span>
              
              <!-- WebSocket详情弹窗 -->
              <div v-if="showWsDetails" class="ws-details-popup">
                <div class="ws-details-header">
                  <h3>系统状态</h3>
                  <button class="ws-details-close" @click="showWsDetails = false">×</button>
                </div>
                <div class="ws-details-content">
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">服务器延迟:</span>
                    <span class="ws-detail-status" :class="latencyStatus">{{ serverLatency }}</span>
                  </div>
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">聊天系统:</span>
                    <span class="connection-dot" :class="{ 'connected': wsStatus.chat, 'disconnected': !wsStatus.chat }"></span>
                    <span class="ws-detail-status">{{ wsStatus.chat ? '已连接' : '未连接' }}</span>
                  </div>
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">通知系统:</span>
                    <span class="connection-dot" :class="{ 'connected': wsStatus.notification, 'disconnected': !wsStatus.notification }"></span>
                    <span class="ws-detail-status">{{ wsStatus.notification ? '已连接' : '未连接' }}</span>
                  </div>
                  <div class="ws-detail-item">
                    <span class="ws-detail-label">在线状态:</span>
                    <span class="connection-dot" :class="{ 'connected': wsStatus.online, 'disconnected': !wsStatus.online }"></span>
                    <span class="ws-detail-status">{{ wsStatus.online ? '已连接' : '未连接' }}</span>
                  </div>
                  
                  <!-- 网络测试区域 -->
                  <div class="network-test-section">
                    <h4>网络测试</h4>
                    
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
                        <span class="progress-text">正在测量平均延迟... {{ Math.round(networkTestProgress) }}%</span>
                        <span class="current-latency">当前延迟: {{ currentLatency }}</span>
                      </div>
                    </div>
                    
                    <!-- 测试结果 -->
                    <div v-if="networkTestResults" class="network-test-results">
                      <div class="test-result-header">测试结果：</div>
                      <div class="test-result-item">
                        <span class="test-label">平均延迟:</span>
                        <span class="test-value" :class="networkTestResults.status">
                          {{ networkTestResults.average }}
                        </span>
                      </div>
                      <div class="test-result-item">
                        <span class="test-label">测试时间:</span>
                        <span class="test-value">{{ formatTestTime(networkTestResults.timestamp) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="ws-details-footer">
                  <button class="ws-refresh-button" @click="latencyService.measure(); reconnectWebSockets();">刷新状态</button>
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
        <router-view v-slot="{ Component, route }">
          <component 
            :is="Component"
            :key="route.fullPath"
          />
        </router-view>
      </div>
      
      <!-- 认证布局也显示底部状态栏 -->
      <div class="status-bar">
        <div class="status-bar-content">
          <div class="status-bar-section">
            <span class="connection-dot" :class="{ 
              'connected': wsStatus.chat && wsStatus.notification && wsStatus.online, 
              'partial': (wsStatus.chat || wsStatus.notification || wsStatus.online) && !(wsStatus.chat && wsStatus.notification && wsStatus.online),
              'disconnected': !wsStatus.chat && !wsStatus.notification && !wsStatus.online 
            }"></span>
            <span class="status-value clickable" 
                  :class="latencyStatus"
                  @click="showWsDetails = !showWsDetails">{{ serverLatency }}</span>
            
            <!-- WebSocket详情弹窗 -->
            <div v-if="showWsDetails" class="ws-details-popup">
              <div class="ws-details-header">
                <h3>系统状态</h3>
                <button class="ws-details-close" @click="showWsDetails = false">×</button>
              </div>
              <div class="ws-details-content">
                <div class="ws-detail-item">
                  <span class="ws-detail-label">服务器延迟:</span>
                  <span class="ws-detail-status" :class="latencyStatus">{{ serverLatency }}</span>
                </div>
                <div class="ws-detail-item">
                  <span class="ws-detail-label">聊天系统:</span>
                  <span class="connection-dot" :class="{ 'connected': wsStatus.chat, 'disconnected': !wsStatus.chat }"></span>
                  <span class="ws-detail-status">{{ wsStatus.chat ? '已连接' : '未连接' }}</span>
                </div>
                <div class="ws-detail-item">
                  <span class="ws-detail-label">通知系统:</span>
                  <span class="connection-dot" :class="{ 'connected': wsStatus.notification, 'disconnected': !wsStatus.notification }"></span>
                  <span class="ws-detail-status">{{ wsStatus.notification ? '已连接' : '未连接' }}</span>
                </div>
                <div class="ws-detail-item">
                  <span class="ws-detail-label">在线状态:</span>
                  <span class="connection-dot" :class="{ 'connected': wsStatus.online, 'disconnected': !wsStatus.online }"></span>
                  <span class="ws-detail-status">{{ wsStatus.online ? '已连接' : '未连接' }}</span>
                </div>
                
                <!-- 网络测试区域 -->
                <div class="network-test-section">
                  <h4>网络测试</h4>
                  
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
                      <span class="progress-text">正在测量平均延迟... {{ Math.round(networkTestProgress) }}%</span>
                      <span class="current-latency">当前延迟: {{ currentLatency }}</span>
                    </div>
                  </div>
                  
                  <!-- 测试结果 -->
                  <div v-if="networkTestResults" class="network-test-results">
                    <div class="test-result-header">测试结果：</div>
                    <div class="test-result-item">
                      <span class="test-label">平均延迟:</span>
                      <span class="test-value" :class="networkTestResults.status">
                        {{ networkTestResults.average }}
                      </span>
                    </div>
                    <div class="test-result-item">
                      <span class="test-label">测试时间:</span>
                      <span class="test-value">{{ formatTestTime(networkTestResults.timestamp) }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="ws-details-footer">
                <button class="ws-refresh-button" @click="latencyService.measure(); reconnectWebSockets();">刷新状态</button>
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
  transition: background-color var(--transition-normal) ease, color var(--transition-normal) ease;
  /* 添加padding-bottom为状态栏的高度，防止内容被状态栏遮挡 */
  padding-bottom: var(--status-bar-height, 24px);
  position: relative;
}

.app-content {
  display: flex;
  min-height: 100vh;
  padding-top: var(--navbar-height);
  transition: all var(--transition-normal) ease;
}

.main-content {
  flex: 1;
  padding: var(--content-padding);
  padding-top: calc(var(--spacing-md) * 0.5);
  transition: padding-left var(--transition-normal) ease;
  min-height: calc(100vh - var(--navbar-height) - var(--status-bar-height, 24px));
  background-color: var(--background-color);
  position: relative;
}

/* 授權頁面佈局 */
.auth-layout {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: var(--background-color);
  padding-bottom: var(--status-bar-height, 24px);
}

/* 底部状态栏样式 */
.status-bar {
  position: fixed;
  bottom: 0;
  left: var(--sidebar-width);
  right: 0;
  width: calc(100% - var(--sidebar-width));
  height: var(--status-bar-height, 24px);
  background-color: var(--surface-color);
  border-top: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: flex-end; /* 内容右对齐 */
  padding: 0 var(--spacing-md);
  font-size: 12px;
  color: var(--text-secondary);
  z-index: 999;
  transition: left var(--transition-normal) ease, width var(--transition-normal) ease;
}

/* 侧边栏折叠时状态栏位置变化 */
.status-bar.sidebar-collapsed {
  left: var(--sidebar-collapsed-width);
  width: calc(100% - var(--sidebar-collapsed-width));
}

/* 认证布局下状态栏占据全宽 */
.auth-layout + .status-bar {
  left: 0;
  width: 100%;
}

/* 移动设备上状态栏占据全宽 */
@media (max-width: 768px) {
  .status-bar {
    left: 0;
    width: 100%;
  }
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
}

.connection-dot.connected {
  background-color: #52c41a; /* 绿色 - 已连接 */
}

.connection-dot.partial {
  background-color: #faad14; /* 黄色 - 部分连接 */
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
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
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
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
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
  .app-content {
    padding-top: calc(var(--navbar-height) + 1px);
  }
  
  .main-content {
    padding: var(--spacing-md);
  }
  
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

.breadcrumb-container {
  margin-bottom: var(--spacing-md);
  position: relative;
  top: -8px;
  background-color: transparent;
}

:root {
  --status-bar-height: 24px;
  --status-bar-height-mobile: 20px;
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
  border: 1px solid var(--border-color);
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
  z-index: 9999;
  backdrop-filter: blur(5px);
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
</style>
