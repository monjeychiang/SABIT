<template>
  <div class="statistic-chart">
    <div class="chart-header">
      <div>
        <h3>{{ title }}</h3>
        <p class="subtitle">{{ subtitle }}</p>
      </div>
      <div class="time-range">
        <button 
          v-for="(range, index) in timeRanges" 
          :key="index"
          :class="{ active: activeRange === range.value }"
          @click="changeTimeRange(range.value)"
        >
          {{ range.label }}
        </button>
      </div>
    </div>
    <div class="price-info">
      <div class="current-price">
        <h2>${{ formatPrice(currentPrice) }}</h2>
        <div class="price-change" :class="{ 'positive': priceChange > 0, 'negative': priceChange < 0 }">
          <span>{{ priceChange > 0 ? '+' : '' }}{{ (priceChange * 100).toFixed(2) }}%</span>
        </div>
      </div>
      <div class="price-range">
        <div class="range-item">
          <span class="label">Low</span>
          <span class="value">${{ formatPrice(lowestPrice) }}</span>
        </div>
        <div class="range-line">
          <div class="range-indicator" 
               :style="{ left: `${((currentPrice - lowestPrice) / (highestPrice - lowestPrice)) * 100}%` }">
          </div>
        </div>
        <div class="range-item">
          <span class="label">High</span>
          <span class="value">${{ formatPrice(highestPrice) }}</span>
        </div>
      </div>
    </div>
    <div class="chart-container" @mousemove="updateMarker" @mouseleave="hideMarker">
      <canvas ref="chartCanvas"></canvas>
      <div class="price-marker" v-if="showMarker" :style="{ left: markerPosition + 'px', top: markerTop + 'px' }">
        <div class="price-tag">${{ highlightedPrice }}</div>
        <div class="date-tag">{{ highlightedDate }}</div>
      </div>
    </div>
    <div class="timeline">
      <span v-for="(label, index) in timeLabels" :key="index">{{ label }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import Chart from 'chart.js/auto';

const props = defineProps({
  title: {
    type: String,
    default: 'Price Statistics'
  },
  subtitle: {
    type: String,
    default: 'Last 6 months'
  },
  currentPrice: {
    type: Number,
    default: 0
  },
  priceChange: {
    type: Number,
    default: 0
  },
  lowestPrice: {
    type: Number,
    default: 0
  },
  highestPrice: {
    type: Number,
    default: 0
  }
});

const chartCanvas = ref(null);
const chart = ref(null);
const highlightedPrice = ref('0');
const highlightedDate = ref('');
const markerPosition = ref(0);
const markerTop = ref(0);
const showMarker = ref(false);
const chartData = ref([]);
const timeLabels = ref([]);
const selectedPoint = ref(null);

const activeRange = ref('6m'); // Default to 6 months

const timeRanges = [
  { label: '1D', value: '1d' },
  { label: '1W', value: '1w' },
  { label: '1M', value: '1m' },
  { label: '6M', value: '6m' },
  { label: '1Y', value: '1y' },
  { label: 'All', value: 'all' }
];

const updateMarker = (event) => {
  if (!chart.value) return;

  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  
  const xValue = chart.value.scales.x.getValueForPixel(x);
  if (xValue >= 0 && xValue < chartData.value.length) {
    const index = Math.round(xValue);
    highlightedPrice.value = formatPrice(chartData.value[index]);
    highlightedDate.value = timeLabels.value[index];
    markerPosition.value = x;
    markerTop.value = chart.value.scales.y.getPixelForValue(chartData.value[index]);
    showMarker.value = true;
  }
};

const hideMarker = () => {
  if (!selectedPoint.value) {
    showMarker.value = false;
  }
};

const handleChartClick = (event) => {
  if (!chart.value) return;
  
  const rect = event.currentTarget.getBoundingClientRect();
  const x = event.clientX - rect.left;
  
  const xValue = chart.value.scales.x.getValueForPixel(x);
  if (xValue >= 0 && xValue < chartData.value.length) {
    const index = Math.round(xValue);
    
    if (selectedPoint.value === index) {
      // Clicking the same point toggles it off
      selectedPoint.value = null;
      showMarker.value = false;
    } else {
      selectedPoint.value = index;
      highlightedPrice.value = formatPrice(chartData.value[index]);
      highlightedDate.value = timeLabels.value[index];
      markerPosition.value = chart.value.scales.x.getPixelForValue(index);
      markerTop.value = chart.value.scales.y.getPixelForValue(chartData.value[index]);
      showMarker.value = true;
    }
  }
};

const formatPrice = (value) => {
  if (value >= 1000) {
    return value.toLocaleString('en-US');
  } else if (value >= 1) {
    return value.toFixed(2);
  } else {
    return value.toFixed(6);
  }
};

const changeTimeRange = (range) => {
  activeRange.value = range;
  generateChartData(range);
  updateChart();
};

const generateChartData = (range) => {
  // In a real app, this would fetch data from an API
  const now = new Date();
  const data = [];
  let labels = [];
  
  switch (range) {
    case '1d':
      // Generate hourly data for 1 day
      for (let i = 0; i < 24; i++) {
        data.push(Math.floor(Math.random() * (props.highestPrice - props.lowestPrice) * 0.2) + props.currentPrice - (props.highestPrice - props.lowestPrice) * 0.1);
        const hour = new Date(now);
        hour.setHours(hour.getHours() - 23 + i);
        labels.push(`${hour.getHours()}:00`);
      }
      break;
    case '1w':
      // Generate daily data for 1 week
      for (let i = 0; i < 7; i++) {
        data.push(Math.floor(Math.random() * (props.highestPrice - props.lowestPrice) * 0.4) + props.currentPrice - (props.highestPrice - props.lowestPrice) * 0.2);
        const day = new Date(now);
        day.setDate(day.getDate() - 6 + i);
        labels.push(day.toLocaleDateString('en-US', { weekday: 'short' }));
      }
      break;
    case '1m':
      // Generate daily data for 1 month
      for (let i = 0; i < 30; i++) {
        data.push(Math.floor(Math.random() * (props.highestPrice - props.lowestPrice) * 0.6) + props.currentPrice - (props.highestPrice - props.lowestPrice) * 0.3);
        const day = new Date(now);
        day.setDate(day.getDate() - 29 + i);
        if (i % 5 === 0) {
          labels.push(day.getDate().toString());
        } else {
          labels.push('');
        }
      }
      break;
    case '6m':
      // Generate weekly data for 6 months
      for (let i = 0; i < 24; i++) {
        data.push(Math.floor(Math.random() * (props.highestPrice - props.lowestPrice) * 0.8) + props.lowestPrice);
        const week = new Date(now);
        week.setDate(week.getDate() - 24 * 7 + i * 7);
        if (i % 4 === 0) {
          labels.push(week.toLocaleDateString('en-US', { month: 'short' }));
        } else {
          labels.push('');
        }
      }
      break;
    case '1y':
      // Generate monthly data for 1 year
      for (let i = 0; i < 12; i++) {
        data.push(Math.floor(Math.random() * (props.highestPrice - props.lowestPrice)) + props.lowestPrice);
        const month = new Date(now);
        month.setMonth(month.getMonth() - 11 + i);
        labels.push(month.toLocaleDateString('en-US', { month: 'short' }));
      }
      break;
    case 'all':
      // Generate yearly data for all time (last 5 years)
      for (let i = 0; i < 60; i++) {
        data.push(Math.floor(Math.random() * (props.highestPrice - props.lowestPrice)) + props.lowestPrice);
        const month = new Date(now);
        month.setMonth(month.getMonth() - 59 + i);
        if (i % 12 === 0) {
          labels.push(month.getFullYear().toString());
        } else {
          labels.push('');
        }
      }
      break;
  }
  
  chartData.value = data;
  timeLabels.value = labels;
};

const emit = defineEmits(['pricePointSelected']);

watch(selectedPoint, (newValue) => {
  if (newValue !== null) {
    emit('pricePointSelected', {
      price: chartData.value[newValue],
      date: timeLabels.value[newValue],
      index: newValue
    });
  }
});

const updateChart = () => {
  if (chart.value) {
    chart.value.data.labels = timeLabels.value;
    chart.value.data.datasets[0].data = chartData.value;
    
    // Update point radius to highlight selected point
    const pointRadius = Array(chartData.value.length).fill(0);
    const pointHoverRadius = Array(chartData.value.length).fill(5);
    
    if (selectedPoint.value !== null) {
      pointRadius[selectedPoint.value] = 6;
      pointHoverRadius[selectedPoint.value] = 8;
    }
    
    chart.value.data.datasets[0].pointRadius = pointRadius;
    chart.value.data.datasets[0].pointHoverRadius = pointHoverRadius;
    
    chart.value.update();
  }
};

watch(selectedPoint, () => {
  updateChart();
});

onMounted(() => {
  generateChartData(activeRange.value);
  
  const ctx = chartCanvas.value.getContext('2d');
  
  const gradient = ctx.createLinearGradient(0, 0, 0, 300);
  gradient.addColorStop(0, 'rgba(75, 75, 255, 0.6)');
  gradient.addColorStop(1, 'rgba(75, 75, 255, 0.1)');
  
  chart.value = new Chart(ctx, {
    type: 'line',
    data: {
      labels: timeLabels.value,
      datasets: [{
        label: 'Price',
        data: chartData.value,
        borderColor: '#4B4BFF',
        borderWidth: 2,
        pointBackgroundColor: 'white',
        pointBorderColor: '#4B4BFF',
        pointBorderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        tension: 0.4,
        fill: true,
        backgroundColor: gradient
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: 'nearest'
      },
      onClick: (e) => {
        handleChartClick(e);
      },
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          enabled: false
        }
      },
      scales: {
        x: {
          display: false
        },
        y: {
          display: false,
          min: props.lowestPrice * 0.9,
          max: props.highestPrice * 1.1
        }
      },
      elements: {
        line: {
          tension: 0.4
        }
      }
    }
  });
});

