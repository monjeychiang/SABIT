<template>
  <div class="trade-test-container">
    <div class="page-header">
      <h1>WebSocket 交易測試介面</h1>
      <div class="sub-header">安全測試您的交易策略</div>
      <div class="api-info">
        <span class="api-badge">🚀 新功能</span> 
        系統已升級為使用 WebSocket API 與幣安直接通信，提供更快的下單速度和更好的實時性能
      </div>
    </div>

    <div class="connection-status" :class="{ 'connected': isConnected, 'disconnected': !isConnected }">
      <div class="status-indicator" :class="{ active: isConnected }"></div>
      <span>WebSocket 狀態: {{ isConnected ? '已連接' : '未連接' }}</span>
      <div class="connection-info" v-if="isConnected">
        <span class="connection-time">上次更新: {{ lastUpdate ? formatTime(lastUpdate) : '尚未更新' }}</span>
      </div>
      <div class="connection-actions">
        <button @click="connect" :disabled="isConnected" class="connect-btn">
          <span class="icon">●</span> 連接
        </button>
        <button @click="disconnect" :disabled="!isConnected" class="disconnect-btn">
          <span class="icon">■</span> 斷開
        </button>
      </div>
    </div>

    <!-- 幣安連接狀態 -->
    <div class="connection-status binance-connection" :class="{ 'connected': binanceConnected, 'websocket-api': isWebSocketAPI, 'rest-api': isRestAPI, 'error': binanceConnectError }" v-if="isConnected">
      <div class="status-indicator" :class="{ active: binanceConnected, error: binanceConnectError }"></div>
      <span>幣安 API 狀態: {{ binanceConnected ? '已連接' : (binanceConnectError ? '連接錯誤' : '未連接') }}</span>
      <div class="connection-info">
        <span class="connection-type" :class="{ 'websocket-api': isWebSocketAPI, 'rest-api': isRestAPI, 'error': binanceConnectError }">
          {{ binanceConnectionType }}
        </span>
        <i class="fas fa-info-circle api-info-icon" title="WebSocket API 提供更快的交易速度和更低的延遲，但需要專門的 Ed25519 密鑰。REST API 是標準接口，使用一般的 HMAC-SHA256 密鑰"></i>
      </div>
      <div class="connection-actions" v-if="binanceConnectError">
        <button @click="reconnectBinance" class="reconnect-btn">
          <span class="icon">↻</span> 重新連接
        </button>
      </div>
    </div>

    <!-- 幣安連接錯誤信息 -->
    <div class="binance-error-message" v-if="isConnected && binanceConnectError">
      <div class="error-icon">!</div>
      <div class="error-content">
        <div class="error-title">幣安 API 連接錯誤</div>
        <div class="error-desc">{{ binanceErrorMessage || '連接意外斷開，請嘗試重新連接' }}</div>
        <div class="error-tips">
          常見原因: 網絡問題、API密鑰過期或權限不足、服務端連接超時
        </div>
      </div>
    </div>

    <div class="card account-info" v-if="isConnected">
      <div class="card-header">
        <h2>賬戶信息</h2>
        <div class="tag">實時數據</div>
      </div>
      <div class="refresh-action">
        <button @click="refreshAccountData" class="refresh-btn">刷新資料</button>
        <span v-if="lastUpdate">上次更新: {{ formatTime(lastUpdate) }}</span>
      </div>
      <div class="account-summary">
        <div class="summary-item">
          <div class="label">可用餘額</div>
          <div class="value">{{ formatNumber(availableBalance) }}</div>
          <div class="subtext">可用於開倉</div>
        </div>
        <div class="summary-item">
          <div class="label">錢包餘額</div>
          <div class="value">{{ formatNumber(totalWalletBalance) }}</div>
          <div class="subtext">總資產</div>
        </div>
        <div class="summary-item">
          <div class="label">未實現盈虧</div>
          <div class="value" :class="getColorClass(totalUnrealizedProfit)">
            {{ formatNumber(totalUnrealizedProfit) }}
          </div>
          <div class="subtext">持倉浮動盈虧</div>
        </div>
      </div>
      <div class="api-type-indicator" v-if="accountInfo && accountInfo.api_type">
        <span 
          class="api-badge" 
          :class="{'ws-api': accountInfo.api_type.includes('WebSocket'), 'rest-api': accountInfo.api_type.includes('REST')}"
        >
          {{ accountInfo.api_type }}
        </span>
        <i class="fas fa-info-circle api-info-icon" title="WebSocket API 提供更快的交易速度和更低的延遲，但需要專門的 Ed25519 密鑰。REST API 是標準接口，使用一般的 HMAC-SHA256 密鑰"></i>
      </div>
    </div>

    <div class="not-connected-message" v-if="!isConnected">
      <div class="message-icon">!</div>
      <div class="message-content">
        <h3>未連接到 WebSocket</h3>
        <p>請點擊「連接」按鈕以獲取實時賬戶數據和執行交易操作。</p>
      </div>
    </div>

    <div class="cards-container" v-if="isConnected">
      <div class="card place-order">
        <div class="card-header">
          <h2>下單測試</h2>
          <div class="tag" :class="{ 'test-tag': testMode }">{{ testMode ? '測試模式' : '實盤模式' }}</div>
        </div>
        <div class="form-group">
          <label>交易對</label>
          <input type="text" v-model="orderForm.symbol" placeholder="例如: BTCUSDT" />
          <div class="field-hint">輸入交易對名稱，如 BTCUSDT, ETHUSDT 等</div>
        </div>
        <div class="form-group">
          <label>方向</label>
          <select v-model="orderForm.side" class="direction-select" :class="orderForm.side.toLowerCase()">
            <option value="BUY">買入 (Buy)</option>
            <option value="SELL">賣出 (Sell)</option>
          </select>
        </div>
        <div class="form-group">
          <label>類型</label>
          <select v-model="orderForm.type">
            <option value="LIMIT">限價單 (Limit)</option>
            <option value="MARKET">市價單 (Market)</option>
          </select>
          <div class="field-hint" v-if="orderForm.type === 'LIMIT'">限價單指定價格和數量</div>
          <div class="field-hint" v-if="orderForm.type === 'MARKET'">市價單只需指定數量</div>
        </div>
        <div class="form-group" v-if="orderForm.type === 'LIMIT'">
          <label>價格</label>
          <div class="input-with-addon">
            <input type="number" v-model="orderForm.price" placeholder="輸入限價" step="0.01" />
            <span class="addon">USDT</span>
          </div>
        </div>
        <div class="form-group">
          <label>數量</label>
          <div class="input-with-addon">
            <input type="number" v-model="orderForm.quantity" placeholder="輸入數量" step="0.001" />
            <span class="addon">{{ orderForm.symbol.replace('USDT', '') }}</span>
          </div>
        </div>
        <div class="form-group" v-if="orderForm.type === 'LIMIT'">
          <label>有效期</label>
          <select v-model="orderForm.timeInForce">
            <option value="GTC">一直有效 (GTC)</option>
            <option value="IOC">立即成交或取消 (IOC)</option>
            <option value="FOK">完全成交或取消 (FOK)</option>
          </select>
        </div>
        <div class="form-group test-mode-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="testMode" />
            <span class="checkbox-text">測試模式</span>
          </label>
          <div class="test-mode-hint">
            {{ testMode ? '僅測試，不實際下單' : '警告：將實際提交訂單到交易所' }}
          </div>
        </div>
        <div class="form-actions">
          <button @click="submitOrder" :disabled="isOrderSubmitting" class="submit-btn" :class="{ 'test-btn': testMode, 'live-btn': !testMode }">
            {{ isOrderSubmitting ? '提交中...' : '提交訂單' }}
          </button>
        </div>
        <div class="response-container" v-if="orderResponse">
          <h3>訂單返回結果</h3>
          <div class="response-summary" v-if="orderResponse.orderId">
            <div class="summary-row">
              <div class="summary-label">訂單ID:</div>
              <div class="summary-value">{{ orderResponse.orderId }}</div>
            </div>
            <div class="summary-row">
              <div class="summary-label">狀態:</div>
              <div class="summary-value">{{ orderResponse.status }}</div>
            </div>
            <div class="summary-row">
              <div class="summary-label">交易對:</div>
              <div class="summary-value">{{ orderResponse.symbol }}</div>
            </div>
          </div>
          <pre>{{ JSON.stringify(orderResponse, null, 2) }}</pre>
        </div>
        <div class="error-container" v-if="orderError">
          <h3>錯誤信息</h3>
          <div class="error-message">{{ orderError }}</div>
        </div>
      </div>

      <div class="card cancel-order">
        <div class="card-header">
          <h2>取消訂單測試</h2>
          <div class="tag">管理訂單</div>
        </div>
        <div class="form-group">
          <label>交易對</label>
          <input type="text" v-model="cancelForm.symbol" placeholder="例如: BTCUSDT" />
        </div>
        <div class="form-group">
          <label>訂單ID</label>
          <input type="text" v-model="cancelForm.orderId" placeholder="輸入訂單ID" />
          <div class="field-hint">輸入您要取消的訂單ID</div>
        </div>
        <div class="form-actions">
          <button @click="submitCancelOrder" :disabled="isCancelSubmitting" class="cancel-btn">
            {{ isCancelSubmitting ? '提交中...' : '取消訂單' }}
          </button>
        </div>
        <div class="response-container" v-if="cancelResponse">
          <h3>取消訂單結果</h3>
          <div class="response-summary" v-if="cancelResponse.orderId">
            <div class="summary-row">
              <div class="summary-label">訂單ID:</div>
              <div class="summary-value">{{ cancelResponse.orderId }}</div>
            </div>
            <div class="summary-row">
              <div class="summary-label">狀態:</div>
              <div class="summary-value">{{ cancelResponse.status }}</div>
            </div>
          </div>
          <pre>{{ JSON.stringify(cancelResponse, null, 2) }}</pre>
        </div>
        <div class="error-container" v-if="cancelError">
          <h3>錯誤信息</h3>
          <div class="error-message">{{ cancelError }}</div>
        </div>
      </div>
    </div>

    <div class="data-section" v-if="isConnected">
      <div class="card balance-card" v-if="filteredBalances.length > 0">
        <div class="card-header">
          <h2>資產餘額</h2>
          <div class="tag">賬戶資產</div>
        </div>
        <div class="table-container">
          <table class="balance-table">
            <thead>
              <tr>
                <th>資產</th>
                <th>可用餘額</th>
                <th>凍結餘額</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="balance in filteredBalances" :key="balance.asset">
                <td class="asset-col">
                  <div class="asset-name">{{ balance.asset }}</div>
                </td>
                <td>{{ formatNumber(balance.availableBalance) }}</td>
                <td>{{ formatNumber(balance.initialMargin) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card position-card" v-if="filteredPositions.length > 0">
        <div class="card-header">
          <h2>持倉信息</h2>
          <div class="tag">當前持倉</div>
        </div>
        <div class="table-container">
          <table class="position-table">
            <thead>
              <tr>
                <th>交易對</th>
                <th>倉位數量</th>
                <th>入場價格</th>
                <th>標記價格</th>
                <th>未實現盈虧</th>
                <th>槓桿</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="position in filteredPositions" :key="position.symbol">
                <td class="symbol-col">{{ position.symbol }}</td>
                <td :class="getColorClass(position.positionAmt)">{{ position.positionAmt }}</td>
                <td>{{ formatNumber(position.entryPrice) }}</td>
                <td>{{ formatNumber(position.markPrice) }}</td>
                <td :class="getColorClass(position.unrealizedProfit)">
                  {{ formatNumber(position.unrealizedProfit) }}
                </td>
                <td>{{ position.leverage }}×</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="footer-section">
      <div class="disclaimer">
        此測試介面僅用於測試 WebSocket 連接。請確保您了解交易風險。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useAccountWebSocket } from '@/composables/useAccountWebSocket';
import { formatNumberWithCommas } from '@/utils/numberFormat';

// 使用帳戶WebSocket組合式函數
const { 
  connect: connectWs, 
  disconnect: disconnectWs, 
  isConnected,
  lastUpdate,
  accountData, 
  balances, 
  positions,
  send,
  placeOrder,
  cancelOrder
} = useAccountWebSocket('binance');

// 初始化訂單表單
const orderForm = ref({
  symbol: 'BTCUSDT',
  side: 'BUY',
  type: 'LIMIT',
  price: '',
  quantity: '',
  timeInForce: 'GTC'
});

// 初始化取消訂單表單
const cancelForm = ref({
  symbol: 'BTCUSDT',
  orderId: ''
});

// 狀態標記
const isOrderSubmitting = ref(false);
const isCancelSubmitting = ref(false);
const testMode = ref(true);

// 幣安連接錯誤狀態
const binanceConnectError = ref(false);
const binanceErrorMessage = ref('');

// 響應和錯誤信息
const orderResponse = ref<any>(null);
const orderError = ref<string | null>(null);
const cancelResponse = ref<any>(null);
const cancelError = ref<string | null>(null);

// 連接WebSocket
const connect = async () => {
  try {
    await connectWs();
    // 清除錯誤狀態
    binanceConnectError.value = false;
    binanceErrorMessage.value = '';
  } catch (error) {
    console.error('連接失敗:', error);
    // 可以在這裡設置錯誤狀態，但因為未連接，所以不會顯示幣安狀態
  }
};

// 斷開WebSocket
const disconnect = () => {
  disconnectWs();
  // 清除錯誤狀態
  binanceConnectError.value = false;
  binanceErrorMessage.value = '';
};

// 重新連接幣安
const reconnectBinance = async () => {
  try {
    // 首先發送刷新請求，這將嘗試重新建立與幣安的連接
    await refreshAccountData();
    
    // 如果成功刷新，清除錯誤狀態
    binanceConnectError.value = false;
    binanceErrorMessage.value = '';
    
  } catch (error) {
    console.error('重新連接幣安失敗:', error);
    // 設置更詳細的錯誤信息
    if (error instanceof Error) {
      binanceErrorMessage.value = error.message;
    } else {
      binanceErrorMessage.value = '重新連接失敗，請檢查網絡和API密鑰';
    }
  }
};

// 刷新帳戶數據
const refreshAccountData = async () => {
  try {
    // 發送刷新請求
    await send({ type: 'refresh' });
  } catch (error) {
    console.error('刷新數據失敗:', error);
    // 設置錯誤狀態
    binanceConnectError.value = true;
    
    if (error instanceof Error) {
      binanceErrorMessage.value = error.message;
    } else if (typeof error === 'string') {
      binanceErrorMessage.value = error;
    } else {
      binanceErrorMessage.value = 'WebSocket 連接錯誤';
    }
    
    throw error; // 重新拋出錯誤以便調用者處理
  }
};

// 提交訂單
const submitOrder = async () => {
  orderResponse.value = null;
  orderError.value = null;

  // 驗證必填欄位
  if (!orderForm.value.symbol) {
    orderError.value = '請輸入交易對';
    return;
  }
  if (!orderForm.value.side) {
    orderError.value = '請選擇方向';
    return;
  }
  if (!orderForm.value.type) {
    orderError.value = '請選擇訂單類型';
    return;
  }
  // 市價單不需要價格，限價單需要價格
  if (orderForm.value.type === 'LIMIT' && !orderForm.value.price) {
    orderError.value = '限價單需要設置價格';
    return;
  }
  if (!orderForm.value.quantity) {
    orderError.value = '請輸入數量';
    return;
  }

  try {
    isOrderSubmitting.value = true;
    
    // 構建訂單參數 - 僅包含必要參數
    const orderParams = {
      // 基本訂單參數
      symbol: orderForm.value.symbol,
      side: orderForm.value.side,
      type: orderForm.value.type,
      quantity: orderForm.value.quantity,
      
      // 時間和請求相關參數
      timestamp: Date.now(),
      recvWindow: 60000
    };

    // 設置測試模式參數
    if (testMode.value) {
      orderParams.test = 'TRUE';
    }

    // 根據訂單類型添加特定參數
    if (orderForm.value.type === 'LIMIT') {
      orderParams.price = orderForm.value.price;
      orderParams.timeInForce = 'GTC'; // 一直有效直到取消
    }

    // 記錄訂單提交
    console.log('提交訂單參數：', orderParams);

    // 發送下單請求 - 使用更新後的placeOrder方法
    const result = await placeOrder(orderParams);
    console.log('訂單響應：', result);

    // 處理響應
    if (result.success === false) {
      orderError.value = result.error || '下單失敗，請檢查輸入參數';
      
      // 檢查是否是WebSocket連接錯誤
      if (result.error && (
          result.error.includes('WebSocket') || 
          result.error.includes('連接') || 
          result.error.includes('網絡') ||
          result.error.includes('no close frame')
      )) {
        binanceConnectError.value = true;
        binanceErrorMessage.value = result.error;
      }
      
      return;
    }

    // 成功處理
    orderResponse.value = result;
    
    // 更新賬戶信息
    try {
      await refreshAccountData();
      // 成功刷新賬戶數據，連接正常
      binanceConnectError.value = false;
      binanceErrorMessage.value = '';
    } catch (error) {
      console.error('刷新賬戶數據出錯:', error);
      // 這裡不設置訂單錯誤，因為訂單已經成功
      // 但標記幣安連接可能有問題
      binanceConnectError.value = true;
      binanceErrorMessage.value = '訂單已提交，但獲取最新賬戶數據時出錯';
    }
  } catch (error) {
    console.error('下單錯誤:', error);
    orderError.value = error.message || '下單過程中發生錯誤';
    
    // 檢查是否是WebSocket連接錯誤
    if (error.message && (
        error.message.includes('WebSocket') || 
        error.message.includes('連接') || 
        error.message.includes('網絡') ||
        error.message.includes('no close frame')
    )) {
      binanceConnectError.value = true;
      binanceErrorMessage.value = error.message;
    }
  } finally {
    isOrderSubmitting.value = false;
  }
};

// 提交取消訂單
const submitCancelOrder = async () => {
  // 清除之前的結果
  cancelResponse.value = null;
  cancelError.value = null;
  
  try {
    isCancelSubmitting.value = true;
    
    // 檢查必填字段
    if (!cancelForm.value.symbol) {
      throw new Error('請輸入交易對');
    }
    
    if (!cancelForm.value.orderId) {
      throw new Error('請輸入訂單ID');
    }
    
    // 構建取消訂單參數
    // 參考：https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-api#cancel-order-trade
    const cancelParams = {
      symbol: cancelForm.value.symbol,
      orderId: cancelForm.value.orderId,
      timestamp: Date.now(), // 添加timestamp參數
      recvWindow: 60000 // 添加recvWindow參數，避免時間同步問題
    };
    
    console.log('提交取消訂單:', cancelParams);
    
    // 發送取消訂單請求
    const result = await cancelOrder(cancelParams);
    console.log('取消訂單響應:', result);
    
    // 檢查響應
    if (result && result.error) {
      // API 返回了錯誤
      const errorMsg = `錯誤 ${result.error.code}: ${result.error.msg}`;
      cancelError.value = errorMsg;
      
      // 檢查是否是WebSocket連接錯誤
      if (result.error.msg && (
          result.error.msg.includes('WebSocket') || 
          result.error.msg.includes('連接') || 
          result.error.msg.includes('網絡') ||
          result.error.msg.includes('no close frame')
      )) {
        binanceConnectError.value = true;
        binanceErrorMessage.value = result.error.msg;
      }
      
      throw new Error(errorMsg);
    }
    
    cancelResponse.value = result;
    
    // 取消訂單成功後刷新賬戶數據
    try {
      await refreshAccountData();
      // 成功刷新賬戶數據，連接正常
      binanceConnectError.value = false;
      binanceErrorMessage.value = '';
    } catch (error) {
      console.error('刷新賬戶數據出錯:', error);
      // 這裡不設置取消訂單錯誤，因為取消訂單可能已經成功
      // 但標記幣安連接可能有問題
      binanceConnectError.value = true;
      binanceErrorMessage.value = '訂單可能已取消，但獲取最新賬戶數據時出錯';
    }
    
  } catch (error) {
    console.error('取消訂單錯誤:', error);
    if (error instanceof Error) {
      cancelError.value = error.message;
      
      // 檢查是否是WebSocket連接錯誤
      if (error.message && (
          error.message.includes('WebSocket') || 
          error.message.includes('連接') || 
          error.message.includes('網絡') ||
          error.message.includes('no close frame')
      )) {
        binanceConnectError.value = true;
        binanceErrorMessage.value = error.message;
      }
    } else if (typeof error === 'object' && error !== null) {
      cancelError.value = JSON.stringify(error);
    } else {
      cancelError.value = String(error);
    }
  } finally {
    isCancelSubmitting.value = false;
  }
};

// 格式化數字
const formatNumber = (value: string | number | undefined) => {
  if (value === undefined || value === null) return '0';
  return formatNumberWithCommas(Number(value));
};

// 格式化時間
const formatTime = (date: Date) => {
  return date.toLocaleTimeString();
};

// 獲取顏色類
const getColorClass = (value: string | number | undefined) => {
  if (value === undefined || value === null) return '';
  const numValue = Number(value);
  if (numValue > 0) return 'positive';
  if (numValue < 0) return 'negative';
  return '';
};

// 幣安連接狀態
const binanceConnected = computed(() => {
  // 檢查是否有賬戶數據並且是否包含API類型信息
  return !!accountData.value && 
         !!accountData.value.api_type && 
         (accountData.value.api_type.includes('WebSocket') || accountData.value.api_type.includes('REST'));
});

// 幣安連接類型
const binanceConnectionType = computed(() => {
  if (!accountData.value || !accountData.value.api_type) {
    return '未連接';
  }
  return accountData.value.api_type || '未知連接類型';
});

// 是否使用 WebSocket API
const isWebSocketAPI = computed(() => {
  return !!accountData.value && 
         !!accountData.value.api_type && 
         accountData.value.api_type.includes('WebSocket');
});

// 是否使用 REST API
const isRestAPI = computed(() => {
  return !!accountData.value && 
         !!accountData.value.api_type && 
         accountData.value.api_type.includes('REST');
});

// 過濾有餘額的資產
const filteredBalances = computed(() => {
  return balances.value.filter(b => Number(b.availableBalance) > 0 || Number(b.initialMargin) > 0);
});

// 過濾有持倉的交易對
const filteredPositions = computed(() => {
  return positions.value.filter(p => Number(p.positionAmt) !== 0);
});

// 賬戶摘要數據
const availableBalance = computed(() => accountData.value.availableBalance || '0');
const totalWalletBalance = computed(() => accountData.value.totalWalletBalance || '0');
const totalUnrealizedProfit = computed(() => accountData.value.totalUnrealizedProfit || '0');

// 組件掛載時自動連接到WebSocket
onMounted(async () => {
  try {
    console.log('TradeTestView組件已掛載，嘗試連接到WebSocket...');
    
    // 連接到WebSocket，設置超時處理
    const connectionTimeout = 10000; // 10秒超時
    
    // 創建Promise競爭：連接 vs 超時
    const connectionResult = await Promise.race([
      connectWs(),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('連接WebSocket超時，請稍後重試')), connectionTimeout)
      )
    ]);
    
    console.log('WebSocket連接結果:', connectionResult);
    
    // 檢查連接是否成功
    if (isConnected.value) {
      console.log('WebSocket連接成功，正在獲取賬戶數據...');
      
      try {
        await refreshAccountData();
        console.log('賬戶數據已加載');
        
        // 設置定期檢查幣安連接狀態
        setInterval(() => {
          // 如果有帳戶數據但最後更新時間超過2分鐘，可能存在連接問題
          if (isConnected.value && lastUpdate.value) {
            const now = new Date();
            const timeDiff = now.getTime() - lastUpdate.value.getTime();
            
            // 如果超過2分鐘沒有更新，標記為可能出現錯誤
            if (timeDiff > 120000) { // 2分鐘 = 120000毫秒
              binanceConnectError.value = true;
              binanceErrorMessage.value = '長時間未收到數據更新，可能連接已斷開';
              console.warn('幣安連接可能已斷開，長時間未收到數據更新');
            }
          }
        }, 60000); // 每分鐘檢查一次
        
      } catch (error) {
        console.error('獲取賬戶數據出錯:', error);
        binanceConnectError.value = true;
        binanceErrorMessage.value = error instanceof Error ? error.message : '獲取賬戶數據失敗，幣安連接可能有問題';
      }
    } else {
      console.error('WebSocket連接失敗');
      orderError.value = '無法連接到WebSocket服務，請稍後重試';
    }
  } catch (error) {
    console.error('掛載組件時發生錯誤:', error);
    orderError.value = `初始化錯誤: ${error.message || '未知錯誤'}`;
  }
  
  // 監聽網絡狀態變化
  window.addEventListener('online', async () => {
    if (isConnected.value && binanceConnectError.value) {
      console.log('網絡恢復連接，嘗試重新連接幣安');
      await reconnectBinance();
    }
  });
  
  window.addEventListener('offline', () => {
    if (isConnected.value) {
      binanceConnectError.value = true;
      binanceErrorMessage.value = '網絡連接已斷開，請檢查您的網絡連接';
      console.warn('網絡已斷開，幣安連接可能受影響');
    }
  });
});
</script>

