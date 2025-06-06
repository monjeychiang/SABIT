/**
 * 版本歷史記錄服務
 * 用於存儲和獲取應用程序的版本更新歷史
 */

export interface VersionHistoryItem {
  version: string;
  releaseDate: string;
  title: string;
  features?: string[];
  improvements?: string[];
  fixes?: string[];
  important?: boolean;
}

// 版本歷史記錄，按照版本號從新到舊排列
const versionHistory: VersionHistoryItem[] = [
  {
    version: '1.0.1',
    releaseDate: '2024-05-15',
    title: '穩定性更新',
    improvements: [
      '優化系統狀態顯示界面',
      '改進WebSocket連接穩定性'
    ],
    fixes: [
      '修復用戶數據加載問題',
      '修復某些情況下通知不顯示的問題',
      '解決深色模式下部分元素顯示異常的問題'
    ],
    important: false
  },
  {
    version: '1.0.0',
    releaseDate: '2024-05-01',
    title: '正式版發布',
    features: [
      '完整的用戶認證系統',
      '即時消息通知功能',
      '支援深色模式切換',
      '系統狀態監控儀表板'
    ],
    improvements: [
      '優化用戶界面響應速度',
      '改進移動設備兼容性'
    ],
    important: true
  },
  {
    version: '0.9.5',
    releaseDate: '2024-04-15',
    title: '預發布版本',
    features: [
      '新增用戶資料設置頁面',
      '整合WebSocket即時通訊功能'
    ],
    improvements: [
      '優化應用加載速度',
      '改進認證流程'
    ],
    fixes: [
      '修復多項用戶反饋的界面問題'
    ],
    important: false
  }
];

/**
 * 獲取完整版本歷史
 */
export const getVersionHistory = (): VersionHistoryItem[] => {
  return versionHistory;
};

/**
 * 獲取指定版本的歷史記錄
 */
export const getVersionDetails = (version: string): VersionHistoryItem | undefined => {
  return versionHistory.find(item => item.version === version);
};

/**
 * 獲取當前版本的歷史記錄
 * 基於環境變量中的版本號
 */
export const getCurrentVersionDetails = (): VersionHistoryItem | undefined => {
  const currentVersion = import.meta.env.VITE_APP_VERSION?.replace('-dev', '') || '1.0.0';
  return getVersionDetails(currentVersion);
};

export default {
  getVersionHistory,
  getVersionDetails,
  getCurrentVersionDetails
}; 