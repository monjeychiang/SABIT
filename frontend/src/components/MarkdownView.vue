<template>
  <div class="markdown-view">
    <div class="markdown-content" v-html="renderedContent"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';

const props = defineProps({
  content: {
    type: String,
    required: true
  }
});

const emit = defineEmits(['code-copy']);

// 配置markdown解析器
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    let language = lang || 'text';
    let highlighted;
    
    try {
      if (lang && hljs.getLanguage(lang)) {
        highlighted = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value;
      } else {
        highlighted = md.utils.escapeHtml(str);
        language = 'text';
      }
    } catch (e) {
      highlighted = md.utils.escapeHtml(str);
      language = 'text';
    }
    
    // 生成带有复制按钮的代码块
    return `<pre class="code-block">
              <div class="code-header">
                <span class="code-language">${language}</span>
                <button class="copy-code-button" data-code="${encodeURIComponent(str)}">
                  <span class="copy-icon">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                  </span>
                  <span class="button-text">复制</span>
                </button>
              </div>
              <code class="${language}">${highlighted}</code>
            </pre>`;
  }
});

// 渲染后的Markdown内容
const renderedContent = computed(() => {
  return md.render(props.content || '');
});

// 复制代码功能
const handleCodeCopy = (event) => {
  const target = event.target.closest('.copy-code-button');
  if (!target) return;
  
  const code = decodeURIComponent(target.dataset.code);
  navigator.clipboard.writeText(code)
    .then(() => {
      // 复制成功，更新按钮状态
      const originalText = target.querySelector('.button-text').textContent;
      target.querySelector('.button-text').textContent = '已复制!';
      target.classList.add('copied');
      
      // 发出复制事件
      emit('code-copy', code);
      
      // 2秒后恢复原始文本
      setTimeout(() => {
        if (target.querySelector('.button-text')) {
          target.querySelector('.button-text').textContent = originalText;
          target.classList.remove('copied');
        }
      }, 2000);
    })
    .catch(err => {
      console.error('复制失败:', err);
    });
};

// 组件挂载后添加事件监听
onMounted(() => {
  document.addEventListener('click', handleCodeCopy);
});

// 组件卸载前移除事件监听
onUnmounted(() => {
  document.removeEventListener('click', handleCodeCopy);
});
</script>

<style scoped>
.markdown-view {
  width: 100%;
}

.markdown-content {
  line-height: 1.6;
}

/* 确保v-html内容正确样式化 */
:deep(p) {
  margin: 0.8em 0;
}

:deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
  margin-top: 1.6em;
  margin-bottom: 0.8em;
  font-weight: 600;
  line-height: 1.25;
}

:deep(h1) {
  font-size: 1.8em;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.3em;
}

:deep(h2) {
  font-size: 1.5em;
  border-bottom: 1px solid #e2e8f0;
  padding-bottom: 0.3em;
}

:deep(h3) {
  font-size: 1.25em;
}

:deep(h4) {
  font-size: 1em;
}

:deep(h5) {
  font-size: 0.875em;
}

:deep(h6) {
  font-size: 0.85em;
  color: #64748b;
}

/* 链接样式 */
:deep(a) {
  color: #444444;
  text-decoration: none;
  font-weight: 500;
  transition: all 0.2s ease;
  border-bottom: 1px solid rgba(68, 68, 68, 0.3);
}

:deep(a:hover) {
  color: #333333;
  border-bottom-color: #333333;
}

/* 图片样式 */
:deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 1em 0;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* 引用块样式 */
:deep(blockquote) {
  border-left: 4px solid #444444;
  margin: 1em 0;
  padding: 0.5em 1em;
  background-color: #f8fafc;
  border-radius: 0 4px 4px 0;
  color: #475569;
}

/* 列表样式 */
:deep(ul), :deep(ol) {
  padding-left: 2em;
  margin: 1em 0;
}

:deep(li) {
  margin: 0.5em 0;
}

/* 表格样式 */
:deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 0.9em;
}

:deep(th), :deep(td) {
  border: 1px solid #e2e8f0;
  padding: 0.5em 0.75em;
  text-align: left;
}

:deep(th) {
  background-color: #f8fafc;
  font-weight: 600;
}

:deep(tr:nth-child(even)) {
  background-color: #f8fafc;
}

/* 代码块样式 */
:deep(.code-block) {
  margin: 1.2em 0;
  border-radius: 8px;
  overflow: hidden;
  background-color: #1e293b;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

:deep(.code-header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5em 1em;
  background-color: #0f172a;
  color: #94a3b8;
  font-size: 0.9em;
}

:deep(.code-language) {
  font-size: 0.8em;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

:deep(.copy-code-button) {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0.25em 0.75em;
  background-color: rgba(255, 255, 255, 0.1);
  border: none;
  border-radius: 4px;
  color: #e2e8f0;
  font-size: 0.8em;
  cursor: pointer;
  transition: all 0.2s ease;
}

:deep(.copy-code-button:hover) {
  background-color: rgba(255, 255, 255, 0.2);
}

:deep(.copy-code-button.copied) {
  background-color: #10b981;
  color: white;
}

:deep(.feather) {
  width: 14px;
  height: 14px;
}

:deep(code) {
  display: block;
  padding: 1em;
  overflow-x: auto;
  font-family: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 0.9em;
  line-height: 1.5;
}

/* 内联代码样式 */
:deep(:not(pre) > code) {
  background-color: #f1f5f9;
  color: #be185d;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Menlo', monospace;
  font-size: 0.9em;
}

/* 暗黑模式 */
@media (prefers-color-scheme: dark) {
  :deep(h1), :deep(h2), :deep(h3), :deep(h4), :deep(h5), :deep(h6) {
    color: #e2e8f0;
  }

  :deep(h1), :deep(h2) {
    border-bottom-color: #334155;
  }

  :deep(h6) {
    color: #94a3b8;
  }

  :deep(a) {
    color: #666666;
    border-bottom-color: rgba(102, 102, 102, 0.3);
  }

  :deep(a:hover) {
    color: #999999;
    border-bottom-color: #999999;
  }

  :deep(blockquote) {
    background-color: #1e293b;
    border-left-color: #666666;
    color: #e2e8f0;
  }

  :deep(th), :deep(td) {
    border-color: #334155;
  }

  :deep(th) {
    background-color: #1e293b;
  }

  :deep(tr:nth-child(even)) {
    background-color: #1e293b;
  }

  :deep(:not(pre) > code) {
    background-color: #334155;
    color: #f9a8d4;
  }
}

/* 响应式样式 */
@media screen and (max-width: 768px) {
  :deep(h1) {
    font-size: 1.6em;
  }

  :deep(h2) {
    font-size: 1.4em;
  }

  :deep(h3) {
    font-size: 1.2em;
  }

  :deep(pre) {
    font-size: 0.85em;
  }
}
</style> 