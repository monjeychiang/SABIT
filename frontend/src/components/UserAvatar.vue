<template>
  <div 
    class="user-avatar-component" 
    :class="{ 'clickable': clickable }"
    @click="clickable ? $emit('click') : null"
  >
    <img
      v-if="avatarUrl"
      :src="avatarUrl"
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

const sizeClass = computed(() => {
  return `size-${props.size}`
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
}

.user-avatar-component.size-small .avatar-placeholder {
  font-size: 14px;
}

.user-avatar-component.size-medium {
  width: 40px;
  height: 40px;
  min-width: 40px;
}

.user-avatar-component.size-medium .avatar-placeholder {
  font-size: 18px;
}

.user-avatar-component.size-large {
  width: 56px;
  height: 56px;
  min-width: 56px;
}

.user-avatar-component.size-large .avatar-placeholder {
  font-size: 24px;
}
</style> 