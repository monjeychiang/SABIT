import { ref, computed } from 'vue';
import { getTokenManager } from '@/services/tokenService';
import { useAuthStore } from '@/stores/auth';

// WebSocket连接类型枚举
export enum WebSocketType {
  NOTIFICATION = 'notification',
  CHATROOM = 'chatroom',
  ONLINE_STATUS = 'onlineStatus',
  MARKET_DATA = 'marketData'
}

// WebSocket连接状态
interface WebSocketState {
  socket: WebSocket | null;
  connected: boolean;
  reconnectAttempts: number;
  heartbeatTimer: number | null;
}

// WebSocket配置选项
interface WebSocketOptions {
  heartbeatInterval?: number; // 心跳间隔(毫秒)
  reconnectDelay?: number;    // 初始重连延迟(毫秒)
  maxReconnectAttempts?: number; // 最大重连次数
  reconnectFactor?: number;   // 重连延迟增长因子
  maxReconnectDelay?: number; // 最大重连延迟(毫秒)
  onMessage?: (event: MessageEvent) => void; // 消息处理回调
  onConnect?: () => void;     // 连接成功回调
  onDisconnect?: () => void;  // 断开连接回调
}

class WebSocketManager {
  private connections: Map<WebSocketType, WebSocketState> = new Map();
  private options: Map<WebSocketType, WebSocketOptions> = new Map();
  private isInitialized = ref(false);
  
  // 构建WebSocket URL
  private buildWebSocketUrl(type: WebSocketType): string {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsBaseUrl = baseUrl.replace(/^https?:\/\//, `${wsProtocol}://`);
    
    // 直接从authStore获取授权令牌
    const authStore = useAuthStore();
    const token = authStore.token || '';
    
    // 根据不同类型构建不同的URL
    switch (type) {
      case WebSocketType.NOTIFICATION:
        return `${wsBaseUrl}/api/v1/notifications/ws?token=${token}`;
      case WebSocketType.CHATROOM:
        return `${wsBaseUrl}/api/v1/chatroom/ws/user/${token}`;
      case WebSocketType.ONLINE_STATUS:
        return `${wsBaseUrl}/api/v1/online/ws/status/${token}`;
      case WebSocketType.MARKET_DATA:
        return `${wsBaseUrl}/api/v1/markets/ws/all`;
      default:
        throw new Error(`未支持的WebSocket类型: ${type}`);
    }
  }
  
  // 注册WebSocket连接
  public register(type: WebSocketType, options: WebSocketOptions): void {
    if (!this.connections.has(type)) {
      this.connections.set(type, {
        socket: null,
        connected: false,
        reconnectAttempts: 0,
        heartbeatTimer: null
      });
      
      this.options.set(type, {
        heartbeatInterval: 30000,  // 默认30秒
        reconnectDelay: 1000,      // 默认1秒
        maxReconnectAttempts: 10,  // 默认最多10次
        reconnectFactor: 1.5,      // 默认1.5倍增长
        maxReconnectDelay: 30000,  // 默认最大30秒
        ...options
      });
    }
  }
  
  // 连接指定类型的WebSocket
  public async connect(type: WebSocketType): Promise<boolean> {
    if (!this.connections.has(type)) {
      console.error(`未注册的WebSocket类型: ${type}`);
      return false;
    }
    
    const state = this.connections.get(type)!;
    const options = this.options.get(type)!;
    
    // 如果已连接，先关闭
    if (state.socket && state.socket.readyState !== WebSocket.CLOSED) {
      this.disconnect(type);
    }
    
    try {
      const url = this.buildWebSocketUrl(type);
      console.log(`[WebSocketManager] 正在连接 ${type} WebSocket: ${url}`);
      
      const socket = new WebSocket(url);
      state.socket = socket;
      
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('WebSocket连接超时'));
        }, 10000); // 10秒连接超时
        
        socket.onopen = () => {
          clearTimeout(timeout);
          console.log(`[WebSocketManager] ${type} WebSocket连接成功`);
          state.connected = true;
          state.reconnectAttempts = 0;
          this.startHeartbeat(type);
          
          // 调用连接成功回调
          if (options.onConnect) {
            options.onConnect();
          }
          
          resolve(true);
        };
        
        socket.onmessage = (event) => {
          // 处理消息
          if (options.onMessage) {
            options.onMessage(event);
          }
        };
        
        socket.onerror = (event) => {
          console.error(`[WebSocketManager] ${type} WebSocket错误:`, event);
        };
        
