<template>
  <div class="grid-trading-page dashboard-container">
    <!-- 頁面標題 -->
    <div class="page-header">
      <h1 class="page-title">網格交易策略</h1>
      <p class="page-description">
        自動化套利交易，無需持續盯盤。通過設定價格區間，利用市場波動自動低買高賣，穩定獲利。
      </p>
    </div>

    <!-- 控制區域 -->
    <div class="controls-container">
      <div class="exchange-selector">
        <span class="selector-label">交易所：</span>
        <el-select v-model="selectedExchange" placeholder="選擇交易所">
          <el-option label="Binance" value="BINANCE" />
          <el-option label="Bybit" value="BYBIT" disabled />
          <el-option label="OKX" value="OKX" disabled />
        </el-select>
      </div>

      <div class="action-buttons">
        <el-button 
          type="primary" 
          :icon="Plus"
          @click="showCreateForm = true"
        >
          創建策略
        </el-button>
        <el-button 
          :icon="Refresh"
          @click="fetchStrategies"
          :loading="loading"
        >
          刷新
        </el-button>
      </div>
    </div>

    <!-- 載入中和錯誤提示 -->
    <div v-if="loading && !strategies.length" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <div v-if="error" class="error-message">
      <el-alert 
        type="error" 
        :title="error" 
        show-icon
        :closable="false"
      />
    </div>

    <!-- 策略列表區域 -->
    <div v-if="!loading || strategies.length > 0">
      <!-- 運行中策略 -->
      <GridStrategyList
        title="運行中的策略"
        :strategies="runningStrategies"
        emptyText="目前沒有運行中的策略"
        @view="viewStrategyDetails"
        @start="handleStartStrategy"
        @stop="showStopConfirm"
        @delete="showDeleteConfirm"
      />

      <!-- 已停止策略 -->
      <GridStrategyList
        title="已停止的策略"
        :strategies="stoppedStrategies"
        emptyText="目前沒有已停止的策略"
        @view="viewStrategyDetails"
        @start="handleStartStrategy"
        @stop="showStopConfirm"
        @delete="showDeleteConfirm"
      />

      <!-- 無策略提示 -->
      <div v-if="!strategies.length && !loading" class="empty-state">
        <div class="empty-icon">
          <i class="fas fa-project-diagram"></i>
        </div>
        <h3>還沒有任何網格交易策略</h3>
        <p>創建你的第一個網格交易策略，開始自動化套利！</p>
        <el-button type="primary" @click="showCreateForm = true">
          創建網格策略
        </el-button>
      </div>
    </div>

    <!-- 查看策略詳情區域 -->
    <el-drawer
      v-model="showDetail"
      direction="rtl"
      size="80%"
      :destroy-on-close="true"
      :with-header="false"
    >
      <div v-if="currentStrategy" class="strategy-detail-container">
        <GridStrategyDetail
          :strategy="currentStrategy"
          :orders="currentOrders"
          :loading="detailLoading"
          :actionLoading="actionLoading"
          @start="handleStartStrategy(currentStrategy)"
          @stop="showStopConfirm(currentStrategy)"
          @delete="showDeleteConfirm(currentStrategy)"
          @back="showDetail = false"
        />
      </div>
    </el-drawer>

    <!-- 創建/編輯策略表單 -->
    <el-drawer
      v-model="showCreateForm"
      direction="rtl"
      size="80%"
      :destroy-on-close="true"
      title="創建網格策略"
    >
      <GridStrategyForm
        :strategy="editingStrategy"
        :loading="formSubmitting"
        @submit="handleFormSubmit"
        @cancel="handleFormCancel"
      />
    </el-drawer>

    <!-- 刪除確認對話框 -->
    <GridDeleteConfirm
      v-if="strategyToDelete"
      v-model="showDeleteDialog"
      :strategy="strategyToDelete"
      :loading="actionLoading"
      :hasOrders="hasOrders"
      @confirm="handleDeleteConfirm"
      @cancel="strategyToDelete = null"
    />

    <!-- 停止策略確認 -->
    <el-dialog
      v-model="showStopDialog"
      title="確認停止"
      width="400px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="confirm-content" v-if="strategyToStop">
        <p class="confirm-message">
          確定要停止「{{ strategyToStop.symbol }}」的網格策略嗎？
        </p>
        <p class="confirm-warning">
          <i class="fas fa-info-circle"></i>
          停止策略後，所有未完成的訂單將被取消，您可以稍後重新啟動策略。
        </p>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="strategyToStop = null">取消</el-button>
          <el-button type="warning" :loading="actionLoading" @click="handleStopConfirm">
            確認停止
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElLoading } from 'element-plus';
import { Plus, Refresh } from '@element-plus/icons-vue';

