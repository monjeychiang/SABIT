import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { gridTradingService, GridStrategy, GridStatus, CreateGridStrategyRequest, GridStrategyDetails } from '@/services/gridTradingService';

export const useGridTradingStore = defineStore('grid-trading', () => {
  // 狀態
  const strategies = ref<GridStrategy[]>([]);
  const currentStrategy = ref<GridStrategyDetails | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  // 計算屬性
  const runningStrategies = computed(() => 
    strategies.value.filter(s => s.status === GridStatus.RUNNING)
  );

  const stoppedStrategies = computed(() => 
    strategies.value.filter(s => 
      s.status === GridStatus.STOPPED || 
      s.status === GridStatus.CREATED || 
      s.status === GridStatus.COMPLETED || 
      s.status === GridStatus.FAILED
    )
  );

  const hasRunningStrategies = computed(() => runningStrategies.value.length > 0);
  
  // 方法
  const clearError = () => {
    error.value = null;
  };

  // 獲取所有網格策略
  const fetchStrategies = async () => {
    loading.value = true;
    error.value = null;

    try {
      strategies.value = await gridTradingService.getStrategies();
    } catch (err: any) {
      error.value = err.message || '獲取網格策略失敗';
      console.error('獲取網格策略失敗:', err);
    } finally {
      loading.value = false;
    }
  };

  // 獲取特定網格策略詳情
  const fetchStrategy = async (gridId: string) => {
    loading.value = true;
    error.value = null;

    try {
      currentStrategy.value = await gridTradingService.getStrategyDetails(gridId);
      // 更新策略列表中對應的數據
      const index = strategies.value.findIndex(s => s.id === gridId);
      if (index !== -1) {
        strategies.value[index] = { ...currentStrategy.value };
      }
    } catch (err: any) {
      error.value = err.message || '獲取網格策略詳情失敗';
      console.error('獲取網格策略詳情失敗:', err);
    } finally {
      loading.value = false;
    }
  };

  // 創建網格策略
  const createStrategy = async (request: CreateGridStrategyRequest): Promise<string | null> => {
    loading.value = true;
    error.value = null;

    try {
      const gridId = await gridTradingService.createStrategy(request);
      await fetchStrategies(); // 重新獲取列表
      return gridId;
    } catch (err: any) {
      error.value = err.message || '創建網格策略失敗';
      console.error('創建網格策略失敗:', err);
      return null;
    } finally {
      loading.value = false;
    }
  };

  // 啟動網格策略
  const startStrategy = async (gridId: string): Promise<boolean> => {
    loading.value = true;
    error.value = null;

    try {
      const success = await gridTradingService.startStrategy(gridId);
      if (success) {
        // 更新策略狀態
        const index = strategies.value.findIndex(s => s.id === gridId);
        if (index !== -1) {
          strategies.value[index].status = GridStatus.RUNNING;
          strategies.value[index].started_at = new Date().toISOString();
        }
        
        // 如果當前正在查看該策略，也更新當前策略狀態
        if (currentStrategy.value && currentStrategy.value.id === gridId) {
          currentStrategy.value.status = GridStatus.RUNNING;
          currentStrategy.value.started_at = new Date().toISOString();
        }
      }
      return success;
    } catch (err: any) {
      error.value = err.message || '啟動網格策略失敗';
      console.error('啟動網格策略失敗:', err);
      return false;
    } finally {
      loading.value = false;
    }
  };

  // 停止網格策略
  const stopStrategy = async (gridId: string): Promise<boolean> => {
    loading.value = true;
    error.value = null;

    try {
      const success = await gridTradingService.stopStrategy(gridId);
      if (success) {
        // 更新策略狀態
        const index = strategies.value.findIndex(s => s.id === gridId);
        if (index !== -1) {
          strategies.value[index].status = GridStatus.STOPPED;
          strategies.value[index].stopped_at = new Date().toISOString();
        }
        
        // 如果當前正在查看該策略，也更新當前策略狀態
        if (currentStrategy.value && currentStrategy.value.id === gridId) {
          currentStrategy.value.status = GridStatus.STOPPED;
          currentStrategy.value.stopped_at = new Date().toISOString();
        }
      }
      return success;
    } catch (err: any) {
      error.value = err.message || '停止網格策略失敗';
      console.error('停止網格策略失敗:', err);
      return false;
    } finally {
      loading.value = false;
    }
  };

  // 刪除網格策略
  const deleteStrategy = async (gridId: string): Promise<boolean> => {
    loading.value = true;
    error.value = null;

    try {
      const success = await gridTradingService.deleteStrategy(gridId);
      if (success) {
        // 從列表中移除該策略
        strategies.value = strategies.value.filter(s => s.id !== gridId);
        
        // 如果當前正在查看該策略，清空當前策略
        if (currentStrategy.value && currentStrategy.value.id === gridId) {
          currentStrategy.value = null;
        }
      }
      return success;
    } catch (err: any) {
      error.value = err.message || '刪除網格策略失敗';
      console.error('刪除網格策略失敗:', err);
      return false;
    } finally {
      loading.value = false;
    }
  };

  // 計算網格策略的盈虧
  const calculatePnl = async (gridId: string) => {
    loading.value = true;
    error.value = null;

    try {
      const pnlData = await gridTradingService.calculatePnl(gridId);
      
      // 更新策略列表中對應的數據
      const index = strategies.value.findIndex(s => s.id === gridId);
      if (index !== -1) {
        strategies.value[index].realized_pnl = pnlData.realized_pnl;
        strategies.value[index].unrealized_pnl = pnlData.unrealized_pnl;
        strategies.value[index].current_pnl = pnlData.total_pnl;
      }
      
      // 如果當前正在查看該策略，也更新當前策略狀態
      if (currentStrategy.value && currentStrategy.value.id === gridId) {
        currentStrategy.value.realized_pnl = pnlData.realized_pnl;
        currentStrategy.value.unrealized_pnl = pnlData.unrealized_pnl;
        currentStrategy.value.current_pnl = pnlData.total_pnl;
      }

      return pnlData;
    } catch (err: any) {
      error.value = err.message || '計算網格策略盈虧失敗';
      console.error('計算網格策略盈虧失敗:', err);
      return null;
    } finally {
      loading.value = false;
    }
  };

  return {
    // 狀態
    strategies,
    currentStrategy,
    loading,
    error,

    // 計算屬性
    runningStrategies,
    stoppedStrategies,
    hasRunningStrategies,

    // 方法
    clearError,
    fetchStrategies,
    fetchStrategy,
    createStrategy,
    startStrategy,
    stopStrategy,
    deleteStrategy,
    calculatePnl
  };
}); 