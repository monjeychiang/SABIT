<template>
  <div class="trade-panel">
    <div class="panel-header">
      <h2>交易{{ formatSymbol(symbol) }}</h2>
    </div>
    
    <el-tabs v-model="activeTab" class="trade-tabs">
      <el-tab-pane label="限价单" name="limit">
        <div class="trade-form">
          <div class="price-input">
            <label>价格 (USDT)</label>
            <el-input-number
              v-model="limitPrice"
              :min="0"
              :precision="getPricePrecision(currentPrice)"
              :step="getPriceStep(currentPrice)"
              :placeholder="formatPrice(currentPrice)"
              class="full-width"
            />
      </div>
          
          <div class="amount-input">
            <label>数量</label>
            <el-input-number
              v-model="amount"
              :min="0"
              :precision="4"
              :step="0.0001"
              class="full-width"
            />
    </div>
    
          <div class="slider-container">
            <el-slider
              v-model="percentage"
              :marks="{0: '0%', 25: '25%', 50: '50%', 75: '75%', 100: '100%'}"
              :step="1"
              :min="0"
              :max="100"
              :show-stops="true"
              @change="updateAmountFromPercentage"
            />
      </div>
          
          <div class="total-container">
            <label>总额 (USDT)</label>
            <div class="total-value">{{ calculateTotal() }}</div>
    </div>
    
          <div class="action-buttons">
            <el-button type="success" class="buy-button" @click="handleTrade('buy')">
              买入
            </el-button>
            <el-button type="danger" class="sell-button" @click="handleTrade('sell')">
              卖出
            </el-button>
          </div>
        </div>
      </el-tab-pane>
      
      <el-tab-pane label="市价单" name="market">
        <div class="trade-form">
          <div class="price-input">
            <label>价格</label>
            <div class="market-price">市价</div>
          </div>
          
          <div class="amount-input">
            <label>数量</label>
            <el-input-number
              v-model="amount"
              :min="0"
              :precision="4"
              :step="0.0001"
              class="full-width"
            />
      </div>
      
          <div class="slider-container">
            <el-slider
              v-model="percentage"
              :marks="{0: '0%', 25: '25%', 50: '50%', 75: '75%', 100: '100%'}"
              :step="1"
              :min="0"
              :max="100"
              :show-stops="true"
              @change="updateAmountFromPercentage"
        />
      </div>
      
          <div class="total-container">
            <label>大约总额 (USDT)</label>
            <div class="total-value">{{ calculateTotal() }}</div>
      </div>
      
          <div class="action-buttons">
            <el-button type="success" class="buy-button" @click="handleTrade('buy', 'market')">
              市价买入
            </el-button>
            <el-button type="danger" class="sell-button" @click="handleTrade('sell', 'market')">
              市价卖出
            </el-button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
    
    <div class="account-info">
      <div class="balance-row">
        <span>可用USDT:</span>
        <span>1000.00</span>
      </div>
      <div class="balance-row">
        <span>可用{{ getBaseCurrency(symbol) }}:</span>
        <span>0.00</span>
      </div>
    </div>
    
    <div class="trade-orders">
      <h3>当前订单</h3>
      <div class="no-orders">
        暂无交易订单
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'

// 定义组件的props
const props = defineProps({
  symbol: {
    type: String,
    required: true
  },
  marketType: {
    type: String,
    required: true
  },
  currentPrice: {
    type: Number,
    required: true
  }
})

// 响应式状态
const activeTab = ref('limit')
const limitPrice = ref(props.currentPrice)
const amount = ref(0)
const percentage = ref(0)
const availableBalance = ref(1000) // 模拟余额，实际应从API获取

// 监视价格变化
watch(() => props.currentPrice, (newPrice) => {
  if (activeTab.value === 'limit' && limitPrice.value === 0) {
    limitPrice.value = newPrice
  }
})

// 格式化交易对符号
const formatSymbol = (symbol) => {
  if (symbol.endsWith('USDT')) {
    return symbol.replace('USDT', '') + '/USDT'
  }
  return symbol
}

// 获取基础货币
const getBaseCurrency = (symbol) => {
  if (symbol.endsWith('USDT')) {
    return symbol.replace('USDT', '')
  }
  return symbol.split('/')[0]
}

// 获取价格精度
const getPricePrecision = (price) => {
  if (price >= 1000) {
    return 2
  } else if (price >= 1) {
    return 4
  } else if (price >= 0.0001) {
    return 6
  } else {
    return 8
  }
}

// 获取价格步长
const getPriceStep = (price) => {
  if (price >= 1000) {
    return 0.01
  } else if (price >= 1) {
    return 0.0001
  } else if (price >= 0.0001) {
    return 0.000001
  } else {
    return 0.00000001
  }
}

// 格式化价格
const formatPrice = (price) => {
  if (price === undefined || price === null) return '-'
  
  const precision = getPricePrecision(price)
  return price.toFixed(precision)
}

