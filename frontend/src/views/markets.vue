<template>
  <div class="markets-container">
    <!-- 市场概览区域 -->
    <div class="market-overview">
      <div class="overview-card">
        <div class="card-content">
          <div class="overview-icon">
            <el-icon><Money /></el-icon>
          </div>
          <div class="overview-details">
            <h3>总市值</h3>
            <div class="overview-value">$2.38T</div>
            <div class="overview-change positive">
              <el-icon><CaretTop /></el-icon> +2.4%
            </div>
          </div>
        </div>
      </div>
      
      <div class="overview-card">
        <div class="card-content">
          <div class="overview-icon volume-icon">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="overview-details">
            <h3>24h交易量</h3>
            <div class="overview-value">$84.7B</div>
            <div class="overview-change negative">
              <el-icon><CaretBottom /></el-icon> -1.2%
            </div>
          </div>
        </div>
      </div>
      
      <div class="overview-card">
        <div class="card-content">
          <div class="overview-icon btc-icon">
            <div class="crypto-icon">₿</div>
          </div>
          <div class="overview-details">
            <h3>比特币主导率</h3>
            <div class="overview-value">51.3%</div>
            <div class="overview-change positive">
              <el-icon><CaretTop /></el-icon> +0.5%
            </div>
          </div>
        </div>
      </div>
      
      <div class="overview-card">
        <div class="card-content">
          <div class="overview-icon exchange-icon">
            <el-icon><DataAnalysis /></el-icon>
          </div>
          <div class="overview-details">
            <h3>活跃交易对</h3>
            <div class="overview-value">710</div>
            <div class="overview-change neutral">
              <span>现货 325 / 合约 385</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 热门交易对快速访问 -->
    <div class="trending-pairs">
      <div class="section-header">
        <h2>热门交易对</h2>
        <el-tooltip content="点击快速进入交易页面" placement="top">
          <el-icon class="info-icon"><InfoFilled /></el-icon>
        </el-tooltip>
      </div>
      
      <div class="trending-cards">
        <div class="trending-card" @click="quickNavigate('spot', 'BTCUSDT')">
          <div class="trending-symbol">BTC/USDT <span class="market-tag spot">现货</span></div>
          <div class="trending-price">$68,245.32</div>
          <div class="trending-change positive">+4.2%</div>
          <div class="mini-chart positive">
            <svg viewBox="0 0 100 30">
              <path d="M0,20 L10,18 L20,22 L30,15 L40,16 L50,12 L60,8 L70,10 L80,6 L90,4 L100,2" fill="none" stroke-width="2" />
            </svg>
          </div>
        </div>
        
        <div class="trending-card" @click="quickNavigate('spot', 'ETHUSDT')">
          <div class="trending-symbol">ETH/USDT <span class="market-tag spot">现货</span></div>
          <div class="trending-price">$3,421.65</div>
          <div class="trending-change positive">+3.7%</div>
          <div class="mini-chart positive">
            <svg viewBox="0 0 100 30">
              <path d="M0,15 L10,16 L20,14 L30,12 L40,13 L50,10 L60,8 L70,9 L80,7 L90,5 L100,3" fill="none" stroke-width="2" />
            </svg>
          </div>
        </div>
        
        <div class="trending-card" @click="quickNavigate('futures', 'SOLUSDT')">
          <div class="trending-symbol">SOL/USDT <span class="market-tag futures">合约</span></div>
          <div class="trending-price">$156.87</div>
          <div class="trending-change positive">+6.9%</div>
          <div class="mini-chart positive">
            <svg viewBox="0 0 100 30">
              <path d="M0,18 L10,15 L20,16 L30,14 L40,12 L50,10 L60,6 L70,8 L80,5 L90,3 L100,1" fill="none" stroke-width="2" />
            </svg>
          </div>
        </div>
        
        <div class="trending-card" @click="quickNavigate('futures', 'XRPUSDT')">
          <div class="trending-symbol">XRP/USDT <span class="market-tag futures">合约</span></div>
          <div class="trending-price">$0.5432</div>
          <div class="trending-change negative">-1.2%</div>
          <div class="mini-chart negative">
            <svg viewBox="0 0 100 30">
              <path d="M0,12 L10,13 L20,15 L30,16 L40,14 L50,17 L60,18 L70,20 L80,22 L90,21 L100,24" fill="none" stroke-width="2" />
            </svg>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 主要市场表格 -->
    <el-card class="market-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
          <h2>交易市場</h2>
            <div class="market-tabs">
              <el-button-group>
                <el-button type="primary" plain :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">全部</el-button>
                <el-button type="primary" plain :class="{ active: activeTab === 'spot' }" @click="activeTab = 'spot'">现货</el-button>
                <el-button type="primary" plain :class="{ active: activeTab === 'futures' }" @click="activeTab = 'futures'">合约</el-button>
              </el-button-group>
            </div>
          </div>
          <div class="header-right">
            <div class="update-status">
              <div class="status-dot"></div>
              <span>实时数据</span>
            </div>
          <el-tooltip
            content="實時更新加密貨幣市場價格"
            placement="top"
          >
            <el-icon class="info-icon"><InfoFilled /></el-icon>
          </el-tooltip>
          </div>
        </div>
      </template>
      
      <!-- 使用 PriceView 組件，通过props传递当前激活的标签 -->
      <PriceView :selected-market="activeTab" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { 
  InfoFilled, 
  Money, 
  TrendCharts, 
  CaretTop, 
  CaretBottom, 
  Minus, 
  DataAnalysis 
} from '@element-plus/icons-vue'
import PriceView from '@/components/PriceView.vue'

