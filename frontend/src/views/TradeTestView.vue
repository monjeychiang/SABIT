<template>
  <div class="trade-test-container">
    <div class="page-header">
      <h1>WebSocket 交易測試介面</h1>
      <div class="sub-header">安全測試您的交易策略</div>
      <div class="api-info">
        <span class="api-badge">🚀 新功能</span> 
        系統已升級為使用連接管理器管理 WebSocket API，提供更穩定的連接和更高的資源利用效率
      </div>
    </div>

    <!-- 重新設計簡化版的連接狀態圖 -->
    <div class="connection-monitor">
      <h2>連接狀態監控</h2>
      
      <!-- 連接圖表主體 - 簡化版 -->
      <div class="connection-graph">
        <!-- 前端節點 -->
        <div class="graph-node frontend">
          <div class="node-icon">💻</div>
          <div class="node-title">前端應用</div>
          <div class="node-status">
            <span class="status-dot active"></span>
            <span class="status-text">已開啟</span>
          </div>
        </div>
        
        <!-- 前端到後端的連接線 -->
        <div class="connection-arrow-path" :class="{ 'active': isConnected, 'inactive': !isConnected }">
          <div class="arrow-label">WebSocket</div>
        </div>
        
        <!-- 後端節點 -->
        <div class="graph-node server" :class="{ 'active': isConnected, 'inactive': !isConnected }">
          <div class="node-icon">🖥️</div>
          <div class="node-title">後端服務</div>
          <div class="node-status">
            <span class="status-dot" :class="{ 'active': isConnected, 'inactive': !isConnected }"></span>
            <span class="status-text">{{ isConnected ? '已連接' : '未連接' }}</span>
          </div>
          <div v-if="isConnected" class="node-text">
            {{ lastUpdate ? getTimeSinceLastUpdate() : '尚無更新' }}
          </div>
        </div>
        
        <!-- 後端到連接管理器的連接線 -->
        <div class="connection-arrow-path" :class="{ 'active': isConnected, 'inactive': !isConnected }">
          <div class="arrow-label">內部通信</div>
        </div>
        
        <!-- 連接管理器節點 -->
        <div class="graph-node manager" :class="{ 
          'active': isConnected && !binanceConnectError, 
          'error': isConnected && binanceConnectError,
          'inactive': !isConnected 
        }">
          <div class="node-icon">🔌</div>
          <div class="node-title">連接管理器</div>
          <div class="node-status">
            <span class="status-dot" :class="{ 
              'active': isConnected && !binanceConnectError, 
              'error': binanceConnectError,
              'inactive': !isConnected 
            }"></span>
            <span class="status-text">{{ isConnected ? (binanceConnectError ? '連接錯誤' : '運行中') : '未啟動' }}</span>
          </div>
        </div>
        
        <!-- 連接管理器到交易所的連接線 -->
        <div class="connection-arrow-path" :class="{ 
          'active': isConnected && binanceConnected, 
          'inactive': !isConnected || !binanceConnected,
          'error': isConnected && binanceConnectError 
        }">
          <div class="arrow-label">{{ 
            (isWebSocketAPI && binanceConnected) ? 'WebSocket API' : 
            (isRestAPI && binanceConnected) ? 'REST API' : 
            '尚未連接' 
          }}</div>
        </div>
        
        <!-- 交易所節點 -->
        <div class="graph-node exchange" :class="{ 
          'active': isConnected && binanceConnected && !binanceConnectError, 
          'error': isConnected && binanceConnectError,
          'inactive': !isConnected || !binanceConnected,
          'websocket': isConnected && binanceConnected && isWebSocketAPI,
          'rest': isConnected && binanceConnected && isRestAPI
        }">
          <div class="node-icon">💹</div>
          <div class="node-title">幣安交易所</div>
          <div class="node-status">
            <span class="status-dot" :class="{ 
              'active': isConnected && binanceConnected && !binanceConnectError, 
              'error': isConnected && binanceConnectError,
              'inactive': !isConnected || !binanceConnected 
            }"></span>
            <span class="status-text">{{ 
              !isConnected ? '未連接' : 
              binanceConnectError ? '連接錯誤' :
              binanceConnected ? '已連接' : '未連接'
            }}</span>
          </div>
          <div v-if="isConnected && binanceConnected && !binanceConnectError" class="node-text">
            {{ binanceConnectionType }}
          </div>
        </div>
      </div>
      
      <!-- 按鈕區域 -->
      <div class="connection-buttons">
        <button @click="connect" :disabled="isConnected" class="control-btn connect">
          <span class="btn-icon">🔄</span> 連接服務
        </button>
        <button @click="disconnect" :disabled="!isConnected" class="control-btn disconnect">
          <span class="btn-icon">⏹️</span> 斷開連接
        </button>
        <button @click="refreshAccountData" :disabled="!isConnected" class="control-btn refresh">
          <span class="btn-icon">🔄</span> 刷新數據
        </button>
        <button @click="reconnectBinance" :disabled="!isConnected || !binanceConnectError" class="control-btn reconnect">
          <span class="btn-icon">🔌</span> 重連交易所
        </button>
      </div>
      
      <!-- 連接詳情區 -->
      <div class="connection-info-panel" v-if="isConnected">
        <div class="info-row">
          <div class="info-label">連接類型</div>
          <div class="info-value">{{ binanceConnectionType }}</div>
        </div>
        <div class="info-row">
          <div class="info-label">狀態更新</div>
          <div class="info-value">{{ lastUpdate ? formatTime(lastUpdate) : '尚未更新' }}</div>
        </div>
        <div class="info-row">
          <div class="info-label">前端連接</div>
          <div class="info-value success">已連接</div>
        </div>
        <div class="info-row">
          <div class="info-label">持久連接模式</div>
          <div class="info-value">已啟用</div>
        </div>
        <div class="info-row error" v-if="binanceConnectError">
          <div class="error-message">{{ binanceErrorMessage || '連接意外斷開，請嘗試重新連接' }}</div>
        </div>
      </div>
    </div>

    <div class="cards-container" v-if="isConnected">
      <div class="card place-order">
        <div class="card-header">
          <h2>下單測試</h2>
          <div class="tag">實盤模式</div>
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
        <div class="form-actions">
          <button @click="submitOrder" :disabled="isOrderSubmitting" class="submit-btn">
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
            <div class="summary-row" v-if="orderLatency > 0">
              <div class="summary-label">下單延遲:</div>
              <div class="summary-value">
                <span class="latency-badge" :class="getLatencyClass(orderLatency)">
                  {{ orderLatency }}ms
                  <span class="latency-text">{{ getLatencyText(orderLatency) }}</span>
                </span>
              </div>
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
            <div class="summary-row" v-if="cancelLatency > 0">
              <div class="summary-label">取消延遲:</div>
              <div class="summary-value">
                <span class="latency-badge" :class="getLatencyClass(cancelLatency)">
                  {{ cancelLatency }}ms
                  <span class="latency-text">{{ getLatencyText(cancelLatency) }}</span>
                </span>
              </div>
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

    <div class="card latency-stats" v-if="isConnected && latencyHistory.length > 0">
      <div class="card-header">
        <h2>延遲統計</h2>
        <div class="tag">WebSocket性能</div>
      </div>
      
      <div class="latency-overview">
        <div class="average-latency">
          <div class="latency-label">平均延遲</div>
          <div class="latency-value">
            <span class="latency-badge" :class="getLatencyClass(averageLatency)">
              {{ averageLatency }}ms
            </span>
          </div>
        </div>
      </div>
      
      <div class="latency-history">
        <h3>最近操作延遲 (最多 {{ MAX_HISTORY }} 筆)</h3>
        <table class="latency-table">
          <thead>
            <tr>
              <th>時間</th>
              <th>操作</th>
              <th>交易對</th>
              <th>類型</th>
              <th>延遲</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in latencyHistory" :key="record.id">
              <td>{{ new Date(record.time).toLocaleTimeString() }}</td>
              <td>{{ record.type }}</td>
              <td>{{ record.symbol }}</td>
              <td>{{ record.orderType || '-' }}</td>
              <td>
                <span class="latency-badge small" :class="getLatencyClass(record.latency)">
                  {{ record.latency }}ms
                </span>
              </td>
            </tr>
          </tbody>
        </table>
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

