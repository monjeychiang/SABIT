import { apiClient } from './api';
import { useAuthStore } from '@/stores/auth';

// 網格交易策略類型定義
export enum GridType {
  ARITHMETIC = 'ARITHMETIC', // 等差網格
  GEOMETRIC = 'GEOMETRIC'    // 等比網格
}

export enum StrategyType {
  LONG = 'LONG',         // 做多
  SHORT = 'SHORT',       // 做空
  NEUTRAL = 'NEUTRAL'    // 中性
}

export enum GridStatus {
  CREATED = 'CREATED',   // 已創建
  RUNNING = 'RUNNING',   // 運行中
  STOPPED = 'STOPPED',   // 已停止
  COMPLETED = 'COMPLETED', // 已完成
  FAILED = 'FAILED'      // 失敗
}

// 網格策略接口
export interface GridStrategy {
  id: string;
  user_id: string;
  exchange: string;
  symbol: string;
  grid_type: GridType;
  strategy_type: StrategyType;
  lower_price: number;
  upper_price: number;
  grid_number: number;
  total_investment: number;
  leverage: number;
  stop_loss?: number;
  take_profit?: number;
  profit_collection?: number;
  status: GridStatus;
  created_at: string;
  updated_at: string;
  started_at?: string;
  stopped_at?: string;
  current_pnl?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  orders_filled?: number;
  current_price?: number;
  grid_points?: number[];
  error_message?: string;
}

// 網格訂單接口
export interface GridOrderHistory {
  id: string;
  grid_id: string;
  order_id: string;
  order_type: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  status: 'FILLED' | 'CANCELED' | 'REJECTED';
  fee: number;
  created_at: string;
  filled_at?: string;
  pnl?: number;
}

// 網格策略詳情接口
export interface GridStrategyDetails extends GridStrategy {
  order_history: GridOrderHistory[];
  grid_points: number[];
}

// 網格策略創建請求
export interface CreateGridStrategyRequest {
  symbol: string;
  grid_type: GridType;
  strategy_type: StrategyType;
  upper_price: number;
  lower_price: number;
  grid_number: number;
  total_investment: number;
  leverage: number;
  stop_loss?: number;
  take_profit?: number;
  profit_collection?: number;
}

// API響應接口
export interface ApiResponse<T> {
  success: boolean;
  message: string;
  grid_id?: string;
  data?: T;
}

/**
 * 網格交易服務
 * 提供網格交易策略管理相關的API
 */
class GridTradingService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  }

  /**
   * 獲取授權請求頭
   */
  private getAuthHeaders() {
    const authStore = useAuthStore();
    return {
      Authorization: `Bearer ${authStore.token}`
    };
  }

  /**
   * 創建網格交易策略
   */
  async createStrategy(request: CreateGridStrategyRequest): Promise<string> {
    const response = await apiClient.post<{ grid_id: string }>('/grid/create', request);
    return response.data.grid_id;
  }

  /**
   * 獲取用戶的所有網格策略
   */
  async getStrategies(): Promise<GridStrategy[]> {
    const response = await apiClient.get<{ strategies: GridStrategy[] }>('/grid/list');
    return response.data.strategies;
  }

  /**
   * 獲取指定網格策略的詳細信息
   */
  async getStrategyDetails(gridId: string): Promise<GridStrategyDetails> {
    const response = await apiClient.get<{ strategy: GridStrategyDetails }>(`/grid/${gridId}`);
    return response.data.strategy;
  }

  /**
   * 啟動網格策略
   */
  async startStrategy(gridId: string): Promise<boolean> {
    const response = await apiClient.post<{ success: boolean }>(`/grid/${gridId}/start`);
    return response.data.success;
  }

  /**
   * 停止網格策略
   */
  async stopStrategy(gridId: string): Promise<boolean> {
    const response = await apiClient.post<{ success: boolean }>(`/grid/${gridId}/stop`);
    return response.data.success;
  }

  /**
   * 刪除網格策略
   */
  async deleteStrategy(gridId: string): Promise<boolean> {
    const response = await apiClient.delete<{ success: boolean }>(`/grid/${gridId}`);
    return response.data.success;
  }

  /**
   * 獲取網格策略的訂單歷史
   */
  async getOrderHistory(gridId: string): Promise<GridOrderHistory[]> {
    const response = await apiClient.get<{ orders: GridOrderHistory[] }>(`/grid/${gridId}/orders`);
    return response.data.orders;
  }

  /**
   * 計算網格策略的盈虧
   */
  async calculatePnl(gridId: string): Promise<{ realized_pnl: number; unrealized_pnl: number; total_pnl: number }> {
    const response = await apiClient.get<{ 
      realized_pnl: number; 
      unrealized_pnl: number; 
      total_pnl: number 
    }>(`/grid/${gridId}/pnl`);
    return response.data;
  }
}

// 導出實例
export const gridTradingService = new GridTradingService();
export default gridTradingService; 