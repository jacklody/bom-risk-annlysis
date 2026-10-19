<template>
  <div class="market-events-page">
    <el-card class="filter-card">
      <template #header>
        <div class="header-row">
          <div>
            <h2>市场事件</h2>
            <p>集中查看行情收件箱、人工录入和采集任务生成的风险事件。</p>
          </div>
          <div class="header-actions">
            <el-button data-testid="events-refresh" :loading="loading" @click="loadEvents">刷新列表</el-button>
            <el-button type="primary" data-testid="events-collect" :loading="collecting" @click="handleCollect">触发采集</el-button>
          </div>
        </div>
      </template>

      <div class="filters">
        <el-input v-model="filters.brand" clearable placeholder="品牌，如 TDK" data-testid="events-filter-brand" />
        <el-input v-model="filters.category" clearable placeholder="品类，如 high_cap_mlcc" data-testid="events-filter-category" />
        <el-select v-model="filters.event_type" clearable placeholder="事件类型" data-testid="events-filter-type">
          <el-option v-for="item in eventTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.severity" clearable placeholder="严重度" data-testid="events-filter-severity">
          <el-option v-for="item in severityOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.active_status" placeholder="活跃状态" data-testid="events-filter-active">
          <el-option label="活跃" value="active" />
          <el-option label="停用" value="inactive" />
          <el-option label="全部" value="all" />
        </el-select>
        <el-button type="primary" data-testid="events-search" @click="loadEvents">查询</el-button>
      </div>
    </el-card>

    <el-card v-if="hasTraceContext" class="trace-card" data-testid="trace-context-card">
      <template #header>
        <div class="header-row">
          <h3>行动追踪上下文</h3>
          <span class="total-text">来自趋势预警行动队列</span>
        </div>
      </template>
      <div class="trace-summary">
        <el-tag type="info">事件 {{ traceContext.eventIds.length }} 个</el-tag>
        <el-tag type="success">项目 {{ traceContext.projectIds.length }} 个</el-tag>
        <el-tag type="warning">物料 {{ traceContext.itemIds.length }} 个</el-tag>
      </div>
      <div v-if="traceContext.projectIds.length" class="trace-projects">
        <span>关联项目：</span>
        <el-button
          v-for="projectId in traceContext.projectIds"
          :key="projectId"
          size="small"
          link
          type="primary"
          :data-testid="`trace-project-${projectId}`"
          @click="openProject(projectId)"
        >
          项目 {{ projectId }}
        </el-button>
      </div>
    </el-card>

    <el-card class="list-card">
      <template #header>
        <div class="header-row">
          <h3>事件列表</h3>
          <span class="total-text">共 {{ total }} 条</span>
        </div>
      </template>

      <div v-if="!loading && !events.length" class="empty-tip" data-testid="events-empty">
        暂无市场事件。可以从行情收件箱确认信号、手动新增事件，或触发采集。
      </div>

      <el-table v-else :data="events" stripe style="width: 100%" v-loading="loading" data-testid="events-table" @row-click="openDetail">
        <el-table-column prop="brand" label="品牌" width="110">
          <template #default="scope">{{ displayValue(scope.row.brand) }}</template>
        </el-table-column>
        <el-table-column prop="category" label="品类" min-width="150">
          <template #default="scope">{{ displayValue(scope.row.category) }}</template>
        </el-table-column>
        <el-table-column prop="event_type" label="事件类型" width="130">
          <template #default="scope"><el-tag>{{ labelFor(eventTypeOptions, scope.row.event_type) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="severity" label="严重度" width="110">
          <template #default="scope"><el-tag :type="severityTag(scope.row.severity)">{{ labelFor(severityOptions, scope.row.severity) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="scope">{{ formatPercent(scope.row.confidence) }}</template>
        </el-table-column>
        <el-table-column prop="source_name" label="来源" min-width="140">
          <template #default="scope">{{ displayValue(scope.row.source_name) }}</template>
        </el-table-column>
        <el-table-column prop="raw_title" label="标题" min-width="180">
          <template #default="scope">{{ displayValue(scope.row.raw_title) }}</template>
        </el-table-column>
        <el-table-column prop="estimated_lead_time_impact_weeks" label="交期影响" width="110">
          <template #default="scope">{{ formatImpact(scope.row.estimated_lead_time_impact_weeks, '周') }}</template>
        </el-table-column>
        <el-table-column prop="estimated_price_impact_pct" label="涨价影响" width="110">
          <template #default="scope">{{ formatImpact(scope.row.estimated_price_impact_pct, '%') }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="scope">{{ formatDate(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="scope">
            <el-button size="small" link type="primary" data-testid="events-detail" @click.stop="openDetail(scope.row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <MarketEventDetailDrawer
      v-model="detailVisible"
      :event="selectedEvent"
      :impact="eventImpact"
      :source-signal="sourceSignal"
      :operating-status="operatingStatus"
      @status-change="changeEventStatus"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarketEventDetailDrawer from '../components/MarketEventDetailDrawer.vue'
import { collectEvents, listEvents, updateEventStatus } from '../api/events'
import { useMarketEventDetail } from '../composables/useMarketEventDetail'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const collecting = ref(false)
const events = ref([])
const total = ref(0)
const {
  detailVisible,
  selectedEvent,
  eventImpact,
  sourceSignal,
  openEventDetail
} = useMarketEventDetail()
const operatingStatus = ref(false)

