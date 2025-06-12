import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'

// 定義 Token 配置介面
export interface TokenConfig {
  accessTokenKey: string;
  refreshTokenKey: string;
  tokenTypeKey: string;
  refreshEndpoint: string;
  refreshThresholdSeconds: number;
  defaultTokenType: string;
  apiBaseUrl: string;
  storage: Storage;
}

// 定義 Token 響應介面
export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  refresh_token_expires_in?: number;
}

/**
 * 整合的 Token 服務
 * 
 * 提供訪問令牌和刷新令牌的管理，自動處理令牌刷新流程，
 * 確保API請求始終使用有效的訪問令牌。
 * 
 * 使用方法:
 * 1. 獲取單例: import { tokenService } from '@/services/token'
 * 2. 登錄後設置令牌: await tokenService.setTokens(accessToken, refreshToken);
 * 3. 發起API請求: await tokenService.fetch('https://api.example.com/data');
 */
export class TokenService {
  private static instance: TokenService | null = null;
  
  // 原 TokenManager 的所有私有屬性
  private config: Required<TokenConfig>;
  private accessToken: string | null;
  private refreshToken: string | null = null; // 不再使用，保留為兼容性
  private tokenType: string;
  private refreshTimerId: number | null;
  private refreshPromise: Promise<boolean> | null;
  private expiresAt: Date | null;
  private refreshTokenExpiresAt: Date | null;
  private refreshCount: number = 0;
  private backendConfig: {
    accessTokenExpireMinutes: number;
    refreshTokenExpireDays: number;
    refreshThresholdSeconds: number;
    refresh_token_expires_in?: number; // 刷新令牌有效期（秒）
    twoFactorExpireMinutes?: number;
    useSecureCookies?: boolean;
    cookieDomain?: string;
    cookieSamesite?: string;
  } = {
    accessTokenExpireMinutes: 1440, // 默認24小時，但會從後端獲取
    refreshTokenExpireDays: 7,      // 默認7天，但會從後端獲取
    refreshThresholdSeconds: 300,   // 默認5分鐘，但會從後端獲取
  };
  private configLoaded: boolean = false;
  private configLoadPromise: Promise<void> | null = null;
  private _isClearing: boolean = false;
  private _isSetting: boolean = false;
  private _isLoggingOut: boolean = false;
  private _useMemoryOnly: boolean = true; // 新增：是否只使用記憶體存儲
  
  /**
   * 私有構造函數，防止直接實例化
   */
  private constructor() {
    // 默認配置
    this.config = {
      accessTokenKey: 'token',
      refreshTokenKey: 'refreshToken',
      tokenTypeKey: 'tokenType',
      refreshEndpoint: '/api/v1/auth/refresh',
      refreshThresholdSeconds: 300, // 提前5分鐘刷新
      defaultTokenType: 'bearer',
      apiBaseUrl: '', // 使用相對路徑，配合 Vite 的代理設置
      storage: localStorage // 默認使用 localStorage
    };
    
    console.log('TokenService 初始化');
    
    // 僅從存儲中恢復 access token 和 token type
    this.accessToken = this._useMemoryOnly ? null : this.config.storage.getItem(this.config.accessTokenKey);
    this.tokenType = this.config.storage.getItem(this.config.tokenTypeKey) || this.config.defaultTokenType;
    
    console.log('從 localStorage 恢復令牌:', {
      hasAccessToken: !!this.accessToken,
      tokenType: this.tokenType
    });
    
    // 嘗試恢復過期時間
    const expiryString = this.config.storage.getItem('tokenExpiry');
    this.expiresAt = expiryString ? new Date(expiryString) : null;
    
    // 恢復 refresh token 過期時間
    const refreshExpiryString = this.config.storage.getItem('refreshTokenExpiry');
    this.refreshTokenExpiresAt = refreshExpiryString ? new Date(refreshExpiryString) : null;
    
    // 恢復刷新次數
    const refreshCountString = this.config.storage.getItem('tokenRefreshCount');
    this.refreshCount = refreshCountString ? parseInt(refreshCountString, 10) : 0;
    
    // 刷新令牌的定時器ID
    this.refreshTimerId = null;
    
    // 正在進行的刷新令牌請求
    this.refreshPromise = null;
    
    // 獲取後端配置
    this.configLoadPromise = this.loadBackendConfig();
    
    // 如果存在令牌，設置自動刷新
    if (this.accessToken && this.expiresAt) {
      this.setupTokenRefresh();
    }
    
    // 監聽身份驗證事件
    this.setupEventListeners();
  }
  
