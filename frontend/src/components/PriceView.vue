<template>
  <div class="price-view">
    <!-- 工具栏：搜索、筛选和排序 -->
    <div class="toolbar">
      <div class="search-bar">
        <el-input
          v-model="searchQuery"
          placeholder="搜索交易对..."
          prefix-icon="Search"
          clearable
        />
      </div>
      
      <div class="filter-bar">
        <el-select v-model="selectedMarket" placeholder="市场类型" class="market-select">
          <el-option label="全部" value="all" />
          <el-option label="现货" value="spot" />
          <el-option label="合约" value="futures" />
        </el-select>
        
        <el-select v-model="sortBy" placeholder="排序方式" class="sort-select">
          <el-option label="交易对" value="symbol" />
          <el-option label="价格" value="price" />
          <el-option label="涨跌幅" value="price_change_24h" />
          <el-option label="成交量" value="volume_24h" />
        </el-select>
        
        <el-select v-model="sortOrder" class="order-select">
          <el-option label="升序" value="asc" />
          <el-option label="降序" value="desc" />
        </el-select>
      </div>
    </div>
    
    <!-- 连接状态 -->
    <div class="connection-status" :class="{ connected: isConnected }">
      <div class="status-dot"></div>
      <span>{{ isConnected ? '实时数据已连接' : '连接中...' }}</span>
    </div>
    
    <!-- 数据表格 -->
    <el-table
      :data="filteredPairs"
      stripe
      style="width: 100%"
      :default-sort="{ prop: 'symbol', order: 'ascending' }"
      max-height="700"
      v-loading="loading"
    >
      <el-table-column
        label="市场"
        prop="marketType"
        width="100"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.marketType === 'spot' ? 'success' : 'warning'"
            size="small"
          >
            {{ row.marketType === 'spot' ? '现货' : '合约' }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column
        label="交易对"
        prop="symbol"
        sortable
        min-width="150"
      >
        <template #default="{ row }">
          <div class="symbol-container" @click="goToTradingView(row)" style="cursor: pointer;">
            <div class="symbol-text">{{ formatSymbol(row.symbol) }}</div>
            <div class="symbol-full">{{ row.symbol }}</div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column
        label="最新价格"
        prop="price"
        sortable
        width="150"
        align="right"
      >
        <template #default="{ row }">
          <div 
            class="price-cell" 
            :class="{
              'price-up': priceMovements[row.id]?.direction === 'up',
              'price-down': priceMovements[row.id]?.direction === 'down'
            }"
          >
            {{ formatPrice(row.price) }}
          </div>
        </template>
      </el-table-column>
      
      <el-table-column
        label="24h涨跌幅"
        prop="price_change_24h"
        sortable
        width="120"
        align="right"
      >
        <template #default="{ row }">
          <div 
            class="price-change"
            :class="{
              'positive': row.price_change_24h > 0,
              'negative': row.price_change_24h < 0
            }"
          >
            {{ formatPriceChange(row.price_change_24h) }}
          </div>
        </template>
      </el-table-column>
      
      <el-table-column
        label="24h成交量"
        prop="volume_24h"
        sortable
        width="150"
        align="right"
      >
        <template #default="{ row }">
          {{ formatVolume(row.volume_24h) }}
        </template>
      </el-table-column>
      
      <el-table-column
        label="24h最高价"
        prop="high_24h"
        sortable
        width="150"
        align="right"
      >
        <template #default="{ row }">
          {{ formatPrice(row.high_24h) }}
        </template>
      </el-table-column>
      
      <el-table-column
        label="24h最低价"
        prop="low_24h"
        sortable
        width="150"
        align="right"
      >
        <template #default="{ row }">
          {{ formatPrice(row.low_24h) }}
        </template>
      </el-table-column>
    </el-table>
    
    <!-- 市场统计 -->
    <div class="market-stats">
      <div class="stats-item">
        <span class="stats-label">现货交易对:</span>
        <span class="stats-value">{{ spotCount }}</span>
      </div>
      <div class="stats-item">
        <span class="stats-label">合约交易对:</span>
        <span class="stats-value">{{ futuresCount }}</span>
      </div>
      <div class="stats-item">
        <span class="stats-label">总交易对:</span>
        <span class="stats-value">{{ totalCount }}</span>
      </div>
      <div class="stats-item">
        <span class="stats-label">更新时间:</span>
        <span class="stats-value">{{ formattedLastUpdate }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useWebSocket } from '@/composables/useWebSocket'

