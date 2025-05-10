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
import { computed } from 'vue'

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
  }
})

defineEmits(['click'])

const userInitial = computed(() => {
  if (!props.username) return '?'
  return props.username.charAt(0).toUpperCase()
})

// 格式化头像URL，确保包含完整的服务器地址
const formatAvatarUrl = (url: string) => {
  if (!url) return '';
  
  // 如果已经是完整URL，直接返回
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  
  // 获取API基础URL
  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  
  // 如果是相对路径，添加后端服务器地址
  if (url.startsWith('/')) {
    return `${apiBaseUrl}${url}`;
  }
  
  // 其他情况，假设是相对路径但没有开头的斜杠
  return `${apiBaseUrl}/${url}`;
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