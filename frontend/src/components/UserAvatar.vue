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
import { computed, ref } from 'vue'

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
  // 添加新的属性，控制是否禁止缓存
  noCache: {
    type: Boolean,
    default: true
  }
})

defineEmits(['click'])

const userInitial = computed(() => {
  if (!props.username) return '?'
  return props.username.charAt(0).toUpperCase()
})

// 生成一个随机的缓存破坏值
const cacheBreaker = ref(Date.now())

// 格式化头像URL，确保包含完整的服务器地址，并添加时间戳防止缓存
const formatAvatarUrl = (url: string) => {
  if (!url) return '';
  
  // 处理基础URL
  let formattedUrl = url;
  
  // 如果已经是完整URL，直接使用
  if (url.startsWith('http://') || url.startsWith('https://')) {
    formattedUrl = url;
  } else {
    // 获取API基础URL
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    
    // 如果是相对路径，添加后端服务器地址
    if (url.startsWith('/')) {
      formattedUrl = `${apiBaseUrl}${url}`;
    } else {
      // 其他情况，假设是相对路径但没有开头的斜杠
      formattedUrl = `${apiBaseUrl}/${url}`;
    }
  }
  
  // 添加时间戳参数防止缓存 (只在启用 noCache 时)
  if (props.noCache) {
    const separator = formattedUrl.includes('?') ? '&' : '?';
    formattedUrl = `${formattedUrl}${separator}_t=${cacheBreaker.value}`;
  }
  
  return formattedUrl;
}
</script>

<style scoped>
.user-avatar-component {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 50%;
  position: relative;
  /* 确保组件始终保持正方形比例 */
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
  /* 移除可能限制GIF动画的属性 */
  image-rendering: auto;
  transform: translateZ(0); /* 开启GPU加速，提升GIF性能 */
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