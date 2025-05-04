import axios from 'axios';

interface LatencyResult {
  value: number;  // 延迟时间（毫秒）
  status: 'excellent' | 'good' | 'fair' | 'poor' | 'failed';  // 延迟状态
  text: string;   // 显示文本（例如 "25ms"）
  timestamp: number; // 测量时间戳
}

interface LatencyConfig {
  pingEndpoint: string;  // 用于ping测试的API端点
  staticResource: string; // 用于资源加载测试的静态资源
  interval: number;      // 自动测量间隔（毫秒）
  thresholds: {         // 延迟阈值（毫秒）
    excellent: number;  // 优秀
    good: number;       // 良好
    fair: number;       // 一般
    poor: number;       // 较差
  };
}

class LatencyService {
  private config: LatencyConfig;
  private latestResult: LatencyResult | null = null;
  private intervalId: number | null = null;
  private listeners: Array<(result: LatencyResult) => void> = [];
  private measurementInProgress = false;
  private apiBaseUrl: string;

  constructor(apiBaseUrl: string, config?: Partial<LatencyConfig>) {
    this.apiBaseUrl = apiBaseUrl;
    
    // 默认配置
    this.config = {
      pingEndpoint: `${apiBaseUrl}/api/v1/ping`,
      staticResource: `${apiBaseUrl}/favicon.ico`,
      interval: 30000, // 30秒
      thresholds: {
        excellent: 100, // 0-100ms: 优秀
        good: 200,      // 101-200ms: 良好
        fair: 400,      // 201-400ms: 一般
        poor: Infinity  // >400ms: 较差
      },
      ...config
    };
  }

  /**
   * 获取最新的延迟测量结果
   */
  public getLatestResult(): LatencyResult | null {
    return this.latestResult;
  }

  /**
   * 添加延迟变化监听器
   */
  public addListener(callback: (result: LatencyResult) => void): void {
    this.listeners.push(callback);
    
    // 如果已有结果，立即通知新监听器
    if (this.latestResult) {
      callback(this.latestResult);
    }
  }

  /**
   * 移除延迟变化监听器
   */
  public removeListener(callback: (result: LatencyResult) => void): void {
    this.listeners = this.listeners.filter(listener => listener !== callback);
  }

  /**
   * 启动自动延迟测量
   */
  public startAutoMeasurement(): void {
    if (this.intervalId !== null) return;
    
    // 立即执行一次
    this.measure();
    
    // 设置定期执行
    this.intervalId = window.setInterval(() => {
      this.measure();
    }, this.config.interval);
  }

  /**
   * 停止自动延迟测量
   */
  public stopAutoMeasurement(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }

  /**
   * 执行一次延迟测量
   */
  public async measure(): Promise<LatencyResult> {
    if (this.measurementInProgress) {
      // 如果已经有测量在进行中，返回最新结果或等待
      return this.latestResult || await new Promise((resolve) => {
        const listener = (result: LatencyResult) => {
          this.removeListener(listener);
          resolve(result);
        };
        this.addListener(listener);
      });
    }

    this.measurementInProgress = true;
    
    try {
      // 优化: 使用多种方法测量延迟并组合结果
      // const results = await Promise.all([
      //   this.measureHttpLatency(),
      //   this.measureResourceLatency(),
      //   this.measureFetchLatency()
      // ]);
      
      // 优化后: 优先使用单一HTTP方法，仅在失败时尝试备选方法
      let latency = await this.measureHttpLatency();
      
      // HTTP方法失败时尝试Fetch方法
      if (latency === -1) {
        latency = await this.measureFetchLatency();
        
        // 如果Fetch也失败，最后尝试资源加载方法
        if (latency === -1) {
          latency = await this.measureResourceLatency();
        }
      }
      
      // 所有方法都失败时
      if (latency === -1) {
        const failedResult: LatencyResult = {
          value: -1,
          status: 'failed',
          text: '--',
          timestamp: Date.now()
        };
        
        this.updateResult(failedResult);
        return failedResult;
      }
      
      // 确定延迟状态
      let status: LatencyResult['status'] = 'excellent';
      if (latency > this.config.thresholds.poor) {
        status = 'poor';
      } else if (latency > this.config.thresholds.fair) {
        status = 'fair';
      } else if (latency > this.config.thresholds.good) {
        status = 'good';
      }
      
      const result: LatencyResult = {
        value: latency,
        status,
        text: `${latency}ms`,
        timestamp: Date.now()
      };
      
      this.updateResult(result);
      return result;
    } catch (error) {
      console.error('延迟测量失败:', error);
      
      const failedResult: LatencyResult = {
        value: -1,
        status: 'failed',
        text: '--',
        timestamp: Date.now()
      };
      
      this.updateResult(failedResult);
      return failedResult;
    } finally {
      this.measurementInProgress = false;
    }
  }

  /**
   * 使用HTTP请求测量延迟
   */
  private async measureHttpLatency(): Promise<number> {
    const startTime = Date.now();
    try {
      // 添加随机参数避免缓存
      await axios.get(`${this.config.pingEndpoint}?_t=${Date.now()}`, {
        headers: {
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache'
        },
        timeout: 5000 // 设置超时
      });
      return Date.now() - startTime;
    } catch (e) {
      console.warn('HTTP延迟测量失败:', e);
      return -1;
    }
  }

