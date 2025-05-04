<template>
  <div class="grid-form-view container">
    <div class="form-header">
      <h1>创建网格交易策略</h1>
      <p>通过设置以下参数创建一个新的网格交易策略。</p>
    </div>
    
    <div v-if="isLoading" class="loading-container card">
      <div class="loading-spinner"></div>
      <p>处理您的请求中...</p>
    </div>
    
    <div v-else-if="errorMessage" class="error-container card">
      <p>{{ errorMessage }}</p>
      <button @click="errorMessage = ''" class="btn btn-primary mt-3">关闭</button>
    </div>
    
    <div v-else-if="successMessage" class="success-container card">
      <p>{{ successMessage }}</p>
      <div class="success-actions">
        <router-link to="/" class="btn btn-primary">返回控制面板</router-link>
        <button @click="resetForm" class="btn btn-secondary">创建另一个</button>
      </div>
    </div>
    
    <form v-else @submit.prevent="createGrid" class="grid-form card">
      <div class="form-section">
        <h2>市场选择</h2>
        
        <div class="form-group">
          <label for="symbol">交易对</label>
          <select id="symbol" v-model="formData.symbol" required>
            <option value="">选择交易对</option>
            <option value="BTCUSDT">BTC/USDT - 比特币</option>
            <option value="ETHUSDT">ETH/USDT - 以太坊</option>
            <option value="BNBUSDT">BNB/USDT - 币安币</option>
            <option value="ADAUSDT">ADA/USDT - 卡尔达诺</option>
            <option value="DOGEUSDT">DOGE/USDT - 狗狗币</option>
            <option value="XRPUSDT">XRP/USDT - 瑞波币</option>
          </select>
        </div>
      </div>
      
      <div class="form-section">
        <h2>网格参数</h2>
        
        <div class="form-group">
          <label for="grid_type">网格类型</label>
          <select id="grid_type" v-model="formData.grid_type" required>
            <option value="">选择网格类型</option>
            <option value="arithmetic">算术网格 - 等价格差</option>
            <option value="geometric">几何网格 - 等百分比差</option>
          </select>
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label for="lower_price">下限价格 ($)</label>
            <input 
              type="number" 
              id="lower_price" 
              v-model.number="formData.lower_price" 
              step="0.01" 
              min="0" 
              required
              placeholder="例如: 20000"
            />
          </div>
          
          <div class="form-group">
            <label for="upper_price">上限价格 ($)</label>
            <input 
              type="number" 
              id="upper_price" 
              v-model.number="formData.upper_price" 
              step="0.01" 
              min="0" 
              required
              placeholder="例如: 30000"
            />
            <p v-if="priceRangeInvalid" class="field-error">上限价格必须大于下限价格</p>
          </div>
        </div>
        
        <div class="form-group">
          <label for="grid_levels">网格级别</label>
          <input 
            type="number" 
            id="grid_levels" 
            v-model.number="formData.grid_levels" 
            min="2" 
            max="100" 
            required
            placeholder="例如: 10"
          />
          <p class="field-help">下限价格和上限价格之间的网格线数量。更多的级别意味着更多的交易但每笔交易的利润更小。</p>
        </div>
      </div>
      
      <div class="form-section">
        <h2>投资</h2>
        
        <div class="form-group">
          <label for="investment">投资金额 ($)</label>
          <input 
            type="number" 
            id="investment" 
            v-model.number="formData.investment" 
            step="0.01" 
            min="10" 
            required
            placeholder="例如: 1000"
          />
        </div>
        
        <div class="form-group">
          <label for="leverage">杠杆</label>
          <select id="leverage" v-model.number="formData.leverage" required>
            <option value="1">1x (无杠杆)</option>
            <option value="2">2x</option>
            <option value="3">3x</option>
            <option value="5">5x</option>
            <option value="10">10x</option>
          </select>
          <p class="field-help">更高的杠杆会增加潜在利润和风险。</p>
        </div>
      </div>
      
      <div class="form-preview card">
        <h2 class="mb-3">策略预览</h2>
        <div class="preview-stats">
          <div class="preview-stat">
            <span class="stat-label">价格范围</span>
            <span class="stat-value">${{ formData.lower_price || 0 }} - ${{ formData.upper_price || 0 }}</span>
          </div>
          <div class="preview-stat">
            <span class="stat-label">网格级别</span>
            <span class="stat-value">{{ formData.grid_levels || 0 }}</span>
          </div>
          <div class="preview-stat">
            <span class="stat-label">每级价格</span>
            <span class="stat-value">${{ calculatePricePerLevel }}</span>
          </div>
          <div class="preview-stat">
            <span class="stat-label">投资金额</span>
            <span class="stat-value">${{ formData.investment || 0 }}</span>
          </div>
          <div class="preview-stat">
            <span class="stat-label">杠杆</span>
            <span class="stat-value">{{ formData.leverage || 1 }}x</span>
          </div>
        </div>
      </div>
      
      <div class="form-actions">
        <router-link to="/" class="btn btn-secondary">取消</router-link>
        <button type="submit" class="btn btn-primary" :disabled="!isFormValid">创建网格</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

