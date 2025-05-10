declare module '@/stores/theme' {
  export interface ThemeStore {
    isDarkMode: boolean;
    currentTheme: 'dark' | 'light';
    initTheme: () => void;
    toggleTheme: () => void;
    applyTheme: () => void;
    updateCSSVariables: () => void;
  }

  export function useThemeStore(): ThemeStore;
} 