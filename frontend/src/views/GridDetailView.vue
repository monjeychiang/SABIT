<template>
  <div class="grid-detail-view">
    <div class="detail-header">
      <div class="header-content">
        <h1>{{ grid?.symbol || 'Grid Details' }}</h1>
        <div class="grid-badge" :class="{ 'status-running': grid?.status === 'running', 'status-stopped': grid?.status === 'stopped' }">
          {{ grid?.status || 'Loading...' }}
        </div>
      </div>
      <div class="header-actions">
        <button v-if="grid?.status === 'stopped'" @click="startGrid" class="action-button start-button" :disabled="isActionLoading">
          {{ isActionLoading ? 'Starting...' : 'Start Grid' }}
        </button>
        <button v-else-if="grid?.status === 'running'" @click="stopGrid" class="action-button stop-button" :disabled="isActionLoading">
          {{ isActionLoading ? 'Stopping...' : 'Stop Grid' }}
        </button>
        <router-link to="/" class="back-link">Back to Dashboard</router-link>
      </div>
    </div>

    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Loading grid details...</p>
    </div>

    <div v-else-if="error" class="error-container">
      <p>{{ error }}</p>
      <button @click="loadGridDetails" class="retry-button">Retry</button>
    </div>

    <div v-else-if="grid" class="grid-content">
      <div class="grid-summary">
        <div class="summary-card">
          <h3>Current Price</h3>
          <p class="summary-number">${{ grid.current_price.toFixed(2) }}</p>
        </div>
        <div class="summary-card">
          <h3>Investment</h3>
          <p class="summary-number">${{ grid.investment.toFixed(2) }}</p>
        </div>
        <div class="summary-card">
          <h3>Total Profit</h3>
          <p class="summary-number" :class="{ 'profit-positive': grid.profit > 0, 'profit-negative': grid.profit < 0 }">
            ${{ grid.profit.toFixed(2) }}
          </p>
        </div>
      </div>

      <div class="detail-container">
        <div class="detail-section">
          <h2>Grid Configuration</h2>
          <div class="grid-config">
            <div class="config-item">
              <span class="item-label">Grid Type</span>
              <span class="item-value">{{ formatGridType(grid.grid_type) }}</span>
            </div>
            <div class="config-item">
              <span class="item-label">Price Range</span>
              <span class="item-value">${{ grid.lower_price }} - ${{ grid.upper_price }}</span>
            </div>
            <div class="config-item">
              <span class="item-label">Grid Levels</span>
              <span class="item-value">{{ grid.grid_levels }}</span>
            </div>
            <div class="config-item">
              <span class="item-label">Price Per Level</span>
              <span class="item-value">${{ calculatePricePerLevel }}</span>
            </div>
            <div class="config-item">
              <span class="item-label">Leverage</span>
              <span class="item-value">{{ grid.leverage }}x</span>
            </div>
            <div class="config-item">
              <span class="item-label">Created</span>
              <span class="item-value">{{ formatDate(grid.created_at) }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h2>Price Chart</h2>
          <div class="chart-container">
            <div class="placeholder-chart">
              <p>Price chart will be displayed here</p>
              <p class="chart-note">Chart displays price movement and grid lines</p>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h2>Grid Positions</h2>
          <div v-if="grid.positions.length === 0" class="empty-state">
            <p>No active positions at the moment</p>
          </div>
          <div v-else class="positions-table">
            <div class="table-header">
              <div class="th">Side</div>
              <div class="th">Price</div>
              <div class="th">Quantity</div>
              <div class="th">Value</div>
              <div class="th">Status</div>
            </div>
            <div v-for="(position, index) in grid.positions" :key="index" class="table-row">
              <div class="td side" :class="position.side.toLowerCase()">{{ position.side }}</div>
              <div class="td">${{ position.price.toFixed(2) }}</div>
              <div class="td">{{ position.quantity.toFixed(6) }}</div>
              <div class="td">${{ (position.price * position.quantity).toFixed(2) }}</div>
              <div class="td status">{{ position.status }}</div>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h2>Recent Transactions</h2>
          <div v-if="grid.orders.length === 0" class="empty-state">
            <p>No transactions yet</p>
          </div>
          <div v-else class="orders-table">
            <div class="table-header">
              <div class="th">Time</div>
              <div class="th">Side</div>
              <div class="th">Price</div>
              <div class="th">Quantity</div>
              <div class="th">Value</div>
            </div>
            <div v-for="(order, index) in grid.orders" :key="index" class="table-row">
              <div class="td">{{ formatTime(order.time) }}</div>
              <div class="td side" :class="order.side.toLowerCase()">{{ order.side }}</div>
              <div class="td">${{ order.price.toFixed(2) }}</div>
              <div class="td">{{ order.quantity.toFixed(6) }}</div>
              <div class="td">${{ (order.price * order.quantity).toFixed(2) }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import axios from 'axios';

const route = useRoute();
const router = useRouter();
const gridId = route.params.id;

const grid = ref(null);
const isLoading = ref(true);
const error = ref(null);
const isActionLoading = ref(false);

// API request with authentication
const createAuthenticatedRequest = () => {
  const token = localStorage.getItem('token');
  const tokenType = localStorage.getItem('tokenType') || 'bearer';
  
  if (!token) {
    router.push('/login');
    return null;
  }
  
  return axios.create({
    baseURL: 'http://localhost:8000',
    headers: {
      'Authorization': `${tokenType} ${token}`
    }
  });
};

// Load grid details
const loadGridDetails = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isLoading.value = true;
    error.value = null;
    
    const response = await api.get(`/api/grids/${gridId}`);
    grid.value = response.data;
    
    if (!grid.value) {
      error.value = 'Grid not found';
    }
  } catch (err) {
    console.error('Error loading grid details:', err);
    if (err.response && err.response.status === 401) {
      router.push('/login');
    } else {
      error.value = err.response?.data?.detail || 'Failed to load grid details';
    }
  } finally {
    isLoading.value = false;
  }
};

