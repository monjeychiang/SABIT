<template>
  <!-- No changes to template section -->
</template>

<script>
export default {
  // No changes to component options
};
</script>

<style>
  /* No changes to style section */
</style>

<script>
export default {
  // No changes to component options

  // 添加調試代碼，在組件掛載時檢查通知列表
  mounted() {
    console.log("NotificationPopover 已掛載，通知列表:", this.notifications);
    
    // 輸出 notificationStore 的狀態
    console.log("通知狀態:", this.notificationStore);
    
    // 註冊調試處理器以檢查通知更新
    this.notificationStore.$subscribe((mutation, state) => {
      console.log("通知狀態變更:", mutation.type, state.notifications.length);
    });
  }
};
</script> 