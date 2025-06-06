<template>
  <div class="grid-strategy-form">
    <slot name="form-header">
      <h3 class="form-title">
        {{ isEditing ? '編輯網格策略' : '創建新網格策略' }}
      </h3>
    </slot>

    <el-form 
      ref="formRef" 
      :model="formData" 
      :rules="formRules" 
      label-position="top"
      class="grid-form"
    >
      <!-- 基本資訊 -->
      <div class="form-section">
        <h4 class="section-title">基本資訊</h4>
        
        <div class="form-row">
          <el-form-item label="交易對" prop="symbol">
            <el-select 
              v-model="formData.symbol" 
              placeholder="選擇交易對" 
              filterable
            >
              <el-option 
                v-for="symbol in availableSymbols" 
                :key="symbol" 
                :label="symbol" 
                :value="symbol"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="交易所" prop="exchange">
            <el-select 
              v-model="formData.exchange" 
              placeholder="選擇交易所"
            >
              <el-option label="Binance" value="BINANCE" />
              <el-option label="Bybit" value="BYBIT" disabled />
              <el-option label="OKX" value="OKX" disabled />
            </el-select>
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="網格類型" prop="grid_type">
            <el-radio-group v-model="formData.grid_type">
              <el-radio-button label="ARITHMETIC">等差網格</el-radio-button>
              <el-radio-button label="GEOMETRIC">等比網格</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="策略方向" prop="strategy_type">
            <el-radio-group v-model="formData.strategy_type">
              <el-radio-button label="LONG">做多</el-radio-button>
              <el-radio-button label="SHORT">做空</el-radio-button>
              <el-radio-button label="NEUTRAL">中性</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </div>
      </div>

      <!-- 價格設置 -->
      <div class="form-section">
        <h4 class="section-title">價格設置</h4>
        
        <div class="form-row">
          <el-form-item label="最低價格（USDT）" prop="lower_price">
            <el-input-number 
              v-model="formData.lower_price" 
              :min="0" 
              :precision="tokenDecimals" 
              :step="0.1"
            />
          </el-form-item>

          <el-form-item label="最高價格（USDT）" prop="upper_price">
            <el-input-number 
              v-model="formData.upper_price" 
              :min="0" 
              :precision="tokenDecimals" 
              :step="0.1"
            />
          </el-form-item>
          
          <el-form-item label="網格數量" prop="grid_number">
            <el-input-number 
              v-model="formData.grid_number" 
              :min="4" 
              :max="100"
              :precision="0" 
              :step="1"
            />
          </el-form-item>
        </div>

        <div class="price-preview" v-if="showPricePreview">
          <div>網格均價：{{ averageGridPrice }} USDT</div>
          <div>預計每格利潤：{{ profitPerGrid }}%</div>
        </div>
      </div>

      <!-- 投資設置 -->
      <div class="form-section">
        <h4 class="section-title">投資設置</h4>
        
        <div class="form-row">
          <el-form-item label="總投資額（USDT）" prop="total_investment">
            <el-input-number 
              v-model="formData.total_investment" 
              :min="10" 
              :precision="2" 
              :step="10"
            />
          </el-form-item>

          <el-form-item label="槓桿倍數" prop="leverage">
            <el-input-number 
              v-model="formData.leverage" 
              :min="1" 
              :max="125" 
              :precision="0" 
              :step="1"
            />
          </el-form-item>
        </div>
      </div>

      <!-- 風控設置 -->
      <div class="form-section">
        <h4 class="section-title">風控設置（選填）</h4>
        
        <div class="form-row">
          <el-form-item label="止損比例 (%)" prop="stop_loss_percentage">
            <el-input-number 
              v-model="formData.stop_loss_percentage" 
              :min="0" 
              :max="100" 
              :precision="1"
              :step="0.1"
            />
          </el-form-item>

          <el-form-item label="止盈比例 (%)" prop="take_profit_percentage">
            <el-input-number 
              v-model="formData.take_profit_percentage" 
              :min="0" 
              :max="1000" 
              :precision="1"
              :step="0.1"
            />
          </el-form-item>
        </div>

        <div class="form-row">
          <el-form-item label="盈利收集比例 (%)" prop="profit_collection_percentage">
            <el-input-number 
              v-model="formData.profit_collection_percentage" 
              :min="0" 
              :max="100" 
              :precision="1"
              :step="5"
            />
          </el-form-item>
        </div>
      </div>

      <!-- 確認按鈕 -->
      <div class="form-actions">
        <el-button @click="$emit('cancel')">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submitForm">
          {{ isEditing ? '更新策略' : '創建策略' }}
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue';
import { ElMessage } from 'element-plus';

const props = defineProps({
  strategy: {
    type: Object,
    default: () => null
  },
  loading: {
    type: Boolean,
    default: false
  },
  availableSymbols: {
    type: Array,
    default: () => ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'XRP/USDT', 'ADA/USDT', 'SOL/USDT']
  }
});

const emit = defineEmits(['submit', 'cancel']);

