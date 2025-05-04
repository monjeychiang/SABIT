export interface TokenManagerConfig {
  accessTokenKey?: string;
  refreshTokenKey?: string;
  tokenTypeKey?: string;
  refreshEndpoint?: string;
  refreshThresholdSeconds?: number;
  defaultTokenType?: string;
  apiBaseUrl?: string;
  storage?: Storage;
}

export interface TokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  refresh_token_expires_in?: number;
}

/**
 * 令牌管理器
 * 
 * 提供訪問令牌和刷新令牌的管理，自動處理令牌刷新流程，
 * 確保API請求始終使用有效的訪問令牌。
 * 
 * 使用方法:
 * 1. 通过TokenService获取实例: import { getTokenManager } from '@/services/tokenService'
 * 2. 登錄後設置令牌: tokenManager.setTokens(accessToken, refreshToken);
 * 3. 發起API請求: await tokenManager.fetch('https://api.example.com/data');
 */
export class TokenManager {
  private config: Required<TokenManagerConfig>;
  private accessToken: string | null;
  private refreshToken: string | null;
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

  /**
   * 構造函數
   * @param {TokenManagerConfig} options - 配置選項
   */
  constructor(options: TokenManagerConfig = {}) {
    // 默認配置
    this.config = {
      accessTokenKey: 'token',
      refreshTokenKey: 'refreshToken',
      tokenTypeKey: 'tokenType',
      refreshEndpoint: '/api/v1/auth/refresh',
      refreshThresholdSeconds: 300, // 提前5分鐘刷新
      defaultTokenType: 'bearer',
      apiBaseUrl: '', // 使用相對路徑，配合 Vite 的代理設置
      storage: localStorage, // 默認使用 localStorage
      ...options
    };
    
    console.log('TokenManager初始化');
    console.log('使用配置:', {
      accessTokenKey: this.config.accessTokenKey,
      refreshTokenKey: this.config.refreshTokenKey,
      tokenTypeKey: this.config.tokenTypeKey,
      refreshEndpoint: this.config.refreshEndpoint
    });
    
    // 從存儲中恢復令牌
    this.accessToken = this.config.storage.getItem(this.config.accessTokenKey);
    this.refreshToken = this.config.storage.getItem(this.config.refreshTokenKey);
    this.tokenType = this.config.storage.getItem(this.config.tokenTypeKey) || this.config.defaultTokenType;
    
    console.log('从localStorage恢复令牌:', {
      hasAccessToken: !!this.accessToken,
      hasRefreshToken: !!this.refreshToken,
      accessToken前10位: this.accessToken ? this.accessToken.substring(0, 10) + '...' : '无',
      refreshToken前10位: this.refreshToken ? this.refreshToken.substring(0, 10) + '...' : '无'
    });
    
    // 嘗試恢復過期時間
    const expiryString = this.config.storage.getItem('tokenExpiry');
    this.expiresAt = expiryString ? new Date(expiryString) : null;
    
    // 恢复refresh token过期时间
    const refreshExpiryString = this.config.storage.getItem('refreshTokenExpiry');
    this.refreshTokenExpiresAt = refreshExpiryString ? new Date(refreshExpiryString) : null;
    
    // 恢复刷新次数
    const refreshCountString = this.config.storage.getItem('tokenRefreshCount');
    this.refreshCount = refreshCountString ? parseInt(refreshCountString, 10) : 0;
    
    // 刷新令牌的定時器ID
    this.refreshTimerId = null;
    
    // 正在進行的刷新令牌請求
    this.refreshPromise = null;
    
    // 獲取後端配置
    this.configLoadPromise = this.loadBackendConfig();
    
    // 如果存在令牌，設置自動刷新
    if (this.accessToken && this.refreshToken && this.expiresAt) {
      this.setupTokenRefresh();
    }
    
    // 監聽身份驗證事件
    this.setupEventListeners();
  }
  
  /**
   * 從後端獲取配置，如令牌有效期等
   */
  private async loadBackendConfig(): Promise<void> {
    if (this.configLoaded) {
      return;
    }
    
    try {
      // 先檢查緩存
      const cachedConfig = this.config.storage.getItem('backendAuthConfig');
      if (cachedConfig) {
        try {
          const parsedConfig = JSON.parse(cachedConfig);
          const cacheTime = new Date(parsedConfig.cacheTime);
          // 如果緩存不超過1小時，使用緩存值
          if (new Date().getTime() - cacheTime.getTime() < 60 * 60 * 1000) {
            this.backendConfig = {
              accessTokenExpireMinutes: parsedConfig.accessTokenExpireMinutes || 1440,
              refreshTokenExpireDays: parsedConfig.refreshTokenExpireDays || 7,
              refreshThresholdSeconds: parsedConfig.refreshThresholdSeconds || 300,
              twoFactorExpireMinutes: parsedConfig.twoFactorExpireMinutes,
              useSecureCookies: parsedConfig.useSecureCookies,
              cookieDomain: parsedConfig.cookieDomain,
              cookieSamesite: parsedConfig.cookieSamesite
            };
            console.log('【TOKEN】從緩存加載後端配置', this.backendConfig);
            this.configLoaded = true;
            return;
          }
        } catch (e) {
          console.warn('解析緩存的後端配置失敗', e);
        }
      }

      // 從後端API獲取配置
      const response = await fetch(`${this.config.apiBaseUrl}/api/v1/auth/config`);
      if (response.ok) {
        const data = await response.json();
        this.backendConfig = {
          accessTokenExpireMinutes: data.access_token_expire_minutes || 1440,
          refreshTokenExpireDays: data.refresh_token_expire_days || 7,
          refreshThresholdSeconds: data.refresh_threshold_seconds || 300,
          twoFactorExpireMinutes: data.two_factor_expire_minutes,
          useSecureCookies: data.use_secure_cookies,
          cookieDomain: data.cookie_domain,
          cookieSamesite: data.cookie_samesite
        };
        
        // 緩存配置
        this.config.storage.setItem('backendAuthConfig', JSON.stringify({
          ...this.backendConfig,
          cacheTime: new Date().toISOString()
        }));
        
        console.log('【TOKEN】從API加載後端配置', this.backendConfig);
      } else {
        console.warn('獲取後端配置失敗，使用默認值', response.status);
      }
    } catch (error) {
      console.error('加載後端配置錯誤，使用默認值', error);
    } finally {
      this.configLoaded = true;
      this.configLoadPromise = null;
    }
  }
  
