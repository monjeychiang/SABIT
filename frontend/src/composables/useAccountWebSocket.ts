import { ref, computed, onMounted, onUnmounted } from 'vue';
import { accountWebSocketService } from '@/services/accountWebSocketService';
import type { AccountData, AccountWSStatus } from '@/services/accountWebSocketService';

export function useAccountWebSocket(exchange: string = 'binance') {
  const isConnecting = ref(false);
  const connectionError = ref<string | null>(null);
  const autoConnect = ref(true);
  
  // 從服務中獲取賬戶數據和狀態
  const accountData = computed<AccountData>(() => accountWebSocketService.accountData.value);
  const status = computed<AccountWSStatus>(() => accountWebSocketService.status.value);
  
  // 獲取特定類型的數據
  const balances = computed(() => accountData.value.balances || []);
  const positions = computed(() => accountData.value.positions || []);
  const orders = computed(() => accountData.value.orders || []);
  
  // 根據錢包類型過濾餘額
  const filterBalancesByWalletType = (walletType: string) => {
    return balances.value.filter(balance => 
      balance.walletType === walletType || 
      (walletType === 'CROSS' && balance.walletType === 'FUNDING')
    );
  };
  
  // 獲取總資產價值
  const totalEquity = computed(() => {
    if (!accountData.value || !accountData.value.totalEquity) {
      return { value: 0, currency: 'USDT' };
    }
    return accountData.value.totalEquity;
  });
  
  // 連接到WebSocket
  const connect = async () => {
    if (status.value.connected || isConnecting.value) {
      return;
    }
    
    isConnecting.value = true;
    connectionError.value = null;
    
    try {
      await accountWebSocketService.connect(exchange);
      return true;
    } catch (error) {
      connectionError.value = error instanceof Error ? error.message : '連接WebSocket時出錯';
      console.error('[useAccountWebSocket] 連接錯誤:', error);
      return false;
    } finally {
      isConnecting.value = false;
    }
  };
  
  // 斷開WebSocket連接
  const disconnect = () => {
    accountWebSocketService.disconnect();
  };
  
  // 發送消息到WebSocket
  const send = (message: any): boolean => {
    return accountWebSocketService.send(message);
  };
  
  // 檢查連接狀態
  const isConnected = computed(() => {
    return status.value.connected;
  });
  
  // 獲取上次更新時間
  const lastUpdate = computed(() => {
    return status.value.lastUpdate;
  });
  
  // 組件掛載時自動連接
  onMounted(() => {
    if (autoConnect.value) {
      connect();
    }
    
    // 監聽全局WebSocket事件
    window.addEventListener('account:data-updated', handleDataUpdated);
  });
  
  // 組件卸載時斷開連接
  onUnmounted(() => {
    disconnect();
    
    // 移除事件監聽器
    window.removeEventListener('account:data-updated', handleDataUpdated);
  });
  
  // 處理數據更新事件
  const handleDataUpdated = (event: Event) => {
    // 可以在這裡添加自定義邏輯
    console.log('[useAccountWebSocket] 收到賬戶數據更新');
  };
  
  // 返回公開API
  return {
    // 狀態
    status,
    isConnecting,
    isConnected,
    connectionError,
    lastUpdate,
    
    // 數據
    accountData,
    balances,
    positions,
    orders,
    totalEquity,
    
    // 方法
    connect,
    disconnect,
    send,
    filterBalancesByWalletType
  };
} 