// 下單延遲測量變量
const orderLatency = ref(0);
const cancelLatency = ref(0);

// 幣安連接錯誤狀態
const binanceConnectError = ref(false);
const binanceErrorMessage = ref('');

// 響應和錯誤信息
const orderResponse = ref<any>(null);
const orderError = ref<string | null>(null);
const cancelResponse = ref<any>(null);
const cancelError = ref<string | null>(null);

// 延遲統計
interface LatencyRecord {
  id: number;
  type: string;
  latency: number;
  symbol: string;
  orderType: string | null;
  time: Date;
}

const latencyHistory = ref<LatencyRecord[]>([]);
const MAX_HISTORY = 10; // 最多記錄10條歷史數據

// 添加延遲數據到歷史記錄
const addLatencyRecord = (type: string, latency: number, symbol: string, orderType: string | null = null) => {
  latencyHistory.value.unshift({
    id: Date.now(),
    type,
    latency,
    symbol,
    orderType,
    time: new Date()
  });
  
  // 保持歷史記錄在最大限制內
  if (latencyHistory.value.length > MAX_HISTORY) {
    latencyHistory.value = latencyHistory.value.slice(0, MAX_HISTORY);
  }
};

// 計算平均延遲
const averageLatency = computed(() => {
  if (latencyHistory.value.length === 0) return 0;
  const sum = latencyHistory.value.reduce((acc, item) => acc + item.latency, 0);
  return Math.round(sum / latencyHistory.value.length);
});

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