  /**
   * 確保配置已加載
   * 這個方法可以在需要使用配置前調用，確保配置已經從後端加載
   */
  public async ensureConfigLoaded(): Promise<void> {
    if (this.configLoaded) {
      return;
    }
    
    if (this.configLoadPromise) {
      await this.configLoadPromise;
    } else {
      await this.loadBackendConfig();
    }
  }
  
  /**
   * 獲取當前的後端配置
   * 如果配置尚未加載，會返回默認值
   */
  public getBackendConfig(): {
    accessTokenExpireMinutes: number;
    refreshTokenExpireDays: number;
    refreshThresholdSeconds: number;
    twoFactorExpireMinutes?: number;
    useSecureCookies?: boolean;
    cookieDomain?: string;
    cookieSamesite?: string;
  } {
    return { ...this.backendConfig };
  }
  
  /**
   * 重新加載後端配置
   * 強制從後端重新獲取配置，忽略緩存
   */
  public async reloadBackendConfig(): Promise<void> {
    this.configLoaded = false;
    this.config.storage.removeItem('backendAuthConfig');
    await this.loadBackendConfig();
  }
  
  /**
   * 設置事件監聽器
   */
  private setupEventListeners(): void {
    // 移除重复的事件监听，让登出流程更清晰
    // 监听令牌失效事件
    window.addEventListener('auth:token-refresh-failed', () => {
      this.clearTokens();
      // 發送需要登入的事件
      window.dispatchEvent(new CustomEvent('show-login-modal'));
    });
  }
  
  /**
   * 設置令牌
   */
  public async setTokens(
    accessToken: string,
    refreshToken: string,
    tokenType: string = this.config.defaultTokenType,
    expiresIn?: number,
    refreshTokenExpiresIn?: number
  ): Promise<boolean> {
    // 防止重复设置
    if (this._isSetting) {
      console.log('令牌设置操作已在进行中，等待之前的操作完成');
      // 等待当前设置操作完成
      await new Promise(resolve => setTimeout(resolve, 100));
      return true;
    }
    
    this._isSetting = true;
    
    try {
    // 確保配置已加載
    await this.ensureConfigLoaded();
    
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    this.tokenType = tokenType;
    
    // 從localStorage檢查是否有keepLoggedIn
    const keepLoggedIn = this.config.storage.getItem('keepLoggedIn') === 'true';
    
    // 確保access token始終使用標準過期時間
    const standardExpiryMinutes = this.backendConfig.accessTokenExpireMinutes;
    const standardExpirySeconds = standardExpiryMinutes * 60;
    
    // 設置access token過期時間 - 統一使用標準設置
      this.expiresAt = new Date();
    this.expiresAt.setMinutes(this.expiresAt.getMinutes() + standardExpiryMinutes);
    
    console.log(`【TOKEN】設置標準Access Token有效期（${standardExpiryMinutes}分鐘）`, {
        過期時間: this.expiresAt.toLocaleString(), 
      後端提供expiresIn: expiresIn ? `${expiresIn}秒 (${Math.round(expiresIn/60)}分鐘)` : '無',
      保持登入: keepLoggedIn ? '是' : '否'
    });
    
    // 保存令牌過期時間到localStorage
      this.config.storage.setItem('tokenExpiry', this.expiresAt.toISOString());
      
    // 設置refresh token過期時間
      if (keepLoggedIn) {
      // 優先使用後端提供的refreshTokenExpiresIn
      if (refreshTokenExpiresIn) {
        this.refreshTokenExpiresAt = new Date();
        this.refreshTokenExpiresAt.setSeconds(this.refreshTokenExpiresAt.getSeconds() + refreshTokenExpiresIn);
        
        console.log(`【TOKEN】使用後端提供的Refresh Token有效期（${Math.round(refreshTokenExpiresIn/86400)}天）`, {
          refresh過期時間: this.refreshTokenExpiresAt.toLocaleString(),
          指定秒數: refreshTokenExpiresIn,
          指定天數: Math.round(refreshTokenExpiresIn/86400)
        });
      } else {
        // 使用默認的長期有效期（後端配置的天數）
        this.refreshTokenExpiresAt = new Date();
        this.refreshTokenExpiresAt.setDate(this.refreshTokenExpiresAt.getDate() + this.backendConfig.refreshTokenExpireDays);
        
        console.log(`【TOKEN】用戶已選擇保持登入，使用默認Refresh Token長期有效期（${this.backendConfig.refreshTokenExpireDays}天）`, {
          refresh過期時間: this.refreshTokenExpiresAt.toLocaleString()
        });
      }
      
      this.config.storage.setItem('refreshTokenExpiry', this.refreshTokenExpiresAt.toISOString());
      } else {
      // 非保持登入状态，優先使用後端提供的refreshTokenExpiresIn
      if (refreshTokenExpiresIn && refreshTokenExpiresIn <= standardExpirySeconds) {
        this.refreshTokenExpiresAt = new Date();
        this.refreshTokenExpiresAt.setSeconds(this.refreshTokenExpiresAt.getSeconds() + refreshTokenExpiresIn);
        
        console.log(`【TOKEN】使用後端提供的Refresh Token標準有效期`, {
          refresh過期時間: this.refreshTokenExpiresAt.toLocaleString(),
          指定秒數: refreshTokenExpiresIn
        });
      } else {
        // 與access token同時過期
        this.refreshTokenExpiresAt = new Date(this.expiresAt.getTime());
        
        console.log(`【TOKEN】用戶未選擇保持登入，refresh token與access token同時過期`, {
          refresh過期時間: this.refreshTokenExpiresAt.toLocaleString()
        });
      }
      
      this.config.storage.setItem('refreshTokenExpiry', this.refreshTokenExpiresAt.toISOString());
    }
    
    // 重置刷新计数
    this.refreshCount = 0;
    this.config.storage.setItem('tokenRefreshCount', '0');
    
    // 存儲令牌
    this.config.storage.setItem(this.config.accessTokenKey, accessToken);
    this.config.storage.setItem(this.config.refreshTokenKey, refreshToken);
    this.config.storage.setItem(this.config.tokenTypeKey, tokenType);
    
    // 設置自動刷新
    this.setupTokenRefresh();
    
      // 發送單一的令牌更新事件
    window.dispatchEvent(new CustomEvent('auth:tokens-updated', {
      detail: { 
        accessToken, 
        refreshToken, 
        tokenType, 
        expiresIn: standardExpirySeconds,
        refreshTokenExpiresIn: refreshTokenExpiresIn || (keepLoggedIn ? this.backendConfig.refreshTokenExpireDays * 86400 : standardExpirySeconds)
      }
    }));
    
    return true;
    } finally {
      // 操作完成后重置标志位
      setTimeout(() => {
        this._isSetting = false;
      }, 100);
    }
  }
  