// 定义props
const props = defineProps({
  selectedMarket: {
    type: String,
    default: 'all'
  }
})

// 路由实例
const router = useRouter()

// 状态变量
const prices = ref({})
const priceMovements = ref({})
const searchQuery = ref('')
// 使用从props传入的市场类型，默认为'all'
const selectedMarket = ref(props.selectedMarket)
const sortBy = ref('symbol')
const sortOrder = ref('desc')
const isConnected = ref(false)
const loading = ref(true)
const lastUpdateTime = ref(null)
const websocket = ref(null)
const reconnectAttempts = ref(0)
const maxReconnectAttempts = 5

// 监听props变化，更新本地状态
watch(() => props.selectedMarket, (newValue) => {
  selectedMarket.value = newValue
})

// 计算属性
const spotCount = computed(() => 
  Object.values(prices.value).filter(item => item.marketType === 'spot').length
)

const futuresCount = computed(() => 
  Object.values(prices.value).filter(item => item.marketType === 'futures').length
)

const totalCount = computed(() => 
  Object.values(prices.value).length
)

const formattedLastUpdate = computed(() => {
  if (!lastUpdateTime.value) return '未更新'
  return new Date(lastUpdateTime.value).toLocaleTimeString()
})

// 根据搜索和筛选条件过滤交易对
const filteredPairs = computed(() => {
  const query = searchQuery.value.toLowerCase()
  const pairs = Object.values(prices.value)
  
  return pairs
    .filter(data => {
      // 根据选择的市场类型过滤
      if (selectedMarket.value !== 'all' && data.marketType !== selectedMarket.value) {
        return false
      }
      
      // 根据搜索关键词过滤
      return data.symbol.toLowerCase().includes(query)
    })
    .sort((a, b) => {
      // 根据排序条件过滤
      if (sortBy.value === 'symbol') {
        return sortOrder.value === 'asc' 
          ? a.symbol.localeCompare(b.symbol) 
          : b.symbol.localeCompare(a.symbol)
      } else if (sortBy.value === 'price') {
        return sortOrder.value === 'asc' 
          ? a.price - b.price 
          : b.price - a.price
      } else if (sortBy.value === 'price_change_24h') {
        return sortOrder.value === 'asc' 
          ? a.price_change_24h - b.price_change_24h 
          : b.price_change_24h - a.price_change_24h
      } else if (sortBy.value === 'volume_24h') {
        return sortOrder.value === 'asc' 
          ? a.volume_24h - b.volume_24h 
          : b.volume_24h - a.volume_24h
      }
      return 0
    })
})

// 格式化函数
const formatSymbol = (symbol) => {
  // 把USDT从结尾提取出来
  if (symbol.endsWith('USDT')) {
    return symbol.replace('USDT', '') + '/USDT'
  }
  return symbol
}

const formatPrice = (price) => {
  if (price === undefined || price === null) return '-'
  
  // 不同价格范围使用不同的小数位数
  if (price >= 1000) {
    return price.toFixed(2)
  } else if (price >= 1) {
    return price.toFixed(4)
  } else if (price >= 0.0001) {
    return price.toFixed(6)
  } else {
    return price.toFixed(8)
  }
}

const formatPriceChange = (change) => {
  if (change === undefined || change === null) return '-'
  const sign = change > 0 ? '+' : ''
  return `${sign}${change.toFixed(2)}%`
}

const formatVolume = (volume) => {
  if (volume === undefined || volume === null) return '-'
  if (volume >= 1000000000) {
    return (volume / 1000000000).toFixed(2) + 'B'
  } else if (volume >= 1000000) {
    return (volume / 1000000).toFixed(2) + 'M'
  } else if (volume >= 1000) {
    return (volume / 1000).toFixed(2) + 'K'
  } else {
    return volume.toFixed(2)
  }
}

