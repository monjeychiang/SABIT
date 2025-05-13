import { ref } from 'vue';
import { useAuthStore } from '@/stores/auth';

// 單一主WebSocket連線類型
export enum WebSocketType {
  MAIN = 'main',
  CHATROOM = 'chatroom'
}

// WebSocket狀態
interface WebSocketState {
  socket: WebSocket | null;
  connected: boolean;
  reconnectAttempts: number;
  heartbeatTimer: number | null;
  lastPongTime: number; // 新增：上次收到pong的時間
}

// 主WebSocket配置
interface MainWebSocketOptions {
  heartbeatInterval?: number;
  reconnectDelay?: number;
  maxReconnectAttempts?: number;
  reconnectFactor?: number;
  maxReconnectDelay?: number;
  heartbeatTimeout?: number; // 新增：心跳超時時間
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

class MainWebSocketManager {
  private state: WebSocketState = {
    socket: null,
    connected: false,
    reconnectAttempts: 0,
    heartbeatTimer: null,
    lastPongTime: 0 // 初始化
  };
  private options: MainWebSocketOptions = {};
  private isInitialized = ref(false);

  // 註冊主WebSocket處理器
  public register(options: MainWebSocketOptions): void {
    this.options = {
      heartbeatInterval: 30000,
      reconnectDelay: 1000,
      maxReconnectAttempts: 10,
      reconnectFactor: 1.5,
      maxReconnectDelay: 30000,
      heartbeatTimeout: 60000, // 默認60秒心跳超時
      ...options
    };
  }

  // 構建主WebSocket URL
  private buildWebSocketUrl(): string {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsBaseUrl = baseUrl.replace(/^https?:\/\//, `${wsProtocol}://`);
    const authStore = useAuthStore();
    const token = authStore.token || '';
    
    // 修正URL，匹配後端路由
    return `${wsBaseUrl}/ws/main?token=${token}`;
  }

  // 連線主WebSocket
  public async connect(): Promise<boolean> {
    if (this.state.socket && this.state.socket.readyState !== WebSocket.CLOSED) {
      this.disconnect();
    }
    try {
      const url = this.buildWebSocketUrl();
      const socket = new WebSocket(url);
      this.state.socket = socket;
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('WebSocket連線逾時'));
        }, 10000);
        socket.onopen = () => {
          clearTimeout(timeout);
          this.state.connected = true;
          this.state.reconnectAttempts = 0;
          this.state.lastPongTime = Date.now(); // 重置心跳時間
          this.startHeartbeat();
          
          // 觸發全局連接事件，通知所有組件
          window.dispatchEvent(new Event('websocket:connected'));
          console.log('[WebSocketManager] 觸發 websocket:connected 事件');
          
          if (this.options.onConnect) this.options.onConnect();
          resolve(true);
        };
        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            
            // 增強日誌以便追蹤
            const type = data.type || '';
            console.debug(`[WS:Main] 收到WebSocket消息: 類型=${type}`, data);
            
            // 處理心跳消息
            if (type === 'ping') {
              // 立即回應ping，更新心跳時間
              this.send({ type: 'pong', timestamp: new Date().toISOString() });
              this.state.lastPongTime = Date.now(); // 更新最後活動時間
              return;
            } else if (type === 'pong') {
              // 收到服務器的pong回應，更新心跳時間
              console.debug('[WS:Main] 收到服務器PONG回應');
              this.state.lastPongTime = Date.now();
              return;
            }
            
            // 處理在線狀態相關消息
            if (type === 'user_status' || type === 'online_status') {
              console.log('[WS:Main] 收到在線狀態消息:', data);
              // 這裡可以發布一個在線狀態事件
              window.dispatchEvent(new CustomEvent('online:user-status-changed', {
                detail: { 
                  userId: data.user_id, 
                  isOnline: data.is_online 
                }
              }));
            }
            
            // 處理聊天相關消息
            if (type.startsWith('chat/')) {
              console.log('[WS:Main] 收到聊天消息:', data);
              // 確保聊天訊息能被正確觸發UI更新
              window.dispatchEvent(new CustomEvent('chat:message-received', {
                detail: { 
                  messageId: data.message_id,
                  roomId: data.room_id
                }
              }));
            }
            
