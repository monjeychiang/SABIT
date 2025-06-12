<template>
  <div class="rtl-test-container">
    <h1 class="text-center mb-4">CSS 邏輯屬性測試頁面</h1>
    
    <div class="direction-toggle mb-4">
      <button class="btn btn-primary me-2" @click="setDirection('ltr')">
        LTR 模式
      </button>
      <button class="btn btn-primary" @click="setDirection('rtl')">
        RTL 模式
      </button>
      <div class="current-dir mt-2">
        當前方向: <strong>{{ currentDir === 'rtl' ? '從右到左 (RTL)' : '從左到右 (LTR)' }}</strong>
      </div>
    </div>

    <div class="test-section" :dir="currentDir">
      <h2 class="text-start mb-3">邏輯屬性測試區域</h2>
      
      <!-- 文字對齊測試 -->
      <div class="card-style mb-4">
        <h3>文字對齊測試</h3>
        <p class="text-start mb-2">這段文字使用 text-align: start 對齊</p>
        <p class="text-end mb-2">這段文字使用 text-align: end 對齊</p>
        <p class="text-center">這段文字使用 text-align: center 對齊</p>
      </div>
      
      <!-- 邊距與內距測試 -->
      <div class="card-style mb-4">
        <h3>邊距與內距測試</h3>
        <div class="demo-box mb-3">
          <div class="ms-5 me-2 border p-3">
            這個元素使用 margin-inline-start: var(--spacing-xl) 和 margin-inline-end: var(--spacing-sm)
          </div>
        </div>
        <div class="demo-box mb-3">
          <div class="ps-4 pe-2 border p-2">
            這個元素使用 padding-inline-start: var(--spacing-lg) 和 padding-inline-end: var(--spacing-sm)
          </div>
        </div>
      </div>
      
      <!-- 邊框測試 -->
      <div class="card-style mb-4">
        <h3>邊框測試</h3>
        <div class="demo-box mb-3">
          <div class="border-s p-3 mb-2">
            這個元素使用 border-inline-start 邊框
          </div>
          <div class="border-e p-3 mb-2">
            這個元素使用 border-inline-end 邊框
          </div>
          <div class="border-t p-3 mb-2">
            這個元素使用 border-block-start 邊框
          </div>
          <div class="border-b p-3">
            這個元素使用 border-block-end 邊框
          </div>
        </div>
      </div>
      
      <!-- 浮動與定位測試 -->
      <div class="card-style mb-4">
        <h3>浮動與定位測試</h3>
        <div class="demo-box mb-3 clearfix">
          <div class="float-start p-2 border">
            這個元素使用 float: inline-start
          </div>
          <div class="float-end p-2 border">
            這個元素使用 float: inline-end
          </div>
        </div>
        <div class="demo-box mb-3 relative" style="height: 100px;">
          <div class="absolute start-0 top-0 p-2 border">
            這個元素使用 inset-inline-start: 0
          </div>
          <div class="absolute end-0 bottom-0 p-2 border">
            這個元素使用 inset-inline-end: 0
          </div>
        </div>
      </div>
      
      <!-- 實際應用示例 -->
      <div class="card-style mb-4">
        <h3>實際應用示例</h3>
        <div class="chat-message mb-3">
          <div class="avatar"></div>
          <div class="message-content">
            <div class="message-header">
              <span class="username">使用者名稱</span>
              <span class="timestamp">10:30 AM</span>
            </div>
            <div class="message-text">
              這是一個聊天訊息範例，展示如何使用邏輯屬性構建聊天界面。
              無論是 LTR 還是 RTL 模式，頭像都會在開始側，時間戳在結束側。
            </div>
          </div>
        </div>
        
        <div class="form-example">
          <label class="form-label" for="example-input">表單標籤:</label>
          <div class="input-group">
            <input id="example-input" type="text" class="form-input" placeholder="請輸入內容...">
            <button class="btn btn-secondary">送出</button>
          </div>
        </div>
      </div>
    </div>
    
    <div class="explanation card-style mt-5">
      <h3>說明</h3>
      <p>
        此頁面展示了 CSS 邏輯屬性如何在不同文字方向下自動調整。
        當切換到 RTL 模式時，所有使用邏輯屬性的元素都會自動調整其方向，
        而無需額外的 CSS 規則。
      </p>
      <p>
        主要使用的邏輯屬性包括：
      </p>
      <ul>
        <li>margin-inline-start/end 替代 margin-left/right</li>
        <li>padding-inline-start/end 替代 padding-left/right</li>
        <li>border-inline-start/end 替代 border-left/right</li>
        <li>text-align: start/end 替代 text-align: left/right</li>
        <li>inset-inline-start/end 替代 left/right</li>
        <li>float: inline-start/end 替代 float: left/right</li>
      </ul>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RTLTestView',
  data() {
    return {
      currentDir: 'ltr'
    }
  },
  methods: {
    setDirection(dir) {
      this.currentDir = dir;
    }
  }
}
</script>

<style scoped>
.rtl-test-container {
  max-width: 800px;
  margin-inline: auto;
  padding: var(--spacing-lg);
}

.test-section {
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-md);
  padding: var(--spacing-lg);
  background-color: var(--surface-color);
}

.demo-box {
  background-color: var(--hover-color);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-sm);
}

.border-s {
  border-inline-start: 4px solid var(--primary-color);
}

.border-e {
  border-inline-end: 4px solid var(--primary-color);
}

.border-t {
  border-block-start: 4px solid var(--primary-color);
}

.border-b {
  border-block-end: 4px solid var(--primary-color);
}

/* 聊天訊息樣式 */
.chat-message {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: var(--primary-color);
  flex-shrink: 0;
}

.message-content {
  flex: 1;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-block-end: var(--spacing-xs);
}

.username {
  font-weight: bold;
  color: var(--text-primary);
}

.timestamp {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}

.message-text {
  background-color: var(--hover-color);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-md);
}

/* 表單樣式 */
.form-example {
  margin-block-start: var(--spacing-lg);
}

.form-label {
  display: block;
  margin-block-end: var(--spacing-xs);
}

.input-group {
  display: flex;
}

.form-input {
  flex: 1;
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--border-radius-sm);
  border-start-end-radius: 0;
  border-end-end-radius: 0;
}

.input-group .btn {
  border-start-start-radius: 0;
  border-end-start-radius: 0;
}

/* 方向切換按鈕 */
.direction-toggle {
  margin-block: var(--spacing-lg);
}

.current-dir {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

/* 說明區塊 */
.explanation {
  background-color: var(--hover-color);
}

.explanation ul {
  padding-inline-start: var(--spacing-lg);
}
</style> 