// 斷開WebSocket - 注意：這裡會斷開前端和後端之間的連接，但後端與交易所的連接會保持
const disconnect = () => {
  // 調用組合函數的 disconnect 方法
  // 在用戶主動點擊斷開按鈕時，我們應該斷開前端到後端的連接
  // 但由於設置了持久連接模式，後端與交易所的連接會保持
  disconnectWs();
  
  // 清除錯誤狀態
  binanceConnectError.value = false;
  binanceErrorMessage.value = '';
  
  console.log('用戶已斷開WebSocket前端連接，後端與交易所的連接仍然保持');
};

// 重新連接幣安
const reconnectBinance = async () => {
  try {
    console.log('[TradeTestView] 嘗試通過連接管理器重連到幣安...');
    
    // 首先發送刷新請求，這將嘗試重新建立與幣安的連接
    console.log('[TradeTestView] 發送連接重建請求');
    
    // 重置錯誤狀態，在進行新的嘗試前
    binanceConnectError.value = false;
    binanceErrorMessage.value = '';
    
    // 發送特定的重新連接請求，要求後端重新建立連接
    await send({ 
      type: 'reconnect', 
      timestamp: Date.now(),
      target: 'binance',
      force: true, // 強制重新建立連接，即使後端認為連接是活躍的
      reconnect_options: {
        clear_cache: true,  // 清除可能的緩存數據
        reset_authentication: true // 重設驗證
      }
    });
    
    // 等待連接建立
    console.log('[TradeTestView] 等待連接建立...');
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // 刷新賬戶數據以確認連接
    console.log('[TradeTestView] 刷新賬戶數據以驗證連接');
    await refreshAccountData();
    
    console.log('[TradeTestView] 幣安連接重建成功');
    
  } catch (error: unknown) {
    console.error('[TradeTestView] 重新連接幣安失敗:', error);
    
    // 設置更詳細的錯誤信息
    binanceConnectError.value = true;
    if (error instanceof Error) {
      binanceErrorMessage.value = `重連失敗: ${error.message}`;
      console.error(`[TradeTestView] ${error.stack || '無錯誤堆棧'}`);
    } else if (typeof error === 'string') {
      binanceErrorMessage.value = `重連失敗: ${error}`;
    } else {
      binanceErrorMessage.value = '重新連接失敗，請檢查網絡和API密鑰';
    }
  }
};

// 刷新帳戶數據
const refreshAccountData = async () => {
  try {
    console.log('[TradeTestView] 刷新帳戶數據，通過連接管理器與幣安交互...');
    
    // 發送刷新請求
    const refreshStartTime = Date.now();
    await send({ 
      type: 'refresh', 
      timestamp: refreshStartTime,
      target: 'account_data',
      options: {
        force_update: true,  // 強制從交易所獲取最新數據而非使用緩存
      }
    });
    
    const responseTime = Date.now() - refreshStartTime;
    console.log(`[TradeTestView] 帳戶數據刷新成功，耗時: ${responseTime}ms`);
    
    // 測量API響應延遲
    if (responseTime > 0) {
      // 添加到延遲歷史
      addLatencyRecord('刷新數據', responseTime, 'ALL', null);
    }
    
    // 如果之前有錯誤，現在清除它們
    if (binanceConnectError.value) {
      binanceConnectError.value = false;
      binanceErrorMessage.value = '';
      console.log('[TradeTestView] 連接恢復正常，已清除錯誤狀態');
    }
  } catch (error: unknown) {
    console.error('[TradeTestView] 刷新數據失敗:', error);
    
    // 設置錯誤狀態
    binanceConnectError.value = true;
    
    // 提供詳細的錯誤信息
    if (error instanceof Error) {
      binanceErrorMessage.value = `刷新失敗: ${error.message}`;
      console.error(`[TradeTestView] 錯誤堆棧: ${error.stack || '無堆棧信息'}`);
    } else if (typeof error === 'string') {
      binanceErrorMessage.value = `刷新失敗: ${error}`;
    } else {
      binanceErrorMessage.value = '無法獲取最新數據，請檢查網絡連接';
    }
    
    throw error; // 重新拋出錯誤以便調用者處理
  }
};

