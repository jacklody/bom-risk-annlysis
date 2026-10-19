<template>
  <div class="risk-signal-flow">
    <div class="panel-header">
      <h2 class="panel-title">风险信号流</h2>
      <div class="header-actions">
        <el-tag v-for="f in typeFilters" :key="f.value"
          :type="activeType === f.value ? '' : 'info'"
          :effect="activeType === f.value ? 'dark' : 'plain'"
          size="small"
          class="filter-tag"
          @click="activeType = activeType === f.value ? 'all' : f.value"
        >{{ f.label }}</el-tag>
      </div>
    </div>

    <div class="signal-list" ref="signalListRef">
      <div v-for="signal in visibleSignals" :key="signal.id"
        class="signal-item"
        :class="[signal.severity, { expanded: expandedId === signal.id }]"
        @click="toggleExpand(signal.id)"
      >
        <div class="signal-main">
          <div class="signal-left">
            <span class="level-badge" :class="signal.level">{{ signal.level }}</span>
            <span class="type-icon" :title="typeLabel(signal.type)">
              {{ typeIcon(signal.type) }}
            </span>
          </div>
          <div class="signal-center">
            <p class="signal-title">{{ signal.title }}</p>
            <div class="signal-meta">
              <el-tag size="small" effect="plain" class="category-tag">{{ signal.category }}</el-tag>
              <span class="signal-time">{{ formatTime(signal.timestamp) }}</span>
            </div>
          </div>
          <div class="signal-severity-dot" :class="signal.severity" />
        </div>

        <transition name="slide">
          <div v-if="expandedId === signal.id" class="signal-detail">
            <p class="detail-desc">{{ signal.description }}</p>
            <div class="detail-brands">
              <span class="detail-label">影响品牌：</span>
              <el-tag v-for="brand in signal.affected_brands" :key="brand" size="small" effect="plain" class="brand-tag">
                {{ brand }}
              </el-tag>
            </div>
            <div class="detail-chain">
              <span class="detail-label">传导链路：</span>
              <div class="chain-path">
                <span v-for="(node, idx) in signal.impact_chain" :key="idx" class="chain-node-item">
                  {{ node }}<span v-if="idx < signal.impact_chain.length - 1" class="chain-arrow">→</span>
                </span>
              </div>
            </div>
          </div>
        </transition>
      </div>

      <el-empty v-if="visibleSignals.length === 0" description="暂无风险信号" :image-size="60" />
    </div>

    <div class="signal-footer">
      <span class="footer-stat">共 {{ filteredSignals.length }} 条信号</span>
      <span class="footer-update">下次刷新：{{ countdownText }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  signals: { type: Array, default: () => [] }
})

const emit = defineEmits(['refresh'])

const activeType = ref('all')
const expandedId = ref(null)
const signalListRef = ref(null)
const countdown = ref(300) // 5 min countdown
let countdownTimer = null

const typeFilters = [
  { label: '行情', value: 'market' },
  { label: '政策', value: 'policy' },
  { label: '灾害', value: 'disaster' },
  { label: '库存', value: 'inventory' },
  { label: 'PCN', value: 'pcn' }
]

const filteredSignals = computed(() => {
  if (activeType.value === 'all') return props.signals
  return props.signals.filter(s => s.type === activeType.value)
})

const visibleSignals = computed(() => filteredSignals.value)

function toggleExpand(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function typeIcon(type) {
  return { market: '📈', policy: '📋', disaster: '🌪️', inventory: '📦', pcn: '🔄' }[type] || '📌'
}

function typeLabel(type) {
  return { market: '行情', policy: '政策', disaster: '灾害', inventory: '库存', pcn: 'PCN' }[type] || type
}

function formatTime(ts) {
  const d = new Date(ts)
  const now = new Date()
  const diff = now - d
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const countdownText = computed(() => {
  const m = Math.floor(countdown.value / 60)
  const s = countdown.value % 60
  return `${m}:${String(s).padStart(2, '0')}`
})

function startCountdown() {
  countdown.value = 300
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      countdown.value = 300
      emit('refresh')
    }
  }, 1000)
}

watch(() => props.signals, () => {
  countdown.value = 300
}, { deep: true })

onMounted(() => {
  startCountdown()
})

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<style scoped>
.risk-signal-flow {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.panel-header {
  padding: 16px 16px 12px;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

.panel-title {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.header-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.filter-tag {
  cursor: pointer;
  user-select: none;
}

.signal-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.signal-list::-webkit-scrollbar {
  width: 4px;
}
.signal-list::-webkit-scrollbar-thumb {
  background: #d0d5dd;
  border-radius: 2px;
}

.signal-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fff;
  position: relative;
}

.signal-item:hover {
  border-color: #c0c6d0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.signal-item.red {
  border-left: 3px solid #F56C6C;
}
.signal-item.orange {
  border-left: 3px solid #E6A23C;
}
.signal-item.yellow {
  border-left: 3px solid #E6D23C;
}

.signal-item.expanded {
  background: #fafbfc;
  border-color: #b0b6c0;
}

.signal-main {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.signal-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  padding-top: 2px;
}

.level-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}
.level-badge.S { background: #b42318; }
.level-badge.A { background: #dc6b2a; }
.level-badge.B { background: #e6a23c; }
.level-badge.C { background: #909399; }

.type-icon {
  font-size: 16px;
  line-height: 1;
}

.signal-center {
  flex: 1;
  min-width: 0;
}

.signal-title {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: #1f2937;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.signal-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}

.category-tag {
  flex-shrink: 0;
}

.signal-time {
  font-size: 11px;
  color: #909399;
}

.signal-severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
}
.signal-severity-dot.red { background: #F56C6C; }
.signal-severity-dot.orange { background: #E6A23C; }
.signal-severity-dot.yellow { background: #E6D23C; }

.signal-detail {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e5e7eb;
}

.detail-desc {
  margin: 0 0 8px;
  font-size: 12px;
  color: #667085;
  line-height: 1.6;
}

.detail-label {
  font-size: 12px;
  color: #667085;
  font-weight: 500;
  margin-right: 4px;
}

.detail-brands {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.brand-tag {
  font-size: 11px;
}

.detail-chain {
  margin-top: 6px;
}

.chain-path {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  margin-top: 6px;
}

.chain-node-item {
  font-size: 12px;
  color: #5b4bb7;
  font-weight: 500;
}

.chain-arrow {
  margin: 0 4px;
  color: #c0c6d0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
  max-height: 200px;
  overflow: hidden;
}
.slide-enter-from,
.slide-leave-to {
  max-height: 0;
  opacity: 0;
}

.signal-footer {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  border-top: 1px solid #ebeef5;
  flex-shrink: 0;
}

.footer-stat {
  font-size: 12px;
  color: #909399;
}

.footer-update {
  font-size: 12px;
  color: #5b4bb7;
  font-weight: 500;
}
</style>
