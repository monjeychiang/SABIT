import { ref, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import axios from 'axios';

// 賬戶數據接口
export interface AccountData {
  balances: any[];
  positions: any[];
  orders: any[];
  [key: string]: any;
}

// 賬戶WebSocket狀態
export interface AccountWSStatus {
  connected: boolean;
  error: string | null;
  lastUpdate: Date | null;
  isConnecting: boolean;
  reconnectAttempts: number;
}

class AccountWebSocketService {
  private socket: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private token: string = '';
  private exchange: string = '';
  private pingInterval: any = null;
  private refreshInterval: any = null;
  private userExchanges: string[] = [];
  private lastExchangeCheck: number = 0;
  private checkingExchanges: boolean = false;

  // 狀態
  private _status = ref<AccountWSStatus>({
    connected: false,
    error: null,
    lastUpdate: null,
    isConnecting: false,
    reconnectAttempts: 0
  });

  // 賬戶數據
  private _accountData = ref<AccountData>({
    balances: [],
    positions: [],
    orders: []
  });

  // 公開計算屬性
  public readonly status = computed(() => this._status.value);
  public readonly accountData = computed(() => this._accountData.value);

  // 檢查用戶是否有特定交易所的API密鑰
  public async hasExchangeApiKey(exchange: string): Promise<boolean> {
    const now = Date.now();
    // 如果距離上次檢查不超過1分鐘，直接使用緩存結果
    if (this.userExchanges.length > 0 && now - this.lastExchangeCheck < 60000) {
      return this.userExchanges.includes(exchange.toLowerCase());
    }
    
    // 如果正在檢查中，等待檢查完成
    if (this.checkingExchanges) {
      await new Promise<void>(resolve => {
        const checkInterval = setInterval(() => {
          if (!this.checkingExchanges) {
            clearInterval(checkInterval);
            resolve();
          }
        }, 100);
      });
      return this.userExchanges.includes(exchange.toLowerCase());
    }
    
    try {
      this.checkingExchanges = true;
      const authStore = useAuthStore();
      
      // 檢查用戶是否已認證
      if (!authStore.isAuthenticated || !authStore.token) {
        this.checkingExchanges = false;
        return false;
      }
      
      // 從API獲取用戶配置的交易所列表
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await axios.get(`${baseUrl}/api-keys/exchanges`, {
        headers: {
          Authorization: `Bearer ${authStore.token}`
        }
      });
      
      // 更新緩存
      this.userExchanges = response.data.map((e: string) => e.toLowerCase());
      this.lastExchangeCheck = now;
      
      return this.userExchanges.includes(exchange.toLowerCase());
    } catch (error) {
      console.error('[AccountWS] 檢查交易所API密鑰時出錯:', error);
      return false;
    } finally {
      this.checkingExchanges = false;
    }
  }
  
  // 獲取用戶配置的所有交易所列表
  public async getUserExchanges(): Promise<string[]> {
    await this.hasExchangeApiKey('dummy'); // 這將更新userExchanges緩存
    return [...this.userExchanges]; // 返回副本
  }

  // 連接到賬戶WebSocket
  public async connect(exchange: string): Promise<boolean> {
    // 檢查用戶是否有此交易所的API密鑰
    const hasApiKey = await this.hasExchangeApiKey(exchange);
    if (!hasApiKey) {
      console.warn(`[AccountWS] 用戶沒有 ${exchange} 的API密鑰，取消連接`);
      this._status.value.error = `沒有配置 ${exchange} 的API密鑰`;
      return false;
    }
    
    // 如果已連接，先斷開
    if (this.socket) {
      this.disconnect();
    }

    // 更新狀態
    this._status.value.isConnecting = true;
    this._status.value.error = null;
    this.exchange = exchange;

    try {
      // 獲取認證token
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated || !authStore.token) {
        throw new Error('用戶未認證');
      }
      this.token = authStore.token;

      // 構建WebSocket URL
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsBaseUrl = baseUrl.replace(/^https?:\/\//, `${wsProtocol}://`);
      const url = `${wsBaseUrl}/account/futures-account/${exchange}`;

      // 創建WebSocket連接
      this.socket = new WebSocket(url);

      return new Promise<boolean>((resolve, reject) => {
        if (!this.socket) {
          this._status.value.isConnecting = false;
          this._status.value.error = '無法創建WebSocket連接';
          reject(new Error('無法創建WebSocket連接'));
          return;
        }

        // 設置連接超時
        const timeout = setTimeout(() => {
          if (this._status.value.isConnecting) {
            this._status.value.isConnecting = false;
            this._status.value.error = 'WebSocket連接超時';
            this.socket?.close();
            reject(new Error('WebSocket連接超時'));
          }
        }, 10000);

        // 連接成功
        this.socket.onopen = async () => {
          clearTimeout(timeout);

          // 發送認證token
          this.socket?.send(this.token);

          // 開始定期發送ping來保持連接
          this.startPingInterval();
          
          // 設置定期請求刷新數據
          this.startRefreshInterval();

          console.log('[AccountWS] WebSocket連接成功');
          this._status.value.connected = true;
          this._status.value.isConnecting = false;
          this._status.value.reconnectAttempts = 0;
          
          // 觸發連接事件
          window.dispatchEvent(new CustomEvent('account:websocket-connected', { 
            detail: { exchange } 
          }));

          resolve(true);
        };

        // 接收消息
        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.debug(`[AccountWS] 收到訊息:`, data);
            
            // 處理心跳響應
            if (data.type === 'pong') {
              console.debug('[AccountWS] 收到PONG響應');
              return;
            }
            
            // 處理服務器發送的心跳請求
            if (data.type === 'ping') {
              console.debug('[AccountWS] 收到服務器心跳請求，發送PONG');
              this.send({ type: 'pong', timestamp: new Date().toISOString() });
              return;
            }

            // 處理賬戶數據更新
            if (data.type === 'account_data' || (!data.type && data.data)) {
              // 更新最後更新時間
              this._status.value.lastUpdate = new Date();
              const accountData = data.data;
              
              // 更新賬戶數據
              if (accountData.balances) {
                this._accountData.value.balances = accountData.balances;
              }
              
              if (accountData.positions) {
                this._accountData.value.positions = accountData.positions;
              }
              
              if (accountData.orders) {
                this._accountData.value.orders = accountData.orders;
              }
              
              // 更新其他字段
              Object.keys(accountData).forEach(key => {
                if (!['balances', 'positions', 'orders'].includes(key)) {
                  this._accountData.value[key] = accountData[key];
                }
              });
              
              // 觸發數據更新事件
              window.dispatchEvent(new CustomEvent('account:data-updated', { 
                detail: { data: accountData, timestamp: data.timestamp } 
              }));
              return;
            }

            // 處理成功/失敗消息
            if (data.success === false) {
              console.error('[AccountWS] 錯誤:', data.message, data.error);
              this._status.value.error = data.message || '接收到錯誤消息';
              
              // 觸發錯誤事件
              window.dispatchEvent(new CustomEvent('account:websocket-error', { 
                detail: { error: data.error, message: data.message } 
              }));
              return;
            }

            // 處理狀態更新
            if (data.status === 'connecting') {
              console.log('[AccountWS] 連接進度:', data.message);
              return;
            }
          } catch (e) {
            console.error('[AccountWS] 處理消息時出錯:', e);
          }
        };

        // 連接錯誤
        this.socket.onerror = (event) => {
          console.error('[AccountWS] WebSocket錯誤:', event);
          this._status.value.error = '連接錯誤';
        };

        // 連接關閉
        this.socket.onclose = (event) => {
          clearTimeout(timeout);
          this.stopPingInterval();
          this.stopRefreshInterval();
          
          this._status.value.connected = false;
          this._status.value.isConnecting = false;
          
          console.log(`[AccountWS] 連接關閉，代碼: ${event.code}，原因: ${event.reason || '未提供'}`);

          // 如果不是正常關閉且用戶已認證，嘗試重新連接
          const authStore = useAuthStore();
          if (event.code !== 1000 && authStore.isAuthenticated) {
            this.attemptReconnect();
          }

          // 觸發關閉事件
          window.dispatchEvent(new CustomEvent('account:websocket-disconnected', { 
            detail: { code: event.code, reason: event.reason } 
          }));
        };
      });
    } catch (error) {
      this._status.value.isConnecting = false;
      this._status.value.error = error instanceof Error ? error.message : '連接時發生未知錯誤';
      console.error('[AccountWS] 連接錯誤:', error);
      return false;
    }
  }

  // 斷開連接
  public disconnect(): void {
    this.stopPingInterval();
    this.stopRefreshInterval();
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    if (this.socket) {
      try {
        // 使用1000正常關閉代碼
        this.socket.close(1000, '用戶主動斷開連接');
      } catch (e) {
        console.error('[AccountWS] 關閉WebSocket時出錯:', e);
      }
      this.socket = null;
      this._status.value.connected = false;
    }
  }

  // 開始定期ping
  private startPingInterval(): void {
    this.stopPingInterval();
    this.pingInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        try {
          this.socket.send(JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() }));
        } catch (e) {
          console.error('[AccountWS] 發送ping時出錯:', e);
        }
      }
    }, 30000); // 每30秒發送一次ping
  }

  // 停止定期ping
  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }
  
  // 開始定期刷新數據
  private startRefreshInterval(): void {
    this.stopRefreshInterval();
    // 每2分鐘主動請求刷新一次數據
    this.refreshInterval = setInterval(() => {
      this.refreshAccountData();
    }, 120000); // 2分鐘
  }
  
  // 停止定期刷新
  private stopRefreshInterval(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }
  
  // 手動刷新帳戶數據
  public refreshAccountData(): boolean {
    return this.send({ 
      type: 'refresh', 
      timestamp: new Date().toISOString() 
    });
  }

  // 嘗試重新連接
  private attemptReconnect(): void {
    if (this._status.value.reconnectAttempts >= 5) {
      console.log('[AccountWS] 已達到最大重連次數，停止重連');
      return;
    }

    const delay = Math.min(1000 * (Math.pow(2, this._status.value.reconnectAttempts)), 30000);
    console.log(`[AccountWS] 將在 ${delay}ms 後嘗試重連...`);
    
    this._status.value.reconnectAttempts++;
    
    this.reconnectTimer = window.setTimeout(() => {
      console.log(`[AccountWS] 嘗試重連 #${this._status.value.reconnectAttempts}`);
      this.connect(this.exchange).catch(() => {
        // 重連失敗，已在內部處理
      });
    }, delay);
  }

  // 發送消息
  public send(message: any): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.error('[AccountWS] WebSocket未連接，無法發送消息');
      return false;
    }
    
    try {
      const data = typeof message === 'string' ? message : JSON.stringify(message);
      this.socket.send(data);
      return true;
    } catch (e) {
      console.error('[AccountWS] 發送消息失敗:', e);
      return false;
    }
  }

  // 檢查是否已連接
  public isConnected(): boolean {
    return this._status.value.connected;
  }
}

// 創建並導出單例
export const accountWebSocketService = new AccountWebSocketService(); 