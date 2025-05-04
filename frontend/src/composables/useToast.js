import { ref, onMounted, onUnmounted, watch } from 'vue';

// 存儲所有的toast訊息
const toasts = ref([]);

// 產生唯一ID
let toastId = 0;

// 預設配置
const defaultOptions = {
  duration: 3000, // 顯示時間（毫秒）
  position: 'top-right', // 位置
};

// 添加一個新toast
const addToast = (message, type = 'info', options = {}) => {
  const id = ++toastId;
  const toast = {
    id,
    message,
    type, // 'info', 'success', 'warning', 'error'
    options: { ...defaultOptions, ...options },
    timestamp: Date.now(),
  };
  
  toasts.value.push(toast);
  
  // 設置自動移除計時器
  setTimeout(() => {
    removeToast(id);
  }, toast.options.duration);
  
  return id;
};

// 移除特定toast
const removeToast = (id) => {
  const index = toasts.value.findIndex(toast => toast.id === id);
  if (index !== -1) {
    toasts.value.splice(index, 1);
  }
};

// 清空所有toast
const clearToasts = () => {
  toasts.value = [];
};

// 創建DOM容器
const createToastContainer = () => {
  const containerId = 'toast-container';
  let container = document.getElementById(containerId);
  
  if (!container) {
    container = document.createElement('div');
    container.id = containerId;
    container.style.position = 'fixed';
    container.style.zIndex = '1000';
    container.style.top = '20px';
    container.style.right = '20px';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    document.body.appendChild(container);
  }
  
  return container;
};

// 渲染toast到DOM
const renderToasts = () => {
  const container = createToastContainer();
  
  // 清空容器
  container.innerHTML = '';
  
  // 遍歷所有toast並創建元素
  toasts.value.forEach(toast => {
    const toastEl = document.createElement('div');
    toastEl.className = `toast toast-${toast.type}`;
    toastEl.setAttribute('role', 'alert');
    
    // 樣式
    toastEl.style.padding = '12px 16px';
    toastEl.style.borderRadius = '6px';
    toastEl.style.backgroundColor = getBackgroundColor(toast.type);
    toastEl.style.color = toast.type === 'info' ? '#4b5563' : '#fff';
    toastEl.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)';
    toastEl.style.display = 'flex';
    toastEl.style.alignItems = 'center';
    toastEl.style.minWidth = '250px';
    toastEl.style.maxWidth = '350px';
    toastEl.style.animation = 'toast-in 0.3s ease-out forwards';
    
    // 添加圖標
    const iconEl = document.createElement('span');
    iconEl.innerHTML = getIconSvg(toast.type);
    iconEl.style.marginRight = '10px';
    iconEl.style.display = 'flex';
    iconEl.style.alignItems = 'center';
    toastEl.appendChild(iconEl);
    
    // 添加訊息
    const messageEl = document.createElement('span');
    messageEl.textContent = toast.message;
    messageEl.style.flex = '1';
    toastEl.appendChild(messageEl);
    
    // 添加關閉按鈕
    const closeEl = document.createElement('button');
    closeEl.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
    closeEl.style.background = 'none';
    closeEl.style.border = 'none';
    closeEl.style.color = 'inherit';
    closeEl.style.cursor = 'pointer';
    closeEl.style.marginLeft = '10px';
    closeEl.style.padding = '0';
    closeEl.style.display = 'flex';
    closeEl.style.alignItems = 'center';
    closeEl.addEventListener('click', () => removeToast(toast.id));
    toastEl.appendChild(closeEl);
    
    container.appendChild(toastEl);
  });
  
  // 添加CSS動畫
  if (!document.getElementById('toast-styles')) {
    const styleEl = document.createElement('style');
    styleEl.id = 'toast-styles';
    styleEl.textContent = `
      @keyframes toast-in {
        from { transform: translateY(-20px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
      }
    `;
    document.head.appendChild(styleEl);
  }
};

// 根據類型獲取背景色
const getBackgroundColor = (type) => {
  switch (type) {
    case 'success': return '#10b981';
    case 'warning': return '#f59e0b';
    case 'error': return '#ef4444';
    default: return '#f3f4f6';
  }
};

// 根據類型獲取圖標
const getIconSvg = (type) => {
  switch (type) {
    case 'success':
      return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
    case 'warning':
      return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
    case 'error':
      return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>';
    default:
      return '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
  }
};

// 快捷函數
const showToast = (message, type = 'info', options = {}) => {
  return addToast(message, type, options);
};

const showSuccessToast = (message, options = {}) => {
  return showToast(message, 'success', options);
};

const showWarningToast = (message, options = {}) => {
  return showToast(message, 'warning', options);
};

const showErrorToast = (message, options = {}) => {
  return showToast(message, 'error', options);
};

// 共用組合式函數
export function useToast() {
  let unwatch = null;
  
  onMounted(() => {
    // 使用watch函數監聽toasts變化
    unwatch = watch(toasts, () => {
      renderToasts();
    }, { immediate: true, deep: true });
  });
  
  onUnmounted(() => {
    // 清理watch
    if (unwatch) {
      unwatch();
    }
    
    clearToasts();
    const container = document.getElementById('toast-container');
    if (container) {
      container.remove();
    }
  });
  
  return {
    toasts,
    showToast,
    showSuccessToast,
    showWarningToast,
    showErrorToast,
    removeToast,
    clearToasts
  };
}

// 添加一個全局方法
const globalToast = {
  showToast,
  showSuccessToast,
  showWarningToast,
  showErrorToast,
  removeToast,
  clearToasts
};

export default globalToast; 