// 表單引用
const formRef = ref(null);

// 判斷是否是編輯模式
const isEditing = computed(() => props.strategy !== null);

// 初始化表單數據
const defaultFormData = {
  symbol: '',
  exchange: 'BINANCE',
  grid_type: 'ARITHMETIC',
  strategy_type: 'NEUTRAL',
  lower_price: null,
  upper_price: null,
  grid_number: 10,
  total_investment: 100,
  leverage: 1,
  stop_loss_percentage: 0,
  take_profit_percentage: 0,
  profit_collection_percentage: 0
};

const formData = reactive({ ...defaultFormData });

// 如果是編輯模式，則使用傳入的策略數據
watch(() => props.strategy, (newStrategy) => {
  if (newStrategy) {
    Object.keys(formData).forEach(key => {
      if (newStrategy[key] !== undefined) {
        formData[key] = newStrategy[key];
      }
    });
  } else {
    // 重置表單
    Object.keys(formData).forEach(key => {
      formData[key] = defaultFormData[key];
    });
  }
}, { immediate: true });

// 表單驗證規則
const formRules = {
  symbol: [{ required: true, message: '請選擇交易對', trigger: 'change' }],
  exchange: [{ required: true, message: '請選擇交易所', trigger: 'change' }],
  grid_type: [{ required: true, message: '請選擇網格類型', trigger: 'change' }],
  strategy_type: [{ required: true, message: '請選擇策略方向', trigger: 'change' }],
  lower_price: [
    { required: true, message: '請輸入最低價格', trigger: 'blur' },
    { type: 'number', min: 0, message: '最低價格必須大於0', trigger: 'blur' }
  ],
  upper_price: [
    { required: true, message: '請輸入最高價格', trigger: 'blur' },
    { type: 'number', min: 0, message: '最高價格必須大於0', trigger: 'blur' }
  ],
  grid_number: [
    { required: true, message: '請輸入網格數量', trigger: 'blur' },
    { type: 'number', min: 4, message: '網格數量至少需要4個', trigger: 'blur' }
  ],
  total_investment: [
    { required: true, message: '請輸入總投資額', trigger: 'blur' },
    { type: 'number', min: 10, message: '總投資額至少需要10 USDT', trigger: 'blur' }
  ],
  leverage: [
    { required: true, message: '請輸入槓桿倍數', trigger: 'blur' },
    { type: 'number', min: 1, message: '槓桿倍數至少為1', trigger: 'blur' }
  ]
};

// 根據交易對判斷小數點位數
const tokenDecimals = computed(() => {
  if (!formData.symbol) return 2;
  return formData.symbol.includes('BTC') ? 2 : 
         formData.symbol.includes('ETH') ? 2 : 
         formData.symbol.includes('BNB') ? 3 : 4;
});

// 顯示價格預覽的條件
const showPricePreview = computed(() => {
  return formData.lower_price && formData.upper_price && formData.grid_number;
});

// 計算網格均價
const averageGridPrice = computed(() => {
  if (!showPricePreview.value) return '-';
  
  const { lower_price, upper_price } = formData;
  return ((lower_price + upper_price) / 2).toFixed(tokenDecimals.value);
});

// 計算每格預計利潤百分比
const profitPerGrid = computed(() => {
  if (!showPricePreview.value) return '-';
  
  const { lower_price, upper_price, grid_number, grid_type } = formData;
  
  if (grid_type === 'ARITHMETIC') {
    // 等差網格每格利潤相同
    const profit = ((upper_price - lower_price) / lower_price) * 100 / (grid_number - 1);
    return profit.toFixed(2);
  } else {
    // 等比網格每格利潤相同百分比
    const ratio = Math.pow(upper_price / lower_price, 1 / (grid_number - 1));
    return ((ratio - 1) * 100).toFixed(2);
  }
});

// 提交表單
const submitForm = async () => {
  if (!formRef.value) return;
  
  try {
    await formRef.value.validate();
    
    // 驗證價格範圍
    if (formData.lower_price >= formData.upper_price) {
      ElMessage.error('最低價格必須小於最高價格');
      return;
    }
    
    // 發出提交事件
    emit('submit', { ...formData });
  } catch (error) {
    console.error('表單驗證失敗', error);
  }
};
</script>

<style scoped>
.grid-strategy-form {
  background-color: var(--el-bg-color);
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: var(--el-box-shadow-light);
}

.form-title {
  margin-top: 0;
  margin-bottom: 1.5rem;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.form-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid var(--el-border-color-light);
}

.form-section:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.section-title {
  margin-top: 0;
  margin-bottom: 1rem;
  font-size: 1.1rem;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.price-preview {
  margin-top: 1rem;
  padding: 0.75rem;
  background-color: var(--el-color-info-light-9);
  border-radius: 4px;
  font-size: 0.875rem;
  color: var(--el-text-color-secondary);
  display: flex;
  justify-content: space-between;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 2rem;
  gap: 1rem;
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .price-preview {
    flex-direction: column;
    gap: 0.5rem;
  }
}
</style> 