<template>
  <div class="trading-view-container">
    <div class="trading-header">
      <div class="symbol-info">
        <h1>{{ formatSymbolDisplay() }}</h1>
        <div v-if="marketData" class="price-info">
          <span class="current-price" :class="{ 'price-up': marketData.price_change_percent > 0, 'price-down': marketData.price_change_percent < 0 }">
            {{ formatPrice(marketData.price) }}
          </span>
          <span class="price-change" :class="{ 'price-up': marketData.price_change_percent > 0, 'price-down': marketData.price_change_percent < 0 }">
            {{ marketData.price_change_percent > 0 ? '+' : '' }}{{ marketData.price_change_percent.toFixed(2) }}%
          </span>
        </div>
      </div>
      <el-button @click="goBackToMarket" type="primary" plain>
        <el-icon><ArrowLeft /></el-icon> 返回市场
      </el-button>
    </div>

    <div class="trading-content">
      <div class="chart-container" ref="chartContainer">
        <!-- TradingView图表将在这里初始化 -->
      </div>
      <div class="trade-panel-container">
        <TradePanel 
          :symbol="symbol" 
          :market-type="marketType" 
          :market-data="marketData" 
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeft } from '@element-plus/icons-vue';
import TradePanel from '@/components/TradePanel.vue';
import { ElMessage } from 'element-plus';
import { useThemeStore } from '@/stores/theme';

const route = useRoute();
const router = useRouter();
const chartContainer = ref(null);
const tvWidget = ref(null);
const marketData = ref(null);
const websocket = ref(null);
const websocketConnected = ref(false);
const themeStore = useThemeStore();

const symbol = computed(() => route.params.symbol || '');
const marketType = computed(() => route.params.marketType || 'spot');

// 返回市场页面
const goBackToMarket = () => {
  router.push('/markets');
};

// 格式化价格显示
const formatPrice = (price) => {
  if (price === undefined || price === null) return '-';
  
  if (price >= 1000) {
    return price.toFixed(2);
  } else if (price >= 1) {
    return price.toFixed(4);
  } else if (price >= 0.0001) {
    return price.toFixed(6);
  } else {
    return price.toFixed(8);
  }
};

// 获取基础货币符号
const getBaseSymbol = () => {
  if (!symbol.value) return '';
  
  if (symbol.value.endsWith('USDT')) {
    return symbol.value.replace('USDT', '');
  }
  
  return symbol.value;
};

// 格式化交易对显示
const formatSymbolDisplay = () => {
  if (!symbol.value) return '';
  
  const base = getBaseSymbol();
  return `${base}/USDT ${marketType.value === 'futures' ? '(合约)' : '(现货)'}`;
};

