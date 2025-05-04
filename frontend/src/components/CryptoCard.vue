<template>
  <div class="crypto-card" :class="{ 'negative': isNegative, 'active': isActive }" 
       @mouseenter="hovering = true" 
       @mouseleave="hovering = false"
       @click="toggleActive">
    <div class="card-header">
      <div class="icon-container">
        <div class="icon" :style="{ backgroundColor: iconBgColor }">
          <span>{{ icon }}</span>
        </div>
        <div class="coin-info">
          <h3>{{ name }}</h3>
          <p>{{ symbol }}</p>
        </div>
      </div>
      <div class="change" :class="{ 'positive': !isNegative }">
        <span>{{ isNegative ? '▼' : '▲' }} {{ Math.abs(change) }}%</span>
      </div>
    </div>
    <div class="card-body">
      <h2>${{ formatPrice(price) }}</h2>
      <div class="price-trend">
        <div v-for="(value, index) in trendData" :key="index" 
             class="trend-bar" 
             :style="{ 
               height: `${value}%`, 
               backgroundColor: isNegative ? '#FF5252' : '#4CAF50',
               opacity: hovering ? 1 : 0.7
             }">
        </div>
      </div>
    </div>
    <div v-if="isActive" class="card-details">
      <div class="detail-item">
        <span class="detail-label">24h Vol:</span>
        <span class="detail-value">${{ formatNumber(volume24h) }}M</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Market Cap:</span>
        <span class="detail-value">${{ formatNumber(marketCap) }}B</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">Supply:</span>
        <span class="detail-value">{{ formatNumber(circulatingSupply) }}M</span>
      </div>
      <div class="trend-info">
        <div class="trend-direction" :class="{ 'positive': !isNegative }">
          <span>{{ getTrendDirection() }}</span>
        </div>
        <button class="trade-button" @click.stop="handleTrade">交易</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue';

const props = defineProps({
  icon: {
    type: String,
    default: '$'
  },
  name: {
    type: String,
    required: true
  },
  symbol: {
    type: String,
    required: true
  },
  price: {
    type: Number,
    required: true
  },
  change: {
    type: Number,
    default: 0
  },
  iconBgColor: {
    type: String,
    default: '#FFD700'
  },
  trendData: {
    type: Array,
    default: () => {
      // Initialize with zeros instead of random data
      return new Array(12).fill(0);
    }
  },
  volume24h: {
    type: Number,
    default: 0
  },
  marketCap: {
    type: Number,
    default: 0
  },
  circulatingSupply: {
    type: Number,
    default: 0
  }
});

const hovering = ref(false);
const isActive = ref(false);

const isNegative = computed(() => {
  return props.change < 0;
});

const formatPrice = (value) => {
  if (value >= 1000) {
    return value.toLocaleString('en-US');
  } else if (value >= 1) {
    return value.toFixed(2);
  } else {
    return value.toFixed(4);
  }
};

const formatNumber = (value) => {
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
};

const toggleActive = () => {
  isActive.value = !isActive.value;
};

const getTrendDirection = () => {
  if (props.change > 3) return '強勁上升';
  if (props.change > 0) return '緩慢上升';
  if (props.change > -3) return '緩慢下降';
  return '強勁下降';
};

const handleTrade = () => {
  alert(`正在前往 ${props.name} (${props.symbol}) 交易頁面...`);
};
</script>

<style scoped lang="scss">
.crypto-card {
  background-color: var(--surface-color);
  border-radius: var(--border-radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--box-shadow-md);
  width: 100%;
  transition: all var(--transition-normal) ease;
  position: relative;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid var(--border-color);
  
  &:hover {
    transform: translateY(-4px);
    box-shadow: var(--box-shadow-lg);
    
    &::after {
      opacity: 1;
    }
  }
  
  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: var(--primary-gradient);
    opacity: 0;
    transition: opacity var(--transition-normal) ease;
  }
  
  &.active {
    transform: scale(1.01);
    box-shadow: var(--box-shadow-lg);
    
    &::after {
      opacity: 1;
    }
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--spacing-lg);
    
    .icon-container {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
    }
    
    .icon {
      width: 40px;
      height: 40px;
      border-radius: var(--border-radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: var(--font-size-lg);
      color: var(--text-light);
      box-shadow: var(--box-shadow-sm);
      transition: all var(--transition-fast) ease;
    }
    
    .coin-info {
      h3 {
        margin: 0;
        font-size: var(--font-size-md);
        font-weight: 600;
        color: var(--text-primary);
      }
      
      p {
        margin: var(--spacing-xs) 0 0;
        color: var(--text-secondary);
        font-size: var(--font-size-sm);
      }
    }
    
    .change {
      font-size: var(--font-size-sm);
      font-weight: 600;
      padding: var(--spacing-xs) var(--spacing-sm);
      border-radius: var(--border-radius-full);
      background-color: rgba(16, 185, 129, 0.1);
      color: var(--success-color);
      transition: all var(--transition-fast) ease;
      
      &.negative {
        background-color: rgba(239, 68, 68, 0.1);
        color: var(--danger-color);
      }
    }
  }
  
  .card-body {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    
    h2 {
      font-size: var(--font-size-xl);
      font-weight: 700;
      margin: 0;
      flex: 1;
      color: var(--text-primary);
    }
    
    .price-trend {
      display: flex;
      align-items: flex-end;
      gap: 2px;
      height: 40px;
      margin-left: var(--spacing-md);
      
      .trend-bar {
        flex: 1;
        min-width: 3px;
        border-radius: 2px;
        transition: all var(--transition-fast) ease;
      }
    }
  }
  
  .card-details {
    margin-top: var(--spacing-lg);
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--border-color);
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--spacing-md);
    
    .detail-item {
      display: flex;
      flex-direction: column;
      gap: var(--spacing-xs);
      
      .detail-label {
        font-size: var(--font-size-xs);
        color: var(--text-tertiary);
      }
      
      .detail-value {
        font-size: var(--font-size-sm);
        font-weight: 500;
        color: var(--text-primary);
      }
    }
    
    .trend-info {
      grid-column: 1 / -1;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: var(--spacing-sm);
      
      .trend-direction {
        font-size: var(--font-size-sm);
        font-weight: 500;
        color: var(--success-color);
        
        &.negative {
          color: var(--danger-color);
        }
      }
      
      .trade-button {
        background-color: var(--primary-color);
        color: var(--text-light);
        border: none;
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: var(--border-radius-md);
        font-size: var(--font-size-sm);
        font-weight: 500;
        cursor: pointer;
        transition: all var(--transition-fast) ease;
        
        &:hover {
          background-color: var(--primary-dark);
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .crypto-card {
    padding: var(--spacing-md);
    
    .card-header {
      margin-bottom: var(--spacing-md);
      
      .icon {
        width: 36px;
        height: 36px;
        font-size: var(--font-size-md);
      }
      
      .coin-info h3 {
        font-size: var(--font-size-sm);
      }
      
      .coin-info p {
        font-size: var(--font-size-xs);
      }
    }
    
    .card-body h2 {
      font-size: var(--font-size-lg);
    }
    
    .card-details {
      grid-template-columns: repeat(2, 1fr);
      gap: var(--spacing-sm);
      
      .trend-info {
        grid-column: 1 / -1;
      }
    }
  }
}
</style> 