            // 調用註冊的消息處理器
            if (this.options.onMessage) {
              this.options.onMessage(data);
            }
          } catch (e) {
            console.error('[WS:Main] 處理WebSocket消息時出錯:', e);
          }
        };
        socket.onerror = (event) => {
          console.error('[WS:Main] WebSocket錯誤:', event);
        };
        socket.onclose = (event) => {
          clearTimeout(timeout);
          this.state.connected = false;
          this.stopHeartbeat();
          
          // 觸發全局斷開事件，通知所有組件
          window.dispatchEvent(new Event('websocket:disconnected'));
          console.log('[WebSocketManager] 觸發 websocket:disconnected 事件');
          
          if (this.options.onDisconnect) this.options.onDisconnect();
          // 自動重連
          const authStore = useAuthStore();
          if (event.code !== 1000 && authStore.isAuthenticated) {
            this.attemptReconnect();
          } else {
            reject(new Error(`WebSocket關閉: ${event.code}`));
          }
        };
      });
    } catch (error) {
      return false;
    }
  }

  // 斷開主WebSocket
  public disconnect(type?: WebSocketType): void {
    this.stopHeartbeat();
    if (this.state.socket) {
      try {
        if (this.state.socket.readyState === WebSocket.OPEN) {
          this.state.socket.send(JSON.stringify({ type: 'close' }));
        }
        this.state.socket.close(1000, '用戶主動關閉');
      } catch {}
      this.state.socket = null;
      this.state.connected = false;
    }
  }

  // 連線
  public async connectAll(): Promise<boolean> {
    return this.connect();
  }
  // 斷開
  public disconnectAll(): void {
    this.disconnect();
  }

  // 發送消息 - 允許一個或兩個參數，兼容舊代碼
  public send(typeOrMessage: WebSocketType | any, message?: any): boolean {
    // 處理參數
    let finalMessage: any;
    
    // 如果只有一個參數，則使用該參數作為消息
    if (message === undefined) {
      finalMessage = typeOrMessage;
    } 
    // 如果有兩個參數，第一個參數是WebSocketType，第二個參數是消息
    else {
      finalMessage = message;
    }
    
    if (!this.state.socket || this.state.socket.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocket] 嘗試發送消息，但連接未打開');
      return false;
    }
    
    try {
      const data = typeof finalMessage === 'string' ? finalMessage : JSON.stringify(finalMessage);
      console.log('[WebSocket] 發送消息:', typeof finalMessage === 'string' ? finalMessage : JSON.parse(data));
      this.state.socket.send(data);
      return true;
    } catch (error) {
      console.error('[WebSocket] 發送消息失敗:', error);
      return false;
    }
  }

  // 啟動心跳
  private startHeartbeat(): void {
    this.stopHeartbeat();
    if (!this.options.heartbeatInterval) return;
    
    // 設置初始心跳時間
    this.state.lastPongTime = Date.now();
    
    this.state.heartbeatTimer = window.setInterval(() => {
      if (!this.state.socket || this.state.socket.readyState !== WebSocket.OPEN) {
        return;
      }
      
      const currentTime = Date.now();
      const heartbeatTimeout = this.options.heartbeatTimeout || 60000;
      
      // 檢查是否超時
      if (currentTime - this.state.lastPongTime > heartbeatTimeout) {
        console.warn('[WebSocket] 心跳超時，重新連接...');
        this.disconnect();
        this.connect();
        return;
      }
      
      // 發送ping
      console.debug('[WebSocket] 發送PING');
      this.state.socket.send(JSON.stringify({ 
        type: 'ping',
        timestamp: new Date().toISOString()
      }));
    }, this.options.heartbeatInterval);
  }
  
  private stopHeartbeat(): void {
    if (this.state.heartbeatTimer) {
      clearInterval(this.state.heartbeatTimer);
      this.state.heartbeatTimer = null;
    }
  }
  private attemptReconnect(): void {
    if (this.state.reconnectAttempts >= (this.options.maxReconnectAttempts || 10)) return;
    const delay = Math.min(
      (this.options.reconnectDelay || 1000) * Math.pow(this.options.reconnectFactor || 1.5, this.state.reconnectAttempts),
      this.options.maxReconnectDelay || 30000
    );
    setTimeout(() => {
      this.state.reconnectAttempts++;
      this.connect();
    }, delay);
  }
  public isConnected(type?: WebSocketType): boolean {
    return this.state.connected;
  }
  public get initialized() {
    return this.isInitialized.value;
  }
}

const mainWebSocketManager = new MainWebSocketManager();
export default mainWebSocketManager; 