// 提交訂單
const submitOrder = async () => {
  orderResponse.value = null;
  orderError.value = null;
  orderLatency.value = 0; // 重置延遲時間

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
    const orderParams: Record<string, any> = {
      // 基本訂單參數
      symbol: orderForm.value.symbol,
      side: orderForm.value.side,
      type: orderForm.value.type,
      quantity: orderForm.value.quantity,
      
      // 時間和請求相關參數
      timestamp: Date.now(),
      recvWindow: 60000
    };

    // 根據訂單類型添加特定參數
    if (orderForm.value.type === 'LIMIT') {
      orderParams.price = orderForm.value.price;
      orderParams.timeInForce = 'GTC'; // 一直有效直到取消
    }

    // 記錄訂單提交
    console.log('提交訂單參數：', orderParams);

    // 測量下單延遲 - 開始時間
    const startTime = Date.now();

    // 發送下單請求 - 修正：將參數包裝在data字段中
    const result = await placeOrder(orderParams);
    console.log('訂單響應：', result);

    // 計算延遲時間 (毫秒)
    orderLatency.value = Date.now() - startTime;
    
    // 添加到延遲歷史
    addLatencyRecord('下單', orderLatency.value, orderForm.value.symbol, orderForm.value.type);

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
  } catch (error: unknown) {
    console.error('下單錯誤:', error);
    const errorMsg = error instanceof Error ? error.message : '下單過程中發生錯誤';
    orderError.value = errorMsg;
    
    // 檢查是否是WebSocket連接錯誤
    if (error instanceof Error && error.message && (
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
  cancelLatency.value = 0; // 重置延遲時間
  
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
    const cancelParams: Record<string, any> = {
      symbol: cancelForm.value.symbol,
      orderId: cancelForm.value.orderId,
      timestamp: Date.now(), // 添加timestamp參數
      recvWindow: 60000 // 添加recvWindow參數，避免時間同步問題
    };
    
    console.log('提交取消訂單:', cancelParams);
    
    // 測量取消訂單延遲 - 開始時間
    const startTime = Date.now();
    
    // 發送取消訂單請求 - 修正：將參數包裝在data字段中
    const result = await cancelOrder(cancelParams);
    console.log('取消訂單響應:', result);
    
    // 計算延遲時間 (毫秒)
    cancelLatency.value = Date.now() - startTime;
    
    // 添加到延遲歷史
    addLatencyRecord('取消', cancelLatency.value, cancelForm.value.symbol, null);
    
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
    
  } catch (error: unknown) {
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

// 獲取距離上次更新的時間
const getTimeSinceLastUpdate = () => {
  if (!lastUpdate.value) return '尚無更新';
  
  const now = new Date();
  const diff = now.getTime() - lastUpdate.value.getTime();
  
  // 轉換為秒
  const seconds = Math.floor(diff / 1000);
  
  // 如果小於1分鐘
  if (seconds < 60) {
    return `${seconds}秒前`;
  }
  
  // 轉換為分鐘
  const minutes = Math.floor(seconds / 60);
  
  // 如果小於1小時
  if (minutes < 60) {
    return `${minutes}分鐘前`;
  }
  
  // 轉換為小時
  const hours = Math.floor(minutes / 60);
  
  // 如果小於1天
  if (hours < 24) {
    return `${hours}小時前`;
  }
  
  // 轉換為天
  const days = Math.floor(hours / 24);
  return `${days}天前`;
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
  // 添加更詳細的調試日誌
  console.debug('[TradeTestView] 檢查幣安連接狀態:', 
    { 
      hasAccountData: !!accountData.value, 
      apiType: accountData.value?.api_type,
      connectionStatus: accountData.value?.connection_status,
      connectionType: accountData.value?.connection_type,
      assetsCount: accountData.value?.assets_count,
      positionsCount: accountData.value?.positions_count,
      totalWalletBalance: accountData.value?.totalWalletBalance,
      availableBalance: accountData.value?.availableBalance,
      hasTotalBalance: accountData.value?.totalWalletBalance !== undefined,
      hasBalances: Array.isArray(balances.value) && balances.value.length > 0,
      hasPositions: Array.isArray(positions.value) && positions.value.length > 0
    }
  );

  // 沒有賬戶數據，肯定未連接
  if (!accountData.value) {
    console.debug('[TradeTestView] 未連接：沒有賬戶數據');
    return false;
  }
  
  // 檢查連接管理器返回的連接狀態 - 最優先級
  if (accountData.value.connection_status === 'connected' || 
      accountData.value.connection_status === 'active' ||
      accountData.value.connection_status === 'established' ||
      accountData.value.status === 'connected' ||
      accountData.value.status === 'active') {
    console.debug('[TradeTestView] 已連接：連接狀態為已連接/活躍');
    return true;
  }
  
  // 檢查連接類型
  if (accountData.value.connection_type && 
     (accountData.value.connection_type === 'websocket' || 
      accountData.value.connection_type === 'rest' || 
      accountData.value.connection_type === 'hybrid' ||
      accountData.value.connection_type.includes('websocket') ||
      accountData.value.connection_type.includes('rest'))) {
    console.debug(`[TradeTestView] 已連接：連接類型為 ${accountData.value.connection_type}`);
    return true;
  }
  
  // 檢查 API 類型
  if (accountData.value.api_type && 
     (accountData.value.api_type.includes('WebSocket') || 
      accountData.value.api_type.includes('REST') ||
      accountData.value.api_type.includes('API'))) {
    console.debug(`[TradeTestView] 已連接：API類型為 ${accountData.value.api_type}`);
    return true;
  }
  
  // 檢查是否有餘額相關信息
  if (accountData.value.totalWalletBalance !== undefined || 
      accountData.value.availableBalance !== undefined) {
    console.debug('[TradeTestView] 已連接：檢測到餘額信息');
    return true;
  }
  
  // 檢查是否有資產和持倉信息
  if ((accountData.value.assets_count !== undefined && accountData.value.assets_count > 0) || 
      (accountData.value.positions_count !== undefined && accountData.value.positions_count > 0)) {
    console.debug('[TradeTestView] 已連接：檢測到資產或持倉信息');
    return true;
  }
  
  // 檢查是否有餘額或持倉數組
  if ((Array.isArray(balances.value) && balances.value.length > 0) || 
      (Array.isArray(positions.value) && positions.value.length > 0)) {
    console.debug('[TradeTestView] 已連接：檢測到餘額或持倉數組');
    return true;
  }
  
  // 檢查是否有其他可識別的連接標識
  if (accountData.value.exchange === 'binance' || 
      accountData.value.exchange_status === 'connected' || 
      accountData.value.manager_status === 'active') {
    console.debug('[TradeTestView] 已連接：檢測到連接管理器狀態信息');
    return true;
  }

  console.debug('[TradeTestView] 未連接：所有連接檢查均未通過');
  return false;
});

// 幣安連接類型
const binanceConnectionType = computed(() => {
  if (!accountData.value) {
    return '未連接';
  }
  
  // 檢查連接管理器返回的連接類型
  if (accountData.value.connection_type) {
    if (accountData.value.connection_type === 'websocket') {
      return 'WebSocket API';
    } else if (accountData.value.connection_type === 'rest') {
      return 'REST API';
    } else if (accountData.value.connection_type === 'hybrid') {
      return 'Hybrid API (混合)';
    }
  }
  
  // 回退到原有的檢測方式
  if (accountData.value.api_type) {
    return accountData.value.api_type;
  }
  
  return accountData.value.connection_status === 'connected' ? '已連接' : '未知連接類型';
});

// 是否使用 WebSocket API
const isWebSocketAPI = computed(() => {
  // 沒有賬戶數據，則不是WebSocket API
  if (!accountData.value) return false;
  
  // 優先檢查連接類型
  if (accountData.value.connection_type) {
    // websocket或hybrid類型都可能使用WebSocket API
    if (accountData.value.connection_type === 'websocket' || 
        accountData.value.connection_type === 'hybrid' ||
        accountData.value.connection_type.includes('websocket') ||
        accountData.value.connection_type.toLowerCase().includes('ws')) {
      console.debug(`[TradeTestView] 檢測到WebSocket API: connection_type=${accountData.value.connection_type}`);
      return true;
    }
    // 如果明確指定為rest類型，則不是WebSocket API
    if (accountData.value.connection_type === 'rest' ||
        accountData.value.connection_type.includes('rest')) {
      return false;
    }
  }
  
  // 檢查API類型字段
  if (accountData.value.api_type) {
    // 檢查API類型是否包含WebSocket關鍵詞
    const isWs = accountData.value.api_type.includes('WebSocket') || 
                accountData.value.api_type.includes('websocket') ||
                accountData.value.api_type.includes('WS') ||
                accountData.value.api_type.includes('ws');
    if (isWs) {
      console.debug(`[TradeTestView] 檢測到WebSocket API: api_type=${accountData.value.api_type}`);
    }
    return isWs;
  }
  
  // 檢查連接管理器特有的字段
  if (accountData.value.manager_connection_type === 'websocket' ||
      (accountData.value.manager_info && accountData.value.manager_info.connection_type === 'websocket')) {
    console.debug('[TradeTestView] 檢測到WebSocket API: 從連接管理器信息中檢測到');
    return true;
  }
  
  // 如果沒有明確指定，則根據其他特徵判斷
  return false;
});

// 是否使用 REST API
const isRestAPI = computed(() => {
  // 沒有賬戶數據，則不是REST API
  if (!accountData.value) return false;
  
  // 如果是WebSocket API，則肯定不是純REST API
  // (雖然hybrid模式可能同時使用兩種API，但界面上我們優先展示WebSocket API)
  if (isWebSocketAPI.value) return false;
  
  // 優先檢查連接類型
  if (accountData.value.connection_type) {
    if (accountData.value.connection_type === 'rest' ||
        accountData.value.connection_type.toLowerCase().includes('rest') ||
        accountData.value.connection_type === 'http') {
      console.debug(`[TradeTestView] 檢測到REST API: connection_type=${accountData.value.connection_type}`);
      return true;
    }
  }
  
  // 檢查API類型字段
  if (accountData.value.api_type) {
    // 檢查API類型是否包含REST關鍵詞
    const isRest = accountData.value.api_type.includes('REST') || 
                  accountData.value.api_type.includes('rest') ||
                  accountData.value.api_type.includes('HTTP') ||
                  accountData.value.api_type.includes('http');
    if (isRest) {
      console.debug(`[TradeTestView] 檢測到REST API: api_type=${accountData.value.api_type}`);
    }
    return isRest;
  }
  
  // 檢查連接管理器特有的字段
  if (accountData.value.manager_connection_type === 'rest' ||
      (accountData.value.manager_info && accountData.value.manager_info.connection_type === 'rest')) {
    console.debug('[TradeTestView] 檢測到REST API: 從連接管理器信息中檢測到');
    return true;
  }
  
  // 默認情況：如果已連接但不是WebSocket API，則假定是REST API
  if (binanceConnected.value) {
    console.debug('[TradeTestView] 已連接但無法確定API類型，預設為REST API');
    return true;
  }
  
  return false;
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

// 獲取延遲等級
const getLatencyClass = (latency: number) => {
  if (!latency) return '';
  if (latency < 200) return 'latency-excellent'; // 極佳: < 200ms
  if (latency < 500) return 'latency-good';      // 良好: 200-500ms
  if (latency < 1000) return 'latency-normal';   // 一般: 500-1000ms
  return 'latency-slow';                         // 緩慢: > 1000ms
};

// 獲取延遲文本描述
const getLatencyText = (latency: number) => {
  if (!latency) return '';
  if (latency < 200) return '極佳';
  if (latency < 500) return '良好';
  if (latency < 1000) return '一般';
  return '緩慢';
};

// 組件掛載時自動連接到WebSocket
onMounted(async () => {
  try {
    console.log('[TradeTestView] 組件已掛載，嘗試連接到WebSocket...');
    
    // 連接到WebSocket，設置超時處理
    const connectionTimeout = 10000; // 10秒超時
    
    // 創建Promise競爭：連接 vs 超時
    const connectionResult = await Promise.race<any>([
      connectWs(),
      new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('連接WebSocket超時，請稍後重試')), connectionTimeout)
      )
    ]);
    
    console.log('[TradeTestView] WebSocket連接結果:', connectionResult);
    
    // 檢查連接是否成功
    if (isConnected.value) {
      console.log('[TradeTestView] WebSocket連接成功，正在獲取賬戶數據...');
      
      try {
        await refreshAccountData();
        console.log('[TradeTestView] 賬戶數據已加載');
        
        // 追蹤連接狀態和最後活動時間
        // 設置定期檢查幣安連接狀態
        setInterval(() => {
          // 如果連接到後端，但最後更新時間超過2分鐘，可能存在幣安連接問題
          if (isConnected.value && lastUpdate.value) {
            const now = new Date();
            const timeDiff = now.getTime() - lastUpdate.value.getTime();
            
            // 根據時間間隔，有不同的處理策略
            if (timeDiff > 300000) { // 5分鐘無更新
              binanceConnectError.value = true;
              binanceErrorMessage.value = '連接可能已斷開：已超過5分鐘未收到更新';
              console.warn('[TradeTestView] 連接可能已斷開：已超過5分鐘未收到更新');
              
              // 自動嘗試重新連接
              reconnectBinance().catch((e: unknown) => {
                console.error('[TradeTestView] 自動重連失敗:', e);
              });
            }
            else if (timeDiff > 120000) { // 2分鐘無更新
              binanceConnectError.value = true;
              binanceErrorMessage.value = '長時間未收到數據更新，可能連接不穩定';
              console.warn('[TradeTestView] 幣安連接可能不穩定，長時間未收到數據更新');
              
              // 嘗試刷新數據，但不重連
              refreshAccountData().catch((e: unknown) => {
                console.error('[TradeTestView] 自動刷新數據失敗:', e);
              });
            }
          }
        }, 30000); // 每30秒檢查一次
        
      } catch (error: unknown) {
        console.error('[TradeTestView] 獲取賬戶數據出錯:', error);
        binanceConnectError.value = true;
        binanceErrorMessage.value = error instanceof Error ? error.message : '獲取賬戶數據失敗，幣安連接可能有問題';
      }
    } else {
      console.error('[TradeTestView] WebSocket連接失敗');
      orderError.value = '無法連接到WebSocket服務，請稍後重試';
    }
  } catch (error: unknown) {
    console.error('[TradeTestView] 掛載組件時發生錯誤:', error);
    orderError.value = `初始化錯誤: ${error instanceof Error ? error.message : '未知錯誤'}`;
  }
  
  // 監聽網絡狀態變化
  window.addEventListener('online', async () => {
    console.log('[TradeTestView] 網絡連接已恢復');
    if (isConnected.value && binanceConnectError.value) {
      console.log('[TradeTestView] 嘗試在網絡恢復後重新連接幣安');
      await reconnectBinance();
    }
  });
  
  window.addEventListener('offline', () => {
    console.log('[TradeTestView] 網絡連接已斷開');
    if (isConnected.value) {
      binanceConnectError.value = true;
      binanceErrorMessage.value = '網絡連接已斷開，請檢查您的網絡連接';
      console.warn('[TradeTestView] 網絡已斷開，幣安連接可能受影響');
    }
  });
  
  // 監聽登出事件，確保在用戶登出時斷開WebSocket前端連接
  window.addEventListener('logout-event', () => {
    console.log('[TradeTestView] 檢測到登出事件，斷開TradeTestView中的WebSocket前端連接');
    if (isConnected.value) {
      disconnect();
    }
  });
});

// 添加明確的提醒，表示頁面卸載時連接仍然保持
console.log('TradeTestView 使用持久連接模式，離開頁面時連接將保持活躍');
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

/* 重新設計簡化版的連接狀態圖 */
.connection-monitor {
  background: #f9fbfd;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 30px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  border: 1px solid #e6ecf5;
  text-align: center;
}

.connection-monitor h2 {
  color: #1a237e;
  font-size: 1.5rem;
  margin-top: 0;
  margin-bottom: 20px;
  font-weight: 600;
}

.connection-graph {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 0;
  margin: 30px 0;
  flex-wrap: wrap;
}

/* 節點樣式 */
.graph-node {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 15px;
  width: 130px;
  text-align: center;
  transition: all 0.3s ease;
}

.graph-node.active {
  border-color: #4caf50;
  box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
}

.graph-node.inactive {
  opacity: 0.7;
}

.graph-node.error {
  border-color: #f44336;
  box-shadow: 0 0 0 2px rgba(244, 67, 54, 0.2);
}

.node-icon {
  font-size: 24px;
  margin-bottom: 6px;
}

.node-title {
  font-weight: 600;
  font-size: 0.9rem;
  color: #333;
  margin-bottom: 6px;
}

.node-status {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 5px;
  font-size: 0.8rem;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #bdbdbd;
  margin-right: 5px;
}

.status-dot.active {
  background-color: #4caf50;
  box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
}

.status-dot.error {
  background-color: #f44336;
  box-shadow: 0 0 0 2px rgba(244, 67, 54, 0.2);
}

.status-text {
  color: #555;
}

.node-text {
  font-size: 0.75rem;
  color: #666;
  margin-top: 5px;
}

/* 連接線樣式 */
.connection-arrow-path {
  position: relative;
  width: 80px;
  height: 2px;
  background: #e0e0e0;
  border-top: 1px dashed #bdbdbd;
  margin: 0 -1px;
}

.connection-arrow-path.active {
  background: #4caf50;
  border-top: none;
}

.connection-arrow-path.inactive {
  background: #e0e0e0;
  border-top: 1px dashed #bdbdbd;
}

.connection-arrow-path.error {
  background: #f44336;
  border-top: none;
}

.connection-arrow-path::after {
  content: "";
  position: absolute;
  right: 0;
  top: -4px;
  width: 0;
  height: 0;
  border-left: 8px solid;
  border-top: 4px solid transparent;
  border-bottom: 4px solid transparent;
  border-left-color: inherit;
}

.connection-arrow-path.active::after {
  border-left-color: #4caf50;
}

.connection-arrow-path.inactive::after {
  border-left-color: #e0e0e0;
}

.connection-arrow-path.error::after {
  border-left-color: #f44336;
}

.arrow-label {
  position: absolute;
  top: -18px;
  width: 100%;
  text-align: center;
  font-size: 0.7rem;
  color: #666;
}

/* 按鈕區域 */
.connection-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 20px;
}

