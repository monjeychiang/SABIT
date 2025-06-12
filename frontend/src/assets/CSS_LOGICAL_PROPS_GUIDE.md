# CSS 邏輯屬性使用指南

## 什麼是 CSS 邏輯屬性？

CSS 邏輯屬性是一種與書寫模式和文字方向無關的屬性，它們使用相對於文字流動方向的術語（如「開始」和「結束」），而非絕對的方向術語（如「左」和「右」）。

## 為什麼要使用邏輯屬性？

- **國際化支援** - 自動適應從右到左(RTL)的語言，如阿拉伯語、希伯來語等
- **減少維護成本** - 不需要為不同書寫方向維護不同的 CSS 規則
- **提高可讀性** - 使 CSS 與內容流向保持一致，更符合邏輯

## 物理屬性與邏輯屬性對照表

| 物理屬性 | 邏輯屬性 | 說明 |
|---------|---------|------|
| `width` | `inline-size` | 內聯方向的尺寸 |
| `height` | `block-size` | 區塊方向的尺寸 |
| `margin-left` | `margin-inline-start` | 內聯起始邊距 |
| `margin-right` | `margin-inline-end` | 內聯結束邊距 |
| `margin-top` | `margin-block-start` | 區塊起始邊距 |
| `margin-bottom` | `margin-block-end` | 區塊結束邊距 |
| `padding-left` | `padding-inline-start` | 內聯起始內距 |
| `padding-right` | `padding-inline-end` | 內聯結束內距 |
| `padding-top` | `padding-block-start` | 區塊起始內距 |
| `padding-bottom` | `padding-block-end` | 區塊結束內距 |
| `border-left` | `border-inline-start` | 內聯起始邊框 |
| `border-right` | `border-inline-end` | 內聯結束邊框 |
| `border-top` | `border-block-start` | 區塊起始邊框 |
| `border-bottom` | `border-block-end` | 區塊結束邊框 |
| `text-align: left` | `text-align: start` | 文字靠內聯起始對齊 |
| `text-align: right` | `text-align: end` | 文字靠內聯結束對齊 |

## 簡寫屬性

邏輯屬性也支援簡寫形式：

```css
/* 設置所有內聯方向的邊距 (左右或右左，取決於書寫方向) */
margin-inline: 1rem;

/* 設置所有區塊方向的邊距 (上下) */
margin-block: 1rem;

/* 分別設置內聯起始和結束的邊距 */
margin-inline: 1rem 2rem; /* start end */

/* 分別設置區塊起始和結束的邊距 */
margin-block: 1rem 2rem; /* start end */

/* 內距也有相同的簡寫方式 */
padding-inline: 1rem;
padding-block: 1rem;
```

## 使用範例

### 基本用法

```css
.card {
  /* 使用邏輯屬性 */
  margin-block: 1rem;
  padding-inline: 1.5rem;
  border-inline-start: 4px solid var(--primary-color);
  text-align: start;
}
```

### 在 RTL 模式下的自動適應

當 HTML 或父元素設置了 `dir="rtl"` 時，邏輯屬性會自動調整：

```html
<!-- LTR 模式 (預設) -->
<div class="card">
  <!-- 內容會靠左對齊，左側有邊框 -->
</div>

<!-- RTL 模式 -->
<div dir="rtl" class="card">
  <!-- 內容會靠右對齊，右側有邊框 -->
</div>
```

## 瀏覽器支援

大多數現代瀏覽器都支援 CSS 邏輯屬性。對於需要支援較舊瀏覽器的情況，可以考慮使用 PostCSS 插件進行轉換，或提供物理屬性作為備用：

```css
.element {
  /* 備用物理屬性 */
  padding-left: 1rem;
  padding-right: 2rem;
  /* 邏輯屬性 */
  padding-inline-start: 1rem;
  padding-inline-end: 2rem;
}
```

## 在我們的專案中使用邏輯屬性

1. 所有新開發的元件應優先使用邏輯屬性
2. 現有元件在進行修改時，應逐步替換為邏輯屬性
3. 功能性 CSS 類別系統已更新，提供了基於邏輯屬性的類別

## 設置文檔方向

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