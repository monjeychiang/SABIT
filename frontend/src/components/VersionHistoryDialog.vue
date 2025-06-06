<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { getVersionHistory, type VersionHistoryItem } from '@/services/versionHistoryService';

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  currentVersion: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['update:visible', 'close']);

// 版本歷史記錄
const versionHistory = ref<VersionHistoryItem[]>([]);
const isLoading = ref(true);

// 關閉對話框
const closeDialog = () => {
  console.log('關閉版本歷史對話框');
  emit('update:visible', false);
  emit('close');
};

// 格式化日期
const formatDate = (dateString: string): string => {
  try {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('zh-TW', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    }).format(date);
  } catch (error) {
    return dateString;
  }
};

// 載入版本歷史
const loadVersionHistory = () => {
  console.log('載入版本歷史數據');
  isLoading.value = true;
  try {
    versionHistory.value = getVersionHistory();
    console.log('載入的版本歷史:', versionHistory.value);
  } catch (error) {
    console.error('載入版本歷史失敗:', error);
  } finally {
    isLoading.value = false;
  }
};

// 監視對話框開啟狀態
watch(() => props.visible, (newVal) => {
  console.log('監測到 visible 變化:', newVal);
  if (newVal) {
    console.log('對話框打開，載入數據');
    loadVersionHistory();
  }
}, { immediate: true });

// 監視點擊對話框外的事件
const handleOutsideClick = (event: MouseEvent) => {
  const dialogContent = document.querySelector('.version-dialog-content');
  if (dialogContent && !dialogContent.contains(event.target as Node)) {
    console.log('點擊了對話框外部，關閉對話框');
    closeDialog();
  }
};

// 初始化
onMounted(() => {
  console.log('VersionHistoryDialog 組件掛載, visible:', props.visible);
  if (props.visible) {
    loadVersionHistory();
  }
});

// 判斷當前版本
const isCurrentVersion = (version: string): boolean => {
  return version === props.currentVersion;
};
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="version-dialog-overlay" @click="handleOutsideClick">
      <div class="version-dialog-content">
        <div class="version-dialog-header">
          <h2>版本更新歷史</h2>
          <button class="close-button" @click="closeDialog">×</button>
        </div>
        
        <div class="version-dialog-body">
          <div v-if="isLoading" class="version-loading">
            載入中...
          </div>
          
          <template v-else>
            <div 
              v-for="(item, index) in versionHistory" 
              :key="item.version" 
              class="version-item" 
              :class="{ 'current-version': isCurrentVersion(item.version), 'important-version': item.important }"
              :style="{ '--item-index': index }"
            >
              <div class="version-header">
                <div class="version-title-section">
                  <span class="version-number">v{{ item.version }}</span>
                  <span v-if="isCurrentVersion(item.version)" class="current-tag">當前版本</span>
                  <span v-if="item.important" class="important-tag">重要更新</span>
                </div>
                <div class="version-date">{{ formatDate(item.releaseDate) }}</div>
              </div>
              
              <h3 class="version-title">{{ item.title }}</h3>
              
              <!-- 新功能 -->
              <div v-if="item.features && item.features.length > 0" class="version-section">
                <h4 class="section-title feature-title">新功能</h4>
                <ul class="change-list feature-list">
                  <li v-for="(feature, index) in item.features" :key="index">{{ feature }}</li>
                </ul>
              </div>
              
              <!-- 改進 -->
              <div v-if="item.improvements && item.improvements.length > 0" class="version-section">
                <h4 class="section-title improvement-title">改進</h4>
                <ul class="change-list improvement-list">
                  <li v-for="(improvement, index) in item.improvements" :key="index">{{ improvement }}</li>
                </ul>
              </div>
              
              <!-- 修復 -->
              <div v-if="item.fixes && item.fixes.length > 0" class="version-section">
                <h4 class="section-title fix-title">修復</h4>
                <ul class="change-list fix-list">
                  <li v-for="(fix, index) in item.fixes" :key="index">{{ fix }}</li>
                </ul>
              </div>
            </div>
          </template>
        </div>
        
        <div class="version-dialog-footer">
          <button class="close-button-text" @click="closeDialog">關閉</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.version-dialog-overlay {
  --primary-color-rgb: 24, 144, 255; /* 藍色 */
  --warning-color-rgb: 250, 173, 20; /* 橙色 */
  --success-color-rgb: 82, 196, 26; /* 綠色 */
  
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(var(--surface-color-rgb), 0.8);
  backdrop-filter: blur(5px);
  -webkit-backdrop-filter: blur(5px);
  z-index: 1000;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  animation: overlay-fade-in 0.3s ease;
}

@keyframes overlay-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.version-dialog-content {
  background-color: var(--card-background);
  border-radius: var(--border-radius-lg);
  box-shadow: var(--box-shadow-lg);
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: dialog-fade-in 0.3s ease;
  position: relative;
  border: 1px solid var(--border-color-light);
}

.version-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
  background-color: var(--surface-color);
}

.version-dialog-header h2 {
  font-size: 18px;
  margin: 0;
  color: var(--text-primary);
  font-weight: 600;
  display: flex;
  align-items: center;
}

.version-dialog-header h2::before {
  content: '';
  display: inline-block;
  width: 16px;
  height: 16px;
  background-color: var(--primary-color);
  border-radius: 50%;
  margin-right: 10px;
  box-shadow: 0 0 8px var(--primary-color);
}