// 導入組件
import GridStrategyList from '@/components/grid/GridStrategyList.vue';
import GridStrategyDetail from '@/components/grid/GridStrategyDetail.vue';
import GridStrategyForm from '@/components/grid/GridStrategyForm.vue';
import GridDeleteConfirm from '@/components/grid/GridDeleteConfirm.vue';

// 路由
const router = useRouter();

// 狀態管理
const loading = ref(false);
const error = ref('');
const strategies = ref([]);
const selectedExchange = ref('BINANCE');

// 表單狀態
const showCreateForm = ref(false);
const editingStrategy = ref(null);
const formSubmitting = ref(false);

// 詳情狀態
const showDetail = ref(false);
const currentStrategy = ref(null);
const currentOrders = ref([]);
const detailLoading = ref(false);

// 刪除確認狀態
const showDeleteDialog = ref(false);
const strategyToDelete = ref(null);

// 停止確認狀態
const showStopDialog = ref(false);
const strategyToStop = ref(null);

// 通用狀態
const actionLoading = ref(false);
const hasOrders = ref(false);

// 計算屬性
const runningStrategies = computed(() => {
  return strategies.value.filter(s => s.status === 'RUNNING');
});

const stoppedStrategies = computed(() => {
  return strategies.value.filter(s => s.status !== 'RUNNING');
});

// 生命週期鉤子
onMounted(async () => {
  await fetchStrategies();
});

