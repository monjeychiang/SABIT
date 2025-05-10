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
      this.isDarkMode = !this.isDarkMode
      localStorage.setItem('theme', this.currentTheme)
      this.applyTheme()
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
        '--el-color-primary-rgb': '59, 130, 246',
        '--el-color-success-rgb': '16, 185, 129',
        '--el-color-warning-rgb': '245, 158, 11',
        '--el-color-danger-rgb': '239, 68, 68',
        '--el-color-error-rgb': '239, 68, 68',
        '--el-color-info-rgb': '147, 151, 184',

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
        '--primary-color': '#3b82f6',
        '--primary-dark': '#2563eb',
        '--primary-light': '#60a5fa',
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
        '--el-color-primary-rgb': '37, 99, 235',
        '--el-color-success-rgb': '16, 185, 129',
        '--el-color-warning-rgb': '245, 158, 11',
        '--el-color-danger-rgb': '239, 68, 68',
        '--el-color-error-rgb': '239, 68, 68',
        '--el-color-info-rgb': '114, 142, 171',
        
        // 背景颜色
        '--el-bg-color': '#ffffff',
        '--el-bg-color-page': '#f5f7fa',
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
        '--el-mask-color': 'rgba(255, 255, 255, 0.8)',
        '--el-mask-color-extra-light': 'rgba(255, 255, 255, 0.3)',
        
        // 阴影
        '--el-box-shadow': '0 2px 4px rgba(0, 0, 0, 0.12), 0 0 6px rgba(0, 0, 0, 0.04)',
        '--el-box-shadow-light': '0 2px 4px rgba(0, 0, 0, 0.1)',
        '--el-box-shadow-lighter': '0 1px 2px rgba(0, 0, 0, 0.05)',
        '--el-box-shadow-dark': '0 4px 8px rgba(0, 0, 0, 0.2)',
        
        // 禁用状态
        '--el-disabled-bg-color': '#f5f7fa',
        '--el-disabled-text-color': '#c0c4cc',
        '--el-disabled-border-color': '#e4e7ed',
        
        // 覆盖我们自己的CSS变量
        '--primary-color': '#2563eb',
        '--primary-dark': '#1d4ed8',
        '--primary-light': '#3b82f6',
        '--background-color': '#f9fafb',
        '--surface-color': '#ffffff',
        '--card-background': '#ffffff',
        '--text-primary': '#1f2937',
        '--text-secondary': '#4b5563',
        '--text-tertiary': '#6b7280',
        '--border-color': '#e5e7eb',
        '--border-light': '#f3f4f6',
      }
      
      // 应用CSS变量
      const cssVars = isDark ? darkThemeVars : lightThemeVars
      for (const [key, value] of Object.entries(cssVars)) {
        document.documentElement.style.setProperty(key, value)
      }
    }
  }
}) 