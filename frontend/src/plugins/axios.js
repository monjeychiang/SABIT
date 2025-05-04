import axios from 'axios';

// 创建axios实例
const axiosInstance = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器
axiosInstance.interceptors.request.use(
  config => {
    // 从localStorage获取token
    const token = localStorage.getItem('token');
    
    // 如果有token，添加到请求头
    if (token) {
      config.headers['Authorization'] = `bearer ${token}`;
    }
    
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// 响应拦截器
axiosInstance.interceptors.response.use(
  response => {
    return response;
  },
  error => {
    // 处理401错误，可能是token过期
    if (error.response && error.response.status === 401) {
      // 清除token
      localStorage.removeItem('token');
      localStorage.removeItem('tokenType');
      
      // 如果是弹框的话可以显示提示信息
      // 如果有通知系统
      if (window.$message) {
        window.$message.error('登录已过期，请重新登录');
      }
      
      // 重定向到登录页
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    
    return Promise.reject(error);
  }
);

// 设置为全局默认axios
export default {
  install: (app) => {
    // 将自定义的axios实例挂载到app上
    app.config.globalProperties.$axios = axiosInstance;
    
    // 替换全局的axios
    window.axios = axiosInstance;
  }
}; 