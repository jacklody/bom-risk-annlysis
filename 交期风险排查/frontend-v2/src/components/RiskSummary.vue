<template>
  <div class="risk-summary">
    <div
      v-for="card in cards"
      :key="card.level"
      class="risk-summary-card"
      :class="{ active: active === card.level }"
      @click="$emit('click-card', card.level)"
    >
      <span class="risk-summary-label">{{ card.label }}</span>
      <strong>{{ summary?.[card.level] ?? 0 }}</strong>
    </div>
  </div>
</template>

<script setup>
defineEmits(['click-card'])

defineProps({
  summary: { type: Object, default: () => ({}) },
  active: { type: String, default: '' }
})

const cards = [
  { level: 'red', label: '高风险' },
  { level: 'yellow', label: '关注' },
  { level: 'green', label: '安全' },
  { level: 'gray', label: '未知' }
]
</script>

<style scoped>
.risk-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.risk-summary-card {
  padding: 12px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  cursor: pointer;
}

.risk-summary-card.active {
  border-color: #409eff;
}

.risk-summary-label {
  display: block;
  color: #909399;
  font-size: 12px;
  margin-bottom: 4px;
}
</style>
