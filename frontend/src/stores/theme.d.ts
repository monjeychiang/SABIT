declare module '@/stores/theme' {
  export interface ThemeStore {
    isDarkMode: boolean;
    currentTheme: 'dark' | 'light';
    initTheme: () => void;
    toggleTheme: () => void;
    applyTheme: (isDark: boolean) => void;
    updateCSSVariables: (isDark: boolean) => void;
  }

  export function useThemeStore(): ThemeStore;
} 