// WebSocket连接函数
const connectWebSocket = () => {
  try {
    // 获取WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = import.meta.env.VITE_API_URL || window.location.host
    const wsUrl = `${protocol}//${host}/api/v1/markets/ws/all`
    
    // 使用增强的WebSocket钩子
    const { 
      data: wsData, 
      isConnected: wsConnected,
      isReconnecting: wsReconnecting,
      error: wsError 
    } = useWebSocket(wsUrl, {
      maxAttempts: 15,         // 增加重试次数
      initialDelay: 1000,      // 1秒开始
      maxDelay: 30000,         // 最多30秒间隔
      factor: 1.5              // 指数增长因子
    });
    
    // 监听连接状态变化
    watch(wsConnected, (newValue) => {
      isConnected.value = newValue;
      if (newValue) {
        loading.value = false;
        reconnectAttempts.value = 0;
        console.log('WebSocket连接已建立');
      } else if (!wsReconnecting.value) {
        loading.value = false;
        console.log('WebSocket连接已断开');
      }
    });
    
    // 监听重连状态
    watch(wsReconnecting, (reconnecting) => {
      if (reconnecting) {
        console.log('正在尝试重新连接WebSocket...');
      }
    });
    
    // 监听错误
    watch(wsError, (error) => {
      if (error) {
        console.error('WebSocket错误:', error);
        ElMessage.error('连接市场数据失败，请检查网络连接');
      }
    });
    
    // 监听数据更新
    watch(wsData, (newData) => {
      if (newData) {
        handleWebSocketMessage(newData);
      }
    });
  } catch (error) {
    console.error('创建WebSocket连接失败:', error);
    loading.value = false;
    ElMessage.error('连接市场数据失败，请稍后重试');
  }
};

// 处理WebSocket消息
const handleWebSocketMessage = (message) => {
  if (message.type === 'connection_established') {
    console.log('连接确认:', message.message)
    return
  }
  
  if (message.type === 'heartbeat') {
    // 收到心跳包，实时连接正常
    return
  }
  
  if (message.type === 'update') {
    // 更新最后更新时间
    lastUpdateTime.value = message.timestamp
    
    // 处理市场数据
    const { markets, stats } = message
    
    if (markets && (markets.spot || markets.futures)) {
      // 临时存储新价格，用于对比变化
      const newPrices = { ...prices.value }
      let spotUpdated = 0, futuresUpdated = 0;
      
      // 处理现货市场数据 - 直接使用后端已过滤的数据
      if (markets.spot) {
        Object.entries(markets.spot).forEach(([symbol, data]) => {
          // 生成唯一ID，避免不同市场的同名交易对互相覆盖
          const id = `spot_${symbol}`;
          
          // 跟踪价格变化方向
          if (prices.value[id]?.price !== undefined && data.price !== undefined) {
            const oldPrice = prices.value[id].price;
            const newPrice = data.price;
            
            // 设置价格变化方向和时间
            if (newPrice > oldPrice) {
              priceMovements.value[id] = { direction: 'up', timestamp: Date.now() };
            } else if (newPrice < oldPrice) {
              priceMovements.value[id] = { direction: 'down', timestamp: Date.now() };
            }
          }
          
          // 更新数据 - 不需要额外过滤，后端已经过滤完成
          newPrices[id] = {
            ...data,
            id,
            symbol,  // 保留原始符号
            marketType: 'spot'
          };
          spotUpdated++;
        });
      }
      
      // 处理合约市场数据 - 直接使用后端已过滤的数据
      if (markets.futures) {
        Object.entries(markets.futures).forEach(([symbol, data]) => {
          // 生成唯一ID，避免不同市场的同名交易对互相覆盖
          const id = `futures_${symbol}`;
          
          // 跟踪价格变化方向
          if (prices.value[id]?.price !== undefined && data.price !== undefined) {
            const oldPrice = prices.value[id].price;
            const newPrice = data.price;
            
            // 设置价格变化方向和时间
            if (newPrice > oldPrice) {
              priceMovements.value[id] = { direction: 'up', timestamp: Date.now() };
            } else if (newPrice < oldPrice) {
              priceMovements.value[id] = { direction: 'down', timestamp: Date.now() };
            }
          }
          
          // 更新数据 - 不需要额外过滤，后端已经过滤完成
          newPrices[id] = {
            ...data,
            id,
            symbol,  // 保留原始符号
            marketType: 'futures'
          };
          futuresUpdated++;
        });
      }
      
      // 更新价格状态
      prices.value = newPrices;
      
      // 首次加载数据时记录一次状态
      if (!lastUpdateTime.value || Object.keys(prices.value).length !== Object.keys(newPrices).length) {
        console.log('数据加载完成: 总交易对数量', Object.keys(newPrices).length);
      }
      
      // 移除旧的价格变化标记（3秒后）
      setTimeout(() => {
        const now = Date.now();
        Object.keys(priceMovements.value).forEach(id => {
          if (priceMovements.value[id] && now - priceMovements.value[id].timestamp > 3000) {
            delete priceMovements.value[id];
          }
        });
      }, 3000);
    }
  }
}

