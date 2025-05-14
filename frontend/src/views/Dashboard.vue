<template>
  <div class="dashboard container">
    <div class="dashboard-header">
      <h1>交易控制面板</h1>
    </div>

    <!-- 資產總覽部分 -->
    <div class="asset-overview">
      <div class="overview-card card">
        <h3>總資產估值</h3>
        <p class="overview-number">${{ totalAssetValue.toFixed(2) }}</p>
        <p class="change-percentage" :class="{ 'positive': assetChangePercentage > 0, 'negative': assetChangePercentage < 0 }">
          {{ assetChangePercentage > 0 ? '+' : '' }}{{ assetChangePercentage.toFixed(2) }}%
        </p>
      </div>
      <div class="overview-card card">
        <h3>可用余額</h3>
        <p class="overview-number">${{ availableBalance.toFixed(2) }}</p>
        <div class="balance-distribution">
          <div class="balance-item">
            <span>USDT</span>
            <span>${{ usdtBalance.toFixed(2) }}</span>
          </div>
          <div class="balance-item">
            <span>BTC</span>
            <span>{{ btcBalance.toFixed(8) }}</span>
          </div>
        </div>
      </div>
      <div class="overview-card card">
        <h3>持倉市值</h3>
        <p class="overview-number">${{ positionValue.toFixed(2) }}</p>
        <div class="position-distribution">
          <div v-for="position in topPositions" :key="position.symbol" class="position-item">
            <span>{{ position.symbol }}</span>
            <span>${{ position.value.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 市場概況部分 -->
    <div class="market-overview">
      <div class="section-header">
        <h2>市場概況</h2>
        <div class="time-selector">
          <button 
            v-for="period in ['24h', '7d', '30d']" 
            :key="period"
            :class="{ active: selectedPeriod === period }"
            @click="selectedPeriod = period"
            class="time-button">
            {{ period }}
          </button>
        </div>
      </div>
      <div class="market-grid">
        <div v-for="market in topMarkets" :key="market.symbol" class="market-card card">
          <div class="market-header">
            <h4>{{ market.symbol }}</h4>
            <span class="price">${{ market.price.toFixed(2) }}</span>
          </div>
          <div class="price-chart">
            <line-chart
              :chart-data="market.chartData"
              :options="chartOptions"
              height="60"
            />
          </div>
          <div class="market-footer">
            <span class="change-percentage" :class="{ 'positive': market.change > 0, 'negative': market.change < 0 }">
              {{ market.change > 0 ? '+' : '' }}{{ market.change.toFixed(2) }}%
            </span>
            <span class="volume">成交量: ${{ formatVolume(market.volume) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 資產變化圖表 -->
    <div class="asset-chart card">
      <div class="section-header">
        <h2>資產變化</h2>
        <div class="chart-controls">
          <div class="time-selector">
            <button 
              v-for="period in ['1W', '1M', '3M', 'ALL']" 
              :key="period"
              :class="{ active: selectedAssetPeriod === period }"
              @click="selectedAssetPeriod = period"
              class="time-button">
              {{ period }}
            </button>
          </div>
        </div>
      </div>
      <div class="chart-container">
        <line-chart
          :chart-data="assetChartData"
          :options="assetChartOptions"
          height="300"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import LineChart from '@/components/LineChart.vue';

// 基礎數據
const isLoading = ref(true);
const errorMessage = ref('');

// 資產數據
const totalAssetValue = ref(0);
const assetChangePercentage = ref(0);
const availableBalance = ref(0);
const usdtBalance = ref(0);
const btcBalance = ref(0);
const positionValue = ref(0);

// 市場數據
const selectedPeriod = ref('24h');
const selectedAssetPeriod = ref('1W');

// 模擬數據
const topPositions = ref([
  { symbol: 'BTC', value: 30000 },
  { symbol: 'ETH', value: 15000 },
  { symbol: 'BNB', value: 5000 }
]);

const topMarkets = ref([
  {
    symbol: 'BTC/USDT',
    price: 57325.42,
    change: 2.5,
    volume: 1500000000,
    chartData: {
      labels: Array.from({ length: 24 }, (_, i) => i),
      datasets: [{
        data: Array.from({ length: 24 }, () => Math.random() * 1000 + 56000),
        borderColor: '#10B981',
        tension: 0.4
      }]
    }
  },
  // ... 其他市場數據
]);

// 圖表配置
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    }
  },
  scales: {
    x: {
      display: false
    },
    y: {
      display: false
    }
  },
  elements: {
    point: {
      radius: 0
    }
  }
};

const assetChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    }
  },
  scales: {
    x: {
      grid: {
        display: false
      }
    },
    y: {
      grid: {
        color: 'rgba(0, 0, 0, 0.1)'
      }
    }
  }
};

const assetChartData = ref({
  labels: Array.from({ length: 30 }, (_, i) => i + 1),
  datasets: [{
    label: '資產價值',
    data: Array.from({ length: 30 }, () => Math.random() * 20000 + 90000),
    borderColor: '#10B981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    fill: true,
    tension: 0.4
  }]
});

// 工具函數
const formatVolume = (value) => {
  if (value >= 1000000000) {
    return (value / 1000000000).toFixed(1) + 'B';
  }
  if (value >= 1000000) {
    return (value / 1000000).toFixed(1) + 'M';
  }
  if (value >= 1000) {
    return (value / 1000).toFixed(1) + 'K';
  }
  return value.toString();
};

// 數據加載函數
const loadData = async () => {
  try {
    isLoading.value = true;
    errorMessage.value = '';
    
    // 模擬API調用延遲
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // 這裡應該是加載資產和市場數據的API調用
    // 為了演示，我們使用靜態數據
    
  } catch (error) {
    console.error('Failed to load data:', error);
    errorMessage.value = '加載數據失敗，請重試';
  } finally {
    isLoading.value = false;
  }
};

// 生命週期鉤子
let dataRefreshInterval;

onMounted(() => {
  loadData();
  // 設置定時刷新，但間隔時間較長
  dataRefreshInterval = setInterval(() => {
    loadData();
  }, 30000); // 30秒刷新一次
});

onUnmounted(() => {
  // 清理定時器
  if (dataRefreshInterval) {
    clearInterval(dataRefreshInterval);
  }
});
</script>

<style scoped>
.dashboard {
  padding: var(--spacing-lg);
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-xl);
}

.asset-overview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.overview-card {
  padding: 20px;
}

.overview-number {
  font-size: 28px;
  font-weight: 600;
  margin: 10px 0;
  color: var(--text-primary);
}

.change-percentage {
  font-size: 14px;
  font-weight: 500;
}

.change-percentage.positive {
  color: var(--success-color);
}

.change-percentage.negative {
  color: var(--danger-color);
}

.balance-distribution,
.position-distribution {
  margin-top: 10px;
}

.balance-item,
.position-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  margin-top: 8px;
  color: var(--text-secondary);
}

.market-overview {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h2 {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.time-selector {
  display: flex;
  gap: 8px;
}

.time-button {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.3s ease;
}

.time-button.active {
  background: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.market-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.market-card {
  padding: 16px;
}

.market-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.market-header h4 {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
}

.price {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.price-chart {
  margin: 10px 0;
  height: 60px;
}

.market-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.volume {
  font-size: 12px;
  color: var(--text-secondary);
}

.asset-chart {
  padding: 20px;
  margin-bottom: 24px;
}

.chart-container {
  height: 300px;
}

@media (max-width: 768px) {
  .asset-overview {
    grid-template-columns: 1fr;
  }
  
  .market-grid {
    grid-template-columns: 1fr;
  }
}
</style> 