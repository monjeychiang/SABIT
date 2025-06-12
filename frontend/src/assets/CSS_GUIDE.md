# CSS 樣式系統使用指南

本文件說明專案的 CSS 架構、命名規範與使用方式，旨在提供一致、高效率且易於維護的樣式系統。

## 目錄
1. [樣式範圍化 (Scoped CSS)](#樣式範圍化)
2. [全域 CSS 變數](#全域-css-變數)
3. [功能性 CSS 類別](#功能性-css-類別)
4. [CSS 邏輯屬性與國際化](#css-邏輯屬性與國際化)
5. [最佳實踐](#最佳實踐)
6. [主題切換](#主題切換)

## 樣式範圍化

為避免樣式衝突，所有元件應使用 `scoped` 屬性限制 CSS 作用範圍：

```vue
<style scoped>
.my-component {
  /* 樣式僅作用於當前元件 */
  color: var(--text-primary);
}
</style>
```

### 優點
- 避免全域樣式污染
- 減少元件間樣式衝突
- 提高樣式可維護性

### 注意事項
- 使用 `::v-deep` 或 `:deep()` 選擇器可穿透 scoped 樣式限制，但應謹慎使用：

```vue
<style scoped>
/* Vue 3 使用 :deep() */
:deep(.third-party-component) {
  /* 修改第三方元件樣式 */
  color: var(--primary-color);
}
</style>
```

## 全域 CSS 變數

專案在 `:root` 中定義了大量 CSS 變數，用於統一管理主題樣式。

### 使用方式

```css
.my-element {
  color: var(--text-primary);
  background-color: var(--surface-color);
  margin: var(--spacing-md);
  border-radius: var(--border-radius-sm);
}
```

### 主要變數類別

#### 顏色系統
```
--primary-color: 主要品牌顏色
--secondary-color: 輔助顏色
--accent-color: 強調顏色
--danger-color: 危險/錯誤顏色
--warning-color: 警告顏色
--info-color: 資訊顏色
--success-color: 成功顏色

--text-primary: 主要文字顏色
--text-secondary: 次要文字顏色
--text-tertiary: 第三層次文字顏色
--text-light: 淺色文字顏色

--background-color: 頁面背景色
--surface-color: 元件表面顏色
--card-background: 卡片背景色
--hover-color: 懸浮狀態色
```

#### 間距系統
```
--spacing-xs: 4px
--spacing-sm: 8px
--spacing-md: 16px
--spacing-lg: 24px
--spacing-xl: 32px
```

#### 邊框與圓角
```
--border-color: 主要邊框顏色
--border-light: 淺色邊框顏色

--border-radius-sm: 8px
--border-radius-md: 16px
--border-radius-lg: 24px
```

#### 陰影效果
```
--box-shadow-sm: 小陰影
--box-shadow-md: 中等陰影
--box-shadow-lg: 大陰影
```

#### 字體系統
```
--font-size-xs: 0.75rem
--font-size-sm: 0.875rem
--font-size-md: 1rem
--font-size-lg: 1.125rem
--font-size-xl: 1.25rem
--font-size-xxl: 1.5rem
```

#### 動畫時間
```
--transition-fast: 150ms
--transition-normal: 250ms
--transition-slow: 350ms
```

#### 層級系統 (Z-index)
```
--z-index-dropdown: 1000
--z-index-sticky: 1020
--z-index-fixed: 1030
--z-index-modal-backdrop: 1040
--z-index-modal: 1050
--z-index-popover: 1060
--z-index-tooltip: 1070
```

## 功能性 CSS 類別

專案提供了一套功能性 CSS 類別，可用於快速構建界面並保持一致性。

### 佈局類別

#### Flex 相關
```
.flex - 顯示為 flex 容器
.flex-col - 垂直方向 flex 佈局
.flex-row - 水平方向 flex 佈局
.flex-wrap - 允許 flex 元素換行
.flex-nowrap - 不允許 flex 元素換行
.flex-center - 居中對齊的 flex 容器

.items-center - 垂直居中對齊
.items-start - 頂部對齊
.items-end - 底部對齊

.justify-center - 水平居中對齊
.justify-between - 元素之間平均分配空間
.justify-around - 元素周圍平均分配空間
.justify-start - 靠左對齊
.justify-end - 靠右對齊

.flex-1 - flex: 1
.flex-auto - flex: auto
.flex-none - flex: none
```

#### Grid 相關
```
.grid - 顯示為 grid 容器
.grid-cols-1 - 單列網格
.grid-cols-2 - 雙列網格
.grid-cols-3 - 三列網格
.grid-cols-4 - 四列網格
.grid-cols-12 - 十二列網格

.gap-1 到 .gap-5 - 網格間距
```

### 間距類別

#### 外邊距 (margin)
```
.m-0 到 .m-5 - 四周外邊距
.mx-1 到 .mx-5 - 水平外邊距 (使用邏輯屬性 margin-inline)
.my-1 到 .my-5 - 垂直外邊距 (使用邏輯屬性 margin-block)
.mt-1 到 .mt-5 - 上外邊距 (使用邏輯屬性 margin-block-start)
.mb-1 到 .mb-5 - 下外邊距 (使用邏輯屬性 margin-block-end)
.ms-1 到 .ms-5 - 開始側外邊距 (使用邏輯屬性 margin-inline-start)
.me-1 到 .me-5 - 結束側外邊距 (使用邏輯屬性 margin-inline-end)
.mx-auto - 水平居中 (使用邏輯屬性 margin-inline: auto)
```

#### 內邊距 (padding)
```
.p-0 到 .p-5 - 四周內邊距
.px-1 到 .px-5 - 水平內邊距 (使用邏輯屬性 padding-inline)
.py-1 到 .py-5 - 垂直內邊距 (使用邏輯屬性 padding-block)
.pt-1 到 .pt-5 - 上內邊距 (使用邏輯屬性 padding-block-start)
.pb-1 到 .pb-5 - 下內邊距 (使用邏輯屬性 padding-block-end)
.ps-1 到 .ps-5 - 開始側內邊距 (使用邏輯屬性 padding-inline-start)
.pe-1 到 .pe-5 - 結束側內邊距 (使用邏輯屬性 padding-inline-end)
```

### 文字樣式
```
.text-truncate - 單行文字溢出省略
.text-break - 文字自動換行
.text-center - 居中對齊
.text-start - 靠開始側對齊 (使用邏輯屬性 text-align: start)
.text-end - 靠結束側對齊 (使用邏輯屬性 text-align: end)
.text-xs 到 .text-xxl - 文字大小
.text-primary, .text-secondary 等 - 文字顏色
```

### 邊框與圓角
```
.rounded-sm, .rounded-md, .rounded-lg - 圓角
.rounded-full - 完全圓形
.border - 標準邊框
.border-light - 淺色邊框
.border-s - 開始側邊框 (使用邏輯屬性 border-inline-start)
.border-e - 結束側邊框 (使用邏輯屬性 border-inline-end)
.border-t - 頂部邊框 (使用邏輯屬性 border-block-start)
.border-b - 底部邊框 (使用邏輯屬性 border-block-end)
```

### 尺寸與定位
```
.w-full - 寬度 100% (同時使用 inline-size: 100%)
.h-full - 高度 100% (同時使用 block-size: 100%)
.inline-full - 內聯尺寸 100% (邏輯屬性)
.block-full - 區塊尺寸 100% (邏輯屬性)
.top-0 - 頂部對齊 (使用邏輯屬性 inset-block-start: 0)
.bottom-0 - 底部對齊 (使用邏輯屬性 inset-block-end: 0)
.start-0 - 開始側對齊 (使用邏輯屬性 inset-inline-start: 0)
.end-0 - 結束側對齊 (使用邏輯屬性 inset-inline-end: 0)
```

### 方向控制
```
.rtl - 從右到左方向 (direction: rtl)
.ltr - 從左到右方向 (direction: ltr)
.float-start - 開始側浮動 (使用邏輯屬性 float: inline-start)
.float-end - 結束側浮動 (使用邏輯屬性 float: inline-end)
```

## CSS 邏輯屬性與國際化

專案使用 CSS 邏輯屬性來支援國際化 (i18n)，特別是對從右到左 (RTL) 語言的支援，如阿拉伯語和希伯來語。

### 什麼是 CSS 邏輯屬性？

CSS 邏輯屬性是一種與書寫模式和文字方向無關的屬性，它們使用相對於文字流動方向的術語（如「開始」和「結束」），而非絕對的方向術語（如「左」和「右」）。

### 物理屬性與邏輯屬性對照

| 物理屬性 | 邏輯屬性 | 說明 |
|---------|---------|------|
| `margin-left` | `margin-inline-start` | 內聯起始邊距 |
| `margin-right` | `margin-inline-end` | 內聯結束邊距 |
| `padding-left` | `padding-inline-start` | 內聯起始內距 |
| `padding-right` | `padding-inline-end` | 內聯結束內距 |
| `text-align: left` | `text-align: start` | 文字靠內聯起始對齊 |
| `text-align: right` | `text-align: end` | 文字靠內聯結束對齊 |

### 使用邏輯屬性的優點

1. **自動適應不同書寫方向** - 當 HTML 的 `dir` 屬性為 `rtl` 時，邏輯屬性會自動調整
2. **減少維護成本** - 不需要為 RTL 語言維護單獨的樣式表
3. **提高可讀性** - 使 CSS 與內容流向保持一致，更符合邏輯

### 在元件中使用邏輯屬性

```vue
<template>
  <div class="card">
    <h2 class="card-title">標題</h2>
    <p class="card-content">內容</p>
  </div>
</template>

<style scoped>
.card {
  /* 使用邏輯屬性 */
  padding-inline: var(--spacing-md);
  padding-block: var(--spacing-lg);
  border-inline-start: 4px solid var(--primary-color);
}

.card-title {
  margin-block-end: var(--spacing-sm);
  text-align: start; /* 自動適應 RTL */
}

.card-content {
  padding-inline-start: var(--spacing-md);
  border-inline-start: 2px solid var(--border-color);
}
</style>
```

### 設置文檔方向

若要切換整個文檔的方向，可以在 HTML 根元素上設置 `dir` 屬性：

```html
<!-- 從左到右 (預設) -->
<html dir="ltr">

<!-- 從右到左 -->
<html dir="rtl">
```

也可以在特定元素上設置 `dir` 屬性，只影響該元素及其子元素：

```html
<div dir="rtl">
  <!-- 這裡的內容會從右到左顯示 -->
</div>
```

### 更多詳細資訊

更多關於 CSS 邏輯屬性的詳細使用方式，請參考 [CSS_LOGICAL_PROPS_GUIDE.md](./CSS_LOGICAL_PROPS_GUIDE.md)。

## 最佳實踐

### 1. 優先使用 CSS 變數
任何重複使用的數值（顏色、尺寸、間距等）應定義為 CSS 變數，避免硬編碼值。

### 2. 合理組合功能類別
```html
<div class="flex-center p-3 rounded-md shadow-md">
  <span class="text-primary text-lg">居中的內容</span>
</div>
```

### 3. 元件特定樣式使用 scoped CSS
功能類別適用於常見樣式，但元件特定的複雜樣式應使用 scoped CSS：

```vue
<template>
  <div class="custom-chart flex-center">
    <!-- 圖表內容 -->
  </div>
</template>

<style scoped>
.custom-chart {
  position: relative;
  min-height: 300px;
  border-radius: var(--border-radius-md);
  background-image: linear-gradient(to right, var(--surface-color), var(--hover-color));
}
</style>
```

### 4. 避免過度內聯樣式
不應使用內聯樣式（style 屬性）處理可重用的樣式，應優先使用功能類別或 scoped CSS。

```html
<!-- 不推薦 -->
<div style="display: flex; justify-content: center; margin: 16px;">

<!-- 推薦 -->
<div class="flex-center m-3">
```

### 5. 層級選擇器不超過 3 層
避免過深的 CSS 選擇器，這會增加特異性和複雜性：

```css
/* 不推薦 */
.card .content .header .title span { ... }

/* 推薦 */
.card-title { ... }
```

### 6. 使用邏輯屬性支援國際化
優先使用邏輯屬性而非物理屬性，特別是在處理方向相關的樣式時：

```css
/* 不推薦 */
.element {
  margin-left: var(--spacing-md);
  text-align: left;
}

/* 推薦 */
.element {
  margin-inline-start: var(--spacing-md);
  text-align: start;
}
```

## 主題切換

專案支援淺色/深色主題切換，實現方式是在 body 元素上添加或移除 `.dark-theme` 類別：

```js
// 切換深色主題
document.body.classList.add('dark-theme');

// 切換淺色主題
document.body.classList.remove('dark-theme');

// 檢查當前主題
const isDarkTheme = document.body.classList.contains('dark-theme');
```

所有與主題相關的樣式變化應通過 CSS 變數實現，避免直接硬編碼深色主題樣式。 