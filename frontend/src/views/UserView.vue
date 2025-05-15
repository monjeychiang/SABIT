<template>
  <div class="user-page" :class="{ 'light-theme': !isDarkTheme }">
    <!-- 用戶資料頂部區域 -->
    <div class="user-profile-section">
      <div class="user-info">
        <div class="user-avatar-container">
          <div class="user-avatar"></div>
        </div>
        <div class="user-name">{{ userData.username }}</div>
        <div class="social-links">
          <button class="social-icon telegram">
            <span class="icon-circle">T</span>
          </button>
          <button class="social-icon twitter">
            <span class="icon-circle">X</span>
          </button>
          <button class="social-icon discord">
            <span class="icon-circle">D</span>
          </button>
        </div>
      </div>

      <div class="user-stats">
        <div class="stat-item">
          <div class="stat-label">UID</div>
          <div class="stat-value">{{ userData.uid }}</div>
        </div>

        <div class="stat-item">
          <div class="stat-label">VIP 等級</div>
          <div class="stat-value">{{ userData.vipLevel }} <span class="chevron">›</span></div>
        </div>

        <div class="stat-item">
          <div class="stat-label">關注中</div>
          <div class="stat-value highlight">{{ userData.following }}</div>
        </div>

        <div class="stat-item">
          <div class="stat-label">粉絲</div>
          <div class="stat-value">{{ userData.followers }} <span class="chevron">›</span></div>
        </div>
      </div>
    </div>

    <!-- 資產估值區域 -->
    <div class="asset-section">
      <div class="asset-header">
        <div class="asset-title">
          總資產估值 <span class="eye-icon"></span>
        </div>
        <div class="asset-actions">
          <button class="asset-btn deposit">充值</button>
          <button class="asset-btn withdraw">提領</button>
          <button class="asset-btn deposit-money">入金</button>
        </div>
      </div>

      <div class="asset-details">
        <div class="asset-value-container">
          <div class="asset-value">{{ userData.totalAsset }}</div>
          <div class="asset-currency">{{ userData.currencyUnit }} <span class="chevron-down">▼</span></div>
        </div>
        <div class="asset-in-local">≈ {{ userData.localCurrency }} {{ userData.localValue }}</div>
        <div class="daily-profit">
          <span class="profit-label">本日盈虧</span> 
          <span class="profit-value positive">+ {{ userData.localCurrency }} {{ userData.dailyProfit }}({{ userData.dailyProfitPercentage }}%)</span>
        </div>
      </div>

      <div class="asset-chart">
        <!-- 資產走勢圖 -->
        <div class="chart-placeholder"></div>
      </div>
    </div>

    <!-- 市場區域 -->
    <div class="market-section">
      <div class="market-header">
        <div class="market-title">市場</div>
        <div class="more-link">更多 ›</div>
      </div>

      <div class="market-tabs">
        <button class="tab-btn active">持有</button>
        <button class="tab-btn">熱門</button>
        <button class="tab-btn">全新上架</button>
        <button class="tab-btn">自選</button>
        <button class="tab-btn">漲幅榜</button>
        <button class="tab-btn">24h成交量</button>
      </div>

      <div class="market-table">
        <div class="table-header">
          <div class="header-cell coin">幣種</div>
          <div class="header-cell amount">金額</div>
          <div class="header-cell price">幣價/成交價格</div>
          <div class="header-cell change">24小時漲跌</div>
          <div class="header-cell action">交易</div>
        </div>

        <!-- USDT 行 -->
        <div class="table-row">
          <div class="cell coin">
            <div class="coin-icon usdt"></div>
            <div class="coin-info">
              <div class="coin-name">USDT</div>
              <div class="coin-full-name">TetherUS</div>
            </div>
          </div>
          <div class="cell amount">
            <div class="amount-value">682.73260299</div>
            <div class="amount-in-local">NT$ 20,693.63</div>
          </div>
          <div class="cell price">
            <div class="price-value">NT$ 30.31</div>
            <div class="price-change">--</div>
          </div>
          <div class="cell change negative">-0.02%</div>
          <div class="cell action">
            <button class="trade-btn">交易</button>
          </div>
        </div>

        <!-- ETH 行 -->
        <div class="table-row">
          <div class="cell coin">
            <div class="coin-icon eth"></div>
            <div class="coin-info">
              <div class="coin-name">ETH</div>
              <div class="coin-full-name">Ethereum</div>
            </div>
          </div>
          <div class="cell amount">
            <div class="amount-value">0.00008913</div>
            <div class="amount-in-local">NT$ 7.00</div>
          </div>
          <div class="cell price">
            <div class="price-value">NT$ 78,495.32</div>
            <div class="price-in-local">NT$ 86,576.16</div>
          </div>
          <div class="cell change negative">-0.26%</div>
          <div class="cell action">
            <button class="trade-btn">交易</button>
          </div>
        </div>

        <!-- RUNE 行 -->
        <div class="table-row">
          <div class="cell coin">
            <div class="coin-icon rune"></div>
            <div class="coin-info">
              <div class="coin-name">RUNE</div>
              <div class="coin-full-name">THORChain</div>
            </div>
          </div>
          <div class="cell amount">
            <div class="amount-value">0.03860518</div>
            <div class="amount-in-local">NT$ 2.31</div>
          </div>
          <div class="cell price">
            <div class="price-value">NT$ 59.74</div>
            <div class="price-in-local">NT$ 196.43</div>
          </div>
          <div class="cell change negative">-4.13%</div>
          <div class="cell action">
            <button class="trade-btn">交易</button>
          </div>
        </div>

        <!-- LTC 行 -->
        <div class="table-row">
          <div class="cell coin">
            <div class="coin-icon ltc"></div>
            <div class="coin-info">
              <div class="coin-name">LTC</div>
              <div class="coin-full-name">Litecoin</div>
            </div>
          </div>
          <div class="cell amount">
            <div class="amount-value">0.00036297</div>
            <div class="amount-in-local">NT$ 1.09</div>
          </div>
          <div class="cell price">
            <div class="price-value">NT$ 3,010.69</div>
            <div class="price-in-local">NT$ 3,862.75</div>
          </div>
          <div class="cell change negative">-2.22%</div>
          <div class="cell action">
            <button class="trade-btn">交易</button>
          </div>
        </div>

        <!-- AAVE 行 -->
        <div class="table-row">
          <div class="cell coin">
            <div class="coin-icon aave"></div>
            <div class="coin-info">
              <div class="coin-name">AAVE</div>
              <div class="coin-full-name">Aave</div>
            </div>
          </div>
          <div class="cell amount">
            <div class="amount-value">0.00008402</div>
            <div class="amount-in-local">NT$ 0.58</div>
          </div>
          <div class="cell price">
            <div class="price-value">NT$ 6,883.70</div>
            <div class="price-in-local">NT$ 6,927.65</div>
          </div>
          <div class="cell change positive">+0.09%</div>
          <div class="cell action">
            <button class="trade-btn">交易</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useThemeStore } from '@/stores/theme'; // 修正引用路徑

