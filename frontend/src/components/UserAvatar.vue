<template>
  <div 
    class="user-avatar-component" 
    :class="{ 'clickable': clickable, ['size-' + size]: true }"
    @click="clickable ? $emit('click') : null"
  >
    <img
      v-if="avatarUrl"
      :src="formatAvatarUrl(avatarUrl)"
      :alt="username"
      class="avatar-image"
    />
    <div v-else class="avatar-placeholder">
      <span>{{ userInitial }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

// 全局頭像URL緩存，用於減少重複請求
const globalAvatarCache = new Map();

const props = defineProps({
  username: {
    type: String,
    default: ''
  },
  avatarUrl: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'medium' // small, medium, large
  },
  clickable: {
    type: Boolean,
    default: false
  },
  // 控制是否禁止緩存
  noCache: {
    type: Boolean,
    default: false  // 改為默認啟用緩存
  }
})

defineEmits(['click'])

const userInitial = computed(() => {
  if (!props.username) return '?'
  return props.username.charAt(0).toUpperCase()
})

// 緩存破壞時間戳，每個應用生命週期只需要一個
const globalCacheBreaker = ref(Date.now());

// 格式化頭像URL，確保包含完整的服務器地址，並添加時間戳防止緩存
const formatAvatarUrl = (url: string) => {
  if (!url) return '';
  
  // 生成一個可緩存的關鍵URL（沒有時間戳參數）
  let baseUrl = url;
  
  // 如果已經是完整URL，直接使用
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    // 獲取API基礎URL
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    
    // 如果是相對路徑，添加後端服務器地址
    if (url.startsWith('/')) {
      baseUrl = `${apiBaseUrl}${url}`;
    } else {
      // 其他情況，假設是相對路徑但沒有開頭的斜杠
      baseUrl = `${apiBaseUrl}/${url}`;
    }
  }
  
  // 檢查全局緩存中是否已有此URL
  if (!props.noCache && globalAvatarCache.has(baseUrl)) {
    return globalAvatarCache.get(baseUrl);
  }
  
  // 需要添加時間戳時才添加（僅在noCache=true時）
  let formattedUrl = baseUrl;
  if (props.noCache) {
    const separator = baseUrl.includes('?') ? '&' : '?';
    formattedUrl = `${baseUrl}${separator}_t=${globalCacheBreaker.value}`;
  }
  
  // 保存到緩存中
  if (!props.noCache) {
    globalAvatarCache.set(baseUrl, formattedUrl);
  }
  
  return formattedUrl;
}

// 組件掛載時清理過期的緩存項
onMounted(() => {
  // 防止緩存過大，每10分鐘清理一次
  const CACHE_CLEANUP_INTERVAL = 10 * 60 * 1000; // 10分鐘
  
  const cleanup = () => {
    // 緩存不超過100項
    if (globalAvatarCache.size > 100) {
      console.log('[頭像] 清理過大的頭像緩存', globalAvatarCache.size);
      globalAvatarCache.clear();
    }
  };
  
  // 定期清理過大的緩存
  const interval = setInterval(cleanup, CACHE_CLEANUP_INTERVAL);
  
  // 組件卸載時清除計時器
  return () => clearInterval(interval);
})
</script>

<style scoped>
.user-avatar-component {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 50%;
  position: relative;
  /* 確保組件始終保持正方形比例 */
  aspect-ratio: 1/1;
}

.clickable {
  cursor: pointer;
  transition: all 0.3s ease;
}

.clickable:hover {
  transform: scale(1.05);
  opacity: 0.95;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  /* 移除可能限制GIF動畫的屬性 */
  image-rendering: auto;
  transform: translateZ(0); /* 開啟GPU加速，提升GIF性能 */
}

.avatar-placeholder {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: var(--el-color-primary-light-5);
  color: var(--el-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.user-avatar-component.size-small {
  width: 30px;
  height: 30px;
  min-width: 30px;
  min-height: 30px;
  max-height: 30px;
}

.user-avatar-component.size-small .avatar-placeholder {
  font-size: 14px;
}

.user-avatar-component.size-medium {
  width: 40px;
  height: 40px;
  min-width: 40px;
  min-height: 40px;
  max-height: 40px;
}

.user-avatar-component.size-medium .avatar-placeholder {
  font-size: 18px;
}

.user-avatar-component.size-large {
  width: 56px;
  height: 56px;
  min-width: 56px;
  min-height: 56px;
  max-height: 56px;
}

.user-avatar-component.size-large .avatar-placeholder {
  font-size: 24px;
}
</style> 