<template>
  <section class="strategy-list-container">
    <h2 class="section-title">
      {{ title }} 
      <span class="strategy-count">{{ strategies.length }}</span>
    </h2>
    
    <div v-if="strategies.length === 0" class="empty-state">
      <div class="empty-icon">
        <i class="fas fa-project-diagram"></i>
      </div>
      <div class="empty-text">{{ emptyText }}</div>
    </div>
    
    <div v-else class="strategy-grid">
      <GridStrategyCard
        v-for="strategy in strategies"
        :key="strategy.id"
        :strategy="strategy"
        @click="$emit('view', strategy.id)"
        @start="$emit('start', strategy)"
        @stop="$emit('stop', strategy)"
        @delete="$emit('delete', strategy)"
      />
    </div>
  </section>
</template>

<script setup>
import { defineProps, defineEmits } from 'vue';
import GridStrategyCard from './GridStrategyCard.vue';

defineProps({
  title: {
    type: String,
    required: true
  },
  strategies: {
    type: Array,
    required: true
  },
  emptyText: {
    type: String,
    default: '目前沒有策略'
  }
});

defineEmits(['view', 'start', 'stop', 'delete']);
</script>

<style scoped>
.strategy-list-container {
  margin-bottom: 2rem;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 1rem;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
}

.strategy-count {
  background-color: var(--el-color-info-light-3);
  color: var(--el-color-info-dark-2);
  border-radius: 12px;
  padding: 0.125rem 0.5rem;
  font-size: 0.875rem;
  margin-left: 0.5rem;
}

.strategy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
}

.empty-state {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  border: 1px dashed var(--el-border-color-lighter);
}

.empty-icon {
  font-size: 2.5rem;
  color: var(--el-text-color-placeholder);
  margin-bottom: 1rem;
}

.empty-text {
  color: var(--el-text-color-secondary);
  font-size: 1rem;
}

@media (max-width: 768px) {
  .strategy-grid {
    grid-template-columns: 1fr;
  }
}
</style> 