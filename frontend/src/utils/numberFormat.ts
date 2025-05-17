/**
 * 使用逗號格式化數字
 * @param value 要格式化的數字
 * @param decimals 小數位數 (預設為保留原有小數位數)
 * @returns 格式化後的字符串
 */
export function formatNumberWithCommas(value: number, decimals?: number): string {
  if (value === null || value === undefined || isNaN(value)) {
    return '0';
  }
  
  let valueStr: string;
  
  if (decimals !== undefined) {
    valueStr = value.toFixed(decimals);
  } else {
    // 保留原有小數位數，但最多8位
    const absValue = Math.abs(value);
    if (absValue >= 1000) {
      valueStr = value.toFixed(2);
    } else if (absValue >= 1) {
      valueStr = value.toFixed(4);
    } else if (absValue === 0) {
      valueStr = '0';
    } else {
      // 對於非常小的數值，保留更多小數位
      valueStr = value.toFixed(8);
    }
  }
  
  // 移除結尾的0
  valueStr = valueStr.replace(/\.?0+$/, '');
  if (valueStr.endsWith('.')) {
    valueStr = valueStr.slice(0, -1);
  }
  
  // 添加千位分隔符
  const parts = valueStr.split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  
  return parts.join('.');
}

/**
 * 格式化百分比數字
 * @param value 要格式化的小數 (例如: 0.12 表示 12%)
 * @param decimals 小數位數 (預設為2)
 * @returns 格式化後的百分比字符串
 */
export function formatPercent(value: number, decimals: number = 2): string {
  if (value === null || value === undefined || isNaN(value)) {
    return '0%';
  }
  
  return (value * 100).toFixed(decimals) + '%';
}

/**
 * 格式化價格顯示
 * @param price 價格
 * @param decimals 小數位數 (如果未提供，將自動根據價格大小確定)
 * @returns 格式化後的價格字符串
 */
export function formatPrice(price: number, decimals?: number): string {
  if (price === null || price === undefined || isNaN(price)) {
    return '0';
  }
  
  if (decimals === undefined) {
    // 根據價格自動確定合適的小數位數
    if (price >= 10000) {
      decimals = 0;
    } else if (price >= 1000) {
      decimals = 1;
    } else if (price >= 100) {
      decimals = 2;
    } else if (price >= 10) {
      decimals = 3;
    } else if (price >= 1) {
      decimals = 4;
    } else if (price >= 0.1) {
      decimals = 5;
    } else if (price >= 0.01) {
      decimals = 6;
    } else {
      decimals = 8;
    }
  }
  
  return formatNumberWithCommas(price, decimals);
} 