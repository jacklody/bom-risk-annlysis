<template>
  <div class="bom-impact-panel">
    <div class="panel-header">
      <h2 class="panel-title">BOM影响和处理建议</h2>
      <div class="header-actions">
        <el-select v-model="roleFilter" size="small" placeholder="角色筛选" clearable style="width: 110px;">
          <el-option label="全部角色" value="" />
          <el-option label="采购" value="purchase" />
          <el-option label="研发" value="rd" />
          <el-option label="项目管理" value="pm" />
        </el-select>
      </div>
    </div>

    <div class="summary-bar">
      <div class="summary-item" v-for="stat in summaryStats" :key="stat.label">
        <span class="summary-value" :style="{ color: stat.color }">{{ stat.value }}</span>
        <span class="summary-label">{{ stat.label }}</span>
      </div>
    </div>

    <div class="impact-list">
      <div v-for="item in filteredItems" :key="item.mpn"
        class="impact-card"
        :class="[item.risk_level, { expanded: expandedMpn === item.mpn }]"
        @click="toggleExpand(item.mpn)"
      >
        <div class="impact-header">
          <div class="mpn-info">
            <span class="mpn-name">{{ item.mpn }}</span>
            <span class="manufacturer">{{ item.manufacturer }}</span>
          </div>
          <div class="risk-info">
            <el-tag :color="getRiskColor(item.risk_level)" size="small"
              effect="dark" style="color: #fff; border: none;">
              {{ riskLabel(item.risk_level) }}
            </el-tag>
            <span class="risk-score">{{ item.risk_score }}分</span>
          </div>
        </div>

        <div class="impact-body">
          <div class="impact-meta">
            <el-tag size="small" effect="plain" class="category-tag">{{ item.category }}</el-tag>
            <el-tag size="small" :type="lifecycleType(item.lifecycle_status)" effect="plain" class="lifecycle-tag">
              {{ item.lifecycle_status }}
            </el-tag>
          </div>

          <div class="trigger-events">
            <span class="meta-label">触发事件：</span>
            <div class="event-tags">
              <el-tag v-for="(evt, idx) in item.trigger_events" :key="idx"
                size="small" type="warning" effect="plain" class="event-tag">
                {{ evt }}
              </el-tag>
            </div>
          </div>
        </div>

        <transition name="expand">
          <div v-if="expandedMpn === item.mpn" class="impact-suggestions">
            <div class="suggestion-title">
              <span>处理建议</span>
              <el-divider style="margin: 6px 0;" />
            </div>
            <div v-for="(sug, idx) in filteredSuggestions(item)" :key="idx" class="suggestion-item">
              <el-tag :type="roleTagType(sug.role)" size="small" effect="dark" class="role-tag">
                {{ roleLabel(sug.role) }}
              </el-tag>
              <p class="suggestion-text">{{ sug.action }}</p>
            </div>
            <el-button size="small" text type="primary" class="detail-link" @click.stop="openDetail(item)">
              查看物料风险详情 →
            </el-button>
          </div>
        </transition>
      </div>

      <el-empty v-if="filteredItems.length === 0" description="暂无受影响的BOM物料" :image-size="60" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  bomImpacts: { type: Array, default: () => [] }
})

const emit = defineEmits(['open-detail'])

const expandedMpn = ref(null)
const roleFilter = ref('')

const riskColors = {
  red: '#F56C6C',
  orange: '#E6A23C',
  yellow: '#E6D23C',
  green: '#67C23A',
  gray: '#909399'
}

const sortedItems = computed(() => {
  return [...props.bomImpacts].sort((a, b) => b.risk_score - a.risk_score)
})

const filteredItems = computed(() => {
  if (!roleFilter.value) return sortedItems.value
  return sortedItems.value.filter(item =>
    item.suggestions.some(s => s.role === roleFilter.value)
  )
})

const summaryStats = computed(() => {
  const items = props.bomImpacts
  return [
    { label: '高风险', value: items.filter(i => i.risk_level === 'red').length, color: '#F56C6C' },
    { label: '中风险', value: items.filter(i => i.risk_level === 'orange').length, color: '#E6A23C' },
    { label: '低风险', value: items.filter(i => i.risk_level === 'yellow').length, color: '#E6D23C' },
    { label: 'EOL', value: items.filter(i => i.lifecycle_status === 'EOL').length, color: '#F56C6C' }
  ]
})

function toggleExpand(mpn) {
  expandedMpn.value = expandedMpn.value === mpn ? null : mpn
}

function getRiskColor(level) {
  return riskColors[level] || riskColors.gray
}

function riskLabel(level) {
  return { red: '高风险', orange: '中风险', yellow: '低风险', green: '安全', gray: '未知' }[level] || level
}

function lifecycleType(status) {
  return { Active: 'success', NRND: 'warning', EOL: 'danger', Unknown: 'info' }[status] || 'info'
}

function roleTagType(role) {
  return { purchase: 'warning', rd: '', pm: 'success' }[role] || 'info'
}

function roleLabel(role) {
  return { purchase: '采购', rd: '研发', pm: '项目管理' }[role] || role
}

function filteredSuggestions(item) {
  if (!roleFilter.value) return item.suggestions
  return item.suggestions.filter(s => s.role === roleFilter.value)
}

function openDetail(item) {
  emit('open-detail', item)
}
</script>

<style scoped>
.bom-impact-panel {
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

.summary-bar {
  display: flex;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid #f0f2f5;
  flex-shrink: 0;
}

.summary-item {
  flex: 1;
  text-align: center;
  padding: 6px 4px;
  background: #fafbfc;
  border-radius: 8px;
}

.summary-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}

.summary-label {
  font-size: 11px;
  color: #909399;
}

.impact-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
}

.impact-list::-webkit-scrollbar {
  width: 4px;
}
.impact-list::-webkit-scrollbar-thumb {
  background: #d0d5dd;
  border-radius: 2px;
}

.impact-card {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #fff;
}

.impact-card:hover {
  border-color: #c0c6c8;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.impact-card.red { border-left: 3px solid #F56C6C; }
.impact-card.orange { border-left: 3px solid #E6A23C; }
.impact-card.yellow { border-left: 3px solid #E6D23C; }
.impact-card.green { border-left: 3px solid #67C23A; }

.impact-card.expanded {
  background: #fafbfc;
  border-color: #b0b6c0;
}

.impact-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.mpn-info {
  flex: 1;
  min-width: 0;
}

.mpn-name {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  word-break: break-all;
}

.manufacturer {
  display: block;
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.risk-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.risk-score {
  font-size: 12px;
  font-weight: 600;
  color: #667085;
}

.impact-body {
  margin-top: 8px;
}

.impact-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.trigger-events {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  flex-wrap: wrap;
}

.meta-label {
  font-size: 11px;
  color: #909399;
  flex-shrink: 0;
  margin-top: 2px;
}

.event-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.event-tag {
  font-size: 11px;
}

.impact-suggestions {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e5e7eb;
}

.suggestion-title {
  font-size: 12px;
  font-weight: 600;
  color: #667085;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.role-tag {
  flex-shrink: 0;
  margin-top: 1px;
}

.suggestion-text {
  margin: 0;
  font-size: 12px;
  color: #1f2937;
  line-height: 1.6;
}

.detail-link {
  margin-top: 4px;
  font-size: 12px;
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.25s ease;
  max-height: 300px;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
