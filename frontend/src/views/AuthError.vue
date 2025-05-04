<template>
  <div class="auth-error">
    <div class="error-container">
      <svg class="error-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
        <path fill="none" d="M0 0h24v24H0z"/>
        <path d="M12 22C6.477 22 2 17.523 2 12S6.477 2 12 2s10 4.477 10 10-4.477 10-10 10zm0-2a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm-1-5h2v2h-2v-2zm0-8h2v6h-2V7z" fill="currentColor"/>
      </svg>
      <h1>登入失敗</h1>
      <div class="error-details">
        <h2>錯誤信息</h2>
        <div class="error-message">{{ errorMessage }}</div>
        
        <div class="error-solutions">
          <h3>可能原因與解決方案</h3>
          <ul>
            <li v-for="(solution, index) in possibleSolutions" :key="index">
              <strong>{{ solution.reason }}</strong>
              <p>{{ solution.solution }}</p>
            </li>
          </ul>
        </div>
      </div>
      <div class="action-buttons">
        <button class="retry-button" @click="handleRetry">重試登入</button>
        <button class="help-button" @click="handleHelp">聯繫客服</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const errorMessage = ref('登入過程中發生錯誤')
const errorType = ref('unknown')

onMounted(() => {
  const params = new URLSearchParams(window.location.search)
  const error = params.get('error')
  const type = params.get('errorType') || 'unknown'
  
  if (error) {
    errorMessage.value = decodeURIComponent(error)
  }
  
  errorType.value = type
})

const possibleSolutions = computed(() => {
  // 根據錯誤類型提供不同的解決方案
  const solutions = {
    'invalid_credentials': [
      {
        reason: '帳號或密碼錯誤',
        solution: '請確認您輸入的帳號和密碼是否正確。如果忘記密碼，可以使用重設密碼功能。'
      }
    ],
    'account_locked': [
      {
        reason: '帳號已鎖定',
        solution: '您的帳號因多次登入失敗而被暫時鎖定，請稍後再試或聯繫客服解鎖。'
      }
    ],
    'session_expired': [
      {
        reason: '登入會話已過期',
        solution: '您的登入會話已過期，請重新登入。'
      }
    ],
    'network_error': [
      {
        reason: '網絡連接問題',
        solution: '請檢查您的網絡連接並確保能夠正常訪問互聯網，然後重試。'
      }
    ],
    'server_error': [
      {
        reason: '伺服器錯誤',
        solution: '我們的伺服器暫時發生問題，請稍後再試。如果問題持續存在，請聯繫客服。'
      }
    ],
    'unknown': [
      {
        reason: '未知錯誤',
        solution: '發生了未知錯誤，請重試或聯繫客服尋求幫助。'
      },
      {
        reason: '瀏覽器問題',
        solution: '嘗試清除瀏覽器緩存和Cookie，或使用其他瀏覽器登入。'
      }
    ]
  }
  
  return solutions[errorType.value as keyof typeof solutions] || solutions.unknown
})

const handleRetry = () => {
  router.push('/login')
}

const handleHelp = () => {
  // 跳轉到幫助頁面或打開聯繫客服的對話框
  router.push('/contact-support')
}
</script>

<style scoped>
.auth-error {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: var(--surface-color);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

.error-container {
  text-align: center;
  padding: var(--spacing-xl);
  background-color: var(--surface-color, #ffffff);
  border-radius: var(--border-radius-lg, 8px);
  box-shadow: var(--shadow-lg, 0 10px 25px rgba(0, 0, 0, 0.1));
  max-width: 550px;
  width: 90%;
}

.error-icon {
  width: 80px;
  height: 80px;
  color: var(--danger-color, #e53935);
  margin-bottom: var(--spacing-md, 16px);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.05); opacity: 0.8; }
  100% { transform: scale(1); opacity: 1; }
}

h1 {
  color: var(--text-primary, #333333);
  font-size: var(--font-size-xl, 28px);
  margin-bottom: var(--spacing-md, 16px);
  font-weight: 600;
}

h2 {
  color: var(--text-primary, #333333);
  font-size: var(--font-size-lg, 20px);
  margin: 24px 0 12px;
  font-weight: 500;
}

h3 {
  color: var(--text-primary, #333333);
  font-size: var(--font-size-md, 16px);
  margin: 16px 0 12px;
  font-weight: 500;
  text-align: left;
}

.error-details {
  background-color: var(--surface-alt, #f5f5f5);
  padding: 20px;
  border-radius: var(--border-radius-md, 6px);
  margin: 20px 0;
  text-align: left;
}

.error-message {
  color: var(--danger-color, #e53935);
  background-color: var(--danger-bg, rgba(229, 57, 53, 0.1));
  padding: 12px;
  border-radius: var(--border-radius-sm, 4px);
  font-weight: 500;
  margin-bottom: 16px;
  border-left: 4px solid var(--danger-color, #e53935);
}

.error-solutions {
  margin-top: 16px;
}

.error-solutions ul {
  list-style-type: none;
  padding: 0;
  margin: 0;
}

.error-solutions li {
  background-color: var(--surface-color, #ffffff);
  padding: 12px;
  border-radius: var(--border-radius-sm, 4px);
  margin-bottom: 12px;
  border: 1px solid var(--border-color, #e0e0e0);
}

.error-solutions li strong {
  color: var(--text-primary, #333333);
  display: block;
  margin-bottom: 4px;
}

.error-solutions li p {
  color: var(--text-secondary, #666666);
  margin: 0;
  font-size: var(--font-size-sm, 14px);
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
}

.retry-button {
  background-color: var(--primary-color, #1976d2);
  color: white;
  border: none;
  padding: var(--spacing-sm, 10px) var(--spacing-lg, 24px);
  border-radius: var(--border-radius-md, 6px);
  font-size: var(--font-size-md, 16px);
  cursor: pointer;
  transition: all var(--transition-fast, 0.2s) ease;
  font-weight: 500;
}

.retry-button:hover {
  background-color: var(--primary-dark, #1565c0);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.help-button {
  background-color: var(--surface-color, #ffffff);
  color: var(--primary-color, #1976d2);
  border: 1px solid var(--primary-color, #1976d2);
  padding: var(--spacing-sm, 10px) var(--spacing-lg, 24px);
  border-radius: var(--border-radius-md, 6px);
  font-size: var(--font-size-md, 16px);
  cursor: pointer;
  transition: all var(--transition-fast, 0.2s) ease;
  font-weight: 500;
}

.help-button:hover {
  background-color: var(--primary-light, rgba(25, 118, 210, 0.1));
  transform: translateY(-2px);
}

@media (max-width: 600px) {
  .error-container {
    padding: var(--spacing-lg, 16px);
  }
  
  .action-buttons {
    flex-direction: column;
  }
  
  .retry-button, .help-button {
    width: 100%;
  }
}
</style> 