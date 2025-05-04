<template>
  <div class="history-view">
    <div class="history-header">
      <h1>交易历史记录</h1>
      
      <div class="filters-container">
        <div class="filters-row">
        <div class="filter-group">
            <label for="date-range">时间范围</label>
            <div class="select-wrapper">
          <select id="date-range" v-model="dateRange" class="filter-select">
            <option value="all">全部</option>
            <option value="today">今天</option>
            <option value="week">本周</option>
            <option value="month">本月</option>
            <option value="custom">自定义</option>
          </select>
              <span class="select-arrow">▼</span>
            </div>
          
          <div v-if="dateRange === 'custom'" class="date-inputs">
            <input 
              type="date" 
              v-model="startDate" 
              class="date-input"
              :max="today"
            />
              <span class="date-separator">至</span>
            <input 
              type="date" 
              v-model="endDate" 
              class="date-input"
              :min="startDate"
              :max="today"
            />
          </div>
        </div>
        
        <div class="filter-group">
            <label for="symbol-filter">交易对</label>
            <div class="select-wrapper">
          <select id="symbol-filter" v-model="symbolFilter" class="filter-select">
            <option value="all">全部</option>
            <option v-for="symbol in availableSymbols" :key="symbol" :value="symbol">
              {{ symbol }}
            </option>
          </select>
              <span class="select-arrow">▼</span>
            </div>
        </div>
        
        <div class="filter-group">
            <label for="grid-filter">网格</label>
            <div class="select-wrapper">
          <select id="grid-filter" v-model="gridFilter" class="filter-select">
            <option value="all">全部</option>
            <option v-for="grid in availableGrids" :key="grid.id" :value="grid.id">
              {{ grid.name || grid.symbol }}
            </option>
          </select>
              <span class="select-arrow">▼</span>
            </div>
          </div>
        </div>
        
        <div class="action-buttons">
          <button @click="resetFilters" class="reset-button">
            <span class="icon">↺</span>重置
          </button>
          <button @click="applyFilters" class="apply-button">
            <span class="icon">✓</span>应用筛选
          </button>
        </div>
      </div>
    </div>
    
    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>加载交易记录中...</p>
    </div>
    
    <div v-else-if="error" class="error-container">
      <div class="error-icon">⚠️</div>
      <p>{{ error }}</p>
      <button @click="loadHistory" class="retry-button">重试</button>
    </div>
    
    <div v-else-if="filteredTransactions.length === 0" class="empty-container">
      <div class="empty-icon">📊</div>
      <h3>暂无交易记录</h3>
      <p>当前筛选条件下没有找到交易记录</p>
      <button @click="resetFilters" class="reset-button">重置筛选条件</button>
    </div>
    
    <div v-else class="history-content">
      <!-- 交易统计卡片 -->
      <div class="summary-stats">
        <div class="stat-card total-trades">
          <div class="stat-icon">🔄</div>
          <div class="stat-details">
          <h3>交易总数</h3>
          <p class="stat-value">{{ filteredTransactions.length }}</p>
        </div>
        </div>
        <div class="stat-card buy-trades">
          <div class="stat-icon">↗️</div>
          <div class="stat-details">
          <h3>买入交易</h3>
          <p class="stat-value">{{ buyCount }}</p>
        </div>
        </div>
        <div class="stat-card sell-trades">
          <div class="stat-icon">↘️</div>
          <div class="stat-details">
          <h3>卖出交易</h3>
          <p class="stat-value">{{ sellCount }}</p>
        </div>
        </div>
        <div class="stat-card volume">
          <div class="stat-icon">💰</div>
          <div class="stat-details">
          <h3>总交易量</h3>
          <p class="stat-value">{{ totalVolume.toFixed(2) }} USD</p>
        </div>
        </div>
        <div class="stat-card avg-price">
          <div class="stat-icon">📈</div>
          <div class="stat-details">
          <h3>平均成交价</h3>
          <p class="stat-value">${{ averagePrice.toFixed(2) }}</p>
          </div>
        </div>
      </div>
      
      <!-- 交易记录表格 -->
      <div class="transactions-table-container">
        <table class="transactions-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>交易对</th>
              <th>网格名称</th>
              <th>类型</th>
              <th>价格</th>
              <th>数量</th>
              <th>总额</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(tx, index) in displayedTransactions" :key="index" class="transaction-row">
              <td>{{ formatDate(tx.time) }}</td>
              <td class="symbol-cell">{{ tx.symbol }}</td>
              <td>{{ tx.gridName || '-' }}</td>
              <td>
                <span :class="['side-badge', tx.side.toLowerCase()]">
                  {{ formatSide(tx.side) }}
                </span>
              </td>
              <td class="price-cell">${{ formatNumber(tx.price) }}</td>
              <td>{{ formatNumber(tx.amount) }}</td>
              <td class="total-cell">${{ formatNumber(tx.price * tx.amount) }}</td>
              <td>
                <span :class="['status-badge', 'status-' + tx.status.toLowerCase()]">
                  {{ formatStatus(tx.status) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      
      <!-- 分页 -->
      <div class="pagination">
        <button 
          @click="prevPage" 
          :disabled="currentPage === 1"
          class="pagination-button prev"
        >
          <span class="icon">◀</span> 上一页
        </button>
        
        <div class="page-numbers">
          <button 
            v-for="page in displayedPageNumbers" 
            :key="page" 
            @click="goToPage(page)"
            :class="['page-number', { active: currentPage === page }]"
          >
            {{ page }}
          </button>
          
          <span v-if="totalPages > 5 && currentPage < totalPages - 2" class="page-ellipsis">...</span>
          
          <button 
            v-if="totalPages > 5 && currentPage < totalPages - 1" 
            @click="goToPage(totalPages)"
            :class="['page-number', { active: currentPage === totalPages }]"
          >
            {{ totalPages }}
          </button>
        </div>
        
        <button 
          @click="nextPage" 
          :disabled="currentPage === totalPages"
          class="pagination-button next"
        >
          下一页 <span class="icon">▶</span>
        </button>
      </div>
      
      <!-- 导出功能 -->
      <div class="export-section">
        <button @click="exportTransactions('csv')" class="export-button csv">
          <span class="icon">📄</span> 导出为 CSV
        </button>
        <button @click="exportTransactions('excel')" class="export-button excel">
          <span class="icon">📊</span> 导出为 Excel
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import axios from 'axios';

// 状态变量
const transactions = ref([]);
const filteredTransactions = ref([]);
const isLoading = ref(true);
const error = ref(null);

// 筛选条件
const dateRange = ref('month');
const startDate = ref('');
const endDate = ref('');
const symbolFilter = ref('all');
const gridFilter = ref('all');

// 分页
const currentPage = ref(1);
const itemsPerPage = 10;

// 可用选项
const availableSymbols = ref([]);
const availableGrids = ref([]);

// 获取今天的日期，格式为 YYYY-MM-DD
const today = new Date().toISOString().split('T')[0];

// 设置默认日期范围
const initDefaultDates = () => {
  const now = new Date();
  endDate.value = now.toISOString().split('T')[0];
  
  const oneMonthAgo = new Date();
  oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
  startDate.value = oneMonthAgo.toISOString().split('T')[0];
};

// 当日期范围改变时更新日期
watch(dateRange, () => {
  const now = new Date();
  const endDateValue = now.toISOString().split('T')[0];
  
  switch(dateRange.value) {
    case 'today':
      startDate.value = endDateValue;
      endDate.value = endDateValue;
      break;
    case 'week':
      const oneWeekAgo = new Date();
      oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
      startDate.value = oneWeekAgo.toISOString().split('T')[0];
      endDate.value = endDateValue;
      break;
    case 'month':
      const oneMonthAgo = new Date();
      oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
      startDate.value = oneMonthAgo.toISOString().split('T')[0];
      endDate.value = endDateValue;
      break;
    case 'custom':
      // 保持当前值
      break;
    default:
      // 'all' - 不需要设置日期
      startDate.value = '';
      endDate.value = '';
  }
});

// 加载交易历史记录
const loadHistory = async () => {
  isLoading.value = true;
  error.value = null;
  
  try {
    const token = localStorage.getItem('token');
    if (!token) {
      // 未登录，重定向到登录页面
      router.push('/login');
      return;
    }
    
    // 获取交易记录
    const response = await axios.get('http://localhost:8000/api/trades', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    transactions.value = response.data.map(tx => ({
      ...tx,
      time: new Date(tx.time), // 确保时间为 Date 对象
    }));
    
    // 初始应用筛选
    applyFilters();
    
    // 获取唯一的交易对和网格列表
    availableSymbols.value = [...new Set(transactions.value.map(tx => tx.symbol))];
    
    // 获取网格列表
    const gridsResponse = await axios.get('http://localhost:8000/api/grids', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    availableGrids.value = gridsResponse.data;
    
    isLoading.value = false;
  } catch (err) {
    console.error('Error loading transaction history:', err);
    error.value = '加载交易历史失败，请稍后重试';
    isLoading.value = false;
    
    // 开发环境下使用模拟数据
    if (process.env.NODE_ENV === 'development') {
      setTimeout(() => {
        mockTransactionData();
        isLoading.value = false;
        error.value = null;
      }, 500);
    }
  }
};

// 应用筛选条件
const applyFilters = () => {
  if (!transactions.value) return;
  
  let filtered = [...transactions.value];
  
  // 按日期筛选
  if (dateRange.value !== 'all' && startDate.value && endDate.value) {
    const start = new Date(startDate.value);
    start.setHours(0, 0, 0, 0);
    
    const end = new Date(endDate.value);
    end.setHours(23, 59, 59, 999);
    
    filtered = filtered.filter(tx => {
      const txDate = new Date(tx.time);
      return txDate >= start && txDate <= end;
    });
  }
  
  // 按交易对筛选
  if (symbolFilter.value !== 'all') {
    filtered = filtered.filter(tx => tx.symbol === symbolFilter.value);
  }
  
  // 按网格筛选
  if (gridFilter.value !== 'all') {
    filtered = filtered.filter(tx => tx.gridId === gridFilter.value);
  }
  
  filteredTransactions.value = filtered;
  currentPage.value = 1; // 重置到第一页
};

// 计算分页相关数据
const totalPages = computed(() => {
  return Math.ceil(filteredTransactions.value.length / itemsPerPage);
});

const displayedTransactions = computed(() => {
  const startIndex = (currentPage.value - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  return filteredTransactions.value.slice(startIndex, endIndex);
});

// 计算要显示的页码
const displayedPageNumbers = computed(() => {
  const pageNumbers = [];
  
  if (totalPages.value <= 5) {
    // 如果总页数少于等于5，显示所有页码
    for (let i = 1; i <= totalPages.value; i++) {
      pageNumbers.push(i);
    }
  } else {
    // 总是显示第一页
    pageNumbers.push(1);
    
    // 如果当前页大于3，显示省略号
    if (currentPage.value > 3) {
      pageNumbers.push('...');
    }
    
    // 计算当前页附近的页码范围
    let rangeStart = Math.max(2, currentPage.value - 1);
    let rangeEnd = Math.min(totalPages.value - 1, currentPage.value + 1);
    
    // 调整范围，如果接近开始或结束
    if (currentPage.value <= 3) {
      rangeEnd = 4;
    } else if (currentPage.value >= totalPages.value - 2) {
      rangeStart = totalPages.value - 3;
    }
    
    // 添加范围内的页码
    for (let i = rangeStart; i <= rangeEnd; i++) {
      pageNumbers.push(i);
    }
    
    // 如果当前页小于总页数-2，显示省略号
    if (currentPage.value < totalPages.value - 2) {
      pageNumbers.push('...');
    }
    
    // 总是显示最后一页
    pageNumbers.push(totalPages.value);
  }
  
  return pageNumbers;
});

// 分页方法
const goToPage = (page) => {
  if (typeof page === 'number') {
    currentPage.value = page;
  }
};

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
};

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
};

// 重置筛选条件
const resetFilters = () => {
  dateRange.value = 'month';
  symbolFilter.value = 'all';
  gridFilter.value = 'all';
  
  const now = new Date();
  endDate.value = now.toISOString().split('T')[0];
  
  const oneMonthAgo = new Date();
  oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
  startDate.value = oneMonthAgo.toISOString().split('T')[0];
  
  applyFilters();
};

// 交易统计
const buyCount = computed(() => {
  return filteredTransactions.value.filter(tx => tx.side.toLowerCase() === 'buy').length;
});

const sellCount = computed(() => {
  return filteredTransactions.value.filter(tx => tx.side.toLowerCase() === 'sell').length;
});

const totalVolume = computed(() => {
  return filteredTransactions.value.reduce((sum, tx) => sum + (tx.price * tx.amount), 0);
});

const averagePrice = computed(() => {
  if (filteredTransactions.value.length === 0) return 0;
  return filteredTransactions.value.reduce((sum, tx) => sum + tx.price, 0) / filteredTransactions.value.length;
});

// 格式化函数
const formatDate = (date) => {
  if (!date) return '';
  return new Date(date).toLocaleString();
};

const formatNumber = (num) => {
  if (typeof num !== 'number') return '0.00';
  return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 6 });
};

const formatSide = (side) => {
  if (!side) return '';
  return side.toLowerCase() === 'buy' ? '买入' : '卖出';
};

const formatStatus = (status) => {
  if (!status) return '';
  
  const statusMap = {
    'completed': '已完成',
    'pending': '处理中',
    'failed': '失败',
    'canceled': '已取消'
  };
  
  return statusMap[status.toLowerCase()] || status;
};

// 导出交易记录
const exportTransactions = (format) => {
  // 这里实现导出功能
  alert(`导出为 ${format} 功能将在未来版本中实现`);
};

// 模拟数据（开发环境）
const mockTransactionData = () => {
  const mockSymbols = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT'];
  const mockGrids = [
    { id: 'grid1', name: 'BTC 网格策略', symbol: 'BTC/USDT' },
    { id: 'grid2', name: 'ETH 网格策略', symbol: 'ETH/USDT' },
    { id: 'grid3', name: '高频 BNB', symbol: 'BNB/USDT' }
  ];
  
  const mockStatuses = ['completed', 'pending', 'failed', 'canceled'];
  const mockSides = ['buy', 'sell'];
  
  // 生成随机交易记录
  const mockTransactions = Array(50).fill(0).map((_, index) => {
    const symbol = mockSymbols[Math.floor(Math.random() * mockSymbols.length)];
    const grid = mockGrids.find(g => g.symbol === symbol) || mockGrids[0];
    const date = new Date();
    date.setDate(date.getDate() - Math.floor(Math.random() * 30));
    
    const side = mockSides[Math.floor(Math.random() * mockSides.length)];
    const price = symbol.startsWith('BTC') ? 60000 + Math.random() * 5000 : 
                  symbol.startsWith('ETH') ? 3000 + Math.random() * 500 :
                  symbol.startsWith('BNB') ? 500 + Math.random() * 100 :
                  symbol.startsWith('SOL') ? 100 + Math.random() * 50 :
                  10 + Math.random() * 5;
    
    return {
      id: `tx${index}`,
      time: date,
      symbol: symbol,
      gridId: grid.id,
      gridName: grid.name,
      side: side,
      price: price,
      amount: 0.01 + Math.random() * 5,
      status: mockStatuses[Math.floor(Math.random() * mockStatuses.length)]
    };
  });
  
  transactions.value = mockTransactions;
  availableSymbols.value = mockSymbols;
  availableGrids.value = mockGrids;
  
  applyFilters();
};

// 组件初始化
onMounted(() => {
  initDefaultDates();
  loadHistory();
});
</script>

<style scoped>
.history-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
  color: var(--text-primary);
  background-color: var(--background-color);
  transition: color 0.3s ease, background-color 0.3s ease;
}

