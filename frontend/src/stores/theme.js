import { defineStore } from 'pinia'

export const useThemeStore = defineStore('theme', {
  state: () => ({
    isDarkMode: false
  }),
  
  getters: {
    currentTheme: (state) => state.isDarkMode ? 'dark' : 'light'
  },
  
  actions: {
    initTheme() {
      // 获取存储的主题
      const savedTheme = localStorage.getItem('theme')
      
      if (savedTheme === 'dark') {
        this.isDarkMode = true
      } else if (savedTheme === 'light') {
        this.isDarkMode = false
      } else {
        // 如果没有保存的主题，检查系统偏好
        const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches
        this.isDarkMode = prefersDarkMode
      }
      
      // 应用主题
      this.applyTheme()
      
      // 监听系统主题变化
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (localStorage.getItem('theme') === null) {
          this.isDarkMode = e.matches
          this.applyTheme()
        }
      })
    },
    
    toggleTheme() {
      // 創建過渡覆蓋層
      const transitionOverlay = document.createElement('div');
      transitionOverlay.className = 'theme-transition-overlay';
      document.body.appendChild(transitionOverlay);
      
      // 觸發覆蓋層動畫 - 延遲讓DOM更新
      setTimeout(() => {
        transitionOverlay.style.opacity = '1';
        
        // 在覆蓋層完全不透明後切換主題
        setTimeout(() => {
          // 實際主題切換邏輯
          this.isDarkMode = !this.isDarkMode
          localStorage.setItem('theme', this.currentTheme)
          this.applyTheme()
          
          // 主題變更後淡出覆蓋層
          setTimeout(() => {
            transitionOverlay.style.opacity = '0';
            
            // 移除覆蓋層
            setTimeout(() => {
              if (document.body.contains(transitionOverlay)) {
                document.body.removeChild(transitionOverlay);
              }
            }, 300);
          }, 50);
        }, 300);
      }, 10);
    },
    
    applyTheme() {
      // 应用到body类
      if (this.isDarkMode) {
        document.body.classList.add('dark-theme')
        document.documentElement.classList.add('dark')
      } else {
        document.body.classList.remove('dark-theme')
        document.documentElement.classList.remove('dark')
      }
      
      // 保存到localStorage
      localStorage.setItem('theme', this.currentTheme)
      
      // 更新CSS变量
      this.updateCSSVariables()
    },
    
    updateCSSVariables() {
      const isDark = this.isDarkMode
      
      // 定义深色和浅色主题的CSS变量
      const darkThemeVars = {
        // 基础颜色
        '--el-color-white': '#ffffff',
        '--el-color-black': '#000000',
        '--el-color-primary-rgb': '32, 32, 32',  // 改為深灰色
        '--el-color-success-rgb': '16, 185, 129',
        '--el-color-warning-rgb': '245, 158, 11',
        '--el-color-danger-rgb': '239, 68, 68',
        '--el-color-error-rgb': '239, 68, 68',
        '--el-color-info-rgb': '128, 128, 128',  // 改為中灰色

        // 背景颜色
        '--el-bg-color': '#111827',
        '--el-bg-color-page': '#0d1117',
        '--el-bg-color-overlay': '#1f2937',
        
        // 文本颜色
        '--el-text-color-primary': '#e0e0e0',
        '--el-text-color-regular': '#b0b0b0',
        '--el-text-color-secondary': '#909090',
        '--el-text-color-placeholder': '#606060',
        '--el-text-color-disabled': '#505050',
        
        // 边框颜色
        '--el-border-color': '#303030',
        '--el-border-color-light': '#404040',
        '--el-border-color-lighter': '#505050',
        '--el-border-color-dark': '#252525',
        '--el-border-color-hover': '#505050',
        
        // 填充颜色
        '--el-fill-color': '#202020',
        '--el-fill-color-light': '#262626',
        '--el-fill-color-lighter': '#303030',
        '--el-fill-color-dark': '#1a1a1a',
        '--el-fill-color-darker': '#141414',
        '--el-fill-color-blank': '#111827',
        
        // 特殊颜色
        '--el-mask-color': 'rgba(0, 0, 0, 0.8)',
        '--el-mask-color-extra-light': 'rgba(0, 0, 0, 0.3)',
        
        // 阴影
        '--el-box-shadow': '0 2px 8px rgba(0, 0, 0, 0.3)',
        '--el-box-shadow-light': '0 1px 4px rgba(0, 0, 0, 0.2)',
        '--el-box-shadow-lighter': '0 1px 2px rgba(0, 0, 0, 0.15)',
        '--el-box-shadow-dark': '0 4px 12px rgba(0, 0, 0, 0.4)',
        
        // 禁用状态
        '--el-disabled-bg-color': '#1d1d1d',
        '--el-disabled-text-color': '#606060',
        '--el-disabled-border-color': '#303030',
        
        // 覆盖我们自己的CSS变量
        '--primary-color': '#444444',  // 改為深灰色
        '--primary-dark': '#222222',   // 改為更深的灰色
        '--primary-light': '#666666',  // 改為較淺的灰色
        '--background-color': '#111827',
        '--surface-color': '#1f2937',
        '--card-background': '#1f2937',
        '--text-primary': '#f9fafb',
        '--text-secondary': '#d1d5db',
        '--text-tertiary': '#9ca3af',
        '--border-color': '#374151',
        '--border-light': '#1f2937',
      }
      
      const lightThemeVars = {
        // 基础颜色
        '--el-color-white': '#ffffff',
        '--el-color-black': '#000000',
        '--el-color-primary-rgb': '24, 144, 255',
        '--el-color-success-rgb': '82, 196, 26',
        '--el-color-warning-rgb': '250, 173, 20',
        '--el-color-danger-rgb': '245, 34, 45',
        '--el-color-error-rgb': '245, 34, 45',
        '--el-color-info-rgb': '144, 147, 153',

        // 背景颜色
        '--el-bg-color': '#ffffff',
        '--el-bg-color-page': '#f2f3f5',
        '--el-bg-color-overlay': '#ffffff',
        
        // 文本颜色
        '--el-text-color-primary': '#303133',
        '--el-text-color-regular': '#606266',
        '--el-text-color-secondary': '#909399',
        '--el-text-color-placeholder': '#a8abb2',
        '--el-text-color-disabled': '#c0c4cc',
        
        // 边框颜色
        '--el-border-color': '#dcdfe6',
        '--el-border-color-light': '#e4e7ed',
        '--el-border-color-lighter': '#ebeef5',
        '--el-border-color-dark': '#d4d7de',
        '--el-border-color-hover': '#c0c4cc',
        
        // 填充颜色
        '--el-fill-color': '#f0f2f5',
        '--el-fill-color-light': '#f5f7fa',
        '--el-fill-color-lighter': '#fafafa',
        '--el-fill-color-dark': '#ebedf0',
        '--el-fill-color-darker': '#e6e8eb',
        '--el-fill-color-blank': '#ffffff',
        
        // 特殊颜色
        '--el-mask-color': 'rgba(0, 0, 0, 0.5)',
        '--el-mask-color-extra-light': 'rgba(0, 0, 0, 0.05)',
        
        // 阴影
        '--el-box-shadow': '0 2px 12px 0 rgba(0, 0, 0, 0.1)',
        '--el-box-shadow-light': '0 2px 8px 0 rgba(0, 0, 0, 0.06)',
        '--el-box-shadow-lighter': '0 1px 6px 0 rgba(0, 0, 0, 0.05)',
        '--el-box-shadow-dark': '0 4px 16px 0 rgba(0, 0, 0, 0.15)',
        
        // 禁用状态
        '--el-disabled-bg-color': '#f5f7fa',
        '--el-disabled-text-color': '#c0c4cc',
        '--el-disabled-border-color': '#e4e7ed',
        
        // 覆盖我们自己的CSS变量
        '--primary-color': '#333333',  // 改為灰色
        '--primary-dark': '#111111',   // 改為黑色
        '--primary-light': '#666666',  // 改為淺灰色
        '--background-color': '#f9fafb',
        '--surface-color': '#ffffff',
        '--card-background': '#ffffff',
        '--text-primary': '#1f2937',
        '--text-secondary': '#4b5563',
        '--text-tertiary': '#6b7280',
        '--border-color': '#e5e7eb',
        '--border-light': '#f3f4f6',
      }
      
      // 应用CSS变量 - 改用一次性設置所有變量的方式
      const cssVars = isDark ? darkThemeVars : lightThemeVars
      
      // 批量設置，減少重排和重繪的次數
      requestAnimationFrame(() => {
        for (const [key, value] of Object.entries(cssVars)) {
          document.documentElement.style.setProperty(key, value)
        }
      })
    }
  }
}) 