.close-button {
  background: none;
  border: none;
  font-size: 28px;
  line-height: 1;
  padding: 0;
  cursor: pointer;
  color: var(--text-tertiary);
  transition: all 0.2s ease;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

.close-button:hover {
  color: var(--text-primary);
  background-color: var(--surface-hover);
  transform: rotate(90deg);
}

.version-dialog-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  /* 隱藏滾動條 */
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */
}

/* 對 Chrome、Safari 和 Opera 隱藏滾動條 */
.version-dialog-body::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

.version-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100px;
  color: var(--text-secondary);
}

.version-item {
  margin-bottom: 30px;
  padding-bottom: 25px;
  border-bottom: 1px solid var(--border-color-light);
  position: relative;
  transition: all 0.3s ease;
  opacity: 0;
  animation: version-item-fade-in 0.5s ease forwards;
  animation-delay: calc(var(--item-index, 0) * 0.1s);
}

@keyframes version-item-fade-in {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.version-item:last-child {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.version-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.version-title-section {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.version-number {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-color);
  text-shadow: 0 0 1px rgba(var(--primary-color-rgb), 0.3);
}

.current-tag {
  background-color: var(--primary-color);
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(var(--primary-color-rgb), 0.3);
}

.important-tag {
  background-color: var(--warning-color, orange);
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(var(--warning-color-rgb, 255, 165, 0), 0.3);
}

.version-date {
  font-size: 12px;
  color: var(--text-tertiary);
  background-color: var(--surface-color);
  padding: 2px 8px;
  border-radius: 12px;
}

.version-title {
  font-size: 16px;
  font-weight: 500;
  margin: 8px 0 16px 0;
  color: var(--text-primary);
  position: relative;
  padding-left: 12px;
}

.version-title::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background-color: var(--primary-color);
  border-radius: 2px;
}

.version-section {
  margin-bottom: 20px;
  animation: section-fade-in 0.5s ease;
  animation-delay: 0.2s;
}

@keyframes section-fade-in {
  from {
    opacity: 0;
    transform: translateX(-10px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0 0 12px 0;
  display: flex;
  align-items: center;
}

.section-title::before {
  content: '';
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 8px;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.1);
}

.feature-title::before {
  background-color: var(--success-color, #52c41a);
}

.improvement-title::before {
  background-color: var(--primary-color, #1890ff);
}

.fix-title::before {
  background-color: var(--warning-color, #faad14);
}

.change-list {
  margin: 0;
  padding-left: 32px;
}

.change-list li {
  margin-bottom: 8px;
  font-size: 14px;
  color: var(--text-secondary);
  position: relative;
  transition: all 0.2s ease;
}

.change-list li:hover {
  color: var(--text-primary);
  transform: translateX(4px);
}

.version-dialog-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  background-color: var(--surface-color);
}

.close-button-text {
  background-color: var(--primary-color);
  border: none;
  padding: 8px 20px;
  border-radius: var(--border-radius-md);
  cursor: pointer;
  font-size: 14px;
  color: white;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(var(--primary-color-rgb), 0.3);
}

.close-button-text:hover {
  background-color: var(--primary-dark);
  box-shadow: 0 4px 8px rgba(var(--primary-color-rgb), 0.4);
  transform: translateY(-2px);
}

.close-button-text:active {
  transform: translateY(0);
  box-shadow: 0 1px 2px rgba(var(--primary-color-rgb), 0.3);
}

/* 當前版本高亮 */
.current-version {
  background-color: var(--surface-hover);
  border-radius: var(--border-radius-md);
  padding: 20px;
  margin: -15px -20px 15px -20px;
  border-left: 4px solid var(--primary-color);
  box-shadow: 0 2px 8px rgba(var(--primary-color-rgb), 0.1);
}

/* 重要版本樣式 */
.important-version {
  position: relative;
}

.important-version::after {
  content: '';
  position: absolute;
  right: -12px;
  top: -12px;
  width: 24px;
  height: 24px;
  background-color: var(--warning-color, orange);
  border-radius: 50%;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='white'%3E%3Cpath d='M12 2L1 21h22L12 2zm0 3.83L19.13 19H4.87L12 5.83zM11 10h2v5h-2v-5zm0 6h2v2h-2v-2z'/%3E%3C/svg%3E");
  background-size: 16px;
  background-position: center;
  background-repeat: no-repeat;
  box-shadow: 0 2px 4px rgba(var(--warning-color-rgb, 255, 165, 0), 0.3);
  z-index: 1;
  transform: scale(0);
  animation: important-badge-appear 0.3s ease forwards;
  animation-delay: 0.5s;
}

@keyframes important-badge-appear {
  from {
    transform: scale(0);
  }
  to {
    transform: scale(1);
  }
}

/* 動畫 */
@keyframes dialog-fade-in {
  from {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* 移動設備適配 */
@media (max-width: 768px) {
  .version-dialog-overlay {
    padding: 10px;
  }
  
  .version-dialog-content {
    width: 100%;
    max-height: 90vh;
  }
  
  .version-dialog-header {
    padding: 12px 16px;
  }
  
  .version-dialog-body {
    padding: 16px;
  }
  
  .version-item {
    margin-bottom: 20px;
    padding-bottom: 20px;
  }
  
  .current-version {
    padding: 15px;
    margin: -10px -16px 10px -16px;
  }
  
  .version-number {
    font-size: 16px;
  }
  
  .version-title {
    font-size: 15px;
  }
  
  .change-list li {
    font-size: 13px;
  }
}
</style> 