  /**
   * 清除令牌
   */
  public clearTokens(): boolean {
    // 防止短时间内重复调用
    if (this._isClearing) {
      console.log('令牌清除操作已在进行中，忽略重复调用');
      return false;
    }
    
    this._isClearing = true;
    
    try {
    const now = new Date();
    console.log('======【TOKEN清除開始】======');
    console.log(`清除開始時間: ${now.toLocaleString()} (${now.toISOString()})`);
    console.log(`當前令牌狀態:`, {
      有訪問令牌: !!this.accessToken,
      有刷新令牌: !!this.refreshToken,
      access過期時間: this.expiresAt ? this.expiresAt.toLocaleString() : '未設置',
      refresh過期時間: this.refreshTokenExpiresAt ? this.refreshTokenExpiresAt.toLocaleString() : '未設置',
      已過期: this.isTokenExpired() ? '是' : '否',
      刷新次數: this.refreshCount
    });
    
    this.accessToken = null;
    this.refreshToken = null;
    this.expiresAt = null;
    this.refreshTokenExpiresAt = null;
    this.refreshCount = 0;
    
    // 從存儲中移除令牌
    console.log('從存儲中移除令牌項目');
    this.config.storage.removeItem(this.config.accessTokenKey);
    this.config.storage.removeItem(this.config.refreshTokenKey);
    this.config.storage.removeItem(this.config.tokenTypeKey);
    this.config.storage.removeItem('tokenExpiry');
    this.config.storage.removeItem('refreshTokenExpiry');
    this.config.storage.removeItem('tokenRefreshCount');
    this.config.storage.removeItem('keepLoggedIn');
    
    // 清除刷新定時器
    if (this.refreshTimerId) {
      console.log('清除令牌刷新定時器');
      window.clearTimeout(this.refreshTimerId);
      this.refreshTimerId = null;
    }
    
      // 發送統一的令牌清除事件 (合并多个事件为一个)
    console.log('觸發令牌清除事件(auth:tokens-cleared)');
    window.dispatchEvent(new CustomEvent('auth:tokens-cleared'));
    
    console.log('======【TOKEN清除完成】======');
    return true;
    } finally {
      // 操作完成后重置标志位
      setTimeout(() => {
        this._isClearing = false;
      }, 100);
    }
  }
  
  /**
   * 獲取授權頭
   */
  public getAuthorizationHeader(): string | null {
    if (!this.accessToken) {
      return null;
    }
    
    return `${this.tokenType.charAt(0).toUpperCase() + this.tokenType.slice(1)} ${this.accessToken}`;
  }
  
  /**
   * 是否已認證
   */
  public isAuthenticated(): boolean {
    return !!this.accessToken && !!this.refreshToken;
  }
  
  /**
   * 令牌是否已過期
   */
  public isTokenExpired(): boolean {
    if (!this.expiresAt) {
      return true;
    }
    
    return new Date() >= this.expiresAt;
  }
  
  /**
   * 令牌是否即將過期（在刷新閾值內）
   */
  public isTokenExpiringSoon(): boolean {
    if (!this.expiresAt) {
      return true;
    }
    
    const thresholdTime = new Date();
    thresholdTime.setSeconds(thresholdTime.getSeconds() + this.config.refreshThresholdSeconds);
    
    return this.expiresAt <= thresholdTime;
  }
  
