<template>
  <div class="dashboard-container">
    <div class="dashboard-header">
      <h1>交易控制面板</h1>
      <div class="header-actions">
        <button class="refresh-all-btn" @click="loadData(); loadGlobalMarketData(true)" :disabled="isLoading || isLoadingGlobalData">
          <i class="fas fa-sync-alt" :class="{ 'fa-spin': isLoading || isLoadingGlobalData }"></i>
          刷新數據
        </button>
      </div>
    </div>

    <!-- 主要儀表板內容 -->
    <div class="dashboard-content">
      <!-- 左側邊欄 - 資產總覽 -->
      <div class="dashboard-sidebar">
        <div class="sidebar-header">
          <h2>資產總覽</h2>
        </div>
        
        <div class="sidebar-card asset-total">
          <div class="card-title">總資產估值</div>
          <div class="asset-value">${{ totalAssetValue.toFixed(2) }}</div>
          <div class="asset-change" :class="{ 'positive': assetChangePercentage > 0, 'negative': assetChangePercentage < 0 }">
            <i :class="assetChangePercentage > 0 ? 'fas fa-arrow-up' : 'fas fa-arrow-down'"></i>
            {{ assetChangePercentage > 0 ? '+' : '' }}{{ assetChangePercentage.toFixed(2) }}%
          </div>
        </div>
        
        <div class="sidebar-card">
          <div class="card-title">可用余額</div>
          <div class="balance-value">${{ availableBalance.toFixed(2) }}</div>
          <div class="balance-details">
            <div class="balance-item">
              <div class="coin-icon usdt">USDT</div>
              <div class="coin-value">${{ usdtBalance.toFixed(2) }}</div>
            </div>
            <div class="balance-item">
              <div class="coin-icon btc">BTC</div>
              <div class="coin-value">{{ btcBalance.toFixed(8) }}</div>
            </div>
          </div>
        </div>
        
        <div class="sidebar-card">
          <div class="card-title">持倉市值</div>
          <div class="position-value">${{ positionValue.toFixed(2) }}</div>
          <div class="position-details">
            <div v-for="position in topPositions" :key="position.symbol" class="position-item">
              <div class="coin-icon" :class="position.symbol.toLowerCase()">{{ position.symbol }}</div>
              <div class="coin-value">${{ position.value.toFixed(2) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右側主要內容區 -->
      <div class="dashboard-main">
        <div class="main-section market-data">
          <div class="section-header">
            <h2>全球市場數據</h2>
            <div class="header-meta">
              <span class="last-updated">{{ formattedLastUpdate }}</span>
              <button class="refresh-btn" @click="loadGlobalMarketData(true)" :disabled="isLoadingGlobalData">
                <i class="fas fa-sync-alt" :class="{ 'fa-spin': isLoadingGlobalData }"></i>
              </button>
            </div>
          </div>
          
          <div class="market-grid">
            <!-- 比特幣市佔率卡片 -->
            <div class="market-card">
              <div class="card-header">
                <h3>比特幣市佔率</h3>
                <div class="card-icon">
                  <i class="fab fa-bitcoin"></i>
                </div>
              </div>
              <div v-if="isLoadingGlobalData" class="loading-indicator">
                <div class="spinner"></div>
              </div>
              <div v-else class="card-content">
                <div class="dominance-value">{{ bitcoinDominance.toFixed(2) }}%</div>
                <div class="dominance-chart">
                  <div class="progress-bar">
                    <div class="progress" :style="{ width: `${bitcoinDominance}%` }"></div>
                  </div>
                </div>
                <div class="dominance-compare">
                  <div class="compare-item">
                    <span>以太坊佔比:</span>
                    <span>{{ ethereumDominance.toFixed(2) }}%</span>
                  </div>
                  <div class="compare-item">
                    <span>其他佔比:</span>
                    <span>{{ (100 - bitcoinDominance - ethereumDominance).toFixed(2) }}%</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 恐懼貪婪指數卡片 -->
            <div class="market-card">
              <div class="card-header">
                <h3>恐懼貪婪指數</h3>
                <div class="card-icon">
                  <i class="fas fa-chart-line"></i>
                </div>
              </div>
              <div v-if="isLoadingGlobalData" class="loading-indicator">
                <div class="spinner"></div>
              </div>
              <div v-else class="card-content fear-greed-content">
                <div class="fear-greed-container">
                  <div class="fear-greed-meter">
                    <div class="meter-gauge">
                      <div class="meter-value" :style="{ transform: `rotate(${(fearGreedIndex - 50) * 1.8}deg)` }"></div>
                    </div>
                    <div class="meter-display">{{ fearGreedIndex }}</div>
                  </div>
                  <div class="meter-labels">
                    <span class="fear">極度恐懼</span>
                    <span class="neutral">中性</span>
                    <span class="greed">極度貪婪</span>
                  </div>
                  <div class="fear-greed-label">{{ fearGreedLabel }}</div>
                </div>
                <div class="historical-data">
                  <div class="history-title">歷史數據</div>
                  <div class="history-grid">
                    <div class="history-item">
                      <div class="history-label">昨天</div>
                      <div class="history-value">{{ fearGreedHistory.yesterday }}</div>
                    </div>
                    <div class="history-item">
                      <div class="history-label">上週</div>
                      <div class="history-value">{{ fearGreedHistory.lastWeek }}</div>
                    </div>
                    <div class="history-item">
                      <div class="history-label">上月</div>
                      <div class="history-value">{{ fearGreedHistory.lastMonth }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 全球市值卡片 -->
            <div class="market-card">
              <div class="card-header">
                <h3>全球加密貨幣市值</h3>
                <div class="card-icon">
                  <i class="fas fa-globe"></i>
                </div>
              </div>
              <div v-if="isLoadingGlobalData" class="loading-indicator">
                <div class="spinner"></div>
              </div>
              <div v-else class="card-content">
                <div class="marketcap-value">{{ formatCurrency(totalMarketCap) }}</div>
                <div class="marketcap-details">
                  <div class="detail-item">
                    <div class="detail-icon"><i class="fas fa-exchange-alt"></i></div>
                    <div class="detail-info">
                      <div class="detail-label">24小時交易量</div>
                      <div class="detail-value">{{ formatCurrency(totalVolume24h) }}</div>
                    </div>
                  </div>
                  <div class="detail-item">
                    <div class="detail-icon"><i class="fas fa-coins"></i></div>
                    <div class="detail-info">
                      <div class="detail-label">活躍加密貨幣</div>
                      <div class="detail-value">{{ activeCoins }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, onUnmounted } from 'vue';
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
const isCachedData = ref(true);
const nextDataUpdateTime = ref(null);

// 模擬數據
const topPositions = ref([
  { symbol: 'BTC', value: 30000 },
  { symbol: 'ETH', value: 15000 },
  { symbol: 'BNB', value: 5000 }
]);

// 工具函數
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
const loadGlobalMarketData = async (forceRefresh = false) => {
  try {
    isLoadingGlobalData.value = true;
    
    // 呼叫全球市場數據API，添加强制刷新參數
    const response = await axios.get('/api/v1/markets/global-metrics', {
      params: { force_refresh: forceRefresh }
    });
    
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
      
      // 處理緩存信息
      if (globalMetrics.cache_info) {
        isCachedData.value = globalMetrics.cache_info.is_cached;
        
        // 如果有下次更新時間信息，計算並儲存
        if (globalMetrics.cache_info.next_update_in_seconds) {
          const nextUpdateSeconds = globalMetrics.cache_info.next_update_in_seconds;
          if (nextUpdateSeconds > 0) {
            nextDataUpdateTime.value = new Date(Date.now() + nextUpdateSeconds * 1000);
          } else {
            nextDataUpdateTime.value = null;
          }
        }
      }
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
  
  // 添加緩存狀態信息
  const cacheStatus = isCachedData.value ? '(緩存)' : '(實時)';
  
  if (days > 0) return `${days} 天前更新 ${cacheStatus}`;
  if (hours > 0) return `${hours} 小時前更新 ${cacheStatus}`;
  if (minutes > 0) return `${minutes} 分鐘前更新 ${cacheStatus}`;
  return `剛剛更新 ${cacheStatus}`;
});

// 生命週期鉤子
let dataRefreshInterval;

onMounted(() => {
  loadData();
  loadGlobalMarketData(false); // 頁面載入時使用緩存數據
  
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
:root {
  --accent-color: #3361FF;
  --accent-hover: #264AD8;
  --success-color: #00C48C;
  --warning-color: #FF9800;
  --danger-color: #FF3D71;
  --text-primary: #FFFFFF;
  --text-secondary: #A7ADBD;
  --text-tertiary: #767C8B;
  --background-primary: #0F111A;
  --background-secondary: #161926;
  --background-tertiary: #1C202F;
  --card-background: #161926;
  --card-border: #2C3248;
  --border-color: #2C3248;
  --chart-gradient-start: rgba(51, 97, 255, 0.5);
  --chart-gradient-end: rgba(51, 97, 255, 0);
}

/* 全局樣式 */
.dashboard-container {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--background-primary);
  color: var(--text-primary);
  padding: 24px;
  width: 100%;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* 頭部樣式 */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 32px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-color);
}

.dashboard-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 16px;
}

.refresh-all-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background-color: var(--accent-color);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.refresh-all-btn:hover {
  background-color: var(--accent-hover);
}

.refresh-all-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 主要內容區域 */
.dashboard-content {
  display: flex;
  gap: 24px;
  flex: 1;
}

/* 側邊欄樣式 */
.dashboard-sidebar {
  width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-header {
  margin-bottom: 8px;
}

.sidebar-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.sidebar-card {
  background-color: var(--card-background);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid var(--card-border);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.sidebar-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

.card-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.asset-value, .balance-value, .position-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.asset-change {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 500;
  padding: 4px 8px;
  border-radius: 4px;
  width: fit-content;
}

.asset-change.positive {
  background-color: rgba(0, 196, 140, 0.15);
  color: var(--success-color);
}

.asset-change.negative {
  background-color: rgba(255, 61, 113, 0.15);
  color: var(--danger-color);
}

.balance-details, .position-details {
  margin-top: 16px;
}

.balance-item, .position-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color);
}

.balance-item:last-child, .position-item:last-child {
  border-bottom: none;
}

.coin-icon {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.coin-icon::before {
  content: '';
  display: inline-block;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  margin-right: 8px;
  background-size: contain;
  background-position: center;
  background-repeat: no-repeat;
}

.coin-icon.btc::before {
  background-color: #F7931A;
}

.coin-icon.eth::before {
  background-color: #627EEA;
}

.coin-icon.usdt::before {
  background-color: #26A17B;
}

.coin-icon.bnb::before {
  background-color: #F3BA2F;
}

.coin-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

/* 主要內容區樣式 */
.dashboard-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.main-section {
  background-color: var(--background-secondary);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid var(--border-color);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.section-header h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.last-updated {
  font-size: 12px;
  color: var(--text-tertiary);
}

.refresh-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:hover {
  background-color: var(--accent-color);
  color: white;
  border-color: var(--accent-color);
}

.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 市場數據網格 */
.market-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.market-card {
  background-color: var(--card-background);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--card-border);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.market-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background-color: var(--background-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.card-header h3 {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0;
}

.card-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background-color: var(--accent-color);
  color: white;
}

.card-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  flex: 1;
}

/* 比特幣市佔率卡片 */
.dominance-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.dominance-chart {
  margin-bottom: 16px;
}

.progress-bar {
  height: 8px;
  background-color: rgba(255, 255, 255, 0.1);
  border-radius: 4px;
  overflow: hidden;
  margin-top: 8px;
}

.progress {
  height: 100%;
  background-color: var(--accent-color);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.dominance-compare {
  margin-top: auto;
}

.compare-item {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 8px;
}

/* 恐懼貪婪指數卡片 */
.fear-greed-content {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;
}

.fear-greed-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20px;
}

.fear-greed-meter {
  position: relative;
  width: 160px;
  height: 80px;
  margin-bottom: 20px;
}

.meter-gauge {
  position: relative;
  width: 160px;
  height: 80px;
  background: conic-gradient(
    #FF3D71 0deg 36deg,
    #FFA26B 36deg 72deg,
    #FFD76B 72deg 108deg,
    #00C48C 108deg 144deg,
    #3361FF 144deg 180deg
  );
  border-radius: 80px 80px 0 0;
  overflow: hidden;
}

.meter-value {
  position: absolute;
  bottom: 0;
  left: 50%;
  height: 70px;
  width: 3px;
  background-color: white;
  transform-origin: bottom center;
  transition: transform 0.5s ease;
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.8);
  z-index: 2;
}

.meter-display {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  background-color: var(--background-tertiary);
  color: var(--text-primary);
  border-radius: 50%;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  border: 3px solid white;
  z-index: 3;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
}

.meter-labels {
  display: flex;
  justify-content: space-between;
  width: 100%;
  margin-top: 10px;
  font-size: 12px;
}

.meter-labels .fear {
  color: #FF3D71;
}

.meter-labels .neutral {
  color: #FFD76B;
}

.meter-labels .greed {
  color: #3361FF;
}

.fear-greed-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: center;
  margin-top: 8px;
}

.historical-data {
  margin-top: auto;
  border-top: 1px solid var(--border-color);
  padding-top: 16px;
}

.history-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.history-grid {
  display: flex;
  justify-content: space-between;
}

.history-item {
  text-align: center;
  flex: 1;
}

.history-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.history-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 全球市值卡片 */
.marketcap-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 24px;
}

.marketcap-details {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: auto;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: rgba(51, 97, 255, 0.15);
  color: var(--accent-color);
}

.detail-info {
  flex: 1;
}

.detail-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.detail-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

/* 加載動畫 */
.loading-indicator {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  min-height: 200px;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(51, 97, 255, 0.2);
  border-radius: 50%;
  border-top-color: var(--accent-color);
  animation: spin 1s infinite ease-in-out;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 響應式調整 */
@media (max-width: 1200px) {
  .dashboard-content {
    flex-direction: column;
  }
  
  .dashboard-sidebar {
    width: 100%;
    margin-bottom: 24px;
  }
  
  .sidebar-cards {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
}

@media (max-width: 992px) {
  .market-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .sidebar-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .market-grid, .sidebar-cards {
    grid-template-columns: 1fr;
  }
  
  .dashboard-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .header-actions {
    width: 100%;
  }
  
  .refresh-all-btn {
    width: 100%;
    justify-content: center;
  }
}
</style> 