.control-btn {
  padding: 6px 12px;
  border-radius: 6px;
  border: none;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  transition: all 0.2s;
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  margin-right: 5px;
}

.control-btn.connect {
  background: #4caf50;
  color: white;
}

.control-btn.disconnect {
  background: #f44336;
  color: white;
}

.control-btn.refresh {
  background: #2196f3;
  color: white;
}

.control-btn.reconnect {
  background: #ff9800;
  color: white;
}

/* 連接信息面板 */
.connection-info-panel {
  margin-top: 20px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 15px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.info-row {
  display: flex;
  flex-direction: column;
}

.info-label {
  font-size: 0.8rem;
  color: #666;
  margin-bottom: 3px;
}

.info-value {
  font-weight: 500;
  color: #333;
}

.info-value.success {
  color: #4caf50;
}

.info-row.error {
  grid-column: 1 / -1;
  background: #ffebee;
  border-radius: 4px;
  padding: 10px;
}

.error-message {
  color: #d32f2f;
}

/* 響應式調整 */
@media (max-width: 768px) {
  .connection-graph {
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }
  
  .connection-arrow-path {
    transform: rotate(90deg);
    width: 40px;
  }
  
  .arrow-label {
    transform: rotate(-90deg);
    top: 0;
    right: -35px;
    width: auto;
    white-space: nowrap;
  }
  
  .connection-info-panel {
    grid-template-columns: 1fr;
  }
}

/* 節點特殊樣式 */
.graph-node.frontend {
  background: linear-gradient(135deg, #ffffff, #f8f9fa);
}

.graph-node.server {
  background: linear-gradient(135deg, #ffffff, #f0f7fa);
}

.graph-node.manager {
  background: linear-gradient(135deg, #ffffff, #e8f0fe);
}

.graph-node.exchange {
  background: linear-gradient(135deg, #ffffff, #e8f5e9);
}

.graph-node.exchange.websocket {
  border-left: 3px solid #2196f3;
}

.graph-node.exchange.rest {
  border-left: 3px solid #ff9800;
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

.test-mode-group,
.test-mode-hint,
.test-btn,
.test-tag {
  display: none;
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

.submit-btn {
  background-color: #e53935;
}

.submit-btn:hover {
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

/* 添加延遲統計卡片相關樣式 */
.latency-stats {
  grid-column: 1 / -1;  /* 跨越所有列 */
  background: linear-gradient(to right, #f8f9fa, #ffffff);
  border-left: 4px solid #5c6bc0;
}

.latency-overview {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.average-latency {
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  min-width: 200px;
}

.latency-label {
  font-size: 1rem;
  color: #546e7a;
  margin-bottom: 10px;
}

.latency-history h3 {
  font-size: 1.1rem;
  color: #37474f;
  margin-bottom: 10px;
  padding-bottom: 5px;
  border-bottom: 1px solid #e0e0e0;
}

.latency-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.latency-table th {
  background-color: #f5f7fa;
  padding: 10px;
  font-weight: 500;
  color: #455a64;
  text-align: left;
  border-bottom: 2px solid #e0e0e0;
}

.latency-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #eeeeee;
}

.latency-table tbody tr:last-child td {
  border-bottom: none;
}

.latency-badge.small {
  padding: 2px 8px;
  font-size: 0.85rem;
}

.node-tooltip {
  font-size: 0.8rem;
  color: #78909c;
  margin-top: 8px;
}

.connection-type.manager-type {
  position: absolute;
  bottom: -20px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.8rem;
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  white-space: nowrap;
  color: #546e7a;
  border: 1px solid #e0e0e0;
}

/* 連接管理器狀態樣式 */
.node.connection-manager.error {
  border-color: #e74c3c;
  box-shadow: 0 0 0 2px rgba(231, 76, 60, 0.2);
  animation: pulse-error 1.5s infinite;
}

.node.connection-manager.active {
  box-shadow: 0 0 0 2px rgba(63, 81, 181, 0.3), 0 2px 4px rgba(0, 0, 0, 0.1);
}

.node.connection-manager .connection-type.manager-type {
  position: absolute;
  bottom: -22px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 0.75rem;
  background-color: #f5f7fa;
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
  color: #546e7a;
  border: 1px solid #e0e0e0;
  z-index: 5;
}

/* 節點特殊樣式 */
.graph-node.frontend {
  background: linear-gradient(135deg, #ffffff, #f8f9fa);
}

.graph-node.server {
  background: linear-gradient(135deg, #ffffff, #f0f7fa);
}

.graph-node.manager {
  background: linear-gradient(135deg, #ffffff, #e8f0fe);
}

.graph-node.exchange {
  background: linear-gradient(135deg, #ffffff, #e8f5e9);
}

.graph-node.exchange.websocket {
  border-left: 3px solid #2196f3;
}

.graph-node.exchange.rest {
  border-left: 3px solid #ff9800;
}

/* 控制區域樣式 */
.connection-controls {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 16px;
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #e6ecf5;
}

.control-group {
  display: flex;
  gap: 12px;
}

.control-button {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 16px;
  border-radius: 8px;
  font-weight: 500;
  font-size: 0.9rem;
  background: white;
  border: 1px solid #e0e0e0;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}

.control-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
}

.control-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.control-icon {
  margin-right: 8px;
}

.control-button.connect {
  background-color: #4caf50;
  color: white;
}

.control-button.disconnect {
  background-color: #f44336;
  color: white;
}

.control-button.refresh {
  background-color: #2196f3;
  color: white;
}

.control-button.reconnect {
  background-color: #ff9800;
  color: white;
}

/* 連接詳情區域 */
.connection-details {
  margin-top: 24px;
}

.detail-card {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.05);
  padding: 16px;
  border-left: 4px solid #4caf50;
}

.detail-card.error {
  border-left-color: #f44336;
  background-color: #fff8f8;
}

.detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.detail-header h3 {
  font-size: 1rem;
  margin: 0;
  margin-left: 8px;
  color: #37474f;
}

.detail-content .error-message {
  color: #d32f2f;
  font-weight: 500;
  margin: 0;
  padding: 10px;
  background-color: rgba(244, 67, 54, 0.05);
  border-radius: 4px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.detail-grid .detail-item {
  display: flex;
  flex-direction: column;
}

.detail-label {
  font-size: 0.8rem;
  color: #78909c;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 0.95rem;
  font-weight: 500;
  color: #37474f;
}

.detail-value.success {
  color: #4caf50;
}

@media (max-width: 768px) {
  .connection-graph {
    flex-direction: column;
    gap: 15px;
  }
  
  .connection-arrow-path {
    transform: rotate(90deg);
    width: 40px;
    height: auto;
    margin: 10px 0;
  }
  
  .connection-line {
    width: 40px;
    height: 3px;
  }
  
  .connection-label {
    transform: rotate(-90deg);
    bottom: auto;
    left: -40px;
  }
  
  .control-group {
    flex-direction: column;
  }
  
  .detail-grid {
    grid-template-columns: 1fr;
  }
}

/* ... 保留其他樣式 ... */
</style> 