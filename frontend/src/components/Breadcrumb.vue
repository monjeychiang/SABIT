<template>
  <div class="breadcrumb-container" v-if="breadcrumbs.length > 0">
    <ul class="breadcrumb">
      <li v-for="(breadcrumb, index) in breadcrumbs" :key="index">
        <router-link 
          v-if="index < breadcrumbs.length - 1" 
          :to="breadcrumb.path"
          class="breadcrumb-link"
        >
          {{ breadcrumb.name }}
        </router-link>
        <span v-else class="breadcrumb-current">{{ breadcrumb.name }}</span>
        <svg 
          v-if="index < breadcrumbs.length - 1" 
          xmlns="http://www.w3.org/2000/svg" 
          viewBox="0 0 24 24" 
          width="16" 
          height="16" 
          class="breadcrumb-separator"
        >
          <path fill="none" d="M0 0h24v24H0z" />
          <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" fill="currentColor" />
        </svg>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

// 使用计算属性根据当前路由生成面包屑
const breadcrumbs = computed(() => {
  // 始终显示首页
  const crumbs = [
    {
      name: '首頁',
      path: '/'
    }
  ];

  // 根据当前路由生成面包屑
  const { path, name, meta, params } = route;
  
  // 如果是首页，只返回首页面包屑
  if (path === '/') {
    return crumbs;
  }
  
  // 获取路由匹配的记录
  const matched = router.currentRoute.value.matched;
  
  // 如果有匹配的路由记录，使用它们创建面包屑
  if (matched.length > 1) {
    // 跳过第一个匹配项(通常是根路由)
    matched.slice(1).forEach(record => {
      // 处理路径中的参数
      let routePath = record.path;
      let crumbName = '';
      
      // 尝试从路由元数据中获取面包屑名称
      if (record.meta && record.meta.breadcrumb) {
        crumbName = record.meta.breadcrumb;
      } else {
        // 尝试从路由名称获取
        crumbName = record.name ? String(record.name).replace(/-/g, ' ') : '';
        crumbName = crumbName.charAt(0).toUpperCase() + crumbName.slice(1);
      }
      
      // 替换路径中的参数
      if (params) {
        Object.keys(params).forEach(key => {
          routePath = routePath.replace(`:${key}`, params[key]);
        });
      }
      
      crumbs.push({
        name: crumbName,
        path: routePath
      });
    });
  } else {
    // 如果没有匹配的路由记录，则使用路径分割方法
    const pathParts = path.split('/').filter(Boolean);
    
    pathParts.forEach((part, index) => {
      // 构建到当前部分的路径
      const currentPath = '/' + pathParts.slice(0, index + 1).join('/');
      
      // 处理路径名称
      let crumbName = '';
      
      // 查找匹配的路由
      const matchingRoute = Object.values(router.options.routes).find(r => r.path === currentPath);
      
      if (matchingRoute && matchingRoute.meta && matchingRoute.meta.breadcrumb) {
        // 使用路由元数据中的面包屑名称
        crumbName = matchingRoute.meta.breadcrumb;
      } else {
        // 使用默认逻辑
        switch (part) {
          case 'dashboard':
            crumbName = '控制面板';
            break;
          case 'history':
            crumbName = '交易歷史';
            break;
          case 'create-grid':
            crumbName = '創建網格';
            break;
          case 'grid':
            crumbName = '網格詳情';
            break;
          case 'markets':
            crumbName = '市場行情';
            break;
          case 'trading':
            crumbName = '交易';
            break;
          case 'settings':
            crumbName = '設置';
            break;
          case 'admin':
            crumbName = '管理員';
            break;
          case 'theme-test':
            crumbName = '主題測試';
            break;
          default:
            // 如果是ID參數，使用格式化的显示
            if (params && params.id && part === params.id) {
              crumbName = `ID: ${part}`;
            } else if (params && params.symbol && part === params.symbol) {
              crumbName = `${part.toUpperCase()}`;
            } else if (params && params.marketType && part === params.marketType) {
              crumbName = part === 'spot' ? '現貨' : part === 'futures' ? '期貨' : part;
            } else {
              // 将短横线替换为空格，并将首字母大写
              crumbName = part.replace(/-/g, ' ');
              crumbName = crumbName.charAt(0).toUpperCase() + crumbName.slice(1);
            }
        }
      }
      
      crumbs.push({
        name: crumbName,
        path: currentPath
      });
    });
  }
  
  return crumbs;
});
</script>

<style scoped>
.breadcrumb-container {
  margin-bottom: var(--spacing-md);
  margin-top: -5px;
  padding: var(--spacing-sm) 0;
  background-color: transparent;
  box-shadow: none;
}

.breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  list-style: none;
  padding: 0;
  margin: 0;
}

.breadcrumb li {
  display: flex;
  align-items: center;
  font-size: var(--font-size-sm);
}

.breadcrumb-link {
  color: var(--primary-color);
  text-decoration: none;
  transition: color var(--transition-fast) ease;
}

.breadcrumb-link:hover {
  color: var(--primary-dark);
  text-decoration: underline;
}

.breadcrumb-current {
  color: var(--text-secondary);
  font-weight: 500;
}

.breadcrumb-separator {
  margin: 0 var(--spacing-xs);
  color: var(--text-tertiary);
  opacity: 0.7;
}

@media (max-width: 768px) {
  .breadcrumb-container {
    padding: var(--spacing-xs) 0;
    margin-bottom: var(--spacing-sm);
    margin-top: -2px;
  }
  
  .breadcrumb li {
    font-size: var(--font-size-xs);
  }
}
</style> 