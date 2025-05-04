<template>
  <div class="transactions-table">
    <div class="table-header">
      <h3>Transactions</h3>
    </div>
    <div class="table-content">
      <div v-for="(transaction, index) in transactions" :key="index" class="transaction-item">
        <div class="coin-info">
          <div class="coin-icon" :style="{ backgroundColor: transaction.iconBgColor }">
            <span>{{ transaction.icon }}</span>
          </div>
          <div class="coin-details">
            <h4>{{ transaction.coinName }}</h4>
            <p>{{ transaction.type }}</p>
          </div>
        </div>
        <div class="transaction-info">
          <h4 :class="{ 'negative': transaction.type === 'Buy' }">{{ transaction.amount }}</h4>
          <p>{{ transaction.time }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const transactions = ref([
  {
    coinName: 'Ethereum',
    type: 'Received',
    amount: '$24,102',
    time: 'Today, 15:30',
    icon: '⟠',
    iconBgColor: '#6B7DFF'
  },
  {
    coinName: 'Bitcoin',
    type: 'Buy',
    amount: '$4,157',
    time: 'Today, 14:32',
    icon: '₿',
    iconBgColor: '#FFB52E'
  },
  {
    coinName: 'Bitcoin',
    type: 'Buy',
    amount: '$64,784',
    time: 'Today, 13:50',
    icon: '₿',
    iconBgColor: '#FFB52E'
  },
  {
    coinName: 'Litecoin',
    type: 'Buy',
    amount: '$14,265',
    time: 'Today, 08:35',
    icon: 'Ł',
    iconBgColor: '#4B4BFF'
  }
]);
</script>

<style scoped lang="scss">
.transactions-table {
  background-color: white;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  
  .table-header {
    margin-bottom: 15px;
    
    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }
  }
  
  .table-content {
    .transaction-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 15px 0;
      border-bottom: 1px solid #eaeaea;
      
      &:last-child {
        border-bottom: none;
      }
      
      .coin-info {
        display: flex;
        align-items: center;
        
        .coin-icon {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-right: 15px;
          color: white;
          font-size: 18px;
        }
        
        .coin-details {
          h4 {
            margin: 0;
            font-size: 16px;
            font-weight: 500;
          }
          
          p {
            margin: 0;
            font-size: 14px;
            color: #666;
          }
        }
      }
      
      .transaction-info {
        text-align: right;
        
        h4 {
          margin: 0;
          font-size: 16px;
          font-weight: 500;
          color: #4CAF50;
          
          &.negative {
            color: #FF5252;
          }
        }
        
        p {
          margin: 0;
          font-size: 14px;
          color: #666;
        }
      }
    }
  }
}
</style> 