// 跳转到交易页面
const goToTradingView = (row) => {
  router.push({
    name: 'trading',
    params: {
      marketType: row.marketType,
      symbol: row.symbol
    }
  })
}

// 生命周期钩子
onMounted(() => {
  connectWebSocket()
})

onUnmounted(() => {
  // 关闭WebSocket连接
  if (websocket.value && isConnected.value) {
    websocket.value.close()
    websocket.value = null
  }
})
</script>

<style scoped>
.price-view {
  width: 100%;
  position: relative;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 16px;
}

.search-bar {
  flex: 1;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.market-select,
.sort-select {
  min-width: 120px;
}

.order-select {
  min-width: 100px;
}

.connection-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 14px;
  color: var(--el-text-color-secondary);
  transition: color 0.3s ease;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--el-color-info);
  transition: background-color 0.3s ease;
}

.connection-status.connected .status-dot {
  background-color: var(--el-color-success);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.6;
    transform: scale(0.8);
  }
  50% {
    opacity: 1;
    transform: scale(1.2);
  }
  100% {
    opacity: 0.6;
    transform: scale(0.8);
  }
}

.symbol-container {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.symbol-text {
  font-weight: 600;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.symbol-full {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  transition: color 0.3s ease;
}

.price-cell {
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.price-cell.price-up {
  color: var(--el-color-success);
  animation: highlight-up 1s ease-out;
  animation-fill-mode: forwards;
}

.price-cell.price-down {
  color: var(--el-color-danger);
  animation: highlight-down 1s ease-out;
  animation-fill-mode: forwards;
}

.price-change {
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.3s ease, background-color 0.3s ease;
}

.price-change.positive {
  color: var(--el-color-success);
  background-color: var(--el-color-success-light-9);
}

.price-change.negative {
  color: var(--el-color-danger);
  background-color: var(--el-color-danger-light-9);
}

/* 深色模式下调整高亮颜色 */
:deep(.dark-theme) .price-change.positive,
:deep([class*="dark"]) .price-change.positive {
  background-color: rgba(var(--el-color-success-rgb), 0.15);
}

:deep(.dark-theme) .price-change.negative,
:deep([class*="dark"]) .price-change.negative {
  background-color: rgba(var(--el-color-danger-rgb), 0.15);
}

.market-stats {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  margin-top: 16px;
  padding: 12px;
  border-radius: 8px;
  background-color: var(--el-fill-color-light);
  transition: background-color 0.3s ease;
}

.stats-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stats-label {
  color: var(--el-text-color-secondary);
  font-size: 14px;
  transition: color 0.3s ease;
}

.stats-value {
  font-weight: 500;
  font-size: 14px;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

@keyframes highlight-up {
  0% { background-color: rgba(var(--el-color-success-rgb), 0.2); }
  100% { background-color: rgba(var(--el-color-success-rgb), 0.1); }
}

@keyframes highlight-down {
  0% { background-color: rgba(var(--el-color-danger-rgb), 0.2); }
  100% { background-color: rgba(var(--el-color-danger-rgb), 0.1); }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .filter-bar {
    justify-content: space-between;
  }
  
  .market-select,
  .sort-select,
  .order-select {
    min-width: unset;
  }
}
</style> 