.history-header {
  background-color: var(--card-background);
  border-radius: var(--border-radius-md);
  padding: 24px;
  box-shadow: var(--box-shadow-sm);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.history-header h1 {
  margin: 0 0 20px 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  transition: color 0.3s ease;
}

.filters-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filters-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  align-items: flex-start;
}

.filter-group {
  flex: 1;
  min-width: 180px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.filter-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  transition: color 0.3s ease;
}

.select-wrapper {
  position: relative;
  display: inline-block;
  width: 100%;
}

.filter-select {
  width: 100%;
  padding: 10px 16px;
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-color);
  background-color: var(--surface-color);
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  appearance: none;
  transition: border-color 0.3s ease, background-color 0.3s ease, color 0.3s ease;
}

.filter-select:hover {
  border-color: var(--primary-color);
}

.filter-select:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

.select-arrow {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  color: var(--text-secondary);
  pointer-events: none;
  transition: color 0.3s ease;
}

.date-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.date-input {
  flex: 1;
  padding: 10px 16px;
  border-radius: var(--border-radius-sm);
  border: 1px solid var(--border-color);
  background-color: var(--surface-color);
  color: var(--text-primary);
  font-size: 14px;
  transition: border-color 0.3s ease, background-color 0.3s ease, color 0.3s ease;
}