// 方法
const fetchStrategies = async () => {
  loading.value = true;
  error.value = '';

  try {
    // TODO: 實際調用API
    // const response = await fetch('/api/grid-trading/strategies');
    // strategies.value = await response.json();

    // 模擬數據
    await new Promise(resolve => setTimeout(resolve, 500));
    
    strategies.value = [
      {
        id: 1,
        symbol: 'BTC/USDT',
        exchange: 'BINANCE',
        grid_type: 'ARITHMETIC',
        strategy_type: 'NEUTRAL',
        grid_number: 10,
        lower_price: 50000,
        upper_price: 60000,
        total_investment: 1000,
        leverage: 1,
        stop_loss_percentage: 5,
        take_profit_percentage: 20,
        profit_collection_percentage: 50,
        status: 'RUNNING',
        current_price: 55000,
        realized_pnl: 50.25,
        unrealized_pnl: 25.75,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      {
        id: 2,
        symbol: 'ETH/USDT',
        exchange: 'BINANCE',
        grid_type: 'GEOMETRIC',
        strategy_type: 'LONG',
        grid_number: 8,
        lower_price: 2800,
        upper_price: 3500,
        total_investment: 500,
        leverage: 2,
        stop_loss_percentage: 10,
        take_profit_percentage: 30,
        profit_collection_percentage: 0,
        status: 'STOPPED',
        realized_pnl: 15.50,
        created_at: new Date(Date.now() - 86400000).toISOString(),
        updated_at: new Date(Date.now() - 3600000).toISOString()
      }
    ];
  } catch (err) {
    console.error('獲取策略失敗', err);
    error.value = '獲取策略失敗，請稍後重試';
  } finally {
    loading.value = false;
  }
};

const fetchStrategyDetails = async (id) => {
  detailLoading.value = true;
  
  try {
    // TODO: 實際調用API
    // const strategyResponse = await fetch(`/api/grid-trading/strategies/${id}`);
    // const ordersResponse = await fetch(`/api/grid-trading/strategies/${id}/orders`);
    // currentStrategy.value = await strategyResponse.json();
    // currentOrders.value = await ordersResponse.json();
    
    // 模擬數據
    await new Promise(resolve => setTimeout(resolve, 300));
    
    const strategy = strategies.value.find(s => s.id === id);
    if (!strategy) throw new Error('策略不存在');
    
    currentStrategy.value = { ...strategy };
    
    // 模擬訂單數據
    currentOrders.value = [
      {
        order_id: 'ORD123456',
        strategy_id: id,
        order_type: 'BUY',
        price: strategy.lower_price + (strategy.upper_price - strategy.lower_price) * 0.3,
        quantity: 0.02,
        status: 'FILLED',
        created_at: new Date(Date.now() - 3600000).toISOString(),
        profit: null
      },
      {
        order_id: 'ORD123457',
        strategy_id: id,
        order_type: 'SELL',
        price: strategy.lower_price + (strategy.upper_price - strategy.lower_price) * 0.4,
        quantity: 0.02,
        status: 'FILLED',
        created_at: new Date(Date.now() - 1800000).toISOString(),
        profit: 15.25
      },
      {
        order_id: 'ORD123458',
        strategy_id: id,
        order_type: 'BUY',
        price: strategy.lower_price + (strategy.upper_price - strategy.lower_price) * 0.25,
        quantity: 0.025,
        status: 'PENDING',
        created_at: new Date().toISOString(),
        profit: null
      }
    ];
    
    hasOrders.value = currentOrders.value.length > 0;
  } catch (err) {
    console.error('獲取策略詳情失敗', err);
    ElMessage.error('獲取策略詳情失敗，請稍後重試');
    showDetail.value = false;
  } finally {
    detailLoading.value = false;
  }
};

const viewStrategyDetails = async (id) => {
  showDetail.value = true;
  await fetchStrategyDetails(id);
};

const handleStartStrategy = async (strategy) => {
  actionLoading.value = true;
  
  try {
    // TODO: 實際調用API
    // await fetch(`/api/grid-trading/strategies/${strategy.id}/start`, { method: 'POST' });
    
    // 模擬API調用
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // 更新狀態
    const index = strategies.value.findIndex(s => s.id === strategy.id);
    if (index !== -1) {
      strategies.value[index].status = 'RUNNING';
      strategies.value[index].updated_at = new Date().toISOString();
    }
    
    // 如果在詳情頁，更新當前策略
    if (currentStrategy.value && currentStrategy.value.id === strategy.id) {
      currentStrategy.value.status = 'RUNNING';
      currentStrategy.value.updated_at = new Date().toISOString();
    }
    
    ElMessage.success(`${strategy.symbol} 策略已成功啟動`);
  } catch (err) {
    console.error('啟動策略失敗', err);
    ElMessage.error('啟動策略失敗，請稍後重試');
  } finally {
    actionLoading.value = false;
  }
};

const showStopConfirm = (strategy) => {
  strategyToStop = ref(strategy);
  showStopDialog.value = true;
};

const handleStopConfirm = async () => {
  if (!strategyToStop.value) return;
  
  actionLoading.value = true;
  
  try {
    // TODO: 實際調用API
    // await fetch(`/api/grid-trading/strategies/${strategyToStop.value.id}/stop`, { method: 'POST' });
    
    // 模擬API調用
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // 更新狀態
    const index = strategies.value.findIndex(s => s.id === strategyToStop.value.id);
    if (index !== -1) {
      strategies.value[index].status = 'STOPPED';
      strategies.value[index].updated_at = new Date().toISOString();
    }
    
    // 如果在詳情頁，更新當前策略
    if (currentStrategy.value && currentStrategy.value.id === strategyToStop.value.id) {
      currentStrategy.value.status = 'STOPPED';
      currentStrategy.value.updated_at = new Date().toISOString();
    }
    
    ElMessage.success(`${strategyToStop.value.symbol} 策略已成功停止`);
  } catch (err) {
    console.error('停止策略失敗', err);
    ElMessage.error('停止策略失敗，請稍後重試');
  } finally {
    actionLoading.value = false;
    strategyToStop.value = null;
    showStopDialog.value = false;
  }
};

const showDeleteConfirm = async (strategy) => {
  strategyToDelete.value = strategy;
  
  // 檢查是否有訂單
  if (strategy.id === currentStrategy.value?.id) {
    hasOrders.value = currentOrders.value.length > 0;
  } else {
    // TODO: 實際調用API檢查
    // const ordersResponse = await fetch(`/api/grid-trading/strategies/${strategy.id}/orders`);
    // const orders = await ordersResponse.json();
    // hasOrders.value = orders.length > 0;
    
    // 模擬檢查
    hasOrders.value = Math.random() > 0.5;
  }
  
  showDeleteDialog.value = true;
};

const handleDeleteConfirm = async () => {
  if (!strategyToDelete.value) return;
  
  actionLoading.value = true;
  
  try {
    // TODO: 實際調用API
    // await fetch(`/api/grid-trading/strategies/${strategyToDelete.value.id}`, { method: 'DELETE' });
    
    // 模擬API調用
    await new Promise(resolve => setTimeout(resolve, 500));
    
    // 更新狀態
    strategies.value = strategies.value.filter(s => s.id !== strategyToDelete.value.id);
    
    // 如果在詳情頁，關閉詳情頁
    if (currentStrategy.value && currentStrategy.value.id === strategyToDelete.value.id) {
      showDetail.value = false;
      currentStrategy.value = null;
    }
    
    ElMessage.success(`${strategyToDelete.value.symbol} 策略已成功刪除`);
  } catch (err) {
    console.error('刪除策略失敗', err);
    ElMessage.error('刪除策略失敗，請稍後重試');
  } finally {
    actionLoading.value = false;
    strategyToDelete.value = null;
    showDeleteDialog.value = false;
  }
};

const handleFormSubmit = async (formData) => {
  formSubmitting.value = true;
  
  try {
    // TODO: 實際調用API
    // const method = editingStrategy.value ? 'PUT' : 'POST';
    // const url = editingStrategy.value 
    //   ? `/api/grid-trading/strategies/${editingStrategy.value.id}` 
    //   : '/api/grid-trading/strategies';
    
    // const response = await fetch(url, {
    //   method,
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(formData)
    // });
    
    // const result = await response.json();
    
    // 模擬API調用
    await new Promise(resolve => setTimeout(resolve, 800));
    
    if (editingStrategy.value) {
      // 更新策略
      const index = strategies.value.findIndex(s => s.id === editingStrategy.value.id);
      if (index !== -1) {
        strategies.value[index] = { 
          ...strategies.value[index], 
          ...formData, 
          updated_at: new Date().toISOString() 
        };
      }
      ElMessage.success('策略已成功更新');
    } else {
      // 新建策略
      const newStrategy = {
        id: Date.now(),
        ...formData,
        status: 'CREATED',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };
      strategies.value.push(newStrategy);
      ElMessage.success('策略已成功創建');
    }
    
    showCreateForm.value = false;
    editingStrategy.value = null;
  } catch (err) {
    console.error('提交策略失敗', err);
    ElMessage.error('提交策略失敗，請稍後重試');
  } finally {
    formSubmitting.value = false;
  }
};

const handleFormCancel = () => {
  showCreateForm.value = false;
  editingStrategy.value = null;
};
</script>

<style scoped>
.grid-trading-page {
  padding: 1.5rem;
}

.page-header {
  margin-bottom: 2rem;
}

.page-title {
  font-size: 1.75rem;
  margin-bottom: 0.5rem;
  color: var(--el-text-color-primary);
}

.page-description {
  color: var(--el-text-color-secondary);
  font-size: 1rem;
  max-width: 800px;
}

.controls-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  flex-wrap: wrap;
  gap: 1rem;
}

.exchange-selector {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.selector-label {
  color: var(--el-text-color-regular);
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.loading-container {
  padding: 2rem;
  background-color: var(--el-bg-color);
  border-radius: 8px;
  margin-bottom: 2rem;
}

.error-message {
  margin-bottom: 2rem;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  background-color: var(--el-bg-color);
  border-radius: 8px;
  border: 1px dashed var(--el-border-color);
}

.empty-icon {
  font-size: 3rem;
  color: var(--el-text-color-placeholder);
  margin-bottom: 1rem;
}

.strategy-detail-container {
  padding: 1.5rem;
}

.confirm-content {
  text-align: center;
  padding: 1rem 0;
}

.confirm-message {
  font-size: 1.125rem;
  margin-bottom: 1rem;
  color: var(--el-text-color-primary);
}

.confirm-warning {
  font-size: 0.875rem;
  color: var(--el-color-warning-dark-2);
  background-color: var(--el-color-warning-light-9);
  padding: 0.5rem;
  border-radius: 4px;
  margin-top: 1rem;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

@media (max-width: 768px) {
  .controls-container {
    flex-direction: column;
    align-items: stretch;
  }
  
  .action-buttons {
    justify-content: space-between;
  }
}
</style> 