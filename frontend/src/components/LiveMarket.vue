<template>
  <div class="live-market">
    <div class="market-header">
      <h3>Live Market</h3>
    </div>
    <div class="market-content">
      <div class="market-table-header">
        <div class="coin-column">Coin</div>
        <div class="change-column">Change</div>
        <div class="price-column">Price</div>
        <div class="chart-column">Chart</div>
      </div>
      <div v-for="(coin, index) in coins" :key="index" class="market-item">
        <div class="coin-column">
          <div class="coin-icon" :style="{ backgroundColor: coin.iconBgColor }">
            <span>{{ coin.icon }}</span>
          </div>
          <div class="coin-info">
            <h4>{{ coin.name }}</h4>
            <p>{{ coin.symbol }}</p>
          </div>
        </div>
        <div class="change-column" :class="{ 'positive': coin.change > 0, 'negative': coin.change < 0 }">
          {{ coin.change > 0 ? '+' : '' }}{{ coin.change }}%
        </div>
        <div class="price-column">
          {{ coin.price }} USD
        </div>
        <div class="chart-column">
          <div class="mini-chart" :class="{ 'positive': coin.change > 0, 'negative': coin.change < 0 }">
            <svg viewBox="0 0 100 30">
              <path :d="generateChartPath(coin.chartData)" fill="none" stroke-width="2" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const coins = ref([
  {
    name: 'Ethereum',
    symbol: 'ETH / USDT',
    price: '0',
    change: 0,
    icon: '⟠',
    iconBgColor: '#6B7DFF',
    chartData: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  },
  {
    name: 'Bitcoin',
    symbol: 'BTC / USDT',
    price: '0',
    change: 0,
    icon: '₿',
    iconBgColor: '#FFB52E',
    chartData: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  },
  {
    name: 'Litecoin',
    symbol: 'LTC / USDT',
    price: '0',
    change: 0,
    icon: 'Ł',
    iconBgColor: '#4B4BFF',
    chartData: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  },
  {
    name: 'Cardano',
    symbol: 'ADA / USDT',
    price: '0',
    change: 0,
    icon: '₳',
    iconBgColor: '#4CAF50',
    chartData: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
  }
]);

const generateChartPath = (data) => {
  if (!data || data.length === 0) return '';
  
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  
  const width = 100;
  const height = 30;
  const step = width / (data.length - 1);
  
  let path = `M 0 ${height - ((data[0] - min) / range) * height}`;
  
  for (let i = 1; i < data.length; i++) {
    const x = i * step;
    const y = height - ((data[i] - min) / range) * height;
    path += ` L ${x} ${y}`;
  }
  
  return path;
};
</script>

<style scoped lang="scss">
.live-market {
  background-color: var(--card-background);
  border-radius: 10px;
  padding: 20px;
  box-shadow: var(--box-shadow-md);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
  
  .market-header {
    margin-bottom: 15px;
    
    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: var(--text-primary);
    }
  }
  
  .market-content {
    .market-table-header {
      display: flex;
      padding: 10px 0;
      border-bottom: 1px solid var(--border-color);
      font-size: 14px;
      color: var(--text-secondary);
      font-weight: 500;
      
      .coin-column {
        flex: 2;
      }
      
      .change-column {
        flex: 1;
        text-align: center;
      }
      
      .price-column {
        flex: 1;
        text-align: center;
      }
      
      .chart-column {
        flex: 1;
        text-align: right;
      }
    }
    
    .market-item {
      display: flex;
      align-items: center;
      padding: 15px 0;
      border-bottom: 1px solid var(--border-color);
      
      &:last-child {
        border-bottom: none;
      }
      
      .coin-column {
        flex: 2;
        display: flex;
        align-items: center;
        
        .coin-icon {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-right: 15px;
          color: white;
          font-size: 16px;
        }
        
        .coin-info {
          h4 {
            margin: 0;
            font-size: 16px;
            font-weight: 500;
            color: var(--text-primary);
          }
          
          p {
            margin: 0;
            font-size: 14px;
            color: var(--text-secondary);
          }
        }
      }
      
      .change-column {
        flex: 1;
        text-align: center;
        font-weight: 500;
        
        &.positive {
          color: var(--success-color);
        }
        
        &.negative {
          color: var(--danger-color);
        }
      }
      
      .price-column {
        flex: 1;
        text-align: center;
        font-weight: 500;
        color: var(--text-primary);
      }
      
      .chart-column {
        flex: 1;
        
        .mini-chart {
          height: 30px;
          
          svg {
            width: 100%;
            height: 100%;
            
            path {
              stroke: var(--success-color);
            }
          }
          
          &.positive path {
            stroke: var(--success-color);
          }
          
          &.negative path {
            stroke: var(--danger-color);
          }
        }
      }
    }
  }
}
</style> 