.date-input:hover {
  border-color: var(--primary-color);
}

.date-input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
}

.date-separator {
  color: var(--text-secondary);
  transition: color 0.3s ease;
}

.action-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.reset-button, 
.apply-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: var(--border-radius-sm);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.reset-button {
  background-color: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-color);
  transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}

.reset-button:hover {
  background-color: var(--hover-color);
  color: var(--text-primary);
}

.apply-button {
  background-color: var(--primary-color);
  color: white;
  transition: background-color 0.3s ease;
}

.apply-button:hover {
  background-color: var(--primary-dark);
}

.loading-container,
.error-container,
.empty-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 0;
  background-color: var(--card-background);
  border-radius: var(--border-radius-md);
  box-shadow: var(--box-shadow-sm);
  text-align: center;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 4px solid var(--border-light);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  margin-bottom: 16px;
  animation: spin 1s linear infinite;
  transition: border-color 0.3s ease;
}

.error-icon,
.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.error-container p,
.empty-container p {
  color: var(--text-secondary);
  margin-bottom: 24px;
  transition: color 0.3s ease;
}

.empty-container h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  transition: color 0.3s ease;
}

.retry-button {
  background-color: var(--primary-color);
  color: white;
  padding: 10px 16px;
  border-radius: var(--border-radius-sm);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background-color 0.3s ease;
}

