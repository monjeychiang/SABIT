<template>
  <div class="theme-test-container">
    <h1>主题测试页面</h1>
    <p class="description">此页面用于测试不同UI元素在深色和浅色主题下的表现</p>
    
    <div class="theme-info">
      <p>当前主题: <strong>{{ themeStore.isDarkMode ? '深色主题' : '浅色主题' }}</strong></p>
      <el-button type="primary" @click="themeStore.toggleTheme">
        切换为{{ themeStore.isDarkMode ? '浅色' : '深色' }}主题
      </el-button>
    </div>
    
    <div class="section">
      <h2>卡片组件</h2>
      <div class="card-container">
        <div class="test-card">
          <h3>标准卡片</h3>
          <p>这是一个标准卡片组件，用于测试在不同主题下的表现。</p>
        </div>
        
        <div class="test-card card-hover">
          <h3>悬停效果卡片</h3>
          <p>将鼠标悬停在此卡片上可以看到悬停效果。</p>
        </div>
      </div>
    </div>
    
    <div class="section">
      <h2>按钮组件</h2>
      <div class="button-container">
        <el-button>默认按钮</el-button>
        <el-button type="primary">主要按钮</el-button>
        <el-button type="success">成功按钮</el-button>
        <el-button type="warning">警告按钮</el-button>
        <el-button type="danger">危险按钮</el-button>
        <el-button type="info">信息按钮</el-button>
      </div>
      
      <div class="button-container" style="margin-top: 16px;">
        <el-button plain>朴素按钮</el-button>
        <el-button type="primary" plain>主要按钮</el-button>
        <el-button type="success" plain>成功按钮</el-button>
        <el-button type="warning" plain>警告按钮</el-button>
        <el-button type="danger" plain>危险按钮</el-button>
        <el-button type="info" plain>信息按钮</el-button>
      </div>
    </div>
    
    <div class="section">
      <h2>表单元素</h2>
      <div class="form-container">
        <el-form label-width="100px">
          <el-form-item label="输入框">
            <el-input v-model="inputText" placeholder="请输入内容"></el-input>
          </el-form-item>
          
          <el-form-item label="选择器">
            <el-select v-model="selectValue" placeholder="请选择">
              <el-option v-for="item in options" :key="item.value" :label="item.label" :value="item.value"></el-option>
            </el-select>
          </el-form-item>
          
          <el-form-item label="开关">
            <el-switch v-model="switchValue"></el-switch>
          </el-form-item>
          
          <el-form-item label="单选框">
            <el-radio-group v-model="radioValue">
              <el-radio :label="1">选项1</el-radio>
              <el-radio :label="2">选项2</el-radio>
              <el-radio :label="3">选项3</el-radio>
            </el-radio-group>
          </el-form-item>
          
          <el-form-item label="复选框">
            <el-checkbox-group v-model="checkboxValue">
              <el-checkbox label="选项1"></el-checkbox>
              <el-checkbox label="选项2"></el-checkbox>
              <el-checkbox label="选项3"></el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-form>
      </div>
    </div>
    
    <div class="section">
      <h2>表格</h2>
      <el-table :data="tableData" style="width: 100%">
        <el-table-column prop="date" label="日期" width="180"></el-table-column>
        <el-table-column prop="name" label="姓名" width="180"></el-table-column>
        <el-table-column prop="address" label="地址"></el-table-column>
      </el-table>
    </div>
    
    <div class="section">
      <h2>返回主页</h2>
      <el-button @click="goToHome" type="primary">
        <el-icon><ArrowLeft /></el-icon> 返回主页
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useThemeStore } from '@/stores/theme'
import { ArrowLeft } from '@element-plus/icons-vue'

const router = useRouter()
const themeStore = useThemeStore()

// 表单数据
const inputText = ref('')
const selectValue = ref('')
const switchValue = ref(false)
const radioValue = ref(1)
const checkboxValue = ref<string[]>([])

// 选项数据
const options = [
  { value: 'option1', label: '选项1' },
  { value: 'option2', label: '选项2' },
  { value: 'option3', label: '选项3' }
]

// 表格数据
const tableData = [
  {
    date: '2023-05-03',
    name: '张三',
    address: '北京市朝阳区芍药居'
  },
  {
    date: '2023-05-02',
    name: '李四',
    address: '北京市海淀区西二旗'
  },
  {
    date: '2023-05-01',
    name: '王五',
    address: '上海市浦东新区张江'
  }
]

// 导航方法
const goToHome = () => {
  router.push('/')
}
</script>

<style scoped>
.theme-test-container {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  margin-bottom: 16px;
  color: var(--el-text-color-primary);
}

.description {
  color: var(--el-text-color-secondary);
  margin-bottom: 24px;
}

.theme-info {
  background-color: var(--el-bg-color-overlay);
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: var(--el-box-shadow-light);
}

.section {
  margin-bottom: 32px;
}

h2 {
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-light);
  color: var(--el-text-color-primary);
}

.card-container {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.test-card {
  background-color: var(--el-bg-color-overlay);
  padding: 16px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
  flex: 1;
  min-width: 250px;
  transition: all 0.3s ease;
}

.card-hover:hover {
  transform: translateY(-5px);
  box-shadow: var(--el-box-shadow);
}

.button-container {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.form-container {
  background-color: var(--el-bg-color-overlay);
  padding: 24px;
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-light);
}

@media (max-width: 768px) {
  .card-container {
    flex-direction: column;
  }
  
  .button-container {
    justify-content: center;
  }
}
</style> 