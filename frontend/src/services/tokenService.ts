import { TokenManager } from '@/utils/tokenManager'
import axios from 'axios'

// TokenManager单例类
class TokenService {
  private static instance: TokenService | null = null;
  private tokenManager: TokenManager;
  private initialized: boolean = false;
  private initPromise: Promise<boolean> | null = null;

  private constructor() {
    console.log('【TokenService】创建TokenService单例');
    
    // 创建TokenManager实例
    this.tokenManager = new TokenManager({
      accessTokenKey: 'token',
      refreshTokenKey: 'refreshToken',
      tokenTypeKey: 'tokenType',
      refreshEndpoint: '/api/v1/auth/refresh'
    });
  }

  /**
   * 获取TokenService单例
   */
  public static getInstance(): TokenService {
    if (!TokenService.instance) {
      TokenService.instance = new TokenService();
    }
    return TokenService.instance;
  }

  /**
   * 初始化TokenManager，设置拦截器等
   */
  public async initialize(): Promise<boolean> {
    if (this.initialized) {
      console.log('【TokenService】已初始化，跳过');
      return true;
    }

    if (this.initPromise) {
      console.log('【TokenService】初始化已在进行中，等待完成');
      return this.initPromise;
    }

    console.log('【TokenService】开始初始化');
    
    // 创建并保存初始化Promise
    this.initPromise = new Promise(async (resolve) => {
      try {
        // 设置全局实例，用于向后兼容
        (window as any).tokenManager = this.tokenManager;
        
        // 设置axios拦截器
        this.tokenManager.setupAxiosInterceptors(axios);
        
        // 加载后端配置
        await this.tokenManager.ensureConfigLoaded();
        
        // 标记为已初始化
        this.initialized = true;
        console.log('【TokenService】初始化完成');
        resolve(true);
      } catch (error) {
        console.error('【TokenService】初始化失败:', error);
        resolve(false);
      }
    });

    return this.initPromise;
  }

  /**
   * 获取TokenManager实例
   */
  public getTokenManager(): TokenManager {
    return this.tokenManager;
  }
}

// 导出单例获取方法
export const getTokenService = (): TokenService => {
  return TokenService.getInstance();
};

// 导出获取TokenManager的便捷方法
export const getTokenManager = (): TokenManager => {
  return TokenService.getInstance().getTokenManager();
};

// 导出初始化方法
export const initializeTokenService = async (): Promise<boolean> => {
  return await TokenService.getInstance().initialize();
}; 