  /**
   * 設置自動令牌刷新
   */
  private setupTokenRefresh(): void {
    // 清除之前的定時器
    if (this.refreshTimerId) {
      window.clearTimeout(this.refreshTimerId);
      this.refreshTimerId = null;
    }
    
    // 如果沒有刷新令牌或過期時間，則不設置定時器
    if (!this.refreshToken || !this.expiresAt) {
      console.log('Token刷新未設置: 沒有刷新令牌或過期時間');
      return;
    }
    
    // 檢查refresh token是否已過期
    if (this.refreshTokenExpiresAt && new Date() >= this.refreshTokenExpiresAt) {
      console.log('Refresh token已過期，需要重新登入', {
        現在: new Date().toLocaleString(),
        refresh過期時間: this.refreshTokenExpiresAt.toLocaleString()
      });
      this.clearTokens();
      window.dispatchEvent(new CustomEvent('show-login-modal'));
      return;
    }
    
    // 獲取 keepLoggedIn 狀態
    const keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true';
    
    // 如果令牌已過期
    if (this.isTokenExpired()) {
      console.log('======【TOKEN刷新計劃】======');
      console.log('Token已過期', {
        現在: new Date().toLocaleString(),
        過期時間: this.expiresAt?.toLocaleString(),
        保持登入: keepLoggedIn ? '是' : '否'
      });
      
      // 只有在保持登入狀態下才刷新，否則登出
      if (keepLoggedIn) {
        console.log('保持登入狀態下，嘗試刷新令牌');
        void this.refreshAccessToken(keepLoggedIn);
      } else {
        console.log('非保持登入狀態，令牌過期，清除令牌');
        this.clearTokens();
        window.dispatchEvent(new CustomEvent('auth:token-expired'));
      }
      return;
    }
    
    // 如果令牌即將過期
    if (this.isTokenExpiringSoon()) {
      console.log('======【TOKEN刷新計劃】======');
      console.log('Token即將過期', {
        現在: new Date().toLocaleString(),
        過期時間: this.expiresAt?.toLocaleString(),
        閾值秒數: this.config.refreshThresholdSeconds,
        保持登入: keepLoggedIn ? '是' : '否'
      });
      
      // 只有在保持登入狀態下才刷新即將過期的令牌
      if (keepLoggedIn) {
        console.log('保持登入狀態下，嘗試刷新即將過期的令牌');
        void this.refreshAccessToken(keepLoggedIn);
      } else {
        // 在非保持登入狀態下，僅計算時間但不自動刷新
        // 等令牌真正過期後再清除
        console.log('非保持登入狀態，等待令牌過期');
        
        // 設置令牌過期後自動登出的定時器
        const timeUntilExpiry = this.expiresAt.getTime() - new Date().getTime();
        
        this.refreshTimerId = window.setTimeout(() => {
          console.log('非保持登入狀態下，令牌已過期，自動清除令牌');
          this.clearTokens();
          window.dispatchEvent(new CustomEvent('auth:token-expired'));
        }, Math.max(1000, timeUntilExpiry));
        
        console.log(`已設置令牌過期自動登出定時器，將在 ${Math.round(timeUntilExpiry/1000)}秒 (${Math.round(timeUntilExpiry/60000)}分鐘) 後登出`);
      }
      return;
    }
    
    // 如果令牌既未過期也不是即將過期，則計算刷新時間
    const now = new Date();
    const timeUntilRefresh = this.expiresAt.getTime() - now.getTime() - (this.config.refreshThresholdSeconds * 1000);
    
    // 只有在保持登入狀態下才設置自動刷新
    if (keepLoggedIn) {
    // 設置定時器
    this.refreshTimerId = window.setTimeout(() => {
      const triggerTime = new Date();
      console.log(`======【TOKEN刷新定時器觸發】======`);
      console.log(`觸發時間: ${triggerTime.toLocaleString()} (${triggerTime.toISOString()})`);
      console.log(`原計劃時間: ${new Date(now.getTime() + timeUntilRefresh).toLocaleString()}`);
        void this.refreshAccessToken(keepLoggedIn);
    }, Math.max(1000, timeUntilRefresh)); // 至少等待1秒
    
    // 更詳細的日誌信息
    const plannedRefreshTime = new Date(now.getTime() + timeUntilRefresh);
    
    // 計算refresh token剩餘有效期
    let refreshTokenRemainingDays = 0;
    let refreshTokenRemainingHours = 0;
    if (this.refreshTokenExpiresAt) {
      const refreshTokenRemainingMs = this.refreshTokenExpiresAt.getTime() - now.getTime();
      refreshTokenRemainingDays = Math.floor(refreshTokenRemainingMs / (1000 * 60 * 60 * 24));
      refreshTokenRemainingHours = Math.floor((refreshTokenRemainingMs % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    }
    
    console.log('======【TOKEN刷新計劃】======');
    console.log(`現在時間: ${now.toLocaleString()} (${now.toISOString()})`);
    console.log(`Access Token過期時間: ${this.expiresAt.toLocaleString()} (${this.expiresAt.toISOString()})`);
    console.log(`Refresh Token過期時間: ${this.refreshTokenExpiresAt?.toLocaleString() || '未設置'} (${this.refreshTokenExpiresAt?.toISOString() || '未設置'})`);
    console.log(`Refresh Token剩餘有效期: ${refreshTokenRemainingDays}天${refreshTokenRemainingHours}小時`);
    console.log(`已刷新次數: ${this.refreshCount}次`);
    console.log(`Access Token剩餘有效期: ${Math.round(timeUntilRefresh/1000)}秒 (${Math.round(timeUntilRefresh/60000)}分鐘)`);
    console.log(`計劃刷新時間: ${plannedRefreshTime.toLocaleString()} (${plannedRefreshTime.toISOString()})`);
    console.log(`距離刷新還有: ${Math.round(timeUntilRefresh/60000)}分鐘${Math.round((timeUntilRefresh % 60000)/1000)}秒`);
    console.log(`保持登入狀態: ${keepLoggedIn ? '是' : '否'}`);
    } else {
      console.log('======【TOKEN信息】======');
      console.log(`現在時間: ${now.toLocaleString()} (${now.toISOString()})`);
      console.log(`Access Token過期時間: ${this.expiresAt.toLocaleString()} (${this.expiresAt.toISOString()})`);
      console.log(`剩餘有效期: ${Math.round(timeUntilRefresh/1000)}秒 (${Math.round(timeUntilRefresh/60000)}分鐘)`);
      console.log(`非保持登入狀態，令牌過期後將自動登出`);
      
      // 設置令牌過期後自動登出的定時器
      this.refreshTimerId = window.setTimeout(() => {
        console.log('非保持登入狀態下，令牌已過期，自動清除令牌');
        this.clearTokens();
        window.dispatchEvent(new CustomEvent('auth:token-expired'));
      }, Math.max(1000, this.expiresAt.getTime() - now.getTime()));
    }
  }
  
  /**
   * 刷新訪問令牌
   */
  public async refreshAccessToken(keepLoggedIn = false): Promise<boolean> {
    // 確保配置已加載
    await this.ensureConfigLoaded();
    
    // 首先從localStorage獲取keepLoggedIn狀態，如果未提供參數
    if (keepLoggedIn === undefined) {
      keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true';
    }
    
    // 非保持登入狀態下，不應進行刷新而應該登出
    if (!keepLoggedIn) {
      console.log('非保持登入狀態下嘗試刷新令牌，拒絕操作並清除令牌');
      // 清除令牌
      this.clearTokens();
      // 觸發令牌過期事件
      window.dispatchEvent(new CustomEvent('auth:token-expired'));
      return false;
    }
    
    const now = new Date();
    console.log('======【TOKEN刷新開始】======');
    console.log(`刷新開始時間: ${now.toLocaleString()} (${now.toISOString()})`);
    console.log(`保持登入狀態: ${keepLoggedIn ? '是' : '否'}`);
    console.log(`當前Token過期時間: ${this.expiresAt ? this.expiresAt.toLocaleString() : '未設置'}`);
    console.log(`當前Refresh Token過期時間: ${this.refreshTokenExpiresAt ? this.refreshTokenExpiresAt.toLocaleString() : '未設置'}`);
    console.log(`已刷新次數: ${this.refreshCount}次`);
    console.log(`是否有刷新令牌: ${this.refreshToken ? '是' : '否'}`);
    console.log(`刷新令牌值 (存储在this.refreshToken): ${this.refreshToken ? this.refreshToken.substring(0, 10) + '...' : '空'}`);
    console.log(`localStorage中的刷新令牌值: ${localStorage.getItem(this.config.refreshTokenKey) ? localStorage.getItem(this.config.refreshTokenKey)!.substring(0, 10) + '...' : '空'}`);
    
    // 检查refresh token是否已过期
    if (this.refreshTokenExpiresAt && new Date() >= this.refreshTokenExpiresAt) {
      console.warn('刷新Token失敗: Refresh token已過期', {
        現在: new Date().toLocaleString(),
        refresh過期時間: this.refreshTokenExpiresAt.toLocaleString()
      });
      window.dispatchEvent(new CustomEvent('auth:token-refresh-failed', { 
        detail: { error: 'Refresh token expired' } 
      }));
      return false;
    }
    
    // 如果已經有一個刷新請求在進行，則返回該請求的 Promise
    if (this.refreshPromise) {
      console.log('已有刷新Token請求進行中，等待結果');
      return this.refreshPromise;
    }
    
    // 檢查令牌狀態
    if (!this.refreshToken) {
      console.warn('刷新Token失敗: 沒有刷新令牌');
      window.dispatchEvent(new CustomEvent('auth:token-refresh-failed', { 
        detail: { error: 'No refresh token available' } 
      }));
      return false;
    }
    
    // 創建新的刷新請求
    this.refreshPromise = (async () => {
      try {
        // 檢查 API 基礎 URL 是否為空，如果為空則嘗試使用 window.location.origin
        let apiBaseUrl = this.config.apiBaseUrl;
        if (!apiBaseUrl || apiBaseUrl.trim() === '') {
          // 在空的 apiBaseUrl 情況下，使用當前頁面的 origin 作為基礎
          console.log('API基礎URL為空，嘗試使用當前頁面的 origin');
          // 由於我們使用 Vite 的代理功能，直接用相對路徑，不需要主機名
          apiBaseUrl = '';
        }
        
        // 構建完整的刷新端點URL
        const refreshUrl = `${apiBaseUrl}${this.config.refreshEndpoint}`;
        console.log(`完整的刷新端點URL: ${refreshUrl}`);
        console.log(`API基础URL: "${apiBaseUrl}"，刷新端點: "${this.config.refreshEndpoint}"`);
        
        const requestStartTime = new Date();
        console.log(`發送刷新Token請求: ${requestStartTime.toLocaleString()}`);
        
        // 尝试使用x-www-form-urlencoded格式
        const urlEncodedParams = new URLSearchParams();
        urlEncodedParams.append('refresh_token', this.refreshToken || '');
        urlEncodedParams.append('keep_logged_in', keepLoggedIn ? 'true' : 'false');
        
        console.log("完整请求体:", urlEncodedParams.toString());
        console.log({
          URL: refreshUrl,
          保持登入: keepLoggedIn,
          刷新令牌前10位: this.refreshToken?.substring(0, 10) + '...',
          請求模式: 'JSON響應' // 明確記錄請求模式
        });
        
        // 詳細調試日誌 - 刷新令牌請求
        console.log('======【刷新令牌請求詳情】======');
        console.log('刷新令牌的實際值:', this.refreshToken);
        console.log('刷新令牌來自:', this.config.refreshTokenKey);
        console.log('localStorage中的刷新令牌:', localStorage.getItem(this.config.refreshTokenKey));
        console.log('完整請求URL:', refreshUrl);
        console.log('請求方法:', 'POST');
        console.log('請求頭:', {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        });
        console.log('請求體:', urlEncodedParams.toString());
        console.log('請求體解碼後:', {
          refresh_token: this.refreshToken,
          keep_logged_in: keepLoggedIn ? 'true' : 'false'
        });
        
        // 增加超時處理
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000); // 10秒超時
        
        try {
        // 發送刷新請求 - 使用urlencoded格式，並明確要求JSON響應
        const response = await fetch(refreshUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
              'Accept': 'application/json', // 明確要求JSON響應
              'X-Requested-With': 'XMLHttpRequest' // 標記為AJAX請求
          },
            body: urlEncodedParams,
            redirect: 'manual', // 保留，但現在應該不會收到重定向響應
            signal: controller.signal,
            credentials: 'include'
        });
          
          clearTimeout(timeoutId);
        
        const requestEndTime = new Date();
        const requestDuration = requestEndTime.getTime() - requestStartTime.getTime();
        
          // 處理異常狀態碼
          if (!response.ok) {
          const errorText = await response.text();
          console.error(`刷新Token請求失敗 (耗時: ${requestDuration}ms)`, {
            狀態碼: response.status,
            錯誤信息: errorText
          });
          
          try {
            // 尝试解析JSON错误信息
            const errorJson = JSON.parse(errorText);
            console.error("错误详情:", errorJson);
          } catch (e) {
            // 非JSON格式，使用原始文本
            console.error("原始错误信息:", errorText);
          }
          
          // 特别处理401错误（无效的刷新令牌）
          if (response.status === 401) {
            console.error('刷新令牌无效或已过期，尝试从localStorage重新加载令牌');
            
            // 从localStorage重新加载刷新令牌（可能是Google OAuth登录后的令牌）
            const storedRefreshToken = localStorage.getItem(this.config.refreshTokenKey);
            
            // 如果localStorage中的令牌与当前使用的不同，尝试使用新的令牌
            if (storedRefreshToken && storedRefreshToken !== this.refreshToken) {
              console.log('发现localStorage中存在不同的刷新令牌，尝试使用新令牌');
              this.refreshToken = storedRefreshToken;
              
              // 尝试重新发送请求
              console.log('使用新的刷新令牌重试请求');
              const retryParams = new URLSearchParams();
              retryParams.append('refresh_token', this.refreshToken);
              retryParams.append('keep_logged_in', keepLoggedIn ? 'true' : 'false');
              
              try {
                const retryResponse = await fetch(refreshUrl, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Accept': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                  },
                  body: retryParams,
                  credentials: 'include'
                });
                
                if (retryResponse.ok) {
                  console.log('使用新刷新令牌重试成功');
                  const retryData = await retryResponse.json() as TokenResponse;
                  
                  // 更新令牌
                  this.accessToken = retryData.access_token;
                  if (retryData.refresh_token) {
                    this.refreshToken = retryData.refresh_token;
                    this.config.storage.setItem(this.config.refreshTokenKey, retryData.refresh_token);
                  }
                  
                  // 更新其他数据
                  if (retryData.expires_in) {
                    this.expiresAt = new Date();
                    this.expiresAt.setSeconds(this.expiresAt.getSeconds() + retryData.expires_in);
                    this.config.storage.setItem('tokenExpiry', this.expiresAt.toISOString());
                  }
                  
                  this.setupTokenRefresh();
                  window.dispatchEvent(new CustomEvent('auth:tokens-updated', {
                    detail: { 
                      accessToken: retryData.access_token, 
                      refreshToken: retryData.refresh_token, 
                      tokenType: retryData.token_type,
                      expiresIn: retryData.expires_in,
                      refreshTokenExpiresIn: retryData.refresh_token_expires_in 
                    }
                  }));
                  
                  return true;
                }
              } catch (retryError) {
                console.error('使用新刷新令牌重试失败:', retryError);
              }
            }
          }
          
          throw new Error(`Token refresh failed: ${response.status}`);
        }
        
          // 處理JSON響應 - 現在我們總是期望JSON響應
        const data = await response.json() as TokenResponse;
        
        if (!data.access_token) {
          console.error('刷新Token響應無效', data);
          throw new Error('Invalid refresh token response: missing access_token');
        }
        
        // 更新刷新次数
        this.refreshCount++;
        this.config.storage.setItem('tokenRefreshCount', this.refreshCount.toString());
        
        console.log(`======【TOKEN刷新成功】(耗時: ${requestDuration}ms)======`);
        console.log(`響應時間: ${requestEndTime.toLocaleString()}`);
        console.log(`当前刷新次数: ${this.refreshCount}次`);
        
        if (data.expires_in) {
          console.log(`新Token有效期: ${data.expires_in}秒 (${Math.round(data.expires_in/60)}分鐘)`);
          const newExpiry = new Date();
          newExpiry.setSeconds(newExpiry.getSeconds() + data.expires_in);
          console.log(`新Token過期時間: ${newExpiry.toLocaleString()} (${newExpiry.toISOString()})`);
        }
        
        console.log(`是否獲得新刷新令牌: ${data.refresh_token ? '是' : '否'}`);
        
        // 更新訪問令牌
        this.accessToken = data.access_token;
        this.config.storage.setItem(this.config.accessTokenKey, data.access_token);
        
        // 如果有新的刷新令牌，也更新它
        if (data.refresh_token) {
          this.refreshToken = data.refresh_token;
          this.config.storage.setItem(this.config.refreshTokenKey, data.refresh_token);
        }
        
        if (data.token_type) {
          this.tokenType = data.token_type;
          this.config.storage.setItem(this.config.tokenTypeKey, data.token_type);
        }
        
          // 更新令牌過期時間
          if (data.expires_in) {
          this.expiresAt = new Date();
            this.expiresAt.setSeconds(this.expiresAt.getSeconds() + data.expires_in);
          this.config.storage.setItem('tokenExpiry', this.expiresAt.toISOString());
          }
        
          // 更新刷新令牌過期時間 - 無論是否有新的刷新令牌，只要有過期時間資訊就更新
          if (data.refresh_token_expires_in) {
            this.refreshTokenExpiresAt = new Date();
            this.refreshTokenExpiresAt.setSeconds(
              this.refreshTokenExpiresAt.getSeconds() + data.refresh_token_expires_in
            );
            this.config.storage.setItem('refreshTokenExpiry', this.refreshTokenExpiresAt.toISOString());
          } else if (data.refresh_token && keepLoggedIn) {
            // 如果有新的刷新令牌且保持登入，但沒有明確的過期時間，使用默認的7天
            this.refreshTokenExpiresAt = new Date();
            this.refreshTokenExpiresAt.setDate(
              this.refreshTokenExpiresAt.getDate() + this.backendConfig.refreshTokenExpireDays
            );
            this.config.storage.setItem('refreshTokenExpiry', this.refreshTokenExpiresAt.toISOString());
        }
        
        // 設置下一次刷新
        this.setupTokenRefresh();
        
        // 發送令牌更新事件
        window.dispatchEvent(new CustomEvent('auth:tokens-updated', {
          detail: { 
            accessToken: data.access_token, 
            refreshToken: data.refresh_token, 
            tokenType: data.token_type,
              expiresIn: data.expires_in,
              refreshTokenExpiresIn: data.refresh_token_expires_in 
          }
        }));
        
        return true;
          
        } catch (fetchError: any) {
          console.error('刷新令牌請求失敗:', fetchError);
            throw fetchError;
          }
      } catch (error: any) {
        console.error('令牌刷新過程中出現錯誤:', error);
        // 需要清除任何可能部分更新的狀態
        window.dispatchEvent(new CustomEvent('auth:token-refresh-failed', { 
          detail: { error: error.message || 'Unknown error during token refresh' } 
        }));
        return false;
      } finally {
        // 無論成功或失敗，最終都清除pending的刷新請求
        this.refreshPromise = null;
      }
    })();
    
    return this.refreshPromise;
  }
  
  /**
   * 包裝的 fetch 方法，自動處理身份驗證和令牌刷新
   */
  public async fetch(url: string, options: RequestInit = {}): Promise<Response> {
    // 如果令牌過期或即將過期，先嘗試刷新
    if ((this.accessToken && this.isTokenExpiringSoon()) || !this.accessToken) {
      if (this.refreshToken) {
        const refreshed = await this.refreshAccessToken();
        if (!refreshed) {
          throw new Error('Token refresh failed before request');
        }
      } else if (!this.accessToken) {
        throw new Error('No access token available');
      }
    }
    
    // 構建完整URL
    const fullUrl = url.startsWith('http') ? url : `${this.config.apiBaseUrl}${url}`;
    
    // 設置默認選項
    const defaultOptions: RequestInit = {
      headers: {
        'Authorization': this.getAuthorizationHeader() ?? ''
      }
    };
    
    // 合併選項
    const requestOptions: RequestInit = { ...defaultOptions, ...options };
    if (options.headers) {
      requestOptions.headers = { ...defaultOptions.headers, ...options.headers };
    }
    
    try {
      // 發送請求
      let response = await fetch(fullUrl, requestOptions);
      
      // 如果返回401未授權，嘗試刷新令牌並重試請求
      if (response.status === 401) {
        if (!this.refreshToken) {
          window.dispatchEvent(new CustomEvent('auth:login-required'));
          throw new Error('Unauthorized and no refresh token available');
        }
        
        const refreshSuccess = await this.refreshAccessToken();
        
        if (refreshSuccess) {
          // 更新授權頭
          const headers = requestOptions.headers as Record<string, string>;
          headers['Authorization'] = this.getAuthorizationHeader() ?? '';
          
          // 重試請求
          response = await fetch(fullUrl, requestOptions);
        } else {
          // 刷新失敗，需要重新登錄
          window.dispatchEvent(new CustomEvent('auth:login-required'));
          throw new Error('Unauthorized and token refresh failed');
        }
      }
      
      return response;
      
    } catch (error) {
      console.error('API request error:', error);
      throw error;
    }
  }
  
  /**
   * 登出
   */
  public async logout(): Promise<boolean> {
    // 防止重复调用
    if (this._isLoggingOut) {
      console.log('登出操作已在进行中，忽略重复调用');
      return false;
    }
    
    this._isLoggingOut = true;
    
    try {
      // 如果没有刷新令牌，直接清除本地状态
      if (!this.refreshToken) {
        this.clearTokens();
        return true;
      }
      
      console.log('执行登出操作，准备撤销刷新令牌');
      
      try {
        // 构建登出URL
      const logoutUrl = `${this.config.apiBaseUrl}/api/v1/auth/logout`;
      
        // 创建FormData，确保与后端接口匹配
        const formData = new FormData();
        formData.append('refresh_token', this.refreshToken);
        
        // 发送登出请求
      const response = await fetch(logoutUrl, {
        method: 'POST',
          body: formData,
        headers: {
          'Authorization': this.getAuthorizationHeader() ?? ''
          }
      });
      
        console.log(`登出请求响应状态: ${response.status}`);
        
        // 无论登出是否成功，都清除本地令牌
      this.clearTokens();
      
      return response.ok;
    } catch (error) {
        console.error('Logout API error:', error);
        // 即使API失败也清除令牌
      this.clearTokens();
      return false;
      }
    } finally {
      // 操作完成后重置标志位
      setTimeout(() => {
        this._isLoggingOut = false;
      }, 100);
    }
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
   * 創建並設置axios實例及其攔截器
   * 用於攔截API請求，自動處理令牌過期和刷新
   */
  public setupAxiosInterceptors(axiosInstance: any) {
    console.log('設置axios攔截器');
    
    // 請求攔截器
    axiosInstance.interceptors.request.use(
      async (config: any) => {
        // 如果沒有授權頭且有令牌，添加授權頭
        if (!config.headers.Authorization && this.accessToken) {
          config.headers.Authorization = this.getAuthorizationHeader();
          console.log('自動添加授權頭到請求');
        }
        
        // 檢查令牌是否即將過期
        const keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true';
        if (this.accessToken && this.isTokenExpiringSoon() && keepLoggedIn) {
          console.log('令牌即將過期，在請求前嘗試刷新');
          
          try {
            // 嘗試刷新令牌
            const refreshed = await this.refreshAccessToken(keepLoggedIn);
            if (refreshed) {
              // 使用新令牌
              config.headers.Authorization = this.getAuthorizationHeader();
              console.log('使用新令牌更新請求授權頭');
            } else {
              console.warn('令牌刷新失敗，使用現有令牌繼續請求');
            }
          } catch (error) {
            console.error('刷新令牌時發生錯誤', error);
            // 錯誤處理已在refreshAccessToken中完成
          }
        }
        
        return config;
      },
      (error: any) => {
        console.error('請求攔截器錯誤', error);
        return Promise.reject(error);
      }
    );
    
    // 響應攔截器
    axiosInstance.interceptors.response.use(
      (response: any) => {
        return response;
      },
      async (error: any) => {
        const originalRequest = error.config;
        const keepLoggedIn = localStorage.getItem('keepLoggedIn') === 'true';
        
        // 處理401錯誤（未授權）
        if (error.response && error.response.status === 401 && !originalRequest._retry) {
          console.log('收到401響應，檢查是否可以刷新令牌');
          
          // 只在保持登入狀態下嘗試刷新令牌
          if (keepLoggedIn && this.refreshToken) {
            console.log('保持登入狀態下，嘗試刷新令牌並重試請求');
            originalRequest._retry = true;
            
            try {
              const refreshed = await this.refreshAccessToken(keepLoggedIn);
              if (refreshed) {
                // 使用新令牌更新授權頭
                originalRequest.headers.Authorization = this.getAuthorizationHeader();
                console.log('令牌刷新成功，重試原始請求');
                return axiosInstance(originalRequest);
              } else {
                console.warn('令牌刷新失敗，不重試請求');
                // 登出處理在refreshAccessToken內部已完成
                return Promise.reject(error);
              }
            } catch (refreshError) {
              console.error('刷新令牌發生錯誤', refreshError);
              return Promise.reject(error);
            }
          } else {
            console.log('非保持登入狀態或無刷新令牌，清除認證並登出');
            // 令牌過期且非保持登入狀態，觸發登出事件
            this.clearTokens();
            window.dispatchEvent(new CustomEvent('auth:token-expired'));
            return Promise.reject(error);
          }
        }
        
        return Promise.reject(error);
      }
    );
    
    console.log('axios攔截器設置完成');
    return axiosInstance;
  }

  /**
   * 获取刷新令牌
   * @returns 当前的刷新令牌，如果没有则返回null
   */
  public getRefreshToken(): string | null {
    return this.refreshToken;
  }

  /**
   * 强制更新令牌状态
   * 在特殊情况下用于强制同步令牌，直接设置内部状态和localStorage
   * 
   * @param accessToken 访问令牌
   * @param refreshToken 刷新令牌
   * @param tokenType 令牌类型
   * @returns 是否成功设置
   */
  public forceUpdateTokens(
    accessToken: string,
    refreshToken: string,
    tokenType: string = this.config.defaultTokenType
  ): boolean {
    try {
      // 直接更新内部状态
      this.accessToken = accessToken;
      this.refreshToken = refreshToken;
      this.tokenType = tokenType;
      
      // 保存到localStorage
      this.config.storage.setItem(this.config.accessTokenKey, accessToken);
      this.config.storage.setItem(this.config.refreshTokenKey, refreshToken);
      this.config.storage.setItem(this.config.tokenTypeKey, tokenType);
      
      console.log('成功强制更新令牌状态');
      return true;
    } catch (error) {
      console.error('强制更新令牌状态失败:', error);
      return false;
    }
  }
} 