.retry-button:hover {
  background-color: var(--primary-dark);
}

.summary-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background-color: var(--card-background);
  border-radius: var(--border-radius-md);
  padding: 20px;
  display: flex;
  align-items: center;
  box-shadow: var(--box-shadow-sm);
  transition: transform 0.2s ease, box-shadow 0.2s ease, background-color 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--box-shadow-md);
}

.stat-icon {
  font-size: 24px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.total-trades .stat-icon {
  background-color: rgba(59, 130, 246, 0.1);
  color: var(--primary-color);
}

.buy-trades .stat-icon {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.sell-trades .stat-icon {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.volume .stat-icon {
  background-color: rgba(245, 158, 11, 0.1);
  color: var(--warning-color);
}

.avg-price .stat-icon {
  background-color: rgba(168, 85, 247, 0.1);
  color: #a855f7;
}

.stat-details h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
  transition: color 0.3s ease;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  transition: color 0.3s ease;
}

.transactions-table-container {
  background-color: var(--card-background);
  border-radius: var(--border-radius-md);
  overflow: hidden;
  box-shadow: var(--box-shadow-sm);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.transactions-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

.transactions-table th {
  background-color: var(--surface-color);
  color: var(--text-secondary);
  font-weight: 500;
  text-align: left;
  padding: 16px;
  transition: background-color 0.3s ease, color 0.3s ease;
}

.transactions-table td {
  padding: 16px;
  border-top: 1px solid var(--border-light);
  color: var(--text-primary);
  transition: border-color 0.3s ease, color 0.3s ease;
}

.transaction-row:hover {
  background-color: var(--hover-color);
}

.symbol-cell {
  font-weight: 500;
  color: var(--primary-color);
}

.price-cell {
  font-family: 'Roboto Mono', monospace;
}

.total-cell {
  font-weight: 500;
}

.side-badge,
.status-badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: var(--border-radius-sm);
  font-size: 12px;
  font-weight: 500;
}

.side-badge.buy {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.side-badge.sell {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.status-badge.status-completed {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.status-badge.status-pending {
  background-color: rgba(245, 158, 11, 0.1);
  color: var(--warning-color);
}

.status-badge.status-failed {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  margin-top: 24px;
}

.pagination-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

.pagination-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-button:not(:disabled):hover {
  background-color: var(--hover-color);
  border-color: var(--primary-color);
}

.page-numbers {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-number {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  font-size: 14px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

.page-number.active {
  background-color: var(--primary-color);
  color: white;
  border-color: var(--primary-color);
}

.page-number:not(.active):hover {
  background-color: var(--hover-color);
  border-color: var(--primary-color);
}

.page-ellipsis {
  color: var(--text-secondary);
  transition: color 0.3s ease;
}

.export-section {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}

.export-button {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: var(--border-radius-sm);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid var(--border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease, color 0.3s ease;
}

.export-button.csv {
  background-color: transparent;
  color: var(--text-secondary);
}

.export-button.excel {
  background-color: transparent;
  color: var(--text-secondary);
}

.export-button:hover {
  background-color: var(--hover-color);
  color: var(--text-primary);
  border-color: var(--primary-color);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 响应式样式 */
@media (max-width: 1200px) {
  .summary-stats {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .history-header {
    padding: 16px;
  }
  
  .filters-row {
    flex-direction: column;
    gap: 16px;
  }
  
  .filter-group {
    width: 100%;
  }
  
  .action-buttons {
    justify-content: center;
  }
  
  .summary-stats {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  
  .transactions-table th,
  .transactions-table td {
    padding: 12px 8px;
    font-size: 13px;
  }
  
  .pagination {
    flex-direction: column;
    gap: 16px;
  }
  
  .export-section {
    justify-content: center;
    flex-wrap: wrap;
  }
}

@media (max-width: 480px) {
  .summary-stats {
    grid-template-columns: 1fr;
  }
  
  .transactions-table {
    display: block;
    overflow-x: auto;
  }
  
  .page-numbers {
    display: none;
  }
  
  .pagination {
    flex-direction: row;
  }
}
</style> 