// Start grid
const startGrid = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isActionLoading.value = true;
    await api.post(`/api/grids/${gridId}/start`);
    await loadGridDetails(); // Reload grid data
  } catch (err) {
    console.error('Error starting grid:', err);
    alert(err.response?.data?.detail || 'Failed to start grid');
  } finally {
    isActionLoading.value = false;
  }
};

// Stop grid
const stopGrid = async () => {
  const api = createAuthenticatedRequest();
  if (!api) return;
  
  try {
    isActionLoading.value = true;
    await api.post(`/api/grids/${gridId}/stop`);
    await loadGridDetails(); // Reload grid data
  } catch (err) {
    console.error('Error stopping grid:', err);
    alert(err.response?.data?.detail || 'Failed to stop grid');
  } finally {
    isActionLoading.value = false;
  }
};

// Calculate price per level
const calculatePricePerLevel = computed(() => {
  if (!grid.value) return '0.00';
  
  const priceDifference = grid.value.upper_price - grid.value.lower_price;
  const levelsCount = grid.value.grid_levels - 1; // Spaces between levels
  const pricePerLevel = priceDifference / levelsCount;
  
  return pricePerLevel.toFixed(2);
});

// Format grid type
const formatGridType = (type) => {
  if (type === 'arithmetic') return 'Arithmetic (Equal Price)';
  if (type === 'geometric') return 'Geometric (Equal Percentage)';
  return type;
};

// Format date
const formatDate = (dateString) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleString();
};

// Format time
const formatTime = (timestamp) => {
  if (!timestamp) return '';
  const date = new Date(timestamp);
  return date.toLocaleString();
};

// Load data on component mount
onMounted(() => {
  loadGridDetails();
});
</script>

<style scoped>
.grid-detail-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  align-items: center;
}

.detail-header h1 {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  margin-right: 16px;
}

.grid-badge {
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
}

.status-running {
  background-color: rgba(46, 125, 50, 0.2);
  color: var(--success-color);
}

.status-stopped {
  background-color: rgba(198, 40, 40, 0.2);
  color: var(--danger-color);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.action-button {
  padding: 10px 20px;
  border-radius: 5px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: background-color 0.3s;
}

.start-button {
  background-color: var(--success-color);
  color: white;
}

.start-button:hover:not(:disabled) {
  background-color: var(--success-color-dark);
}

.stop-button {
  background-color: var(--danger-color);
  color: white;
}

.stop-button:hover:not(:disabled) {
  background-color: var(--danger-color-dark);
}

.action-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.back-link {
  color: var(--primary-color);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
}

.back-link:hover {
  text-decoration: underline;
}

.loading-container, .error-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background-color: var(--card-background);
  border-radius: 10px;
  box-shadow: var(--box-shadow-md);
  text-align: center;
  margin-bottom: 30px;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-light);
  border-top: 4px solid var(--primary-color);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.retry-button {
  margin-top: 16px;
  padding: 8px 16px;
  background-color: var(--primary-color);
  color: white;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.3s ease;
}

.retry-button:hover {
  background-color: var(--primary-dark);
}

.grid-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.summary-card {
  background-color: var(--card-background);
  border-radius: 10px;
  padding: 20px;
  box-shadow: var(--box-shadow-md);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.summary-card h3 {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.summary-number {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.profit-positive {
  color: var(--success-color);
}

.profit-negative {
  color: var(--danger-color);
}

.detail-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.detail-section {
  background-color: var(--card-background);
  border-radius: 10px;
  padding: 24px;
  box-shadow: var(--box-shadow-md);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.detail-section h2 {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border-color);
}

.grid-config {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.item-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.item-value {
  font-size: 16px;
  color: var(--text-primary);
}

.chart-container {
  height: 300px;
  width: 100%;
}

.placeholder-chart {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: var(--surface-color);
  border-radius: 5px;
  color: var(--text-secondary);
  transition: background-color 0.3s ease;
}

.chart-note {
  font-size: 12px;
  margin-top: 8px;
  color: var(--text-tertiary);
}

.empty-state {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary);
  background-color: var(--surface-color);
  border-radius: 5px;
  transition: background-color 0.3s ease;
}

.positions-table, .orders-table {
  width: 100%;
  overflow-x: auto;
}

.table-header {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  padding: 12px;
  font-weight: 500;
  background-color: var(--surface-color);
  border-radius: 5px 5px 0 0;
  border-bottom: 1px solid var(--border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.table-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr 1fr;
  padding: 12px;
  border-bottom: 1px solid var(--border-color);
  transition: background-color 0.3s ease, border-color 0.3s ease;
}

.table-row:hover {
  background-color: var(--hover-color);
}

.th, .td {
  padding: 8px;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.th {
  font-weight: 600;
  color: var(--text-secondary);
}

.td {
  color: var(--text-primary);
}

.td.side {
  font-weight: 600;
}

.td.side.buy {
  color: var(--success-color);
}

.td.side.sell {
  color: var(--danger-color);
}

.td.status {
  text-transform: capitalize;
}

@media (max-width: 768px) {
  .grid-summary {
    grid-template-columns: 1fr;
  }
  
  .header-actions {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .detail-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .table-header, .table-row {
    grid-template-columns: repeat(5, minmax(100px, 1fr));
  }
  
  .positions-table, .orders-table {
    overflow-x: auto;
  }
}
</style> 