  /**
   * 獲取 TokenService 單例實例
   */
  public static getInstance(): TokenService {
    if (!TokenService.instance) {
      TokenService.instance = new TokenService();
    }
    return TokenService.instance;
  }
  
  /**
   * 設置 TokenService 配置
   */
  public configure(options: Partial<TokenConfig>): void {
    this.config = { ...this.config, ...options };
    console.log('TokenService 配置已更新');
  }
  
  /**
   * 從後端加載認證配置
   */
  private async loadBackendConfig(): Promise<void> {
    if (this.configLoaded) {
      return;
    }
    
    try {
      // 先嘗試從 localStorage 加載配置
      const cachedConfig = this.config.storage.getItem('backendAuthConfig');
      if (cachedConfig) {
        this.backendConfig = { ...this.backendConfig, ...JSON.parse(cachedConfig) };
        console.log('從緩存加載後端配置:', this.backendConfig);
        this.configLoaded = true;
        return;
      }
      
      // 沒有緩存，從後端獲取
      const response = await axios.get('/api/v1/auth/config');
      if (response.data && response.status === 200) {
        this.backendConfig = { ...this.backendConfig, ...response.data };
        // 緩存配置
        this.config.storage.setItem('backendAuthConfig', JSON.stringify(this.backendConfig));
        console.log('從後端加載認證配置:', this.backendConfig);
      }
      
      this.configLoaded = true;
    } catch (error) {
      console.error('加載後端認證配置失敗:', error);
      // 使用默認值
    }
  }
  
  /**
   * 確保配置已加載
   */
  public async ensureConfigLoaded(): Promise<void> {
    if (this.configLoaded) {
      return;
    }
    
    if (this.configLoadPromise) {
      await this.configLoadPromise;
      return;
    }
    
    this.configLoadPromise = this.loadBackendConfig();
    await this.configLoadPromise;
    this.configLoadPromise = null;
  }
  
  /**
   * 重新加載後端配置
   */
  public async reloadBackendConfig(): Promise<void> {
    this.configLoaded = false;
    this.config.storage.removeItem('backendAuthConfig');
    await this.loadBackendConfig();
  }
  