// 初始化TradingView图表
const initTradingView = () => {
  if (!chartContainer.value) return;
  
  // 格式化TradingView识别的交易对
  const formattedSymbol = formatTradingViewSymbol();
  
  // 使用ThemeStore获取当前主题状态
  const isDarkMode = themeStore.isDarkMode;
  
  // 设置ID，如果不存在则创建
  if (!chartContainer.value.id) {
    chartContainer.value.id = 'tv_chart_container';
  }
  
  // TradingView Widget配置
  const widgetOptions = {
    symbol: formattedSymbol,
    interval: '15',
    timezone: 'Asia/Shanghai',
    theme: isDarkMode ? 'dark' : 'light',
    style: '1',
    locale: 'zh_CN',
    toolbar_bg: isDarkMode ? '#121212' : '#f1f3f6',
    enable_publishing: false,
    withdateranges: true,
    hide_side_toolbar: false,
    allow_symbol_change: false,
    save_image: false,
    container_id: chartContainer.value.id,
    height: '100%',
    width: '100%',
    studies: ['MACD@tv-basicstudies', 'RSI@tv-basicstudies'],
    loading_screen: { backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF' },
    autosize: true,
    hide_top_toolbar: false,
    popup_width: '1000',
    popup_height: '650',
    overrides: {
      'paneProperties.background': isDarkMode ? '#1E1E1E' : '#FFFFFF',
      'paneProperties.vertGridProperties.color': isDarkMode ? '#292929' : '#E6E6E6',
      'paneProperties.horzGridProperties.color': isDarkMode ? '#292929' : '#E6E6E6',
      'symbolWatermarkProperties.transparency': 90,
      'scalesProperties.textColor': isDarkMode ? '#AAA' : '#666',
    },
  };
  
  // 如果存在window.TradingView且有Widget类，则初始化
  if (window.TradingView && window.TradingView.widget) {
    tvWidget.value = new window.TradingView.widget(widgetOptions);
  } else {
    // 动态加载TradingView widget脚本
    const script = document.createElement('script');
    script.src = 'https://s3.tradingview.com/tv.js';
    script.async = true;
    script.onload = () => {
      if (window.TradingView) {
        tvWidget.value = new window.TradingView.widget(widgetOptions);
      }
    };
    document.head.appendChild(script);
  }
};

// 格式化TradingView可识别的交易对格式
const formatTradingViewSymbol = () => {
  if (!symbol.value) return 'BINANCE:BTCUSDT';
  
  // 通常TradingView使用交易所:交易对的格式，这里假设使用BINANCE作为交易所
  const base = getBaseSymbol();
  return `BINANCE:${base}USDT`;
};

// 连接WebSocket获取实时价格
const connectWebSocket = () => {
  // 关闭已存在的连接
  if (websocket.value && websocket.value.readyState !== WebSocket.CLOSED) {
    websocket.value.close();
  }
  
  // 确定WebSocket URL
  const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  const host = window.location.host;
  const wsUrl = `${protocol}${host}/api/v1/markets/ws/ticker/${symbol.value}`;
  
  console.log(`Connecting to WebSocket: ${wsUrl}`);
  
  try {
    websocket.value = new WebSocket(wsUrl);
    
    websocket.value.onopen = () => {
      console.log('WebSocket connected');
      websocketConnected.value = true;
      ElMessage.success('实时价格数据已连接');
    };
    
    websocket.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received ticker data:', data);
        
        if (data && data.symbol === symbol.value) {
          marketData.value = data;
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    
    websocket.value.onerror = (error) => {
      console.error('WebSocket error:', error);
      websocketConnected.value = false;
      ElMessage.error('价格数据连接失败，将使用模拟数据');
      
      // 如果连接失败，使用模拟数据
      useSimulatedData();
    };
    
    websocket.value.onclose = () => {
      console.log('WebSocket closed');
      websocketConnected.value = false;
    };
  } catch (error) {
    console.error('Error creating WebSocket connection:', error);
    websocketConnected.value = false;
    
    // 如果无法创建连接，使用模拟数据
    useSimulatedData();
  }
};

// 使用模拟数据
const useSimulatedData = () => {
  // 为测试创建模拟数据
  marketData.value = {
    symbol: symbol.value,
    price: Math.random() * (symbol.value.includes('BTC') ? 50000 : 2000),
    price_change_percent: (Math.random() * 10) - 5,
    high_24h: Math.random() * (symbol.value.includes('BTC') ? 52000 : 2100),
    low_24h: Math.random() * (symbol.value.includes('BTC') ? 48000 : 1900),
    volume: Math.random() * 10000000,
    market_type: marketType.value
  };
  
  // 模拟定期价格更新
  setInterval(() => {
    if (!websocketConnected.value && marketData.value) {
      const priceChange = (Math.random() * 2 - 1) * (marketData.value.price * 0.005);
      marketData.value.price += priceChange;
      marketData.value.price_change_percent += (priceChange / marketData.value.price) * 100;
      if (marketData.value.price > marketData.value.high_24h) {
        marketData.value.high_24h = marketData.value.price;
      }
      if (marketData.value.price < marketData.value.low_24h) {
        marketData.value.low_24h = marketData.value.price;
      }
    }
  }, 5000);
};

// 组件挂载时设置图表和连接
onMounted(() => {
  // 设置chart容器id
  if (chartContainer.value) {
    chartContainer.value.id = 'tv_chart_container';
  }
  
  // 初始化图表
  initTradingView();
  
  // 连接WebSocket
  connectWebSocket();

  // 监听主题变化
  themeStore.$subscribe((mutation, state) => {
    // 当主题改变时重新初始化图表
    if (chartContainer.value) {
      if (tvWidget.value && typeof tvWidget.value.remove === 'function') {
        tvWidget.value.remove();
        tvWidget.value = null;
      }
      initTradingView();
    }
  });
});

// 组件卸载前清理资源
onBeforeUnmount(() => {
  if (websocket.value) {
    websocket.value.close();
  }
  
  if (tvWidget.value && typeof tvWidget.value.remove === 'function') {
    tvWidget.value.remove();
  }
});
</script>

<style scoped>
.trading-view-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background-color: var(--el-bg-color);
  color: var(--el-text-color-primary);
  transition: background-color 0.3s, color 0.3s;
}

.trading-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--el-border-color);
  background-color: var(--el-bg-color-overlay);
  box-shadow: var(--el-box-shadow-light);
  transition: background-color 0.3s, border-color 0.3s;
}

.symbol-info {
  display: flex;
  flex-direction: column;
}

.symbol-info h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  transition: color 0.3s;
}

.price-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
}

.current-price {
  font-size: 24px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  transition: color 0.3s;
}

.price-change {
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 500;
  transition: background-color 0.3s, color 0.3s;
}

.price-up {
  color: var(--el-color-success);
  background-color: rgba(var(--el-color-success-rgb), 0.1);
}

.price-down {
  color: var(--el-color-danger);
  background-color: rgba(var(--el-color-danger-rgb), 0.1);
}

.back-button {
  transition: color 0.3s, background-color 0.3s;
}

.back-button:hover {
  color: var(--el-color-primary);
  background-color: var(--el-color-primary-light-9);
}

.trading-content {
  display: flex;
  flex: 1;
  overflow: hidden;
  background-color: var(--el-bg-color);
  transition: background-color 0.3s;
}

.chart-container {
  flex: 3;
  min-width: 0;
  height: 100%;
  background-color: var(--el-bg-color-overlay);
  border-radius: 4px;
  margin: 8px;
  box-shadow: var(--el-box-shadow-light);
  transition: background-color 0.3s, box-shadow 0.3s;
}

.trade-panel-container {
  flex: 1;
  min-width: 300px;
  max-width: 400px;
  border-left: 1px solid var(--el-border-color);
  overflow-y: auto;
  background-color: var(--el-bg-color-overlay);
  border-radius: 4px;
  margin: 8px 8px 8px 0;
  transition: border-color 0.3s, background-color 0.3s;
}

/* 响应式布局 */
@media (max-width: 992px) {
  .trading-content {
    flex-direction: column;
  }
  
  .chart-container {
    height: 50vh;
    margin: 8px;
  }
  
  .trade-panel-container {
    max-width: none;
    border-left: none;
    border-top: 1px solid var(--el-border-color);
    margin: 0 8px 8px 8px;
  }
}

@media (max-width: 768px) {
  .trading-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .chart-container {
    height: 40vh;
  }
}
</style> 