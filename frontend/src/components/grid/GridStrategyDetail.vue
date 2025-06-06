<template>
  <div class="grid-strategy-detail">
    <el-card class="detail-card" v-loading="loading">
      <template #header>
        <div class="detail-header">
          <h3 class="strategy-title">
            {{ strategy.symbol }}
            <el-tag size="small" :type="statusTagType">{{ statusText }}</el-tag>
          </h3>
          <div class="strategy-actions">
            <el-button 
              v-if="canStart" 
              type="success" 
              size="small" 
              @click="$emit('start')" 
              :loading="actionLoading"
            >
              啟動策略
            </el-button>
            <el-button 
              v-if="canStop" 
              type="warning" 
              size="small" 
              @click="$emit('stop')" 
              :loading="actionLoading"
            >
              停止策略
            </el-button>
            <el-button 
              v-if="canDelete" 
              type="danger" 
              size="small" 
              @click="$emit('delete')" 
              :loading="actionLoading"
            >
              刪除策略
            </el-button>
            <el-button 
              type="info" 
              size="small" 
              @click="$emit('back')"
            >
              返回列表
            </el-button>
          </div>
        </div>
      </template>

      <!-- 基本信息 -->
      <el-descriptions title="基本信息" :column="2" border>
        <el-descriptions-item label="交易對">{{ strategy.symbol }}</el-descriptions-item>
        <el-descriptions-item label="交易所">{{ exchangeText }}</el-descriptions-item>
        <el-descriptions-item label="網格類型">{{ gridTypeText }}</el-descriptions-item>
        <el-descriptions-item label="策略方向">{{ strategyTypeText }}</el-descriptions-item>
        <el-descriptions-item label="網格數量">{{ strategy.grid_number }}</el-descriptions-item>
        <el-descriptions-item label="價格範圍">{{ strategy.lower_price }} - {{ strategy.upper_price }} USDT</el-descriptions-item>
        <el-descriptions-item label="總投資額">{{ strategy.total_investment }} USDT</el-descriptions-item>
        <el-descriptions-item label="槓桿倍數">{{ strategy.leverage }}x</el-descriptions-item>
        <el-descriptions-item label="止損比例" v-if="strategy.stop_loss_percentage">{{ strategy.stop_loss_percentage }}%</el-descriptions-item>
        <el-descriptions-item label="止盈比例" v-if="strategy.take_profit_percentage">{{ strategy.take_profit_percentage }}%</el-descriptions-item>
        <el-descriptions-item label="盈利收集比例" v-if="strategy.profit_collection_percentage">{{ strategy.profit_collection_percentage }}%</el-descriptions-item>
        <el-descriptions-item label="創建時間">{{ formatDateTime(strategy.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="最後更新時間">{{ formatDateTime(strategy.updated_at) }}</el-descriptions-item>
      </el-descriptions>

      <!-- 運行數據 -->
      <div class="section-container" v-if="hasRunningData">
        <h4 class="section-title">運行數據</h4>

        <div class="data-cards">
          <el-card class="data-card">
            <div class="data-card-title">當前價格</div>
            <div class="data-card-value">{{ formatPrice(strategy.current_price) }}</div>
          </el-card>

          <el-card class="data-card">
            <div class="data-card-title">已實現收益</div>
            <div class="data-card-value" :class="profitClass(strategy.realized_pnl)">
              {{ formatProfit(strategy.realized_pnl) }}
            </div>
          </el-card>

          <el-card class="data-card">
            <div class="data-card-title">未實現收益</div>
            <div class="data-card-value" :class="profitClass(strategy.unrealized_pnl)">
              {{ formatProfit(strategy.unrealized_pnl) }}
            </div>
          </el-card>

          <el-card class="data-card">
            <div class="data-card-title">總收益</div>
            <div class="data-card-value" :class="profitClass(totalPnl)">
              {{ formatProfit(totalPnl) }} 
              <span class="profit-percentage" v-if="pnlPercentage !== null">
                ({{ pnlPercentage }}%)
              </span>
            </div>
          </el-card>
        </div>
      </div>

      <!-- 網格分佈圖 -->
      <div class="section-container">
        <h4 class="section-title">網格分佈圖</h4>
        <div class="chart-container" ref="chartRef"></div>
      </div>

      <!-- 訂單列表 -->
      <div class="section-container" v-if="orders && orders.length > 0">
        <h4 class="section-title">訂單列表</h4>
        
        <el-table :data="orders" style="width: 100%" stripe>
          <el-table-column prop="order_id" label="訂單ID" width="120" />
          <el-table-column prop="order_type" label="訂單類型">
            <template #default="scope">
              <el-tag 
                :type="scope.row.order_type === 'BUY' ? 'success' : 'danger'" 
                size="small"
              >
                {{ scope.row.order_type === 'BUY' ? '買入' : '賣出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="price" label="價格">
            <template #default="scope">
              {{ formatPrice(scope.row.price) }}
            </template>
          </el-table-column>
          <el-table-column prop="quantity" label="數量">
            <template #default="scope">
              {{ formatQuantity(scope.row.quantity) }}
            </template>
          </el-table-column>
          <el-table-column prop="status" label="狀態">
            <template #default="scope">
              <el-tag 
                :type="orderStatusType(scope.row.status)" 
                size="small"
              >
                {{ orderStatusText(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="創建時間">
            <template #default="scope">
              {{ formatDateTime(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column prop="profit" label="盈利" v-if="scope.row.profit">
            <template #default="scope">
              <span :class="profitClass(scope.row.profit)">
                {{ formatProfit(scope.row.profit) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// 註冊必要的 echarts 組件
echarts.use([
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  CanvasRenderer
]);

const props = defineProps({
  strategy: {
    type: Object,
    required: true
  },
  orders: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  actionLoading: {
    type: Boolean,
    default: false
  }
});

defineEmits(['start', 'stop', 'delete', 'back']);

// UI 元素引用
const chartRef = ref(null);
let chartInstance = null;

// 計算屬性
const statusText = computed(() => {
  switch (props.strategy.status) {
    case 'RUNNING':
      return '運行中';
    case 'STOPPED':
      return '已停止';
    case 'CREATED':
      return '未啟動';
    case 'COMPLETED':
      return '已完成';
    case 'FAILED':
      return '失敗';
    default:
      return props.strategy.status;
  }
});

const statusTagType = computed(() => {
  switch (props.strategy.status) {
    case 'RUNNING':
      return 'success';
    case 'STOPPED':
      return 'info';
    case 'CREATED':
      return 'warning';
    case 'FAILED':
      return 'danger';
    case 'COMPLETED':
      return 'success';
    default:
      return 'info';
  }
});

const gridTypeText = computed(() => {
  switch (props.strategy.grid_type) {
    case 'ARITHMETIC':
      return '等差網格';
    case 'GEOMETRIC':
      return '等比網格';
    default:
      return props.strategy.grid_type;
  }
});

const strategyTypeText = computed(() => {
  switch (props.strategy.strategy_type) {
    case 'LONG':
      return '做多';
    case 'SHORT':
      return '做空';
    case 'NEUTRAL':
      return '中性';
    default:
      return props.strategy.strategy_type;
  }
});

const exchangeText = computed(() => {
  switch (props.strategy.exchange) {
    case 'BINANCE':
      return 'Binance';
    case 'BYBIT':
      return 'Bybit';
    case 'OKX':
      return 'OKX';
    default:
      return props.strategy.exchange;
  }
});

const canStart = computed(() => {
  return props.strategy.status === 'CREATED' || props.strategy.status === 'STOPPED';
});

const canStop = computed(() => {
  return props.strategy.status === 'RUNNING';
});

const canDelete = computed(() => {
  return props.strategy.status !== 'RUNNING';
});

const hasRunningData = computed(() => {
  return props.strategy.status === 'RUNNING' || props.strategy.realized_pnl || props.strategy.unrealized_pnl;
});

const totalPnl = computed(() => {
  const realized = props.strategy.realized_pnl || 0;
  const unrealized = props.strategy.unrealized_pnl || 0;
  return realized + unrealized;
});

const pnlPercentage = computed(() => {
  if (!props.strategy.total_investment || props.strategy.total_investment === 0) return null;
  
  const percentage = (totalPnl.value / props.strategy.total_investment) * 100;
  return percentage.toFixed(2);
});

// 格式化輔助函數
function formatPrice(price) {
  if (!price && price !== 0) return '-';
  return price.toFixed(2);
}

function formatQuantity(quantity) {
  if (!quantity && quantity !== 0) return '-';
  return quantity.toFixed(4);
}

function formatProfit(profit) {
  if (!profit && profit !== 0) return '-';
  return profit > 0 
    ? `+${profit.toFixed(4)} USDT` 
    : `${profit.toFixed(4)} USDT`;
}

function profitClass(profit) {
  if (!profit && profit !== 0) return '';
  return profit > 0 ? 'profit-positive' : profit < 0 ? 'profit-negative' : '';
}

function formatDateTime(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function orderStatusText(status) {
  switch (status) {
    case 'FILLED':
      return '已成交';
    case 'PARTIALLY_FILLED':
      return '部分成交';
    case 'PENDING':
      return '等待中';
    case 'CANCELED':
      return '已取消';
    case 'REJECTED':
      return '已拒絕';
    case 'EXPIRED':
      return '已過期';
    default:
      return status;
  }
}

function orderStatusType(status) {
  switch (status) {
    case 'FILLED':
      return 'success';
    case 'PARTIALLY_FILLED':
      return 'warning';
    case 'PENDING':
      return 'info';
    case 'CANCELED':
      return 'info';
    case 'REJECTED':
      return 'danger';
    case 'EXPIRED':
      return 'info';
    default:
      return 'info';
  }
}

// 初始化和更新圖表
const initChart = () => {
  if (!chartRef.value) return;
  
  // 如果已經創建了實例，先銷毀
  if (chartInstance) {
    chartInstance.dispose();
  }
  
  // 創建新的實例
  chartInstance = echarts.init(chartRef.value);
  
  // 更新圖表
  updateChart();
};

const updateChart = () => {
  if (!chartInstance || !props.strategy) return;

  const { lower_price, upper_price, grid_number, grid_type } = props.strategy;
  
  // 生成網格價格點
  const gridPoints = [];
  
  if (grid_type === 'ARITHMETIC') {
    // 等差網格
    const step = (upper_price - lower_price) / (grid_number - 1);
    for (let i = 0; i < grid_number; i++) {
      gridPoints.push(lower_price + step * i);
    }
  } else {
    // 等比網格
    const ratio = Math.pow(upper_price / lower_price, 1 / (grid_number - 1));
    for (let i = 0; i < grid_number; i++) {
      gridPoints.push(lower_price * Math.pow(ratio, i));
    }
  }
  
  // 當前價格線
  const currentPrice = props.strategy.current_price;
  
  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: gridPoints.map((_, index) => `網格${index + 1}`)
    },
    yAxis: {
      type: 'value',
      name: '價格 (USDT)',
      axisLabel: {
        formatter: '{value}'
      }
    },
    series: [
      {
        name: '網格價格',
        type: 'line',
        data: gridPoints,
        markPoint: currentPrice ? {
          data: [
            { name: '當前價格', value: currentPrice, xAxis: -1, yAxis: currentPrice }
          ],
          symbolSize: 40,
          itemStyle: {
            color: '#409EFF'
          },
          label: {
            formatter: '{b}: {c}'
          }
        } : {}
      }
    ]
  };
  
  chartInstance.setOption(option);
};

// 監聽策略數據變化，更新圖表
watch(() => props.strategy, () => {
  updateChart();
}, { deep: true });

// 監聽窗口大小變化，調整圖表大小
const handleResize = () => {
  if (chartInstance) {
    chartInstance.resize();
  }
};

onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
});

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.grid-strategy-detail {
  width: 100%;
}

.detail-card {
  margin-bottom: 1rem;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.strategy-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.strategy-actions {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.section-container {
  margin-top: 1.5rem;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 500;
  margin-bottom: 1rem;
  color: var(--el-text-color-primary);
}

.data-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.data-card {
  text-align: center;
}

.data-card-title {
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
  margin-bottom: 0.5rem;
}

.data-card-value {
  font-size: 1.25rem;
  font-weight: 600;
}

.chart-container {
  width: 100%;
  height: 400px;
  margin-bottom: 1rem;
}

.profit-positive {
  color: var(--el-color-success);
}

.profit-negative {
  color: var(--el-color-danger);
}

.profit-percentage {
  font-size: 0.875rem;
  opacity: 0.8;
}

@media (max-width: 768px) {
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .data-cards {
    grid-template-columns: 1fr 1fr;
  }
  
  .chart-container {
    height: 300px;
  }
}
</style> 