// 模擬用戶數據
const userData = ref({
  username: '100u就夠了',
  uid: '719730518',
  vipLevel: '普通用戶',
  following: 16,
  followers: 10,
  totalAsset: '683.11269331',
  currencyUnit: 'USDT',
  localCurrency: 'NT$',
  localValue: '20,705.15',
  dailyProfit: '1,375.66',
  dailyProfitPercentage: '5.98'
});

// 使用全局主題
const themeStore = useThemeStore();
const isDarkTheme = ref(themeStore.isDarkMode);

// 監聽主題變化
watch(() => themeStore.isDarkMode, (newValue) => {
  isDarkTheme.value = newValue;
});

onMounted(() => {
  console.log('用戶頁面已載入');
});
</script>

<style scoped>
/* 主題變數 - 暗色 (默認) */
.user-page {
  --bg-primary: #1f2128;
  --bg-secondary: #2b2f3a;
  --bg-tertiary: #3d4252;
  --text-primary: #fff;
  --text-secondary: #a1a3b0;
  --accent-color: #4f94ff;
  --positive-color: #22c55e;
  --negative-color: #ef4444;
  --border-color: #2b2f3a;
  
  padding: var(--spacing-md);
  color: var(--text-primary);
  max-width: 1200px;
  margin: 0 auto;
  transition: all 0.3s ease;
}

/* 亮色主題變數 */
.user-page.light-theme {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-tertiary: #e0e0e0;
  --text-primary: #333333;
  --text-secondary: #666666;
  --accent-color: #1a73e8;
  --positive-color: #0f9d58;
  --negative-color: #d93025;
  --border-color: #dddddd;
}

/* 用戶資料頂部區域 */
.user-profile-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 20px;
  background-color: var(--bg-primary);
  border-radius: 12px;
  padding: 20px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.user-avatar-container {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  overflow: hidden;
  background-color: var(--bg-tertiary);
}

.user-avatar {
  width: 100%;
  height: 100%;
  background-color: var(--accent-color);
  border-radius: 12px;
}

.user-name {
  font-size: 22px;
  font-weight: 600;
}

.social-links {
  display: flex;
  gap: 8px;
  align-items: center;
}

.social-icon {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
}

.icon-circle {
  display: block;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: var(--bg-tertiary);
}

