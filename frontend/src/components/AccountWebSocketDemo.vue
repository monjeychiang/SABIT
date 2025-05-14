<template>
  <div class="account-websocket-demo">
    <div class="connection-status">
      <div class="status-indicator" :class="{ 'connected': isConnected, 'disconnected': !isConnected }">
        {{ isConnected ? '已連接' : '未連接' }}
      </div>
      <button v-if="!isConnected" @click="connect" :disabled="isConnecting">
        {{ isConnecting ? '連接中...' : '連接' }}
      </button>
      <button v-else @click="disconnect">斷開連接</button>
    </div>

    <div v-if="connectionError" class="error-message">
      連接錯誤: {{ connectionError }}
    </div>

    <div v-if="isConnected" class="account-data">
      <div class="section">
        <h3>賬戶信息</h3>
        <div v-if="lastUpdate" class="last-update">
          最後更新: {{ formatTime(lastUpdate) }}
        </div>
        <div class="total-equity">
          <strong>總資產價值:</strong> {{ totalEquity.value }} {{ totalEquity.currency }}
        </div>
      </div>

      <!-- 餘額 -->
      <div class="section">
        <h3>餘額</h3>
        <div v-if="balances.length === 0" class="no-data">
          無可用餘額數據
        </div>
        <div v-else class="data-table">
          <table>
            <thead>
              <tr>
                <th>資產</th>
                <th>錢包類型</th>
                <th>可用</th>
                <th>凍結</th>
                <th>總額</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(balance, index) in balances" :key="index">
                <td>{{ balance.asset }}</td>
                <td>{{ balance.walletType || 'SPOT' }}</td>
                <td>{{ balance.free }}</td>
                <td>{{ balance.locked }}</td>
                <td>{{ (parseFloat(balance.free) + parseFloat(balance.locked)).toFixed(8) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 持倉 -->
      <div class="section">
        <h3>持倉</h3>
        <div v-if="positions.length === 0" class="no-data">
          無持倉數據
        </div>
        <div v-else class="data-table">
          <table>
            <thead>
              <tr>
                <th>交易對</th>
                <th>方向</th>
                <th>數量</th>
                <th>入場價</th>
                <th>標記價</th>
                <th>未實現盈虧</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(position, index) in positions" :key="index">
                <td>{{ position.symbol }}</td>
                <td :class="position.positionSide === 'LONG' ? 'long' : 'short'">
                  {{ position.positionSide }}
                </td>
                <td>{{ position.positionAmt }}</td>
                <td>{{ position.entryPrice }}</td>
                <td>{{ position.markPrice }}</td>
                <td :class="parseFloat(position.unrealizedProfit) >= 0 ? 'profit' : 'loss'">
                  {{ position.unrealizedProfit }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 訂單 -->
      <div class="section">
        <h3>當前訂單</h3>
        <div v-if="orders.length === 0" class="no-data">
          無訂單數據
        </div>
        <div v-else class="data-table">
          <table>
            <thead>
              <tr>
                <th>訂單ID</th>
                <th>交易對</th>
                <th>類型</th>
                <th>方向</th>
                <th>價格</th>
                <th>數量</th>
                <th>狀態</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(order, index) in orders" :key="index">
                <td>{{ order.orderId }}</td>
                <td>{{ order.symbol }}</td>
                <td>{{ order.type }}</td>
                <td :class="order.side === 'BUY' ? 'long' : 'short'">{{ order.side }}</td>
                <td>{{ order.price }}</td>
                <td>{{ order.origQty }}</td>
                <td>{{ order.status }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import { useAccountWebSocket } from '@/composables/useAccountWebSocket';

// 從組合式API中獲取所有狀態和方法
const {
  status,
  isConnecting,
  isConnected,
  connectionError,
  lastUpdate,
  accountData,
  balances,
  positions,
  orders,
  totalEquity,
  connect,
  disconnect
} = useAccountWebSocket('binance');

// 格式化時間
const formatTime = (date: Date | null): string => {
  if (!date) return '未知';
  return new Intl.DateTimeFormat('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(date);
};
</script>

<style scoped>
.account-websocket-demo {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  font-family: Arial, sans-serif;
}

.connection-status {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}

.status-indicator {
  padding: 6px 12px;
  border-radius: 4px;
  margin-right: 10px;
  font-weight: bold;
}

.connected {
  background-color: #4caf50;
  color: white;
}

.disconnected {
  background-color: #f44336;
  color: white;
}

button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  background-color: #2196f3;
  color: white;
  cursor: pointer;
  font-weight: bold;
}

button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}

button:hover:not(:disabled) {
  background-color: #0b7dda;
}

.error-message {
  padding: 10px;
  background-color: #ffebee;
  border: 1px solid #f44336;
  color: #b71c1c;
  border-radius: 4px;
  margin-bottom: 20px;
}

.section {
  margin-bottom: 30px;
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 15px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

h3 {
  margin-top: 0;
  color: #333;
  border-bottom: 1px solid #ddd;
  padding-bottom: 10px;
}

.last-update {
  color: #666;
  font-size: 0.9em;
  margin-bottom: 10px;
}

.total-equity {
  font-size: 1.2em;
  margin-bottom: 10px;
  padding: 10px;
  background-color: #e3f2fd;
  border-radius: 4px;
}

.no-data {
  padding: 20px;
  text-align: center;
  color: #666;
  font-style: italic;
}

.data-table {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

th, td {
  padding: 12px 15px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

th {
  background-color: #f2f2f2;
  font-weight: bold;
}

tr:hover {
  background-color: #f5f5f5;
}

.long {
  color: #4caf50;
}

.short {
  color: #f44336;
}

.profit {
  color: #4caf50;
  font-weight: bold;
}

.loss {
  color: #f44336;
  font-weight: bold;
}
</style> 