// 计算总额
const calculateTotal = () => {
  const price = activeTab.value === 'limit' ? limitPrice.value : props.currentPrice
  const total = price * amount.value
  return total.toFixed(2)
}

// 根据百分比更新数量
const updateAmountFromPercentage = (value) => {
  if (activeTab.value === 'limit' && limitPrice.value > 0) {
    amount.value = (availableBalance.value * (value / 100)) / limitPrice.value
  } else if (props.currentPrice > 0) {
    amount.value = (availableBalance.value * (value / 100)) / props.currentPrice
  }
}

// 处理交易
const handleTrade = (direction, type = 'limit') => {
  if (amount.value <= 0) {
    ElMessage.warning('请输入有效的交易数量')
    return
  }
  
  if (type === 'limit' && limitPrice.value <= 0) {
    ElMessage.warning('请输入有效的价格')
    return
  }
  
  // 这里只是模拟交易，实际应调用API
  const price = type === 'limit' ? limitPrice.value : props.currentPrice
  const total = price * amount.value
  
  if (direction === 'buy' && total > availableBalance.value) {
    ElMessage.error('余额不足')
    return
  }
  
  ElMessage.success(`已提交${type === 'limit' ? '限价' : '市价'}${direction === 'buy' ? '买入' : '卖出'}订单: ${amount.value} ${getBaseCurrency(props.symbol)} @ ${formatPrice(price)} USDT`)
  
  // 重置表单
  amount.value = 0
  percentage.value = 0
}
</script>

<style scoped>
.trade-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  color: var(--el-text-color-primary);
  background-color: var(--el-bg-color-overlay);
  border-radius: 4px;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.panel-header {
  margin-bottom: 16px;
}

.panel-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.trade-tabs {
  margin-bottom: 16px;
}

.trade-tabs :deep(.el-tabs__item) {
  color: var(--el-text-color-secondary);
  transition: color 0.3s ease;
}

.trade-tabs :deep(.el-tabs__item.is-active) {
  color: var(--el-color-primary);
}

.trade-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--el-color-primary);
}

.trade-tabs :deep(.el-tabs__nav-wrap::after) {
  background-color: var(--el-border-color);
  transition: background-color 0.3s ease;
}

.trade-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.price-input,
.amount-input,
.total-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.price-input label,
.amount-input label,
.total-container label {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  transition: color 0.3s ease;
}

.full-width {
  width: 100%;
}

.full-width :deep(.el-input-number__decrease),
.full-width :deep(.el-input-number__increase) {
  background-color: var(--el-fill-color);
  color: var(--el-text-color-regular);
  border-color: var(--el-border-color);
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}

.full-width :deep(.el-input__wrapper) {
  background-color: var(--el-fill-color);
  box-shadow: 0 0 0 1px var(--el-border-color) inset;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.full-width :deep(.el-input__inner) {
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.market-price {
  padding: 8px 12px;
  background-color: var(--el-fill-color);
  border-radius: 4px;
  font-weight: 500;
  text-align: center;
  transition: background-color 0.3s ease, border-color 0.3s ease;
  border: 1px solid var(--el-border-color);
  color: var(--el-text-color-primary);
}

.slider-container {
  margin: 8px 0;
}

.slider-container :deep(.el-slider__runway) {
  background-color: var(--el-border-color);
  transition: background-color 0.3s ease;
}

.slider-container :deep(.el-slider__bar) {
  background-color: var(--el-color-primary);
  transition: background-color 0.3s ease;
}

.slider-container :deep(.el-slider__button) {
  border-color: var(--el-color-primary);
  transition: border-color 0.3s ease;
}

.slider-container :deep(.el-slider__marks-text) {
  color: var(--el-text-color-secondary);
  transition: color 0.3s ease;
}

.total-value {
  font-size: 16px;
  font-weight: 500;
  padding: 8px 0;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.action-buttons {
  display: flex;
  gap: 12px;
  margin-top: 8px;
}

.buy-button,
.sell-button {
  flex: 1;
  padding: 10px 0;
  font-weight: 500;
}

.action-buttons :deep(.el-button--success) {
  background-color: var(--el-color-success);
  border-color: var(--el-color-success);
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

.action-buttons :deep(.el-button--danger) {
  background-color: var(--el-color-danger);
  border-color: var(--el-color-danger);
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

.account-info {
  margin-top: 24px;
  padding: 16px;
  background-color: var(--el-fill-color);
  border-radius: 4px;
  transition: background-color 0.3s ease;
  border: 1px solid var(--el-border-color);
}

.balance-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.balance-row:last-child {
  margin-bottom: 0;
}

.trade-orders {
  margin-top: 24px;
}

.trade-orders h3 {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
  transition: color 0.3s ease;
}

.no-orders {
  padding: 24px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  background-color: var(--el-fill-color);
  border-radius: 4px;
  font-size: 14px;
  transition: background-color 0.3s ease, color 0.3s ease;
  border: 1px solid var(--el-border-color);
}
</style> 