const router = useRouter();
const isLoading = ref(false);
const errorMessage = ref('');
const successMessage = ref('');

const formData = ref({
  symbol: '',
  grid_type: '',
  lower_price: null,
  upper_price: null,
  grid_levels: 10,
  investment: 1000,
  leverage: 1
});

// Form validation
const priceRangeInvalid = computed(() => {
  return formData.value.lower_price != null && 
         formData.value.upper_price != null && 
         formData.value.lower_price >= formData.value.upper_price;
});

const isFormValid = computed(() => {
  return formData.value.symbol && 
         formData.value.grid_type && 
         formData.value.lower_price != null && 
         formData.value.upper_price != null && 
         formData.value.lower_price < formData.value.upper_price &&
         formData.value.grid_levels >= 2 && 
         formData.value.investment >= 10;
});

// Calculate price per level for preview
const calculatePricePerLevel = computed(() => {
  if (!formData.value.lower_price || !formData.value.upper_price || !formData.value.grid_levels) {
    return '0.00';
  }
  
  const priceDifference = formData.value.upper_price - formData.value.lower_price;
  const levelsCount = formData.value.grid_levels - 1; // Spaces between levels
  const pricePerLevel = priceDifference / levelsCount;
  
  return pricePerLevel.toFixed(2);
});

// Create grid strategy
const createGrid = async () => {
  try {
    isLoading.value = true;
    errorMessage.value = '';
    
    // Get token from localStorage
    const token = localStorage.getItem('token');
    const tokenType = localStorage.getItem('tokenType') || 'bearer';
    
    if (!token) {
      router.push('/login');
      return;
    }
    
    const response = await axios.post('http://localhost:8000/api/grids', formData.value, {
      headers: {
        'Authorization': `${tokenType} ${token}`
      }
    });
    
    if (response.data) {
      successMessage.value = '网格策略创建成功！';
    } else {
      errorMessage.value = '服务器返回无效响应';
    }
  } catch (error) {
    console.error('Error creating grid:', error);
    if (error.response && error.response.data) {
      errorMessage.value = error.response.data.detail || '创建网格失败';
    } else {
      errorMessage.value = '网络错误，请重试';
    }
  } finally {
    isLoading.value = false;
  }
};

// Reset form for creating another grid
const resetForm = () => {
  formData.value = {
    symbol: '',
    grid_type: '',
    lower_price: null,
    upper_price: null,
    grid_levels: 10,
    investment: 1000,
    leverage: 1
  };
  successMessage.value = '';
};
</script>

<script>
export default {
  name: 'CreateGridView',  // 添加名称以匹配路由
}
</script>

<style scoped>
.grid-form-view {
  padding: var(--spacing-lg);
}

.form-header {
  margin-bottom: var(--spacing-xl);
}

.form-header h1 {
  margin-bottom: var(--spacing-sm);
}

.form-header p {
  font-size: var(--font-size-md);
  color: var(--text-secondary);
}

.loading-container, .error-container, .success-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  margin-bottom: var(--spacing-xl);
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: var(--spacing-lg);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-container {
  background-color: rgba(230, 57, 70, 0.05);
  color: var(--danger-color);
}

.success-container {
  background-color: rgba(67, 211, 158, 0.05);
  color: var(--success-color);
}

.success-container p {
  font-size: var(--font-size-lg);
  margin-bottom: var(--spacing-lg);
}

.success-actions {
  display: flex;
  gap: var(--spacing-md);
}

.grid-form {
  padding: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
}

.form-section {
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-lg);
  border-bottom: 1px solid var(--border-light);
}

.form-section:last-of-type {
  border-bottom: none;
}

.form-section h2 {
  font-size: var(--font-size-lg);
  margin-bottom: var(--spacing-lg);
}

.form-group {
  margin-bottom: var(--spacing-lg);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
}

label {
  display: block;
  margin-bottom: var(--spacing-sm);
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-secondary);
}

.field-help {
  margin-top: var(--spacing-sm);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.field-error {
  color: var(--danger-color);
  font-size: var(--font-size-xs);
  margin-top: var(--spacing-xs);
}

.form-preview {
  background-color: rgba(75, 112, 226, 0.03);
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.preview-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
}

.preview-stat {
  display: flex;
  flex-direction: column;
  margin-bottom: var(--spacing-sm);
}

.stat-label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.stat-value {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--text-primary);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
}

@media (max-width: 768px) {
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .preview-stats {
    grid-template-columns: 1fr;
  }
  
  .form-actions {
    flex-direction: column;
  }
  
  .form-actions .btn {
    width: 100%;
    margin-bottom: var(--spacing-sm);
  }
}
</style>