  /**
   * 使用静态资源加载测量延迟
   */
  private measureResourceLatency(): Promise<number> {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const img = new Image();
      
      // 设置超时
      const timeout = setTimeout(() => {
        img.onload = img.onerror = null;
        resolve(-1);
      }, 5000);
      
      img.onload = () => {
        clearTimeout(timeout);
        resolve(Date.now() - startTime);
      };
      
      img.onerror = () => {
        clearTimeout(timeout);
        resolve(-1);
      };
      
      // 加载小图片并添加随机参数避免缓存
      img.src = `${this.config.staticResource}?_t=${Date.now()}`;
    });
  }

  /**
   * 使用Fetch API测量延迟
   */
  private async measureFetchLatency(): Promise<number> {
    const startTime = Date.now();
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      await fetch(`${this.config.pingEndpoint}?_t=${Date.now()}`, {
        cache: 'no-store',
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      return Date.now() - startTime;
    } catch (e) {
      console.warn('Fetch延迟测量失败:', e);
      return -1;
    }
  }

  /**
   * 更新延迟结果并通知监听器
   */
  private updateResult(result: LatencyResult): void {
    this.latestResult = result;
    
    // 通知所有监听器
    this.listeners.forEach(listener => {
      try {
        listener(result);
      } catch (e) {
        console.error('延迟监听器回调错误:', e);
      }
    });
  }

  /**
   * 获取延迟状态的颜色代码
   */
  public static getStatusColor(status: LatencyResult['status']): string {
    switch (status) {
      case 'excellent': return '#52c41a'; // 绿色
      case 'good': return '#1890ff';      // 蓝色
      case 'fair': return '#faad14';      // 黄色
      case 'poor': return '#ff4d4f';      // 红色
      case 'failed': return '#d9d9d9';    // 灰色
      default: return '#d9d9d9';
    }
  }

  /**
   * 测量一段时间内的平均延迟
   * @param duration 测量持续时间（毫秒）
   * @param interval 每次测量的间隔（毫秒），或者一个函数，接收已经过去的时间，返回下一次间隔
   * @param onMeasurement 每次测量后的回调函数，接收当前测量值
   * @returns 包含平均延迟的延迟结果
   */
  public async measureAverage(
    duration: number = 15000, 
    interval: number | ((elapsed: number) => number) = 1000,
    onMeasurement?: (latency: number) => void
  ): Promise<LatencyResult> {
    // 创建一个状态对象用于跟踪测量进度
    const status = {
      measurements: [] as number[],
      inProgress: true,
      startTime: Date.now(),
      lastMeasurementTime: Date.now() // 记录上次测量时间
    };
    
    // 获取下一次间隔的函数
    const getNextInterval = typeof interval === 'function' 
      ? interval 
      : () => interval as number;
    
    // 创建一个Promise，当所有测量完成时解析
    const resultPromise = new Promise<LatencyResult>((resolve) => {
      // 执行测量的函数
      const performMeasurement = async () => {
        const now = Date.now();
        const elapsed = now - status.startTime;
        
        // 如果已经到达持续时间，完成测量
        if (elapsed >= duration) {
          status.inProgress = false;
          
          // 计算平均延迟（排除失败的测量）
          const validMeasurements = status.measurements.filter(m => m !== -1);
          
          if (validMeasurements.length === 0) {
            // 如果没有有效测量，返回失败结果
            resolve({
              value: -1,
              status: 'failed',
              text: '测量失败',
              timestamp: Date.now()
            });
            return;
          }
          
          // 计算平均值
          const avgLatency = Math.round(
            validMeasurements.reduce((sum, val) => sum + val, 0) / validMeasurements.length
          );
          
          // 确定延迟状态
          let latencyStatus: LatencyResult['status'] = 'excellent';
          if (avgLatency > this.config.thresholds.poor) {
            latencyStatus = 'poor';
          } else if (avgLatency > this.config.thresholds.fair) {
            latencyStatus = 'fair';
          } else if (avgLatency > this.config.thresholds.good) {
            latencyStatus = 'good';
          }
          
          // 创建结果对象
          const result: LatencyResult = {
            value: avgLatency,
            status: latencyStatus,
            text: `${avgLatency}ms`,
            timestamp: Date.now()
          };
          
          // 更新最新结果
          this.updateResult(result);
          resolve(result);
          return;
        }
        
        // 执行单次测量
        try {
          const latency = await this.measureHttpLatency();
          if (latency !== -1) {
            status.measurements.push(latency);
            
            // 如果提供了回调函数，将当前测量结果传递给调用者
            if (onMeasurement) {
              onMeasurement(latency);
            }
          }
        } catch (e) {
          console.warn('延迟测量失败:', e);
        }
        
        // 如果测量还在进行中，计算下一次测量时间
        if (status.inProgress) {
          status.lastMeasurementTime = Date.now();
          const nextInterval = getNextInterval(Date.now() - status.startTime);
          setTimeout(performMeasurement, nextInterval);
        }
      };
      
      // 立即开始第一次测量
      performMeasurement();
    });
    
    return resultPromise;
  }
}

// 创建服务实例
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const latencyService = new LatencyService(apiBaseUrl);

export default latencyService; 