<template>
  <div class="profile-view">
    <PageHeader title="用户资料" subtitle="查看和管理您的个人信息" />
    
    <div class="content-container">
      <UserProfile />
    </div>
  </div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import UserProfile from '@/components/UserProfile.vue'
</script>

<style scoped>
.profile-view {
  padding: 20px;
}

.content-container {
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  margin-top: 20px;
}
</style> 