<template>
  <div class="dashboard container">
    <div class="dashboard-header">
      <h1>交易控制面板</h1>
      <div class="dashboard-actions">
        <router-link to="/grid/new" class="btn btn-primary">
          <span class="icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </span>
          创建新网格
        </router-link>
      </div>
    </div>

    <!-- 资产总览部分 -->
    <div class="asset-overview">
      <div class="overview-card card">
        <h3>总资产估值</h3>
        <p class="overview-number">${{ totalAssetValue.toFixed(2) }}</p>
        <p class="change-percentage" :class="{ 'positive': assetChangePercentage > 0, 'negative': assetChangePercentage < 0 }">
          {{ assetChangePercentage > 0 ? '+' : '' }}{{ assetChangePercentage.toFixed(2) }}%
        </p>
      </div>
      <div class="overview-card card">
        <h3>可用余额</h3>
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
        <h3>持仓市值</h3>
        <p class="overview-number">${{ positionValue.toFixed(2) }}</p>
        <div class="position-distribution">
          <div v-for="position in topPositions" :key="position.symbol" class="position-item">
            <span>{{ position.symbol }}</span>
            <span>${{ position.value.toFixed(2) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 市场概况部分 -->
    <div class="market-overview">
      <div class="section-header">
        <h2>市场概况</h2>
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

    <!-- 资产变化图表 -->
    <div class="asset-chart card">
      <div class="section-header">
        <h2>资产变化</h2>
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

    <div class="grid-summary">
      <div class="summary-card card">
        <h3>活跃网格</h3>
        <p class="summary-number">{{ activeGridsCount }}</p>
        <div class="summary-icon active-icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"></path>
          </svg>
        </div>
      </div>
      <div class="summary-card card">
        <h3>总投资额</h3>
        <p class="summary-number">${{ totalInvestment.toFixed(2) }}</p>
        <div class="summary-icon investment-icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"></path>
            <line x1="12" y1="6" x2="12" y2="8"></line>
            <line x1="12" y1="16" x2="12" y2="18"></line>
          </svg>
        </div>
      </div>
      <div class="summary-card card">
        <h3>总利润</h3>
        <p class="summary-number" :class="{ 'profit-positive': totalProfit > 0, 'profit-negative': totalProfit < 0 }">
          ${{ totalProfit.toFixed(2) }}
        </p>
        <div class="summary-icon profit-icon">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline>
            <polyline points="17 6 23 6 23 12"></polyline>
          </svg>
        </div>
      </div>
    </div>

    <div v-if="isLoading" class="loading-container card">
      <div class="loading-spinner"></div>
      <p>加载网格数据中...</p>
    </div>

    <div v-else-if="errorMessage" class="error-container card">
      <p>{{ errorMessage }}</p>
      <button @click="loadGrids" class="btn btn-primary mt-3">重试</button>
    </div>

    <div v-else-if="grids.length === 0" class="empty-state card">
      <div class="empty-icon">📊</div>
      <h3>暂无网格策略</h3>
      <p>您还没有创建任何网格交易策略。</p>
      <router-link to="/grid/new" class="btn btn-primary mt-3">创建您的第一个网格</router-link>
    </div>

    <div v-else class="grid-list">
      <div v-for="grid in grids" :key="grid.grid_id" class="grid-card card">
        <div class="grid-header">
          <h3>{{ grid.symbol }}</h3>
          <div class="grid-status" :class="{ 'status-running': grid.status === 'running', 'status-stopped': grid.status === 'stopped' }">
            {{ grid.status === 'running' ? '运行中' : '已停止' }}
          </div>
        </div>
        
        <div class="grid-body">
          <div class="grid-info">
            <div class="info-row">
              <span class="info-label">类型:</span>
              <span class="info-value">{{ grid.grid_type === 'arithmetic' ? '算术' : '几何' }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">价格范围:</span>
              <span class="info-value">${{ grid.lower_price }} - ${{ grid.upper_price }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">网格等级:</span>
              <span class="info-value">{{ grid.grid_levels }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">投资额:</span>
              <span class="info-value">${{ grid.investment }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">当前价格:</span>
              <span class="info-value">${{ grid.current_price }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">利润:</span>
              <span class="info-value" :class="{ 'profit-positive': grid.profit > 0, 'profit-negative': grid.profit < 0 }">
                ${{ grid.profit.toFixed(2) }}
              </span>
            </div>
          </div>
          <div class="grid-actions">
            <button v-if="grid.status === 'stopped'" @click="startGrid(grid.grid_id)" class="btn btn-primary" :disabled="actionLoading">
              启动
            </button>
            <button v-else @click="stopGrid(grid.grid_id)" class="btn btn-danger" :disabled="actionLoading">
              停止
            </button>
            <button @click="viewGridDetails(grid.grid_id)" class="btn btn-secondary">
              详情
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';
import LineChart from '@/components/LineChart.vue';

// 基础数据
const isLoading = ref(true);
const errorMessage = ref('');
const grids = ref([]);

// 资产数据
const totalAssetValue = ref(0);
const assetChangePercentage = ref(0);
const availableBalance = ref(0);
const usdtBalance = ref(0);
const btcBalance = ref(0);
const positionValue = ref(0);

// 市场数据
const selectedPeriod = ref('24h');
const selectedAssetPeriod = ref('1W');

// 网格统计
const activeGridsCount = ref(0);
const totalInvestment = ref(0);
const totalProfit = ref(0);

// 模拟数据
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
  // ... 其他市场数据
]);

// 图表配置
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
    label: '资产价值',
    data: Array.from({ length: 30 }, () => Math.random() * 20000 + 90000),
    borderColor: '#10B981',
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    fill: true,
    tension: 0.4
  }]
});

// 工具函数
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

// 数据加载函数
const loadGrids = async () => {
  try {
    isLoading.value = true;
    errorMessage.value = '';
    
    // 模拟API调用延迟
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // 模拟数据
    grids.value = [
      {
        grid_id: 1,
        symbol: 'BTC/USDT',
        status: 'running',
        grid_type: 'arithmetic',
        lower_price: 55000,
        upper_price: 60000,
        grid_levels: 100,
        investment: 50000,
        current_price: 57325.42,
        profit: 2500
      },
      // ... 其他网格数据
    ];
  } catch (error) {
    console.error('Failed to load grids:', error);
    errorMessage.value = '加载数据失败，请重试';
  } finally {
    isLoading.value = false;
  }
};

// 生命周期钩子
let dataRefreshInterval;

onMounted(() => {
  loadGrids();
  // 设置定时刷新，但间隔时间较长
  dataRefreshInterval = setInterval(() => {
    loadGrids();
  }, 30000); // 30秒刷新一次
});

onUnmounted(() => {
  // 清理定时器
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

.dashboard-actions {
  display: flex;
  gap: var(--spacing-md);
}

.btn .icon {
  display: inline-flex;
  margin-right: var(--spacing-xs);
}

.grid-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.summary-card {
  position: relative;
  overflow: hidden;
  padding: var(--spacing-lg);
  border-radius: var(--border-radius-lg);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.summary-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--box-shadow-md);
}

.summary-card h3 {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.summary-number {
  font-size: var(--font-size-xxl);
  font-weight: 700;
  margin: 0;
}

.summary-icon {
  position: absolute;
  top: var(--spacing-lg);
  right: var(--spacing-lg);
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.2;
}

.active-icon {
  color: var(--info-color);
}

.investment-icon {
  color: var(--primary-color);
}

.profit-icon {
  color: var(--success-color);
}

.profit-positive {
  color: var(--success-color);
}

.profit-negative {
  color: var(--danger-color);
}

.loading-container, .error-container, .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: var(--spacing-lg);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-lg);
}

.grid-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: var(--spacing-lg);
}

