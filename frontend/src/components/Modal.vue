<template>
  <Teleport to="body">
    <transition name="modal-fade">
      <div class="modal-backdrop" v-if="show" @click.self="handleBackdropClick">
        <div class="modal-container" :class="{ 'modal-large': size === 'large', 'modal-small': size === 'small' }">
          <div class="modal-header">
            <slot name="header">
              <h3 class="modal-title">{{ title }}</h3>
            </slot>
            <button class="close-button" @click="$emit('close')" aria-label="Close">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
          
          <div class="modal-body">
            <slot name="body"></slot>
          </div>
          
          <div class="modal-footer">
            <slot name="footer">
              <button class="btn btn-secondary" @click="$emit('close')">取消</button>
              <button class="btn btn-primary" @click="$emit('confirm')">確認</button>
            </slot>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup>
import { onMounted, onUnmounted, watch, ref } from 'vue';

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'medium', // 'small', 'medium', 'large'
    validator: (value) => ['small', 'medium', 'large'].includes(value)
  },
  closeOnBackdrop: {
    type: Boolean,
    default: true
  },
  show: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['close', 'confirm']);

// 處理點擊背景
const handleBackdropClick = () => {
  if (props.closeOnBackdrop) {
    emit('close');
  }
};

// 處理ESC鍵關閉模態框
const handleEsc = (e) => {
  if (e.key === 'Escape') {
    emit('close');
  }
};

// 阻止頁面滾動
const preventScroll = () => {
  document.body.style.overflow = 'hidden';
  document.body.style.paddingRight = '15px'; // 防止滾動條消失導致頁面抖動
};

// 恢復頁面滾動
const restoreScroll = () => {
  document.body.style.overflow = '';
  document.body.style.paddingRight = '';
};

// 監聽show屬性變化
watch(() => props.show, (newValue) => {
  if (newValue) {
    preventScroll();
    window.addEventListener('keydown', handleEsc);
  } else {
    restoreScroll();
    window.removeEventListener('keydown', handleEsc);
  }
});

// 組件掛載時
onMounted(() => {
  if (props.show) {
    preventScroll();
    window.addEventListener('keydown', handleEsc);
  }
});

// 組件銷毀時
onUnmounted(() => {
  restoreScroll();
  window.removeEventListener('keydown', handleEsc);
});
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
  padding: var(--spacing-md);
}

.modal-container {
  background-color: var(--surface-color);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-lg);
  max-width: 90%;
  max-height: 90vh;
  width: 500px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-small {
  width: 400px;
}

.modal-large {
  width: 800px;
}

.modal-header {
  padding: var(--spacing-md) var(--spacing-lg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color);
}

.modal-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.close-button {
  background: none;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--transition-fast) ease;
  padding: var(--spacing-xs);
  border-radius: var(--border-radius-sm);
}

.close-button:hover {
  color: var(--text-primary);
  background-color: var(--hover-color);
}

.modal-body {
  padding: var(--spacing-lg);
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  padding: var(--spacing-md) var(--spacing-lg);
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}

/* 過渡動畫 */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-active .modal-container,
.modal-fade-leave-active .modal-container {
  transition: transform 0.2s ease;
}

.modal-fade-enter-from .modal-container,
.modal-fade-leave-to .modal-container {
  transform: translateY(20px);
}
</style> 