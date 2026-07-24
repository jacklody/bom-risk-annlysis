<template>
  <div>
    <div class="table-toolbar">
      <span class="filter-label">筛选：</span>
      <el-tag
        v-for="lv in levels" :key="lv.value"
        :type="tagType(lv.value)"
        :effect="filterLevel === lv.value ? 'dark' : 'plain'"
        class="filter-tag"
        @click="filterLevel = filterLevel === lv.value ? '' : lv.value"
      >
        {{ lv.label }} ({{ countByLevel(lv.value) }})
      </el-tag>
      <span class="total-hint">共 {{ totalCount }} 条</span>
    </div>

    <el-table
      :data="filteredItems"
      stripe
      max-height="500"
      style="margin-top: 8px"
      row-key="row_number"
      :row-class-name="rowClassName"
    >
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="raw_part_number" label="型号" min-width="180">
        <template #default="{ row }">
          <div class="part-cell">
            <strong>{{ row.raw_part_number }}</strong>
            <el-tag v-if="row.trace_highlight" size="small" type="warning" data-testid="trace-hit-tag">
              行动命中
            </el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="raw_brand" label="品牌" width="110" />
      <el-table-column prop="raw_category" label="品类" width="110" />
      <el-table-column label="综合风险" width="150" sortable prop="risk_score">
        <template #default="{ row }">
          <el-popover
            trigger="click"
            :width="420"
            placement="left"
          >
            <template #reference>
              <el-button size="small" link type="primary" class="risk-btn" data-testid="consolidated-risk-button">
                <el-tag :type="tagType(row.risk_level)" size="small">
                  {{ levelLabel(row.risk_level) }}
                </el-tag>
                <span class="risk-score">{{ row.risk_score ?? '-' }}分</span>
                <span class="risk-detail-arrow">▸</span>
              </el-button>
            </template>
            <div class="risk-breakdown">
              <div class="breakdown-row">
                <span class="breakdown-label">市场事件风险：</span>
                <el-tag :type="tagType(row.risk_level)" size="small">{{ levelLabel(row.risk_level) }}</el-tag>
              </div>
              <div v-if="hasV32(row)" class="breakdown-row">
                <span class="breakdown-label">v3.2 双轨风险：</span>
                <el-tag :type="tagType(row.v32_risk_level)" size="small">{{ levelLabel(row.v32_risk_level) }}</el-tag>
                <span v-if="row.v32_risk_score != null">({{ row.v32_risk_score }}分)</span>
                <span v-if="row.v32_primary_track" class="breakdown-detail">轨道：{{ trackLabel(row.v32_primary_track) }}</span>
              </div>
              <div class="breakdown-row">
                <span class="breakdown-label">供应/交期风险：</span>
                <el-tag :type="tagType(row.production_risk_level)" size="small">{{ productionLabel(row) }}</el-tag>
                <span v-if="row.production_risk_score != null">({{ row.production_risk_score }}分)</span>
              </div>
              <div class="breakdown-row">
                <span class="breakdown-label">综合判定原因：</span>
                <span class="breakdown-reason">{{ displayValue(row.risk_reason) }}</span>
              </div>
              <div v-if="hasV32(row)" class="breakdown-v32">
                <el-divider content-position="left">v3.2 详情</el-divider>
                <V32EvidencePanel :item="row" />
              </div>
            </div>
          </el-popover>
        </template>
      </el-table-column>
      <el-table-column label="EOL" width="105">
        <template #default="{ row }">
          <el-tag :type="eolTagType(row.eol_status)" size="small">
            {{ eolLabel(row.eol_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="供应数据" min-width="260">
        <template #default="{ row }">
          <div class="supply-cell">
            <span>{{ supplyText(row) }}</span>
            <span class="supply-life">生命周期：{{ displayValue(row.lifecycle_status) }}</span>
            <el-button
              size="small"
              link
              type="primary"
              data-testid="refresh-supply-item"
              :loading="refreshingSupplyIds.has(row.id)"
              @click="refreshRowSupply(row)"
            >
              刷新供应数据
            </el-button>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="v32_evidence_summary" label="v3.2依据摘要" min-width="240" show-overflow-tooltip />
      <el-table-column prop="v32_action_suggestion" label="v3.2处置建议" min-width="240" show-overflow-tooltip />
      <el-table-column prop="supply_risk_reason" label="排产/交期原因" min-width="240" show-overflow-tooltip />
      <el-table-column prop="procurement_suggestion" label="采购建议" min-width="260" show-overflow-tooltip />
      <el-table-column prop="risk_reason" label="综合原因" min-width="220" show-overflow-tooltip />
      <el-table-column label="关联事件" width="90">
        <template #default="{ row }">
          <el-popover
            v-if="row.matched_events && row.matched_events.length"
            trigger="click"
            :width="380"
            placement="left"
          >
            <template #reference>
              <el-button size="small" link type="primary" data-testid="matched-events-button">
                {{ row.matched_events.length }} 条
              </el-button>
            </template>
            <div v-for="e in row.matched_events" :key="e.id" class="event-pop-item">
              <div class="event-title-row">
                <el-tag :type="e.severity === 'high' ? 'danger' : e.severity === 'medium' ? 'warning' : 'info'" size="small">
                  {{ e.event_type }}
                </el-tag>
                <strong>{{ eventTitle(e) }}</strong>
              </div>
              <div class="event-source">触发源头：{{ displayValue(e.source_name) }}</div>
              <div class="event-source">命中对象：{{ displayValue(e.brand) }} / {{ displayValue(e.category) }}</div>
              <el-button size="small" link type="primary" :data-testid="`open-matched-event-${e.id}`" @click="openMatchedEvent(e)">
                打开事件源头
              </el-button>
            </div>
          </el-popover>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import V32EvidencePanel from './V32EvidencePanel.vue'
import { refreshSupplyItem } from '../api/supply'

const props = defineProps({
  items: { type: Array, default: () => [] }
})

const emit = defineEmits(['supply-refreshed', 'open-event-detail'])
const refreshingSupplyIds = ref(new Set())
const filterLevel = ref('')

const levels = [
  { value: 'red', label: '高风险' },
  { value: 'orange', label: '较高' },
  { value: 'yellow', label: '关注' },
  { value: 'green', label: '安全' },
  { value: 'gray', label: '无数据' }
]

const totalCount = computed(() => props.items.length)

function countByLevel(level) {
  return props.items.filter(i => i.risk_level === level || i.v32_risk_level === level || i.production_risk_level === level).length
}

const filteredItems = computed(() => {
  if (!filterLevel.value) return props.items
  return props.items.filter(i => i.risk_level === filterLevel.value || i.v32_risk_level === filterLevel.value || i.production_risk_level === filterLevel.value)
})

function tagType(level) {
  const map = { red: 'danger', orange: 'warning', yellow: 'warning', green: 'success', gray: 'info' }
  return map[level] || 'info'
}

function levelLabel(level) {
  const map = { red: '🔴 高', orange: '🟠 较高', yellow: '🟡 关注', green: '🟢 安全', gray: '⚪ 未知' }
  return map[level] || level || '未知'
}

function productionLabel(row) {
  const levelMap = { red: '高', orange: '较高', yellow: '关注', green: '低', gray: '未知' }
  const level = levelMap[row.production_risk_level] || '未知'
  return row.lead_time_risk_weeks ? `${level}/${row.lead_time_risk_weeks}周` : level
}

function eolTagType(status) {
  const map = { confirmed: 'danger', suspected: 'warning', none: 'success' }
  return map[status] || 'info'
}

function eolLabel(status) {
  const map = { confirmed: '确认EOL', suspected: '疑似EOL', none: '未发现' }
  return map[status] || '未知'
}

function trackLabel(track) {
  const map = {
    demand_supply: '需求/供应轨',
    material: '材料传导轨',
    information_insufficient: '信息不足',
    buffer: '缓冲因素'
  }
  return map[track] || track
}

function hasV32(row) {
  return Boolean(row.v32_risk_level || row.v32_evidence_summary || row.v32_evidence_chain?.length)
}

function rowClassName({ row }) {
  return row.trace_highlight ? 'trace-hit-row' : ''
}

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '暂无' : value
}

function supplyText(row) {
  const stock = displayValue(row.total_stock)
  const suppliers = displayValue(row.supplier_count)
  const lead = row.lead_time_days ? `${row.lead_time_days}天` : '暂无交期'
  const price = row.unit_price ? `${row.unit_price}` : '暂无价格'
  return `库存 ${stock} / 来源 ${suppliers} / ${lead} / ${price}`
}

function eventTitle(event) {
  return event.raw_title || event.title || `${displayValue(event.brand)} ${displayValue(event.category)}`
}

function openMatchedEvent(event) {
  if (event?.id) emit('open-event-detail', event.id)
}

async function refreshRowSupply(row) {
  if (!row.id) return
  refreshingSupplyIds.value = new Set([...refreshingSupplyIds.value, row.id])
  try {
    const { data } = await refreshSupplyItem(row.id)
    if (data.updated) {
      ElMessage.success('供应数据已刷新')
      emit('supply-refreshed', data.item)
    } else {
      ElMessage.warning(data.failure_reason || data.result?.error_reason || '供应数据暂不可用')
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '供应数据刷新失败')
  } finally {
    const next = new Set(refreshingSupplyIds.value)
    next.delete(row.id)
    refreshingSupplyIds.value = next
  }
}
</script>

<style scoped>
.table-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: #909399;
}

.filter-tag {
  cursor: pointer;
}

.total-hint {
  margin-left: auto;
  font-size: 12px;
  color: #c0c4cc;
}

.part-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

:deep(.trace-hit-row) {
  background: #fff7ed;
}

.v32-risk-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.v32-score {
  margin-left: 4px;
  color: #606266;
}

.track-label {
  font-size: 12px;
  color: #606266;
}

.supply-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
}

.supply-life {
  color: #909399;
}

.event-pop-item {
  padding: 6px 0;
  border-bottom: 1px solid #ebeef5;
}
.event-pop-item:last-child {
  border-bottom: none;
}
.event-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.event-source {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.text-muted {
  color: #c0c4cc;
}

.risk-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.risk-score {
  margin-left: 4px;
  color: #606266;
}

.risk-detail-arrow {
  margin-left: 2px;
  color: #909399;
  font-size: 12px;
}

.risk-breakdown {
  font-size: 13px;
  line-height: 1.8;
}

.breakdown-row {
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.breakdown-label {
  color: #606266;
  font-weight: 600;
  white-space: nowrap;
}

.breakdown-reason {
  color: #303133;
  flex: 1;
}

.breakdown-detail {
  color: #909399;
  font-size: 12px;
  margin-left: 4px;
}

.breakdown-v32 {
  margin-top: 8px;
}
</style>
