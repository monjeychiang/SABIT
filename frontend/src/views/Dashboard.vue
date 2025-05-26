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

    <!-- 全球市場數據 -->
    <div class="global-market-data">
      <div class="section-header">
        <h2>全球市場數據</h2>
        <div class="refresh-section">
          <span class="last-updated">{{ formattedLastUpdate }}</span>
          <div class="refresh-button" @click="loadGlobalMarketData" :disabled="isLoadingGlobalData">
            <i class="fas fa-sync-alt" :class="{ 'fa-spin': isLoadingGlobalData }"></i>
          </div>
        </div>
      </div>
      <div class="global-data-grid">
        <!-- 比特幣市佔率卡片 -->
        <div class="global-data-card card">
          <div class="data-header">
            <h3>比特幣市佔率</h3>
          </div>
          <div v-if="isLoadingGlobalData" class="loading-indicator">
            <div class="spinner"></div>
          </div>
          <div v-else class="data-content">
            <div class="data-value">{{ bitcoinDominance.toFixed(2) }}%</div>
            <div class="data-chart">
              <div class="progress-bar">
                <div class="progress" :style="{ width: `${bitcoinDominance}%` }"></div>
              </div>
            </div>
            <div class="data-info">
              <span>以太坊佔比: {{ ethereumDominance.toFixed(2) }}%</span>
            </div>
          </div>
        </div>

        <!-- 恐懼貪婪指數卡片 -->
        <div class="global-data-card card">
          <div class="data-header">
            <h3>恐懼貪婪指數</h3>
          </div>
          <div v-if="isLoadingGlobalData" class="loading-indicator">
            <div class="spinner"></div>
          </div>
          <div v-else class="data-content">
            <div class="fear-greed-container">
              <div class="fear-greed-meter">
                <div class="meter-gauge">
                  <div class="meter-value" :style="{ transform: `rotate(${(fearGreedIndex - 50) * 1.8}deg)` }"></div>
                </div>
                <div class="meter-labels">
                  <span class="fear">極度恐懼</span>
                  <span class="greed">極度貪婪</span>
                </div>
              </div>
              <div class="fear-greed-value">{{ fearGreedIndex }}</div>
              <div class="fear-greed-label">{{ fearGreedLabel }}</div>
            </div>
            <div class="historical-data">
              <div class="historical-item">
                <span>昨天:</span>
                <span>{{ fearGreedHistory.yesterday }}</span>
              </div>
              <div class="historical-item">
                <span>上週:</span>
                <span>{{ fearGreedHistory.lastWeek }}</span>
              </div>
              <div class="historical-item">
                <span>上月:</span>
                <span>{{ fearGreedHistory.lastMonth }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 全球市值卡片 -->
        <div class="global-data-card card">
          <div class="data-header">
            <h3>全球加密貨幣市值</h3>
          </div>
          <div v-if="isLoadingGlobalData" class="loading-indicator">
            <div class="spinner"></div>
          </div>
          <div v-else class="data-content">
            <div class="data-value">{{ formatCurrency(totalMarketCap) }}</div>
            <div class="data-info">
              <div class="info-item">
                <span>24小時交易量:</span>
                <span>{{ formatCurrency(totalVolume24h) }}</span>
              </div>
              <div class="info-item">
                <span>活躍加密貨幣:</span>
                <span>{{ activeCoins }}</span>
              </div>
            </div>
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
import axios from 'axios';

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

// 全球市場數據
const isLoadingGlobalData = ref(false);
const bitcoinDominance = ref(42.5);
const ethereumDominance = ref(18.2);
const fearGreedIndex = ref(55);
const fearGreedLabel = ref('中性');
const fearGreedHistory = ref({
  yesterday: 53,
  lastWeek: 48,
  lastMonth: 60
});
const totalMarketCap = ref(2300000000000);
const totalVolume24h = ref(85000000000);
const activeCoins = ref(10384);
const lastGlobalDataUpdate = ref(null);

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

const formatCurrency = (value) => {
  if (value >= 1000000000000) {
    return '$' + (value / 1000000000000).toFixed(2) + ' 兆';
  }
  if (value >= 1000000000) {
    return '$' + (value / 1000000000).toFixed(2) + ' 十億';
  }
  if (value >= 1000000) {
    return '$' + (value / 1000000).toFixed(2) + ' 百萬';
  }
  return '$' + value.toFixed(2);
};

// 獲取恐懼和貪婪指數對應的描述和顏色
const getFearGreedInfo = (value) => {
  if (value <= 10) return { label: '極度恐懼', color: '#E53E3E' };
  if (value <= 25) return { label: '恐懼', color: '#F6AD55' };
  if (value <= 45) return { label: '偏向恐懼', color: '#F6E05E' };
  if (value <= 55) return { label: '中性', color: '#68D391' };
  if (value <= 75) return { label: '偏向貪婪', color: '#4FD1C5' };
  if (value <= 90) return { label: '貪婪', color: '#3182CE' };
  return { label: '極度貪婪', color: '#805AD5' };
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

// 加載全球市場數據
const loadGlobalMarketData = async () => {
  try {
    isLoadingGlobalData.value = true;
    
    // 呼叫全球市場數據API
    const response = await axios.get('/api/v1/markets/global-metrics');
    
    if (response.data && response.data.success) {
      // 更新比特幣市佔率數據
      const globalMetrics = response.data.global_metrics;
      bitcoinDominance.value = globalMetrics.bitcoin_dominance || 0;
      ethereumDominance.value = globalMetrics.ethereum_dominance || 0;
      totalMarketCap.value = globalMetrics.total_market_cap_usd || 0;
      totalVolume24h.value = globalMetrics.total_volume_24h_usd || 0;
      activeCoins.value = globalMetrics.active_cryptocurrencies || 0;
      
      // 更新恐懼貪婪指數數據
      const fearGreedData = response.data.fear_greed_index;
      fearGreedIndex.value = fearGreedData.value || 0;
      fearGreedLabel.value = fearGreedData.readable_classification || '未知';
      
      // 更新歷史數據
      const historyData = fearGreedData.historical_data || {};
      fearGreedHistory.value = {
        yesterday: historyData.yesterday || 0,
        lastWeek: historyData.last_week || 0,
        lastMonth: historyData.last_month || 0
      };
      
      // 記錄最後更新時間
      lastGlobalDataUpdate.value = new Date();
    } else {
      console.error('Invalid response format from global metrics API');
      errorMessage.value = '獲取全球市場數據失敗，返回數據格式不正確';
    }
  } catch (error) {
    console.error('Failed to load global market data:', error);
    errorMessage.value = '獲取全球市場數據失敗，請重試';
  } finally {
    isLoadingGlobalData.value = false;
  }
};

// 格式化最後更新時間
const formattedLastUpdate = computed(() => {
  if (!lastGlobalDataUpdate.value) return '尚未更新';
  
  const now = new Date();
  const diff = now - lastGlobalDataUpdate.value;
  const minutes = Math.floor(diff / (1000 * 60));
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);
  
  if (days > 0) return `${days} 天前更新`;
  if (hours > 0) return `${hours} 小時前更新`;
  if (minutes > 0) return `${minutes} 分鐘前更新`;
  return '剛剛更新';
});

// 生命週期鉤子
let dataRefreshInterval;

onMounted(() => {
  loadData();
  loadGlobalMarketData(); // 僅在頁面載入時獲取一次
  
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

/* 全球市場數據樣式 */
.global-market-data {
  margin-bottom: 24px;
}

.refresh-section {
  display: flex;
  align-items: center;
  gap: 10px;
}

.last-updated {
  font-size: 14px;
  color: var(--text-secondary);
}

.global-data-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.global-data-card {
  padding: 20px;
  min-height: 250px;
  height: auto;
  display: flex;
  flex-direction: column;
}

.data-header {
  margin-bottom: 15px;
}

.data-header h3 {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-primary);
}

.data-content {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
}

.data-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 15px;
  word-break: break-word;
}

.data-chart {
  margin: 15px 0;
}

.data-info {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: auto;
  word-break: break-word;
}

.info-item {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  flex-wrap: wrap;
  gap: 5px;
}

.info-item > span:first-child {
  margin-right: 5px;
}

.info-item > span:last-child {
  font-weight: 500;
}

/* 進度條樣式 */
.progress-bar {
  height: 8px;
  background-color: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.progress {
  height: 100%;
  background-color: var(--primary-color);
  border-radius: 4px;
}

/* 恐懼貪婪指數儀表盤樣式 */
.fear-greed-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 10px;
}

.fear-greed-meter {
  position: relative;
  width: 140px;
  height: 80px;
  margin-bottom: 10px;
}

.meter-gauge {
  position: relative;
  width: 140px;
  height: 80px;
  background: conic-gradient(
    #E53E3E 0deg 36deg,
    #F6AD55 36deg 72deg,
    #F6E05E 72deg 108deg,
    #68D391 108deg 144deg,
    #4FD1C5 144deg 180deg
  );
  border-radius: 90px 90px 0 0;
  overflow: hidden;
}

.meter-value {
  position: absolute;
  bottom: 0;
  left: 50%;
  height: 70px;
  width: 3px;
  background-color: #000;
  transform-origin: bottom center;
  transition: transform 0.5s ease;
}

.meter-labels {
  display: flex;
  justify-content: space-between;
  width: 100%;
  margin-top: 5px;
  font-size: 11px;
}

.meter-labels .fear {
  color: #E53E3E;
}

.meter-labels .greed {
  color: #4FD1C5;
}

.fear-greed-value {
  font-size: 28px;
  font-weight: 600;
  margin: 5px 0;
  line-height: 1;
}

.fear-greed-label {
  font-size: 14px;
  color: var(--text-secondary);
  text-align: center;
  margin-bottom: 5px;
}

.historical-data {
  margin-top: auto;
  width: 100%;
}

.historical-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  margin: 5px 0;
  color: var(--text-secondary);
}

/* 加載動畫 */
.loading-indicator {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.spinner {
  width: 30px;
  height: 30px;
  border: 3px solid rgba(0, 0, 0, 0.1);
  border-radius: 50%;
  border-top-color: var(--primary-color);
  animation: spin 1s infinite ease-in-out;
}

.refresh-button {
  cursor: pointer;
  padding: 8px;
  border-radius: 50%;
  transition: background-color 0.3s;
}

.refresh-button:hover {
  background-color: rgba(0, 0, 0, 0.05);
}

.refresh-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
  .asset-overview,
  .global-data-grid {
    grid-template-columns: 1fr;
  }
  
  .market-grid {
    grid-template-columns: 1fr;
  }
}
</style> 