onUnmounted(() => {
  if (chart.value) {
    chart.value.destroy();
  }
});
</script>

<style scoped lang="scss">
.statistic-chart {
  background-color: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  height: 100%;
  
  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
    
    h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: #333;
    }
    
    .subtitle {
      margin: 4px 0 0;
      font-size: 14px;
      color: #666;
    }
    
    .time-range {
      display: flex;
      gap: 4px;
      
      button {
        background: none;
        border: none;
        padding: 4px 10px;
        font-size: 12px;
        border-radius: 12px;
        cursor: pointer;
        color: #666;
        transition: all 0.2s ease;
        
        &:hover {
          background-color: #f5f5f5;
        }
        
        &.active {
          background-color: #4B4BFF;
          color: white;
        }
      }
    }
  }
  
  .price-info {
    margin-bottom: 20px;
    
    .current-price {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      margin-bottom: 16px;
      
      h2 {
        font-size: 28px;
        font-weight: 700;
        margin: 0;
        line-height: 1;
      }
      
      .price-change {
        font-size: 14px;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 12px;
        
        &.positive {
          color: #4CAF50;
          background-color: rgba(76, 175, 80, 0.1);
        }
        
        &.negative {
          color: #FF5252;
          background-color: rgba(255, 82, 82, 0.1);
        }
      }
    }
    
    .price-range {
      display: flex;
      flex-direction: column;
      gap: 8px;
      
      .range-line {
        height: 4px;
        background-color: #f0f0f0;
        border-radius: 2px;
        position: relative;
        margin: 4px 0;
        
        .range-indicator {
          position: absolute;
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background-color: #4B4BFF;
          top: 50%;
          transform: translate(-50%, -50%);
        }
      }
      
      .range-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .label {
          font-size: 12px;
          color: #666;
        }
        
        .value {
          font-size: 12px;
          font-weight: 600;
          color: #333;
        }
      }
    }
  }
  
  .chart-container {
    height: 200px;
    position: relative;
    
    &:hover {
      cursor: pointer;
    }
    
    .price-marker {
      position: absolute;
      width: 1px;
      height: calc(100% + 20px);
      background-color: rgba(75, 75, 255, 0.5);
      bottom: 0;
      pointer-events: none;
      transition: left 0.2s ease;
      
      &::after {
        content: '';
        position: absolute;
        top: attr(data-y);
        left: -4px;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #4B4BFF;
        box-shadow: 0 0 0 3px rgba(75, 75, 255, 0.2);
      }
      
      .price-tag {
        position: absolute;
        top: -40px;
        left: 50%;
        transform: translateX(-50%);
        background-color: #4B4BFF;
        color: white;
        padding: 5px 10px;
        border-radius: 5px;
        font-size: 14px;
        font-weight: 500;
        white-space: nowrap;
        z-index: 10;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        animation: fadeIn 0.2s ease;
      }
      
      .date-tag {
        position: absolute;
        top: -20px;
        left: 50%;
        transform: translateX(-50%);
        background-color: rgba(75, 75, 255, 0.9);
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 12px;
        white-space: nowrap;
        z-index: 10;
        animation: fadeIn 0.2s ease;
      }
    }
  }
  
  .timeline {
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    
    span {
      font-size: 12px;
      color: #666;
      text-align: center;
    }
  }
  
  @media (max-width: 768px) {
    padding: 16px;
    
    .chart-header {
      flex-direction: column;
      gap: 10px;
      
      .time-range {
        width: 100%;
        justify-content: space-between;
      }
    }
    
    .price-info .current-price h2 {
      font-size: 24px;
    }
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}
</style> 