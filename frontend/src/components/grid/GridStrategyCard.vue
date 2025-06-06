<template>
  <div 
    class="strategy-card"
    :class="{ 
      'running': strategy.status === 'RUNNING',
      'stopped': strategy.status === 'STOPPED' || strategy.status === 'CREATED',
      'failed': strategy.status === 'FAILED'
    }"
    @click="$emit('click', strategy.id)"
  >
    <div class="card-header">
      <div class="symbol">{{ strategy.symbol }}</div>
      <div class="strategy-type">
        {{ strategyTypeText }} / {{ gridTypeText }}
      </div>
    </div>

    <div class="card-body">
      <div class="price-range">
        <div class="range-label">價格範圍</div>
        <div class="range-value">{{ strategy.lower_price }} - {{ strategy.upper_price }} USDT</div>
      </div>
      
      <div class="grid-info">
        <div class="grid-item">
          <div class="item-label">網格數</div>
          <div class="item-value">{{ strategy.grid_number }}</div>
        </div>
        <div class="grid-item">
          <div class="item-label">槓桿</div>
          <div class="item-value">{{ strategy.leverage }}x</div>
        </div>
        <div class="grid-item">
          <div class="item-label">投資額</div>
          <div class="item-value">{{ strategy.total_investment }} USDT</div>
        </div>
      </div>

      <div class="profit-section">
        <div class="profit-item" v-if="strategy.current_price">
          <div class="profit-label">當前價格</div>
          <div class="profit-value">{{ formatPrice(strategy.current_price) }}</div>
        </div>
        <div class="profit-item">
          <div class="profit-label">總收益</div>
          <div class="profit-value" :class="profitClass(totalPnl)">
            {{ formatProfit(totalPnl) }}
            <span v-if="pnlPercent !== null">
              ({{ pnlPercent }}%)
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="card-footer">
      <div class="strategy-status">
        <span class="status-dot"></span>
        <span>{{ statusText }}</span>
      </div>
      <div class="strategy-actions">
        <button 
          v-if="strategy.status === 'RUNNING'"
          class="stop-btn" 
          @click.stop="$emit('stop', strategy)"
          title="停止策略"
        >
          <i class="fas fa-stop"></i>
        </button>
        <button 
          v-if="strategy.status === 'CREATED' || strategy.status === 'STOPPED'"
          class="start-btn" 
          @click.stop="$emit('start', strategy)"
          title="啟動策略"
        >
          <i class="fas fa-play"></i>
        </button>
        <button 
          v-if="strategy.status !== 'RUNNING'"
          class="delete-btn" 
          @click.stop="$emit('delete', strategy)"
          title="刪除策略"
        >
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  strategy: {
    type: Object,
    required: true
  }
});

defineEmits(['click', 'start', 'stop', 'delete']);

// 計算屬性
const gridTypeText = computed(() => {
  switch (props.strategy.grid_type) {
    case 'ARITHMETIC':
      return '等差';
    case 'GEOMETRIC':
      return '等比';
    default:
      return props.strategy.grid_type;
  }
});

const strategyTypeText = computed(() => {
  switch (props.strategy.strategy_type) {
    case 'LONG':
      return '做多';
    case 'SHORT':
      return '做空';
    case 'NEUTRAL':
      return '中性';
    default:
      return props.strategy.strategy_type;
  }
});

const statusText = computed(() => {
  switch (props.strategy.status) {
    case 'RUNNING':
      return '運行中';
    case 'STOPPED':
      return '已停止';
    case 'CREATED':
      return '未啟動';
    case 'COMPLETED':
      return '已完成';
    case 'FAILED':
      return '失敗';
    default:
      return props.strategy.status;
  }
});

const totalPnl = computed(() => {
  const realized = props.strategy.realized_pnl || 0;
  const unrealized = props.strategy.unrealized_pnl || 0;
  return realized + unrealized;
});

const pnlPercent = computed(() => {
  if (!props.strategy.total_investment) return null;
  
  const percentage = (totalPnl.value / props.strategy.total_investment) * 100;
  return percentage.toFixed(2);
});

// 輔助函數
function formatPrice(price) {
  return price ? price.toFixed(2) : '-';
}

function formatProfit(profit) {
  return profit > 0 
    ? `+${profit.toFixed(4)} USDT` 
    : `${profit.toFixed(4)} USDT`;
}

function profitClass(profit) {
  return profit > 0 ? 'profit-positive' : profit < 0 ? 'profit-negative' : '';
}
</script>

<style scoped>
.strategy-card {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
}

.strategy-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--el-box-shadow);
}

.card-header {
  padding: 1rem;
  border-bottom: 1px solid var(--el-border-color-light);
  background-color: var(--el-bg-color-secondary);
}

.card-header .symbol {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.card-header .strategy-type {
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
  margin-top: 0.25rem;
}

.card-body {
  padding: 1rem;
  flex: 1;
}

.price-range {
  margin-bottom: 1rem;
}

.range-label {
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.25rem;
}

.range-value {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.grid-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.grid-item {
  text-align: center;
  flex: 1;
}

.item-label {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.25rem;
}

.item-value {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.profit-section {
  display: flex;
  justify-content: space-between;
  padding-top: 1rem;
  border-top: 1px solid var(--el-border-color-light);
}

.profit-item {
  flex: 1;
}

.profit-label {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.25rem;
}

.profit-value {
  font-weight: 600;
  font-size: 1rem;
  color: var(--el-text-color-primary);
}

.profit-positive {
  color: var(--el-color-success);
}

.profit-negative {
  color: var(--el-color-danger);
}

.card-footer {
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid var(--el-border-color-light);
  background-color: var(--el-bg-color-secondary);
}

.strategy-status {
  display: flex;
  align-items: center;
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 0.5rem;
}

.running .status-dot {
  background-color: var(--el-color-success);
}

.stopped .status-dot {
  background-color: var(--el-color-info);
}

.failed .status-dot {
  background-color: var(--el-color-danger);
}

.strategy-actions {
  display: flex;
  gap: 0.5rem;
}

.strategy-actions button {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
}

.start-btn {
  background-color: var(--el-color-success);
  color: white;
}

.stop-btn {
  background-color: var(--el-color-warning);
  color: white;
}

.delete-btn {
  background-color: var(--el-color-danger);
  color: white;
}
</style> 