<template>
  <el-dialog
    v-model="visible"
    title="確認刪除"
    width="400px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
  >
    <div class="confirm-content">
      <div class="warning-icon">
        <i class="fas fa-exclamation-triangle"></i>
      </div>
      <p class="confirm-message">
        確定要刪除「{{ strategy.symbol }}」的網格策略嗎？
      </p>
      <p class="confirm-warning" v-if="hasOrders">
        <i class="fas fa-info-circle"></i>
        此策略已有相關訂單記錄，刪除後將無法恢復。
      </p>
    </div>
    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="danger" :loading="loading" @click="handleConfirm">
          確認刪除
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue';

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  strategy: {
    type: Object,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  hasOrders: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel']);

const visible = ref(props.modelValue);

// 監聽外部 modelValue 的變化
watch(() => props.modelValue, (newVal) => {
  visible.value = newVal;
});

// 監聽內部 visible 的變化，同步到外部
watch(visible, (newVal) => {
  if (newVal !== props.modelValue) {
    emit('update:modelValue', newVal);
  }
});

// 處理確認按鈕點擊事件
const handleConfirm = () => {
  emit('confirm');
};

// 處理取消按鈕點擊事件
const handleCancel = () => {
  emit('cancel');
  visible.value = false;
};
</script>

<style scoped>
.confirm-content {
  text-align: center;
  padding: 1rem 0;
}

.warning-icon {
  font-size: 3rem;
  color: var(--el-color-danger);
  margin-bottom: 1rem;
}

.confirm-message {
  font-size: 1.125rem;
  margin-bottom: 1rem;
  color: var(--el-text-color-primary);
}

.confirm-warning {
  font-size: 0.875rem;
  color: var(--el-color-warning-dark-2);
  background-color: var(--el-color-warning-light-9);
  padding: 0.5rem;
  border-radius: 4px;
  margin-top: 1rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style> 