        socket.onclose = (event) => {
          clearTimeout(timeout);
          console.log(`[WebSocketManager] ${type} WebSocket连接关闭: ${event.code}, ${event.reason}`);
          state.connected = false;
          this.stopHeartbeat(type);
          
          // 调用断开连接回调
          if (options.onDisconnect) {
            options.onDisconnect();
          }
          
          // 如果不是正常关闭且用户已认证，尝试重连
          const authStore = useAuthStore();
          if (event.code !== 1000 && authStore.isAuthenticated) {
            this.attemptReconnect(type);
          } else {
            reject(new Error(`WebSocket连接关闭: ${event.code}`));
          }
        };
      });
    } catch (error) {
      console.error(`[WebSocketManager] ${type} WebSocket连接失败:`, error);
      return false;
    }
  }
  
  // 断开指定类型的WebSocket
  public disconnect(type: WebSocketType): void {
    const state = this.connections.get(type);
    if (!state) return;
    
    this.stopHeartbeat(type);
    
    if (state.socket) {
      try {
        // 发送关闭消息
        if (state.socket.readyState === WebSocket.OPEN) {
          state.socket.send(JSON.stringify({ type: 'close' }));
        }
        
        // 正常关闭连接
        state.socket.close(1000, '用户主动关闭');
      } catch (error) {
        console.error(`[WebSocketManager] 关闭 ${type} WebSocket出错:`, error);
      }
      
      state.socket = null;
      state.connected = false;
    }
  }
  
  // 断开所有WebSocket连接
  public disconnectAll(): void {
    for (const type of this.connections.keys()) {
      this.disconnect(type);
    }
  }
  
  // 连接所有注册的WebSocket
  public async connectAll(): Promise<boolean> {
    let allSuccess = true;
    
    for (const type of this.connections.keys()) {
      try {
        const success = await this.connect(type);
        if (!success) {
          allSuccess = false;
        }
      } catch (error) {
        console.error(`[WebSocketManager] 连接 ${type} WebSocket失败:`, error);
        allSuccess = false;
      }
    }
    
    this.isInitialized.value = true;
    return allSuccess;
  }
  
  // 发送消息
  public send(type: WebSocketType, message: any): boolean {
    const state = this.connections.get(type);
    if (!state || !state.socket || state.socket.readyState !== WebSocket.OPEN) {
      console.error(`[WebSocketManager] 无法发送消息: ${type} WebSocket未连接`);
      return false;
    }
    
    try {
      const data = typeof message === 'string' ? message : JSON.stringify(message);
      state.socket.send(data);
      return true;
    } catch (error) {
      console.error(`[WebSocketManager] 发送消息到 ${type} WebSocket失败:`, error);
      return false;
    }
  }
  
  // 启动心跳
  private startHeartbeat(type: WebSocketType): void {
    const state = this.connections.get(type);
    const options = this.options.get(type);
    if (!state || !options) return;
    
    this.stopHeartbeat(type);
    
    state.heartbeatTimer = window.setInterval(() => {
      if (state.socket && state.socket.readyState === WebSocket.OPEN) {
        state.socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, options.heartbeatInterval);
  }
  
  // 停止心跳
  private stopHeartbeat(type: WebSocketType): void {
    const state = this.connections.get(type);
    if (!state) return;
    
    if (state.heartbeatTimer) {
      clearInterval(state.heartbeatTimer);
      state.heartbeatTimer = null;
    }
  }
  
  // 尝试重连
  private attemptReconnect(type: WebSocketType): void {
    const state = this.connections.get(type);
    const options = this.options.get(type);
    if (!state || !options) return;
    
    if (state.reconnectAttempts >= options.maxReconnectAttempts!) {
      console.log(`[WebSocketManager] ${type} WebSocket已达到最大重连次数，停止重连`);
      return;
    }
    
    // 计算延迟时间
    const delay = Math.min(
      options.reconnectDelay! * Math.pow(options.reconnectFactor!, state.reconnectAttempts),
      options.maxReconnectDelay!
    );
    
    console.log(`[WebSocketManager] ${type} WebSocket将在${delay}ms后尝试重连 (${state.reconnectAttempts + 1}/${options.maxReconnectAttempts})`);
    
    state.reconnectAttempts++;
    
    setTimeout(() => {
      const authStore = useAuthStore();
      if (!state.connected && authStore.isAuthenticated) {
        this.connect(type).catch(error => {
          console.error(`[WebSocketManager] ${type} WebSocket重连失败:`, error);
        });
      }
    }, delay);
  }
  
  // 返回连接状态
  public isConnected(type: WebSocketType): boolean {
    const state = this.connections.get(type);
    return state ? state.connected : false;
  }
  
  // 返回初始化状态
  public get initialized() {
    return computed(() => this.isInitialized.value);
  }
}

// 创建单例
const webSocketManager = new WebSocketManager();

export default webSocketManager; 