// 路由实例
const router = useRouter()

// 激活的市场类型标签
const activeTab = ref('all')

// 快速导航到交易页面
const quickNavigate = (marketType: string, symbol: string) => {
  router.push({
    name: 'trading',
    params: {
      marketType,
      symbol
    }
  })
}
</script>

<style scoped>
.markets-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: var(--el-text-color-primary);
  background-color: var(--el-bg-color);
  transition: color 0.3s ease, background-color 0.3s ease;
}

/* 市场概览区域样式 */
.market-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.overview-card {
  background-color: var(--el-bg-color-overlay);
  border-radius: 12px;
  box-shadow: var(--el-box-shadow-light);
  padding: 20px;
  transition: transform 0.3s ease, box-shadow 0.3s ease, background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
  border: 1px solid var(--el-border-color);
}

.overview-card:hover {
  transform: translateY(-5px);
  box-shadow: var(--el-box-shadow);
}

.card-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.overview-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background-color: rgba(var(--el-color-primary-rgb), 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-color-primary);
  font-size: 22px;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.volume-icon {
  background-color: rgba(var(--el-color-success-rgb), 0.1);
  color: var(--el-color-success);
}

.btc-icon {
  background-color: rgba(var(--el-color-warning-rgb), 0.1);
  color: var(--el-color-warning);
}

.exchange-icon {
  background-color: rgba(var(--el-color-info-rgb), 0.1);
  color: var(--el-color-info);
}

.crypto-icon {
  font-size: 22px;
  font-weight: bold;
  line-height: 1;
}

.overview-details {
  flex: 1;
}

.overview-details h3 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
  transition: color 0.3s ease;
}

.overview-value {
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
  transition: color 0.3s ease;
}

.overview-change {
  display: flex;
  align-items: center;
  font-size: 14px;
  font-weight: 500;
  transition: color 0.3s ease;
}

.overview-change.positive {
  color: var(--el-color-success);
}

.overview-change.negative {
  color: var(--el-color-danger);
}