<style scoped>
.trade-test-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  color: #263238;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.page-header {
  margin-bottom: 24px;
  border-bottom: 2px solid #e0e0e0;
  padding-bottom: 16px;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 600;
  color: #1a237e;
  margin: 0;
}

.sub-header {
  font-size: 1rem;
  font-weight: 500;
  color: #78909c;
  margin-top: 8px;
}

.api-info {
  margin-top: 10px;
  padding: 10px 15px;
  background-color: #e8f5e9;
  border-left: 4px solid #43a047;
  border-radius: 4px;
  font-size: 0.9rem;
  color: #2e7d32;
  display: flex;
  align-items: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  animation: fadeIn 0.5s ease-in-out;
}

.api-badge {
  background-color: #43a047;
  color: white;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
  margin-right: 10px;
  display: inline-block;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 連接狀態區塊 */
.connection-status {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  padding: 15px;
  background-color: #f7f9fc;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border-left: 4px solid #cfd8dc;
  transition: all 0.3s ease;
}

.connection-status.connected {
  border-left-color: #43a047;
  background-color: #f1f8e9;
}

.connection-status.disconnected {
  border-left-color: #e53935;
  background-color: #fef8f8;
}

.connection-status:hover {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.status-indicator {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background-color: #e0e0e0;
  margin-right: 12px;
  box-shadow: 0 0 0 2px rgba(224, 224, 224, 0.3);
  transition: all 0.3s ease;
}

.status-indicator.active {
  background-color: #43a047;
  box-shadow: 0 0 0 2px rgba(67, 160, 71, 0.3);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(67, 160, 71, 0.7);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(67, 160, 71, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(67, 160, 71, 0);
  }
}

.connection-status span {
  font-size: 1rem;
  font-weight: 500;
}

.connection-info {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.connection-info span {
  font-size: 0.9rem;
  color: #78909c;
}

.connection-actions {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.connection-actions button {
  min-width: 80px;
}

.connect-btn {
  background-color: #43a047;
}

.connect-btn:hover {
  background-color: #388e3c;
}

.disconnect-btn {
  background-color: #e53935;
}

.disconnect-btn:hover {
  background-color: #d32f2f;
}

.icon {
  font-size: 0.8em;
  margin-right: 4px;
}

/* 通用卡片樣式 */
.card {
  background-color: white;
  border-radius: 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  padding: 24px;
  margin-bottom: 24px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  border: 1px solid #f0f0f0;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.card h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #1a237e;
  margin-top: 0;
  margin-bottom: 20px;
  border-bottom: 2px solid #f5f5f5;
  padding-bottom: 10px;
}

.card h3 {
  font-size: 1.2rem;
  font-weight: 500;
  color: #37474f;
  margin-top: 16px;
  margin-bottom: 12px;
}

/* 卡片容器 */
.cards-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .cards-container {
    grid-template-columns: 1fr;
  }
}

/* 帳戶資訊卡片 */
.account-info {
  background: linear-gradient(to right, #f7f9fc, #ffffff);
  border-left: 4px solid #1a237e;
}

.refresh-action {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.refresh-action button {
  display: flex;
  align-items: center;
  gap: 6px;
}

.refresh-action button::before {
  content: "↻";
  font-size: 1.2em;
}

.refresh-action span {
  font-size: 0.9rem;
  color: #78909c;
}

.account-summary {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}

@media (max-width: 600px) {
  .account-summary {
    grid-template-columns: 1fr;
  }
}

.summary-item {
  background-color: #f9fafc;
  padding: 16px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  border: 1px solid #f0f4f8;
  transition: all 0.2s ease;
}

.summary-item:hover {
  background-color: #ffffff;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08);
}

.label {
  font-size: 0.9rem;
  color: #546e7a;
  margin-bottom: 8px;
  font-weight: 500;
}

.value {
  font-size: 1.3rem;
  font-weight: 600;
  color: #263238;
}

.subtext {
  font-size: 0.8rem;
  color: #90a4ae;
  margin-top: 6px;
}

.not-connected-message {
  display: flex;
  align-items: center;
  padding: 16px;
  background-color: #ffebee;
  border-radius: 8px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.message-icon {
  font-size: 2rem;
  color: #e53935;
  margin-right: 16px;
  background-color: rgba(229, 57, 53, 0.1);
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.message-content {
  flex: 1;
}

.message-content h3 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #37474f;
  margin-top: 0;
  margin-bottom: 8px;
}

.message-content p {
  margin: 0;
  color: #78909c;
}

/* 下單和取消訂單表單 */
.form-group {
  margin-bottom: 18px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #37474f;
  font-size: 0.95rem;
}

.form-group input, 
.form-group select {
  width: 100%;
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 1rem;
  transition: all 0.2s ease;
  background-color: #fafafa;
  color: #37474f;
}

.form-group input:focus, 
.form-group select:focus {
  border-color: #1976d2;
  outline: none;
  box-shadow: 0 0 0 2px rgba(25, 118, 210, 0.2);
  background-color: #ffffff;
}

.form-group input:hover, 
.form-group select:hover {
  border-color: #bbdefb;
}

.form-group input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.input-with-addon {
  display: flex;
  align-items: center;
}

.input-with-addon input {
  flex: 1;
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}

.addon {
  padding: 12px 14px;
  background-color: #e0e0e0;
  border-top-right-radius: 6px;
  border-bottom-right-radius: 6px;
  font-weight: 500;
  font-size: 0.9rem;
  color: #546e7a;
}

.direction-select.buy {
  border-left: 4px solid #43a047;
}

.direction-select.sell {
  border-left: 4px solid #e53935;
}

.test-mode-group {
  padding: 15px;
  border-radius: 8px;
  background-color: #fff9c4;
  border: 1px solid #fff176;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.checkbox-text {
  font-weight: 500;
}

.test-mode-hint {
  margin-top: 8px;
  font-size: 0.9rem;
  font-style: italic;
  color: #ff6f00;
}

/* 表單操作按鈕 */
.form-actions {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}

button {
  padding: 10px 20px;
  background-color: #1976d2;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.95rem;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 40px;
}

button:hover {
  background-color: #1565c0;
  transform: translateY(-1px);
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

button:active {
  transform: translateY(0);
  box-shadow: none;
}

button:disabled {
  background-color: #b0bec5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.submit-btn.test-btn {
  background-color: #fb8c00;
}

.submit-btn.test-btn:hover {
  background-color: #f57c00;
}

.submit-btn.live-btn {
  background-color: #e53935;
}

.submit-btn.live-btn:hover {
  background-color: #d32f2f;
}

.cancel-btn {
  background-color: #e53935;
}

.cancel-btn:hover {
  background-color: #d32f2f;
}

.refresh-btn {
  background-color: #546e7a;
}

.refresh-btn:hover {
  background-color: #455a64;
}

/* 響應和錯誤容器 */
.response-container, .error-container {
  margin-top: 24px;
  padding: 16px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.response-container {
  background-color: #e8f5e9;
  border-left: 4px solid #43a047;
}

.error-container {
  background-color: #ffebee;
  border-left: 4px solid #e53935;
}

.error-message {
  color: #d32f2f;
  font-weight: 500;
}

.response-summary {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  background-color: white;
  padding: 12px;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.summary-row {
  display: flex;
  align-items: center;
}

.summary-label {
  min-width: 100px;
  font-weight: 500;
  color: #546e7a;
}

.summary-value {
  font-weight: 600;
  color: #263238;
}

pre {
  background-color: #f5f7fa;
  padding: 16px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.9em;
  border: 1px solid #eaeef2;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
  color: #37474f;
}

/* 卡片頭部樣式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tag {
  padding: 4px 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: 500;
  color: #78909c;
}

.test-tag {
  background-color: #fff9c4;
  color: #ff6f00;
}

/* 資料區域 */
.data-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

@media (max-width: 992px) {
  .data-section {
    grid-template-columns: 1fr;
  }
}

.table-container {
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}

/* 表格樣式 */
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  border-radius: 8px;
  overflow: hidden;
}

th, td {
  padding: 14px 16px;
  text-align: left;
}

th {
  background-color: #f5f7fa;
  font-weight: 600;
  color: #37474f;
  border-bottom: 2px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 10;
}

td {
  border-bottom: 1px solid #eceff1;
}

tbody tr {
  transition: background-color 0.2s ease;
}

tbody tr:last-child td {
  border-bottom: none;
}

tbody tr:hover {
  background-color: #f9fafc;
}

.asset-col {
  display: flex;
  align-items: center;
}

.asset-name {
  margin-right: 8px;
  font-weight: 600;
}

.symbol-col {
  font-weight: 600;
  color: #1a237e;
}

/* 正負值顏色 */
.positive {
  color: #43a047;
  font-weight: 600;
}

.negative {
  color: #e53935;
  font-weight: 600;
}

.field-hint {
  font-size: 0.8rem;
  color: #78909c;
  margin-top: 8px;
}

/* 頁腳區域 */
.footer-section {
  margin-top: 24px;
  padding: 16px;
  background-color: #f7f9fc;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.disclaimer {
  font-size: 0.9rem;
  color: #78909c;
}

/* 響應式調整 */
@media (max-width: 992px) {
  .trade-test-container {
    padding: 16px;
  }
  
  .card {
    padding: 20px;
  }
  
  .account-summary {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 480px) {
  .account-summary {
    grid-template-columns: 1fr;
  }
  
  .refresh-action {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .form-actions {
    justify-content: center;
  }
  
  button {
    width: 100%;
  }
  
  .connection-status {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
  
  .connection-info, .connection-actions {
    margin-left: 0;
    width: 100%;
  }
}

/* API 類型指示器樣式 */
.api-type-indicator {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  font-size: 0.85rem;
}

.api-badge {
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 500;
  margin-right: 8px;
}

.ws-api {
  background-color: rgba(52, 152, 219, 0.15);
  color: #3498db;
  border: 1px solid rgba(52, 152, 219, 0.3);
}

.rest-api {
  background-color: rgba(243, 156, 18, 0.15);
  color: #d35400;
  border: 1px solid rgba(243, 156, 18, 0.3);
}

.api-info-icon {
  color: #7f8c8d;
  cursor: help;
}

/* 幣安連接狀態樣式 */
.connection-status.binance-connection {
  border-left-color: #3498db;
  background-color: rgba(52, 152, 219, 0.05);
  margin-top: -16px;
  margin-bottom: 24px;
}

.connection-status.binance-connection.connected {
  background-color: rgba(52, 152, 219, 0.1);
}

.connection-status.binance-connection.disconnected {
  border-left-color: #e74c3c;
  background-color: rgba(231, 76, 60, 0.05);
}

.connection-status.binance-connection.websocket-api {
  border-left-color: #3498db;
}

.connection-status.binance-connection.rest-api {
  border-left-color: #f39c12;
}

.connection-status.binance-connection .status-indicator.active {
  background-color: #3498db;
  box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.3);
}

.connection-status.binance-connection.rest-api .status-indicator.active {
  background-color: #f39c12;
  box-shadow: 0 0 0 2px rgba(243, 156, 18, 0.3);
}

.connection-status.binance-connection span {
  color: #2c3e50;
}

.connection-status.binance-connection .connection-info {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 10px;
}

.connection-status.binance-connection .connection-info span {
  font-size: 0.9rem;
  color: #7f8c8d;
}

.connection-status.binance-connection .connection-info .connection-type {
  font-weight: 500;
  padding: 3px 8px;
  border-radius: 4px;
}

.connection-status.binance-connection .connection-info .connection-type.websocket-api {
  background-color: rgba(52, 152, 219, 0.15);
  color: #3498db;
  border: 1px solid rgba(52, 152, 219, 0.3);
}

.connection-status.binance-connection .connection-info .connection-type.rest-api {
  background-color: rgba(243, 156, 18, 0.15);
  color: #d35400;
  border: 1px solid rgba(243, 156, 18, 0.3);
}

.api-info-icon {
  color: #7f8c8d;
  cursor: help;
}

/* 幣安連接錯誤信息樣式 */
.binance-error-message {
  display: flex;
  align-items: flex-start;
  padding: 16px;
  background-color: #ffebee;
  border-radius: 8px;
  margin-top: -16px;
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  border-left: 4px solid #e74c3c;
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.error-icon {
  font-size: 2rem;
  color: #e53935;
  margin-right: 16px;
  background-color: rgba(229, 57, 53, 0.1);
  width: 50px;
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.error-content {
  flex: 1;
}

.error-title {
  font-size: 1.5rem;
  font-weight: 600;
  color: #37474f;
  margin-top: 0;
  margin-bottom: 8px;
}

.error-desc {
  margin: 0;
  color: #78909c;
}

.error-tips {
  margin-top: 8px;
  font-size: 0.9rem;
  color: #78909c;
}

.connection-status.binance-connection.error {
  border-left-color: #e74c3c;
  background-color: rgba(231, 76, 60, 0.1);
}

.connection-status.binance-connection .status-indicator.error {
  background-color: #e74c3c;
  box-shadow: 0 0 0 2px rgba(231, 76, 60, 0.3);
  animation: pulse-error 2s infinite;
}

@keyframes pulse-error {
  0% {
    box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7);
  }
  70% {
    box-shadow: 0 0 0 6px rgba(231, 76, 60, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(231, 76, 60, 0);
  }
}

.connection-status.binance-connection .connection-info .connection-type.error {
  background-color: rgba(231, 76, 60, 0.15);
  color: #e74c3c;
  border: 1px solid rgba(231, 76, 60, 0.3);
}

.reconnect-btn {
  background-color: #e74c3c;
  color: white;
  font-weight: 500;
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.reconnect-btn:hover {
  background-color: #c0392b;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

.reconnect-btn .icon {
  font-size: 1.1em;
  margin-right: 4px;
  animation: spin 1.5s linear infinite;
  display: inline-block;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style> 