.user-stats {
  display: flex;
  gap: 40px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.stat-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 16px;
  color: var(--text-primary);
}

.stat-value .chevron {
  color: var(--text-secondary);
}

.highlight {
  color: var(--accent-color);
}

/* 資產估值區域 */
.asset-section {
  background-color: var(--bg-primary);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  position: relative;
}

.asset-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.asset-title {
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

.eye-icon::before {
  content: "👁️";
  margin-left: 8px;
}

.asset-actions {
  display: flex;
  gap: 10px;
}

.asset-btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: none;
  background-color: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.asset-btn:hover {
  background-color: var(--bg-tertiary);
}

.asset-details {
  margin-bottom: 20px;
}

.asset-value-container {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.asset-value {
  font-size: 32px;
  font-weight: 700;
}

.asset-currency {
  font-size: 18px;
  color: var(--text-secondary);
}

.chevron-down {
  font-size: 12px;
}

.asset-in-local {
  font-size: 16px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.daily-profit {
  font-size: 14px;
}

.profit-label {
  color: var(--text-secondary);
}

.profit-value {
  font-weight: 500;
}

.positive {
  color: var(--positive-color);
}

.negative {
  color: var(--negative-color);
}

.asset-chart {
  height: 80px;
  position: relative;
}

.chart-placeholder {
  background: linear-gradient(transparent, rgba(34, 197, 94, 0.2));
  position: relative;
  height: 100%;
  overflow: hidden;
}

.chart-placeholder::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #22c55e20, #22c55e10);
  border-bottom: 2px solid #22c55e;
}

/* 市場區域 */
.market-section {
  background-color: var(--bg-primary);
  border-radius: 12px;
  padding: 20px;
}

.market-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.market-title {
  font-size: 18px;
  font-weight: 600;
}

.more-link {
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
}

.market-tabs {
  display: flex;
  gap: 15px;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 15px;
  overflow-x: auto;
  padding-bottom: 10px;
}

.tab-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 14px;
  padding: 6px 10px;
  cursor: pointer;
  border-radius: 4px;
  white-space: nowrap;
}

.tab-btn.active {
  color: var(--text-primary);
  border-bottom: 2px solid var(--accent-color);
}

.market-table {
  width: 100%;
}

.table-header {
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr 0.8fr 0.5fr;
  padding: 10px 0;
  color: var(--text-secondary);
  font-size: 14px;
  border-bottom: 1px solid var(--border-color);
}

.table-row {
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr 0.8fr 0.5fr;
  padding: 15px 0;
  border-bottom: 1px solid var(--border-color);
  align-items: center;
}

.cell {
  padding: 0 10px;
}

.coin {
  display: flex;
  align-items: center;
  gap: 10px;
}

.coin-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-tertiary);
  color: white;
  font-weight: bold;
  font-size: 10px;
}

.coin-icon.usdt::before {
  content: "T";
  background-color: #26a17b;
}

.coin-icon.eth::before {
  content: "E";
  background-color: #627eea;
}

.coin-icon.rune::before {
  content: "R";
  background-color: #00afd1;
}

.coin-icon.ltc::before {
  content: "L";
  background-color: #345d9d;
}

.coin-icon.aave::before {
  content: "A";
  background-color: #8a2be2;
}

.coin-info {
  display: flex;
  flex-direction: column;
}

.coin-name {
  font-weight: 600;
}

.coin-full-name {
  font-size: 12px;
  color: var(--text-secondary);
}

.amount, .price {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.amount-value, .price-value {
  font-weight: 500;
}

.amount-in-local, .price-in-local, .price-change {
  font-size: 12px;
  color: var(--text-secondary);
}

.change {
  font-weight: 500;
}

.trade-btn {
  background-color: var(--bg-secondary);
  color: #ffc107;
  border: none;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
}

.trade-btn:hover {
  background-color: var(--bg-tertiary);
}

@media (max-width: 950px) {
  .user-profile-section {
    flex-direction: column;
    gap: 20px;
  }
  
  .user-stats {
    justify-content: space-between;
    width: 100%;
  }
}

@media (max-width: 768px) {
  .table-header, .table-row {
    grid-template-columns: 1.5fr 1fr 0.8fr 0.8fr 0.5fr;
  }
  
  .user-stats {
    flex-wrap: wrap;
    gap: 20px;
  }
  
  .stat-item {
    flex-basis: 45%;
  }
}

@media (max-width: 576px) {
  .table-header, .table-row {
    grid-template-columns: 1.5fr 1fr 0.8fr;
  }
  
  .header-cell.price, .cell.price {
    display: none;
  }
  
  .header-cell.action, .cell.action {
    display: none;
  }
}
</style> 