  /**
   * 設置令牌
   */
  public async setTokens(
    accessToken: string,
    refreshToken: string = '', // 不再使用，保留為兼容性
    tokenType: string = this.config.defaultTokenType,
    expiresIn?: number,
    refreshTokenExpiresIn?: number
  ): Promise<boolean> {
    // 防止重複設置
    if (this._isSetting) {
      console.log('令牌設置操作已在進行中，等待之前的操作完成');
      // 等待當前設置操作完成
      await new Promise(resolve => setTimeout(resolve, 100));
      return true;
    }
    
    this._isSetting = true;
    
    // 安全地顯示 token 部分內容的函數
    const maskToken = (token: string | null): string => {
      if (!token) return 'null';
      if (token.length <= 8) return '***' + token.substring(token.length - 3);
      return token.substring(0, 4) + '...' + token.substring(token.length - 4);
    };
    
    console.log(`【TOKEN】開始設置新的 access token: ${maskToken(accessToken)}`);
    
    try {
      // 確保配置已加載
      await this.ensureConfigLoaded();
      
      // 只設置 Access Token
      this.accessToken = accessToken;
      this.tokenType = tokenType;
      
      // 設置 access token 過期時間
      const standardExpiryMinutes = this.backendConfig.accessTokenExpireMinutes;
      const standardExpirySeconds = standardExpiryMinutes * 60;
      
      this.expiresAt = new Date();
      this.expiresAt.setMinutes(this.expiresAt.getMinutes() + standardExpiryMinutes);
      
      console.log(`【TOKEN】設置 Access Token 有效期（${standardExpiryMinutes}分鐘）`, {
        過期時間: this.expiresAt.toLocaleString(), 
        後端提供expiresIn: expiresIn ? `${expiresIn}秒 (${Math.round(expiresIn/60)}分鐘)` : '無'
      });
      
      // 如果不使用記憶體模式，保存令牌到存儲中
      if (!this._useMemoryOnly) {
      // 保存令牌過期時間到 localStorage
      this.config.storage.setItem('tokenExpiry', this.expiresAt.toISOString());
      
        // 根據使用者是否選擇保持登入來決定是否儲存到 localStorage
        const keepLoggedIn = localStorage.getItem('keepLoggedIn') !== 'false'; // 默認為 true
        if (keepLoggedIn) {
          this.config.storage.setItem(this.config.accessTokenKey, accessToken);
          this.config.storage.setItem(this.config.tokenTypeKey, tokenType);
        } else {
          // 不保持登入，清除 localStorage 中的令牌
          this.config.storage.removeItem(this.config.accessTokenKey);
          this.config.storage.removeItem(this.config.tokenTypeKey);
        }
      } else {
        // 記憶體模式：不保存到本地存儲
        this.config.storage.removeItem(this.config.accessTokenKey);
        this.config.storage.removeItem(this.config.tokenTypeKey);
        this.config.storage.removeItem('tokenExpiry');
      }
      
      // 重置刷新次數
      this.refreshCount = 0;
      this.config.storage.setItem('tokenRefreshCount', '0');
      
      // 設置令牌刷新
      this.setupTokenRefresh();
      
      // 分發 token:set 事件
      window.dispatchEvent(new CustomEvent('token:set', { 
        detail: { hasAccessToken: true }
      }));
      
      console.log('【TOKEN】成功完成 token 設置');
      return true;
    } catch (error) {
      console.error('設置令牌失敗:', error);
      return false;
    } finally {
      this._isSetting = false;
    }
  }
  
  /**
   * 檢查令牌是否已過期
   */
  public isTokenExpired(): boolean {
    if (!this.expiresAt) {
      return true;
    }
    return new Date() >= this.expiresAt;
  }
  
  /**
   * 檢查令牌是否即將過期
   */
  public isTokenExpiringSoon(): boolean {
    if (!this.expiresAt) {
      return true;
    }
    
    const now = new Date();
    const thresholdMs = this.config.refreshThresholdSeconds * 1000;
    const expiryTime = this.expiresAt.getTime();
    const timeLeft = expiryTime - now.getTime();
    
    return timeLeft <= thresholdMs;
  }
  
  /**
   * 檢查是否已認證（有有效令牌）
   */
  public isAuthenticated(): boolean {
    return !!this.accessToken && !this.isTokenExpired();
  }
  
  /**
   * 設置令牌刷新定時器
   */
  private setupTokenRefresh(): void {
    // 清除現有定時器
    if (this.refreshTimerId !== null) {
      window.clearTimeout(this.refreshTimerId);
      this.refreshTimerId = null;
    }
    
    if (!this.accessToken || !this.refreshToken || !this.expiresAt) {
      return;
    }
    
    // 計算到過期前閾值的時間
    const now = new Date();
    const expiryTime = this.expiresAt.getTime();
    const thresholdMs = this.config.refreshThresholdSeconds * 1000;
    const refreshTime = expiryTime - thresholdMs;
    let timeUntilRefresh = refreshTime - now.getTime();
    
    // 如果已經過了刷新時間，立即刷新
    if (timeUntilRefresh <= 0) {
      console.log('【TOKEN】令牌已過期或即將過期，立即嘗試刷新');
      this.refreshToken_().catch(e => console.error('自動刷新令牌失敗:', e));
      return;
    }
    
    // 設置定時器在閾值時間刷新令牌
    console.log(`【TOKEN】設置定時刷新，${Math.round(timeUntilRefresh / 1000 / 60)}分鐘後執行`);
    this.refreshTimerId = window.setTimeout(() => {
      console.log('【TOKEN】執行定時令牌刷新');
      this.refreshToken_().catch(e => console.error('定時刷新令牌失敗:', e));
    }, timeUntilRefresh);
  }
  