.overview-change.neutral {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

/* 热门交易对样式 */
.trending-pairs {
  background-color: var(--el-bg-color-overlay);
  border-radius: 12px;
  box-shadow: var(--el-box-shadow-light);
  padding: 20px;
  border: 1px solid var(--el-border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.section-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.trending-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.trending-card {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  padding: 16px;
  border: 1px solid var(--el-border-color);
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease, border-color 0.3s ease;
  cursor: pointer;
}

.trending-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--el-box-shadow);
  border-color: var(--el-color-primary-light-5);
}

.trending-symbol {
  font-weight: 600;
  font-size: 16px;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: color 0.3s ease;
}

.market-tag {
  font-size: 12px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: normal;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.market-tag.spot {
  background-color: rgba(var(--el-color-success-rgb), 0.1);
  color: var(--el-color-success);
}

.market-tag.futures {
  background-color: rgba(var(--el-color-warning-rgb), 0.1);
  color: var(--el-color-warning);
}

.trending-price {
  font-size: 18px;
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.trending-change {
  font-weight: 600;
  margin-bottom: 12px;
  transition: color 0.3s ease;
}

.trending-change.positive {
  color: var(--el-color-success);
}

.trending-change.negative {
  color: var(--el-color-danger);
}

.mini-chart {
  height: 30px;
}

.mini-chart svg {
  width: 100%;
  height: 100%;
}

.mini-chart.positive path {
  stroke: var(--el-color-success);
  transition: stroke 0.3s ease;
}

.mini-chart.negative path {
  stroke: var(--el-color-danger);
  transition: stroke 0.3s ease;
}

/* 主市场卡片样式 */
.market-card {
  background-color: var(--el-bg-color-overlay);
  border-radius: 12px;
  box-shadow: var(--el-box-shadow-light);
  flex: 1;
  border: 1px solid var(--el-border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease;
}

.market-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color);
  transition: border-color 0.3s ease, background-color 0.3s ease;
  background-color: var(--el-bg-color-overlay);
}

.market-card :deep(.el-card__body) {
  background-color: var(--el-bg-color);
  transition: background-color 0.3s ease;
  padding: 0;
  border-radius: 0 0 12px 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.header-left h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.market-tabs {
  display: flex;
}

.market-tabs .el-button-group {
  margin-left: 16px;
}

.market-tabs .el-button {
  padding: 6px 12px;
  font-size: 13px;
  transition: color 0.3s ease, background-color 0.3s ease, border-color 0.3s ease;
}

.market-tabs .el-button.active {
  color: var(--el-color-primary);
  background-color: rgba(var(--el-color-primary-rgb), 0.1);
  border-color: var(--el-color-primary-light-5);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.update-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  transition: color 0.3s ease;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--el-color-success);
  animation: pulse 2s infinite;
  transition: background-color 0.3s ease;
}

.info-icon {
  color: var(--el-color-info);
  cursor: help;
  font-size: 16px;
  transition: color 0.3s ease;
}

@keyframes pulse {
  0% {
    opacity: 0.5;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
  100% {
    opacity: 0.5;
    transform: scale(0.8);
  }
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .market-overview,
  .trending-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .markets-container {
    padding: 12px;
    gap: 16px;
  }
  
  .market-overview {
    grid-template-columns: 1fr;
  }
  
  .trending-cards {
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .market-tabs .el-button-group {
    margin-left: 0;
  }
  
  .trending-card {
    padding: 12px;
  }
  
  .overview-card {
    padding: 16px;
  }
  
  .card-header h2 {
    font-size: 16px;
  }
  
  .section-header h2 {
    font-size: 16px;
  }
  
  .overview-value {
    font-size: 18px;
  }
}

@media (max-width: 480px) {
  .trending-cards {
    grid-template-columns: 1fr;
  }
  
  .overview-icon {
    width: 40px;
    height: 40px;
    font-size: 20px;
  }

  .market-card :deep(.el-card__header) {
    padding: 12px 15px;
  }

  .header-right {
    gap: 8px;
  }
  
  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .header-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style> 