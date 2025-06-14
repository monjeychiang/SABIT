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
  private token: string | null = null;
  private exchange: string = '';
  private pingInterval: number | null = null;
  private refreshInterval: number | null = null;
  private userExchanges: string[] = [];
  private lastExchangeCheck: number = 0;
  private checkingExchanges: boolean = false;
  
  // 添加連接鎖定標誌，防止重複初始化
  private _connecting: boolean = false;
  
  // 添加全局持久連接標誌 - 預設為 true
  private _persistentConnection: boolean = true;

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
  
  // 新增：檢查用戶是否有特定交易所的特定類型API密鑰
  public async hasExchangeApiKeyType(exchange: string, keyType: 'hmac' | 'ed25519'): Promise<boolean> {
    try {
      const authStore = useAuthStore();
      
      // 檢查用戶是否已認證
      if (!authStore.isAuthenticated || !authStore.token) {
        return false;
      }
      
      // 從API獲取用戶配置的API密鑰詳情
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await axios.get(`${baseUrl}/api/v1/api-keys`, {
        headers: {
          Authorization: `Bearer ${authStore.token}`
        }
      });
      
      if (!response.data || !Array.isArray(response.data)) {
        return false;
      }
      
      // 尋找匹配的交易所記錄
      const exchangeApiKey = response.data.find(
        (key: any) => key.exchange.toLowerCase() === exchange.toLowerCase()
      );
      
      if (!exchangeApiKey) {
        return false;
      }
      
      // 根據請求的密鑰類型檢查是否存在
      if (keyType === 'hmac') {
        return !!exchangeApiKey.has_hmac;
      } else if (keyType === 'ed25519') {
        return !!exchangeApiKey.has_ed25519;
      }
      
      return false;
    } catch (error) {
      console.error(`[AccountWS] 檢查交易所 ${exchange} 的 ${keyType} 密鑰時出錯:`, error);
      return false;
    }
  }
  
  // 獲取用戶配置的所有交易所列表
  public async getUserExchanges(): Promise<string[]> {
    await this.hasExchangeApiKey('dummy'); // 這將更新userExchanges緩存
    return [...this.userExchanges]; // 返回副本
  }

  // 連接到賬戶WebSocket
  public async connect(exchange: string): Promise<boolean> {
    // 如果已經在連接中，避免重複連接
    if (this._connecting) {
      console.log(`[AccountWS] 連接初始化正在進行中，避免重複連接 - exchange: ${exchange}`);
      return new Promise<boolean>((resolve) => {
        const checkInterval = setInterval(() => {
          if (!this._connecting) {
            clearInterval(checkInterval);
            resolve(this.isConnected());
          }
        }, 100);
      });
    }
    
    // 如果已經連接到相同的交易所，避免重複連接
    if (this.isConnected() && this.exchange === exchange) {
      console.log(`[AccountWS] 已經連接到 ${exchange}，跳過重複連接`);
      return true;
    }

    // 設置連接鎖定標誌
    this._connecting = true;
    
    try {
      // 檢查用戶是否有此交易所的API密鑰
      const hasApiKey = await this.hasExchangeApiKey(exchange);
      if (!hasApiKey) {
        console.warn(`[AccountWS] 用戶沒有 ${exchange} 的API密鑰，取消連接`);
        this._status.value.error = `沒有配置 ${exchange} 的API密鑰`;
        return false;
      }
      
      // 針對 Binance WebSocket，檢查是否有必要的 Ed25519 密鑰
      if (exchange.toLowerCase() === 'binance') {
        const hasEd25519 = await this.hasExchangeApiKeyType(exchange, 'ed25519');
        if (!hasEd25519) {
          console.warn(`[AccountWS] 用戶沒有 ${exchange} 的 Ed25519 密鑰，Binance WebSocket 需要 Ed25519 密鑰才能成功連接`);
          this._status.value.error = `Binance WebSocket 需要 Ed25519 密鑰，請在設置中配置`;
          return false;
        }
      }
      
      // 如果已連接，先斷開
      if (this.socket) {
        this.disconnect(true); // 使用強制斷開
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
            if (this.token) {
              this.socket?.send(this.token);
            } else {
              console.error('[AccountWS] 認證token為空，無法完成認證');
              this.socket?.close(1000, '認證token為空');
              this._status.value.error = '認證token為空，無法完成認證';
              clearTimeout(timeout);
              reject(new Error('認證token為空'));
              return;
            }

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
    } finally {
      // 釋放連接鎖
      this._connecting = false;
    }
  }

  // 斷開連接
  public disconnect(force: boolean = false): void {
    // 記錄之前的連接狀態，用於事件觸發
    const wasConnected = this._status.value.connected;
    
    // 停止所有相關計時器
    this.stopPingInterval();
    this.stopRefreshInterval();
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    // 處理WebSocket連接關閉
    if (this.socket) {
      try {
        // 確保在關閉前發送明確的關閉消息
        if (this.socket.readyState === WebSocket.OPEN) {
          // 發送一個標準的關閉消息 - 與主WebSocket一致使用 type: 'close'
          this.send({
            type: 'close',
            message: force ? '用戶登出，強制斷開連接' : '用戶離開頁面，前端連接斷開',
            timestamp: new Date().toISOString(),
            logout: force  // 添加登出標記
          });
          
          // 直接關閉WebSocket
          this.socket.close(1000, force ? '用戶登出，強制斷開連接' : '用戶離開頁面，前端連接斷開');
        } else if (this.socket.readyState !== WebSocket.CLOSED) {
          // 如果不是已經關閉的狀態，嘗試關閉
          this.socket.close(1000);
        }
      } catch (e) {
        console.error('[AccountWS] 關閉WebSocket時出錯:', e);
      }
      
      // 重置連接狀態
      this.socket = null;
      this._status.value.connected = false;
      
      // 發送一個全局事件通知其他組件
      if (wasConnected) {
        window.dispatchEvent(new CustomEvent('account:websocket-disconnected', {
          detail: { forced: force, logout: force }
        }));
      }
    }
    
    // 如果是強制斷開（登出），重置持久連接標誌
    if (force) {
      console.log('[AccountWS] 用戶登出，完全斷開連接');
      this._persistentConnection = false; // 重置持久連接標記
    } else if (this._persistentConnection) {
      // 非強制斷開且啟用了持久連接時
      console.log('[AccountWS] 保持後端持久連接，但前端WebSocket已斷開');
    } else {
      // 非強制斷開也沒有持久連接時
      console.log('[AccountWS] 前端連接斷開，未啟用持久連接');
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
    // 檢查是否已達到最大重連次數
    if (this._status.value.reconnectAttempts >= 5) {
      console.error('[AccountWS] 達到最大重連次數，停止重連');
      this._status.value.error = '達到最大重連次數，請手動重新連接';
      return;
    }
    
    // 增加重連計數
    this._status.value.reconnectAttempts++;
    
    // 計算退避時間 (0.5秒, 1秒, 2秒, 4秒, 8秒)
    const backoffTime = Math.pow(2, this._status.value.reconnectAttempts - 1) * 500;
    
    console.log(`[AccountWS] 嘗試第 ${this._status.value.reconnectAttempts} 次重連，延遲 ${backoffTime}ms`);
    
    // 清除之前的重連計時器
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    
    // 設置新的重連計時器
    this.reconnectTimer = window.setTimeout(async () => {
      this.reconnectTimer = null;
      console.log('[AccountWS] 執行重連...');
      
      try {
        // 重新連接
        await this.connect(this.exchange);
        
        // 連接成功，重置重連計數
        if (this._status.value.connected) {
          console.log('[AccountWS] 重連成功');
          this._status.value.reconnectAttempts = 0;
          
          // 觸發重連成功事件
          window.dispatchEvent(new CustomEvent('account:websocket-reconnected', { 
            detail: { exchange: this.exchange } 
          }));
        }
      } catch (error) {
        console.error('[AccountWS] 重連失敗:', error);
        // 如果重連失敗，會自動在下一次錯誤時再次觸發重連
      }
    }, backoffTime);
  }

  // 發送消息
  public send(message: any): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.error('[AccountWS] 嘗試向未連接的WebSocket發送消息');
      return false;
    }
    
    try {
      // 確保消息是一個物件
      const msgObj = typeof message === 'string' ? JSON.parse(message) : message;
      
      // 發送消息
      this.socket.send(JSON.stringify(msgObj));
      return true;
    } catch (error) {
      console.error('[AccountWS] 發送消息時出錯:', error);
      return false;
    }
  }

  // 發送消息並等待響應 - 新增方法
  public async sendMessage(message: any): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket未連接，無法發送消息'));
        return;
      }

      // 請求唯一ID
      const requestId = `req_${Date.now()}`;
      
      // 將requestId添加到消息中
      const msgWithId = { ...message, request_id: requestId };
      
      // 註冊一次性消息處理器來接收響應
      const handleResponse = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          
          // 檢查是否是我們所等待的響應
          if ((data.type === 'order_response' || data.type === 'order_result') && 
              (data.request_id === requestId || !data.request_id)) {
            // 收到響應，移除監聽器
            this.socket?.removeEventListener('message', handleResponse);
            clearTimeout(timeout);
            
            // 解析響應
            if (data.success === false) {
              reject(data.error || new Error('請求失敗'));
            } else {
              resolve(data);
            }
          }
        } catch (e) {
          console.error('[AccountWS] 處理響應時出錯:', e);
        }
      };
      
      // 添加臨時消息處理器
      this.socket.addEventListener('message', handleResponse);
      
      // 設置響應超時
      const timeout = setTimeout(() => {
        this.socket?.removeEventListener('message', handleResponse);
        reject(new Error('請求超時，沒有收到響應'));
      }, 30000);
      
      // 發送消息
      const success = this.send(msgWithId);
      
      if (!success) {
        clearTimeout(timeout);
        this.socket.removeEventListener('message', handleResponse);
        reject(new Error('發送消息失敗'));
      }
    });
  }

  // 透過WebSocket下單
  public async placeOrder(orderParams: any): Promise<any> {
    // 確保使用正確的消息格式
    const message = {
      type: 'place_order',
      data: orderParams // 將 params 修改為 data 作為鍵名，以符合後端期望
    };
    
    return await this.sendMessage(message);
  }
  
  // 透過WebSocket取消訂單
  public async cancelOrder(cancelParams: any): Promise<any> {
    return new Promise((resolve, reject) => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket未連接，無法取消訂單'));
        return;
      }

      // 請求唯一ID
      const requestId = `cancel_${Date.now()}`;
      
      // 註冊一次性消息處理器來接收取消訂單響應
      const handleResponse = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'cancel_response') {
            // 收到取消訂單響應，移除監聽器
            this.socket?.removeEventListener('message', handleResponse);
            
            if (data.success) {
              resolve(data.data);
            } else {
              reject(new Error(data.message || '取消訂單失敗'));
            }
          }
        } catch (e) {
          console.error('[AccountWS] 處理取消訂單響應時出錯:', e);
        }
      };
      
      // 添加臨時消息處理器
      this.socket.addEventListener('message', handleResponse);
      
      // 設置響應超時
      const timeout = setTimeout(() => {
        this.socket?.removeEventListener('message', handleResponse);
        reject(new Error('取消訂單請求超時'));
      }, 30000);
      
      // 發送取消訂單請求
      const success = this.send({
        type: 'cancel_order',
        data: cancelParams,  // 將 params 改為 data 作為鍵名，以符合後端期望
        request_id: requestId
      });
      
      if (!success) {
        clearTimeout(timeout);
        this.socket.removeEventListener('message', handleResponse);
        reject(new Error('發送取消訂單請求失敗'));
      }
    });
  }

  // 檢查是否已連接
  public isConnected(): boolean {
    return this._status.value.connected;
  }

  // 設置持久連接模式
  public setPersistentMode(persistent: boolean): void {
    this._persistentConnection = persistent;
    console.log(`[AccountWS] 持久連接模式: ${persistent ? '開啟' : '關閉'}`);
  }
  
  // 獲取持久連接模式狀態
  public isPersistentMode(): boolean {
    return this._persistentConnection;
  }

  // 新增：全局初始化方法，統一與主WebSocket管理接口
  public async initializeConnection(): Promise<boolean> {
    console.log('[AccountWS] 開始初始化賬戶WebSocket連接');
    
    // 如果已經連接，直接返回成功
    if (this.isConnected()) {
      console.log('[AccountWS] 賬戶WebSocket已經連接，跳過初始化');
      return true;
    }
    
    // 如果正在連接中，等待連接完成
    if (this._connecting) {
      console.log('[AccountWS] 賬戶WebSocket連接正在進行中，等待完成...');
      return new Promise<boolean>((resolve) => {
        const checkInterval = setInterval(() => {
          if (!this._connecting) {
            clearInterval(checkInterval);
            resolve(this.isConnected());
          }
        }, 100);
      });
    }
    
    try {
      // 檢查用戶是否已認證
      const authStore = useAuthStore();
      if (!authStore.isAuthenticated || !authStore.token) {
        console.log('[AccountWS] 用戶未認證，無法初始化連接');
        return false;
      }
      
      // 設置持久連接模式
      this.setPersistentMode(true);
      
      // 檢查是否有 binance 的 API 密鑰
      const hasApiKey = await this.hasExchangeApiKey('binance');
      if (!hasApiKey) {
        console.log('[AccountWS] 用戶沒有 binance 的 API 密鑰，無法初始化連接');
        return false;
      }
      
      // 針對 Binance 檢查是否有 Ed25519 密鑰
      const hasEd25519 = await this.hasExchangeApiKeyType('binance', 'ed25519');
      if (!hasEd25519) {
        console.log('[AccountWS] 用戶沒有 binance 的 Ed25519 密鑰，無法初始化連接');
        this._status.value.error = `Binance WebSocket 需要 Ed25519 密鑰，請在設置中配置`;
        return false;
      }
      
      // 連接到 WebSocket
      console.log('[AccountWS] 開始初始化連接到 binance');
      return await this.connect('binance');
    } catch (error) {
      console.error('[AccountWS] 初始化連接失敗:', error);
      return false;
    }
  }

  // 新增：全局關閉方法，統一與主WebSocket管理接口
  public closeConnection(forced: boolean = false): void {
    console.log(`[AccountWS] 關閉連接，強制模式: ${forced}`);
    this.disconnect(forced);
  }
}

// 創建並導出單例
export const accountWebSocketService = new AccountWebSocketService(); 