  /**
   * 刷新令牌
   */
  private async refreshToken_(): Promise<boolean> {
    // 避免重複刷新
    if (this.refreshPromise) {
      console.log('【TOKEN】已有刷新操作進行中，等待其完成');
      return this.refreshPromise;
    }
    
    // 添加全局節流機制
    const MIN_REFRESH_INTERVAL_MS = 2000; // 最小刷新間隔為2秒
    
    // 檢查上次刷新時間
    const lastRefreshTime = parseInt(this.config.storage.getItem('lastTokenRefreshTime') || '0');
    const now = Date.now();
    
    if (now - lastRefreshTime < MIN_REFRESH_INTERVAL_MS) {
      console.log(`【TOKEN】刷新請求被節流，距離上次刷新不足${MIN_REFRESH_INTERVAL_MS/1000}秒`);
      
      // 如果上次刷新成功且距離現在很近，直接返回成功
      const lastRefreshSuccess = this.config.storage.getItem('lastTokenRefreshSuccess') === 'true';
      if (lastRefreshSuccess) {
        console.log('【TOKEN】使用上次刷新的結果（成功）');
        return true;
      }
      
      // 如果上次刷新失敗但時間很近，則等待一段時間後再嘗試
      await new Promise(resolve => setTimeout(resolve, MIN_REFRESH_INTERVAL_MS - (now - lastRefreshTime)));
    }
    
    console.log('【TOKEN】開始刷新令牌');
    
    // 更新最後刷新時間
    this.config.storage.setItem('lastTokenRefreshTime', now.toString());
    this.config.storage.setItem('lastTokenRefreshSuccess', 'false'); // 先標記為失敗，成功後再更新
    
    // 安全地顯示 token 部分內容的函數
    const maskToken = (token: string | null): string => {
      if (!token) return 'null';
      if (token.length <= 8) return '***' + token.substring(token.length - 3);
      return token.substring(0, 4) + '...' + token.substring(token.length - 4);
    };
    
    // 記錄原始 token
    console.log(`【TOKEN】刷新前的 access token: ${maskToken(this.accessToken)}`);
    
    this.refreshPromise = (async () => {
      try {
        // 增加刷新次數
        this.refreshCount++;
        this.config.storage.setItem('tokenRefreshCount', this.refreshCount.toString());
        
        // HTTP-only cookie 會自動發送，不需要明確傳遞 refresh_token
        const response = await axios.post(this.config.refreshEndpoint, {
          keep_logged_in: localStorage.getItem('keepLoggedIn') !== 'false' // 默認為 true
        });
        
        if (response.status === 200 && response.data) {
          const { access_token, token_type, expires_in } = response.data;
          
          // 記錄新的 token
          console.log(`【TOKEN】刷新後獲得的新 access token: ${maskToken(access_token)}`);
          
          // 更新令牌
          this.accessToken = access_token;
          
          // 更新令牌類型
          if (token_type) {
            this.tokenType = token_type;
          }
          
          // 更新過期時間
          const expiryMinutes = this.backendConfig.accessTokenExpireMinutes;
          this.expiresAt = new Date();
          this.expiresAt.setMinutes(this.expiresAt.getMinutes() + expiryMinutes);
          
          // 更新 localStorage
          if (!this._useMemoryOnly) {
          const keepLoggedIn = localStorage.getItem('keepLoggedIn') !== 'false'; // 默認為 true
          if (keepLoggedIn) {
            this.config.storage.setItem(this.config.accessTokenKey, access_token);
            if (token_type) {
              this.config.storage.setItem(this.config.tokenTypeKey, token_type);
          }
          
          // 保存過期時間
          this.config.storage.setItem('tokenExpiry', this.expiresAt.toISOString());
            }
          } else {
            // 記憶體模式：確保不保存到本地存儲
            this.config.storage.removeItem(this.config.accessTokenKey);
            this.config.storage.removeItem(this.config.tokenTypeKey);
            this.config.storage.removeItem('tokenExpiry');
          }
          
          console.log('【TOKEN】令牌刷新成功，設置下次刷新時間');
          
          // 標記本次刷新成功
          this.config.storage.setItem('lastTokenRefreshSuccess', 'true');
          
          // 設置下次刷新
          this.setupTokenRefresh();
          
          // 分發事件
          window.dispatchEvent(new CustomEvent('token:refreshed', { 
            detail: { success: true, count: this.refreshCount }
          }));
          
          return true;
        } else {
          console.error('【TOKEN】刷新令牌失敗，服務器響應非 200');
          // 分發失敗事件
          window.dispatchEvent(new CustomEvent('token:refreshed', { 
            detail: { success: false, error: 'server_error' }
          }));
          return false;
        }
      } catch (error) {
        console.error('【TOKEN】刷新令牌出錯:', error);
        // 如果是 401 錯誤，可能是刷新令牌無效
        if (axios.isAxiosError(error) && error.response?.status === 401) {
          console.log('【TOKEN】刷新令牌無效，需要重新登入');
          this.clearTokens();
          window.dispatchEvent(new Event('auth:logout'));
        }
        
        // 分發失敗事件
        window.dispatchEvent(new CustomEvent('token:refreshed', { 
          detail: { success: false, error: 'refresh_failed' }
        }));
        
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();
    
    return this.refreshPromise;
  }
  
  /**
   * 如果需要，刷新令牌
   */
  public async refreshTokenIfNeeded(): Promise<boolean> {
    if (this.isTokenExpiringSoon()) {
      // 移除對 this.refreshToken 的檢查，因為刷新令牌現在存儲在 HTTP-only cookie 中
      return await this.refreshToken_();
    }
    return true;
  }
  
  /**
   * 清除所有令牌
   */
  public clearTokens(): void {
    if (this._isClearing) {
      return;
    }
    
    this._isClearing = true;
    
    try {
      // 安全地顯示 token 部分內容的函數
      const maskToken = (token: string | null): string => {
        if (!token) return 'null';
        if (token.length <= 8) return '***' + token.substring(token.length - 3);
        return token.substring(0, 4) + '...' + token.substring(token.length - 4);
      };
      
      // 記錄正在清除的 token
      console.log(`【TOKEN】開始清除 token，當前 access token: ${maskToken(this.accessToken)}`);
      
      // 清除內存中的令牌
      this.accessToken = null;
      this.refreshToken = null; // 不再使用，但保持兼容性
      this.expiresAt = null;
      this.refreshTokenExpiresAt = null;
      
      // 清除存儲中的令牌
      this.config.storage.removeItem(this.config.accessTokenKey);
      this.config.storage.removeItem(this.config.tokenTypeKey);
      this.config.storage.removeItem('tokenExpiry');
      this.config.storage.removeItem('refreshTokenExpiry');
      this.config.storage.removeItem('tokenRefreshCount');
      
      // 清除定時器
      if (this.refreshTimerId !== null) {
        window.clearTimeout(this.refreshTimerId);
        this.refreshTimerId = null;
      }
      
      console.log('【TOKEN】所有令牌已清除完成');
      
      // 分發事件，但不使用 token:cleared，避免觸發其他可能導致 API 調用的事件處理程序
      window.dispatchEvent(new CustomEvent('token:state:cleared', { 
        detail: { source: 'clearTokens' }
      }));
    } finally {
      this._isClearing = false;
    }
  }
  
  /**
   * 獲取訪問令牌
   */
  public getAccessToken(): string | null {
    return this.accessToken;
  }
  
  /**
   * 獲取刷新令牌 (已棄用，刷新令牌現在存儲在HTTP-only cookie中)
   */
  public getRefreshToken(): string | null {
    // 返回 null，因為刷新令牌現在存儲在HTTP-only cookie中
    console.warn('試圖獲取刷新令牌，但它現在存儲在HTTP-only cookie中，前端無法存取');
    return null;
  }
  
  /**
   * 獲取令牌類型
   */
  public getTokenType(): string {
    return this.tokenType;
  }
  
  /**
   * 獲取授權頭
   */
  public getAuthHeader(): string | null {
    if (!this.accessToken) {
      return null;
    }
    return `${this.tokenType} ${this.accessToken}`;
  }
  
  /**
   * 為 axios 設置攔截器
   */
  public setupAxiosInterceptors(axiosInstance: AxiosInstance = axios): void {
    // 請求攔截器
    axiosInstance.interceptors.request.use(
      async (config) => {
        // 如果目標是刷新令牌端點，只添加刷新令牌
        if (config.url === this.config.refreshEndpoint) {
          return config;
        }
        
        // 如果已認證，添加令牌並確保其有效
        if (this.isAuthenticated()) {
          // 需要時刷新令牌
          if (this.isTokenExpiringSoon()) {
            await this.refreshTokenIfNeeded();
          }
          
          // 添加授權頭
          if (this.accessToken) {
            config.headers = config.headers || {};
            config.headers['Authorization'] = this.getAuthHeader();
          }
        }
        
        return config;
      },
      (error) => Promise.reject(error)
    );
    
    // 響應攔截器
    axiosInstance.interceptors.response.use(
      (response) => response,
      async (error) => {
        // 如果是 401 錯誤，嘗試刷新令牌並重試
        if (error.response?.status === 401) {
          const originalRequest = error.config;
          
          // 避免循環重試
          if (!originalRequest._retry) {
            originalRequest._retry = true;
            
            // 嘗試刷新令牌
            const refreshed = await this.refreshTokenIfNeeded();
            if (refreshed && this.accessToken) {
              // 更新請求的授權頭
              originalRequest.headers['Authorization'] = this.getAuthHeader();
              return axios(originalRequest);
            }
          }
        }
        
        return Promise.reject(error);
      }
    );
    
    console.log('【TOKEN】已設置 axios 攔截器');
  }
  
  /**
   * 包裝 fetch API 添加授權
   */
  public async fetch(url: string, options: RequestInit = {}): Promise<Response> {
    await this.refreshTokenIfNeeded();
    
    const headers = new Headers(options.headers || {});
    if (this.accessToken) {
      headers.set('Authorization', this.getAuthHeader() as string);
    }
    
    return fetch(url, { ...options, headers });
  }
  
  /**
   * 包裝 axios 添加授權
   */
  public async axiosRequest<T = any>(config: AxiosRequestConfig): Promise<AxiosResponse<T>> {
    await this.refreshTokenIfNeeded();
    
    config.headers = config.headers || {};
    if (this.accessToken) {
      config.headers['Authorization'] = this.getAuthHeader();
    }
    
    return axios.request<T>(config);
  }
  
  /**
   * 獲取令牌狀態
   */
  public getTokenStatus(): {
    isAuthenticated: boolean;
    accessToken: string | null;
    refreshToken: string | null;
    tokenType: string;
    expiresAt: Date | null;
    refreshTokenExpiresAt: Date | null;
    refreshCount: number;
    isExpired: boolean;
    isExpiringSoon: boolean;
  } {
    return {
      isAuthenticated: this.isAuthenticated(),
      accessToken: this.accessToken,
      refreshToken: this.refreshToken,
      tokenType: this.tokenType,
      expiresAt: this.expiresAt,
      refreshTokenExpiresAt: this.refreshTokenExpiresAt,
      refreshCount: this.refreshCount,
      isExpired: this.isTokenExpired(),
      isExpiringSoon: this.isTokenExpiringSoon()
    };
  }
  
  /**
   * 設置事件監聽
   */
  private setupEventListeners(): void {
    // 登出事件
    window.addEventListener('auth:logout', () => {
      if (!this._isLoggingOut) {
        this._isLoggingOut = true;
        // 避免循環調用
        if (!this._isClearing) {
        this.clearTokens();
        }
        this._isLoggingOut = false;
      }
    });
  }
  
  /**
   * 強制更新令牌狀態（用於特殊情況）
   */
  public forceUpdateTokens(
    accessToken: string,
    refreshToken: string,
    tokenType: string = this.config.defaultTokenType
  ): boolean {
    try {
      // 直接更新內部狀態
      this.accessToken = accessToken;
      this.refreshToken = refreshToken;
      this.tokenType = tokenType;
      
      // 保存到 localStorage
      this.config.storage.setItem(this.config.accessTokenKey, accessToken);
      this.config.storage.setItem(this.config.tokenTypeKey, tokenType);
      
      console.log('成功強制更新令牌狀態');
      return true;
    } catch (error) {
      console.error('強制更新令牌狀態失敗:', error);
      return false;
    }
  }
}

// 創建單例實例
export const tokenService = TokenService.getInstance();

// 導出方便獲取單例的函數（向後兼容）
export const getTokenService = (): TokenService => {
  return TokenService.getInstance();
}; 