const filters = reactive({
  brand: '',
  category: '',
  event_type: '',
  severity: '',
  active_status: 'active'
})

const eventTypeOptions = [
  { label: '缺货', value: 'shortage' },
  { label: '涨价', value: 'price_increase' },
  { label: '产能问题', value: 'capacity_issue' },
  { label: '交期延长', value: 'lead_time' },
  { label: '停产', value: 'eol' },
  { label: '政策', value: 'policy' },
  { label: '灾害', value: 'disaster' },
  { label: '其他', value: 'other' }
]

const severityOptions = [
  { label: '严重', value: 'critical' },
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
  { label: '未知', value: 'unknown' }
]

const traceContext = computed(() => ({
  eventIds: parseQueryIds(route.query?.event_ids),
  projectIds: parseQueryIds(route.query?.project_ids),
  itemIds: parseQueryIds(route.query?.item_ids)
}))

const hasTraceContext = computed(() =>
  traceContext.value.eventIds.length > 0 || traceContext.value.projectIds.length > 0 || traceContext.value.itemIds.length > 0
)

function parseQueryIds(value) {
  if (!value) return []
  const raw = Array.isArray(value) ? value.join(',') : String(value)
  return raw.split(',').map((part) => part.trim()).filter(Boolean)
}

function buildParams() {
  const params = { active_status: filters.active_status }
  if (route.query?.event_ids) {
    params.active_status = 'all'
    params.event_ids = route.query.event_ids
  }
  if (filters.brand) params.brand = filters.brand
  if (filters.category) params.category = filters.category
  if (filters.event_type) params.event_type = filters.event_type
  if (filters.severity) params.severity = filters.severity
  return params
}

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '暂无' : value
}

function noticeSourceText(notice) {
  if (!notice) return '暂无'
  const sourceType = displayValue(notice.source_type)
  const sourceName = displayValue(notice.source_name)
  if (sourceType === '暂无' && sourceName === '暂无') return '暂无'
  return `${sourceType} / ${sourceName}`
}

function formatPercent(value) {
  if (value === null || value === undefined) return '暂无'
  return `${Math.round(Number(value) * 100)}%`
}

function formatImpact(value, unit) {
  if (value === null || value === undefined || value === '') return '暂无'
  return unit === '%' ? `${value}${unit}` : `${value} ${unit}`
}

function formatDate(value) {
  if (!value) return '暂无'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function labelFor(options, value) {
  return options.find((item) => item.value === value)?.label || displayValue(value)
}

function severityTag(value) {
  if (value === 'critical' || value === 'high') return 'danger'
  if (value === 'medium') return 'warning'
  if (value === 'low') return 'success'
  return 'info'
}

function riskText(level) {
  const map = { red: '红色', yellow: '黄色', green: '绿色', gray: '灰色' }
  return map[level] || displayValue(level)
}

function eventTriggerText(event) {
  if (!event) return '暂无'
  return `严重度 ${labelFor(severityOptions, event.severity)}，置信度 ${formatPercent(event.confidence)}，交期影响 ${formatImpact(event.estimated_lead_time_impact_weeks, '周')}，价格影响 ${formatImpact(event.estimated_price_impact_pct, '%')}`
}

function isActive(event) {
  return Number(event?.is_active ?? 1) === 1
}

function openProject(projectId) {
  const query = route.query?.item_ids ? { item_ids: route.query.item_ids } : {}
  router.push({
    path: `/projects/${projectId}`,
    query
  })
}

async function loadEvents() {
  loading.value = true
  try {
    const { data } = await listEvents(buildParams())
    events.value = data.events || []
    total.value = data.total || 0
    if (route.query?.eventId) {
      await openEventDetail(route.query.eventId)
    }
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '市场事件加载失败')
    events.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function openDetail(row) {
  return openEventDetail(row)
}

async function changeEventStatus(action) {
  if (!selectedEvent.value) return
  operatingStatus.value = true
  try {
    const { data } = await updateEventStatus(selectedEvent.value.id, { action })
    selectedEvent.value = data.event
    ElMessage.success(data.message || '事件状态已更新')
    await loadEvents()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '事件状态更新失败')
  } finally {
    operatingStatus.value = false
  }
}

async function handleCollect() {
  collecting.value = true
  try {
    const { data } = await collectEvents()
    ElMessage.success(`采集完成，新增 ${data.collected || 0} 条事件`)
    await loadEvents()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '事件采集失败')
  } finally {
    collecting.value = false
  }
}

onMounted(loadEvents)
</script>

<style scoped>
.market-events-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header-row h2,
.header-row h3 {
  margin: 0;
}

.header-row p {
  margin: 6px 0 0;
  color: #6b7280;
  font-size: 13px;
}

.header-actions,
.filters,
.trace-summary,
.trace-projects {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.filters .el-input,
.filters .el-select {
  width: 190px;
}

.total-text,
.empty-tip {
  color: #6b7280;
  font-size: 13px;
}

.empty-tip {
  padding: 32px;
  text-align: center;
  background: #f8fafc;
  border-radius: 8px;
}

.detail-body section {
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid #edf2f7;
}

.detail-body h4 {
  margin: 0 0 12px;
}

.detail-body p {
  margin: 8px 0;
  line-height: 1.6;
}

.detail-body span:first-child {
  color: #6b7280;
}

.detail-actions {
  margin-top: 10px;
}

.impact-projects {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.impact-project {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 13px;
}
</style>