.grid-card {
  display: flex;
  flex-direction: column;
  border-radius: var(--border-radius-lg);
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.grid-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--box-shadow-md);
}

.grid-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-light);
}

.grid-header h3 {
  font-size: var(--font-size-lg);
  font-weight: 600;
  margin: 0;
}

.grid-status {
  padding: 4px 8px;
  border-radius: var(--border-radius-sm);
  font-size: var(--font-size-xs);
  font-weight: 500;
  text-transform: uppercase;
}

.status-running {
  background-color: rgba(76, 175, 80, 0.1);
  color: var(--success-color);
}

.status-stopped {
  background-color: rgba(244, 67, 54, 0.1);
  color: var(--danger-color);
}

.grid-body {
  padding: var(--spacing-md);
  flex: 1;
  display: flex;
  flex-direction: column;
}

.grid-info {
  flex: 1;
  margin-bottom: var(--spacing-md);
}

.info-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
  font-size: var(--font-size-sm);
}

.info-label {
  color: var(--text-secondary);
  font-weight: 500;
}

.info-value {
  font-weight: 600;
}

.grid-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.grid-actions .btn {
  flex: 1;
}

@media (max-width: 1024px) {
  .grid-summary {
    grid-template-columns: repeat(3, 1fr);
  }
  
  .grid-list {
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  }
}

@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
  }
  
  .grid-summary {
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }
  
  .grid-list {
    grid-template-columns: 1fr;
  }
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