import { ref, onMounted, onUnmounted, watch } from 'vue'

// 指数退避重连配置
const DEFAULT_RECONNECT_OPTIONS = {
  maxAttempts: 10,          // 最大重连次数
  initialDelay: 1000,       // 初始延迟1秒
  maxDelay: 30000,          // 最大延迟30秒
  factor: 1.5               // 延迟指数因子
}

export interface ReconnectOptions {
  maxAttempts: number;
  initialDelay: number;
  maxDelay: number;
  factor: number;
}

export function useWebSocket<T>(url: string, options: Partial<ReconnectOptions> = {}) {
  const data = ref<T | null>(null)
  const ws = ref<WebSocket | null>(null)
  const isConnected = ref(false)
  const error = ref<Error | null>(null)
  const reconnectAttempts = ref(0)
  const isReconnecting = ref(false)
  
  // 合并用户选项与默认选项
  const reconnectOptions = {
    ...DEFAULT_RECONNECT_OPTIONS,
    ...options
  }
  
  // 计算下一次重连延迟
  const getNextDelay = () => {
    const delay = reconnectOptions.initialDelay * 
      Math.pow(reconnectOptions.factor, reconnectAttempts.value)
    return Math.min(delay, reconnectOptions.maxDelay)
  }

  const connect = async () => {
    return new Promise<void>((resolve, reject) => {
      try {
        // 关闭现有连接
        if (ws.value && ws.value.readyState !== WebSocket.CLOSED) {
          ws.value.close()
        }
        
        console.log(`正在连接WebSocket: ${url}`)
        ws.value = new WebSocket(url)
        
        ws.value.onopen = () => {
          console.log('WebSocket连接成功')
          isConnected.value = true
          error.value = null
          reconnectAttempts.value = 0
          isReconnecting.value = false
          resolve()
        }
        
        ws.value.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            if (message.type === 'initial') {
              data.value = message.data
            } else {
              // 处理其他类型的消息
              data.value = message
            }
          } catch (e) {
            console.error('解析WebSocket消息失败:', e)
          }
        }
        
        ws.value.onerror = (event) => {
          console.error('WebSocket错误:', event)
          error.value = new Error('WebSocket连接错误')
          // 不在这里reject，让onclose处理重连逻辑
        }
        
        ws.value.onclose = (event) => {
          console.log(`WebSocket连接关闭，代码: ${event.code}，原因: ${event.reason || '未提供原因'}`)
          isConnected.value = false
          
          // 区分不同的关闭代码
          if (event.code === 1000) {
            console.log('WebSocket正常关闭')
            // 正常关闭，不尝试重连
            reject(new Error('WebSocket连接已正常关闭'))
            return
          }
          
          // 如果还未超过最大重连次数，尝试重连
          if (reconnectAttempts.value < reconnectOptions.maxAttempts) {
            const delay = getNextDelay()
            console.log(`WebSocket将在${delay}ms后尝试重连 (${reconnectAttempts.value + 1}/${reconnectOptions.maxAttempts})`)
            
            isReconnecting.value = true
            reconnectAttempts.value++
            
            setTimeout(() => {
              if (!isConnected.value) {
                connect().catch(() => {
                  // 重连失败，但已在内部处理
                })
              }
            }, delay)
          } else {
            console.log('已达到最大重连次数，停止重连')
            isReconnecting.value = false
            reject(new Error('WebSocket连接失败，已达到最大重连次数'))
          }
        }
      } catch (e) {
        error.value = e as Error
        isConnected.value = false
        reject(error.value)
      }
    })
  }

  const disconnect = () => {
    if (ws.value) {
      // 使用1000正常关闭代码
      ws.value.close(1000, '用户主动断开连接')
      ws.value = null
      isConnected.value = false
    }
  }

  // 发送消息
  const send = (message: string | object) => {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.error('WebSocket未连接，无法发送消息')
      return false
    }
    
    try {
      const data = typeof message === 'string' ? message : JSON.stringify(message)
      ws.value.send(data)
      return true
    } catch (e) {
      console.error('发送WebSocket消息失败:', e)
      return false
    }
  }

  onMounted(() => {
    connect().catch(e => {
      console.error('初始WebSocket连接失败:', e)
    })
  })

  onUnmounted(() => {
    disconnect()
  })

  return {
    data,
    isConnected,
    isReconnecting,
    error,
    reconnectAttempts,
    connect,
    disconnect,
    send,
    ws
  }
} 