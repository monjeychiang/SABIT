<template>
  <div class="user-profile-container">
    <div class="profile-header">
      <h2>用户资料</h2>
      <div class="cache-info">
        <span>缓存状态: {{ cacheStatus }}</span>
        <n-button size="small" type="primary" @click="refreshUserData">
          刷新数据
        </n-button>
      </div>
    </div>
    
    <n-card v-if="user" class="profile-card">
      <template #header>
        <div class="user-header">
          <div class="avatar">
            <img v-if="user.avatar_url" :src="user.avatar_url" alt="用户头像" />
            <n-avatar v-else :size="64">{{ user.username.charAt(0).toUpperCase() }}</n-avatar>
          </div>
          <div class="user-info">
            <h3>{{ user.username }}</h3>
            <p v-if="user.email">{{ user.email }}</p>
            <n-tag v-if="user.is_admin" type="success">管理员</n-tag>
            <n-tag v-else type="info">用户</n-tag>
          </div>
        </div>
      </template>
      
      <n-descriptions bordered>
        <n-descriptions-item label="ID">{{ user.id }}</n-descriptions-item>
        <n-descriptions-item label="账号状态">
          {{ user.is_active ? '正常' : '已禁用' }}
        </n-descriptions-item>
        <n-descriptions-item label="账号验证">
          {{ user.is_verified ? '已验证' : '未验证' }}
        </n-descriptions-item>
        <n-descriptions-item label="注册时间">
          {{ formatDate(user.created_at) }}
        </n-descriptions-item>
        <n-descriptions-item v-if="user.phone" label="电话">
          {{ user.phone }}
        </n-descriptions-item>
        <n-descriptions-item v-if="user.referral_code" label="推荐码">
          {{ user.referral_code }}
        </n-descriptions-item>
      </n-descriptions>
      
      <template v-if="user.bio">
        <div class="bio-section">
          <h4>个人简介</h4>
          <p>{{ user.bio }}</p>
        </div>
      </template>
    </n-card>
    
    <div v-else-if="loading" class="loading-container">
      <n-spin size="large" />
      <p>加载用户资料中...</p>
    </div>
    
    <n-alert v-else-if="error" type="error" :title="error" />
    
    <div class="cache-settings">
      <h3>缓存设置</h3>
      <div class="setting-row">
        <span>缓存时间:</span>
        <n-slider v-model:value="cacheTime" :min="5" :max="300" :step="5" style="width: 300px" />
        <span>{{ cacheTime }}秒</span>
        <n-button size="small" @click="updateCacheTime(cacheTime)">应用</n-button>
      </div>
    </div>
    
    <div class="debug-section">
      <h3>调试信息</h3>
      <pre>{{ debugInfo }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { format } from 'date-fns'

// 获取Auth Store
const authStore = useAuthStore()

// 用户数据
const user = computed(() => authStore.user)
const loading = computed(() => authStore.loading)
const error = computed(() => authStore.error)

// 缓存相关状态
const lastFetchTime = ref(0)
const fetchCount = ref(0)
const debugInfo = ref({})
const cacheTime = ref(60) // 缓存时间，默认60秒

// 计算缓存状态
const cacheStatus = computed(() => {
  if (!lastFetchTime.value) return '未加载'
  
  const now = Date.now()
  const cacheAge = now - lastFetchTime.value
  
  if (cacheAge < 1000) return '刚刚刷新'
  if (cacheAge < 60000) return `已缓存 ${Math.floor(cacheAge / 1000)} 秒`
  return `已缓存 ${Math.floor(cacheAge / 60000)} 分钟 ${Math.floor((cacheAge % 60000) / 1000)} 秒`
})

// 加载用户数据
const loadUserData = async (forceRefresh = false) => {
  try {
    const startTime = Date.now()
    fetchCount.value++
    
    // 获取用户数据
    await authStore.getUserProfile(forceRefresh)
    
    // 记录获取时间
    lastFetchTime.value = Date.now()
    
    // 更新调试信息
    updateDebugInfo({
      fetchTime: new Date().toLocaleTimeString(),
      fetchDuration: `${Date.now() - startTime}ms`,
      fetchCount: fetchCount.value,
      forceRefresh: forceRefresh,
      dataFromCache: !forceRefresh
    })
  } catch (error) {
    console.error('加载用户数据失败:', error)
  }
}

// 刷新用户数据
const refreshUserData = () => {
  loadUserData(true)
}

// 格式化日期
const formatDate = (dateString) => {
  try {
    return format(new Date(dateString), 'yyyy-MM-dd HH:mm:ss')
  } catch (error) {
    return dateString
  }
}

// 更新调试信息
const updateDebugInfo = (info) => {
  debugInfo.value = {
    ...debugInfo.value,
    ...info,
    lastUpdate: new Date().toLocaleTimeString()
  }
}

// 更新缓存时间
const updateCacheTime = (seconds) => {
  cacheTime.value = seconds
  authStore.userCacheDuration = seconds * 1000
  
  updateDebugInfo({
    cacheTimeUpdated: true,
    newCacheTime: `${seconds}秒`,
    updatedAt: new Date().toLocaleTimeString()
  })
}

// 组件挂载时加载用户数据
onMounted(() => {
  loadUserData()
  
  // 设置定时器，每15秒使用缓存检查一次用户数据
  const interval = setInterval(() => {
    loadUserData(false)
  }, 15000)
  
  // 组件卸载时清除定时器
  onUnmounted(() => {
    clearInterval(interval)
  })
})
</script>

<style scoped>
.user-profile-container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.cache-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.profile-card {
  margin-bottom: 20px;
}

.user-header {
  display: flex;
  align-items: center;
  gap: 20px;
}

.avatar img {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  object-fit: cover;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.user-info h3 {
  margin: 0;
}

.user-info p {
  margin: 0;
  color: #666;
}

.bio-section {
  margin-top: 20px;
}

.bio-section h4 {
  margin-bottom: 10px;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 50px 0;
}

.debug-section {
  margin-top: 30px;
  padding: 15px;
  border: 1px dashed #ccc;
  border-radius: 4px;
  background-color: #f9f9f9;
}

.debug-section h3 {
  margin-top: 0;
  margin-bottom: 10px;
  font-size: 16px;
  color: #666;
}

.debug-section pre {
  margin: 0;
  white-space: pre-wrap;
  font-size: 12px;
}

.cache-settings {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #eee;
  border-radius: 4px;
}

.cache-settings h3 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 16px;
}

.setting-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style> 