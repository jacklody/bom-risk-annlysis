<template>
  <div class="market-trends-page">
    <header class="page-header">
      <div>
        <h2>趋势预警</h2>
        <p>基于现有市场事件、复核信号和 BOM 命中结果生成只读趋势判断。</p>
      </div>
      <el-button data-testid="trends-refresh" :loading="loading" type="primary" @click="loadAll">刷新</el-button>
    </header>

    <section class="summary-grid">
      <el-card v-for="card in summaryCards" :key="card.label" class="summary-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </el-card>
    </section>

    <el-card class="section-card">
      <div class="section-header">
        <h3>趋势分布</h3>
        <el-select v-model="days" data-testid="trends-days" @change="loadTimeline">
          <el-option label="近 7 天" :value="7" />
          <el-option label="近 30 天" :value="30" />
          <el-option label="近 90 天" :value="90" />
        </el-select>
      </div>
      <p v-if="!hasTrendData">暂无趋势数据</p>
      <div v-else class="trend-columns">
        <div>
          <h4>品牌排行</h4>
          <div v-for="row in timeline.brand_rank" :key="row.brand" class="rank-row">
            <strong>{{ displayValue(row.brand) }}</strong>
            <span>事件 {{ row.event_count }} / 物料 {{ row.item_count }}</span>
          </div>
        </div>
        <div>
          <h4>品类排行</h4>
          <div v-for="row in timeline.category_rank" :key="row.category" class="rank-row">
            <strong>{{ displayValue(row.category) }}</strong>
            <span>事件 {{ row.event_count }} / 物料 {{ row.item_count }}</span>
          </div>
        </div>
        <div>
          <h4>每日事件</h4>
          <div v-for="row in timeline.daily_events" :key="row.date" class="rank-row">
            <strong>{{ row.date }}</strong>
            <span>事件 {{ row.event_count }} / 高风险 {{ row.high_severity_event_count }}</span>
          </div>
        </div>
        <div>
          <h4>严重度分布</h4>
          <div v-for="row in severityRows" :key="row.severity" class="rank-row">
            <span>{{ severityText(row.severity) }} {{ row.count }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="section-card">
      <h3>预测验证</h3>
      <div class="validation-grid">
        <p><span>已命中风险：</span>{{ validation.risk_hit_count ?? 0 }}</p>
        <p><span>暂未命中：</span>{{ validation.not_hit_yet_count ?? 0 }}</p>
        <p><span>待复核：</span>{{ validation.needs_review_count ?? 0 }}</p>
        <p><span>命中率：</span>{{ percent(validation.hit_rate) }}</p>
      </div>
      <div class="validation-audit-form">
        <label class="field">
          <span>复盘人</span>
          <input v-model="validationForm.reviewer" data-testid="validation-reviewer" class="native-input" placeholder="例如：采购复盘张三" />
        </label>
        <label class="field wide">
          <span>复盘备注</span>
          <textarea v-model="validationForm.notes" data-testid="validation-notes" class="native-textarea" rows="3" placeholder="记录供应商确认、BOM 命中依据或误报原因" />
        </label>
      </div>
      <div class="validation-events">
        <h4>待复盘事件</h4>
        <p v-if="!validation.events?.length" class="empty-hint">暂无待复盘事件</p>
        <article v-for="event in validation.events" v-else :key="event.event_id" class="record-card">
          <div>
            <el-tag size="small">{{ validationStatusText(event.validation_status) }}</el-tag>
            <button class="event-title-button" type="button" @click="openValidationEvent(event)">{{ validationEventTitle(event) }}</button>
          </div>
          <p>来源：{{ displayValue(event.source_name) }} / 事件ID：{{ event.event_id }}</p>
          <p>影响项目：{{ event.project_count }} / 影响物料：{{ event.item_count }}</p>
          <p>触发条件：{{ event.trigger_reason || validationTriggerText(event) }}</p>
          <p>影响原则：{{ impactPrincipleText(event) }}</p>
          <div class="record-actions">
            <el-button size="small" type="primary" :data-testid="`validation-open-event-${event.event_id}`" @click="openValidationEvent(event)">查看事件源头</el-button>
            <el-button size="small" type="success" data-testid="validation-confirm-hit" @click="createReviewRecord(event, 'confirmed_hit')">确认命中</el-button>
            <el-button size="small" data-testid="validation-watch" @click="createReviewRecord(event, 'watching')">继续观察</el-button>
            <el-button size="small" type="warning" data-testid="validation-false-positive" @click="createReviewRecord(event, 'false_positive')">标记误报</el-button>
          </div>
        </article>
      </div>
      <div class="validation-records">
        <h4>复盘记录</h4>
        <p v-if="!validation.recent_records?.length" class="empty-hint">暂无复盘记录</p>
        <article v-for="record in validation.recent_records" v-else :key="record.id" class="record-card">
          <div>
            <el-tag size="small">{{ outcomeText(record.outcome) }}</el-tag>
            <button class="event-title-button" type="button" @click="openValidationEvent(record)">{{ validationRecordTitle(record) }}</button>
          </div>
          <p>事件ID：{{ record.event_id }} / 复盘人：{{ displayValue(record.reviewer) }} / 影响项目：{{ record.affected_project_count }} / 影响物料：{{ record.affected_item_count }}</p>
          <p v-if="record.notes">{{ record.notes }}</p>
        </article>
      </div>
    </el-card>

    <el-card class="section-card">
      <h3>主动预警行动队列</h3>
      <p v-if="!actions.length">暂无主动预警动作</p>
      <div v-else class="action-list">
        <article v-for="action in actions" :key="action.id" class="action-card">
          <div>
            <el-tag>{{ priorityText(action.priority) }}</el-tag>
            <strong>{{ action.title }}</strong>
          </div>
          <p>{{ action.reason }}</p>
          <p>触发条件：{{ action.trigger_reason || action.reason || '暂无' }}</p>
          <p>影响原则：{{ actionImpactPrincipleText(action) }}</p>
          <p>品牌：{{ displayValue(action.brand) }} / 品类：{{ displayValue(action.category) }}</p>
          <p>影响项目：{{ action.project_count }} / 影响物料：{{ action.item_count }}</p>
          <el-button size="small" data-testid="action-open-events" @click="openActionEvent(action)">查看事件</el-button>
          <el-button size="small" data-testid="action-go-events" @click="goEvents(action)">前往事件库</el-button>
        </article>
      </div>
    </el-card>

    <MarketEventDetailDrawer
      v-model="detailVisible"
      :event="selectedEvent"
      :impact="eventImpact"
      :source-signal="sourceSignal"
      :operating-status="false"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createPredictionValidationRecord, getTrendActions, getTrendSummary, getTrendTimeline, getTrendValidation } from '../api/marketTrends'
import MarketEventDetailDrawer from '../components/MarketEventDetailDrawer.vue'
import { useMarketEventDetail } from '../composables/useMarketEventDetail'

const router = useRouter()
const loading = ref(false)
const days = ref(30)
const summary = ref({})
const timeline = ref({ daily_events: [], brand_rank: [], category_rank: [], severity_counts: {} })
const validation = ref({})
const actions = ref([])
const validationForm = reactive({ reviewer: '趋势复盘', notes: '' })
const {
  detailVisible,
  selectedEvent,
  eventImpact,
  sourceSignal,
  openEventDetail
} = useMarketEventDetail()

const summaryCards = computed(() => [
  { label: '活跃事件', value: summary.value.active_event_count ?? 0 },
  { label: '高风险事件', value: summary.value.high_severity_event_count ?? 0 },
  { label: '近 7 天新增', value: summary.value.new_events_7d ?? 0 },
  { label: '受影响项目', value: summary.value.affected_project_count ?? 0 },
  { label: '受影响物料', value: summary.value.affected_item_count ?? 0 },
  { label: '主动预警动作', value: summary.value.action_count ?? 0 }
])

const severityRows = computed(() => {
  return Object.entries(timeline.value.severity_counts || {})
    .filter(([, count]) => Number(count) > 0)
    .map(([severity, count]) => ({ severity, count }))
})

const hasTrendData = computed(() => {
  return Boolean(
    timeline.value.daily_events?.length ||
    timeline.value.brand_rank?.length ||
    timeline.value.category_rank?.length ||
    severityRows.value.length
  )
})

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '暂无' : value
}

function percent(value) {
  if (value === null || value === undefined) return '0%'
  return `${Math.round(Number(value) * 100)}%`
}

function severityText(severity) {
  return { critical: '严重', high: '高', medium: '中', low: '低', unknown: '未知' }[severity] || displayValue(severity)
}

function priorityText(priority) {
  return { high: '高', medium: '中', low: '低' }[priority] || displayValue(priority)
}

function outcomeText(outcome) {
  return {
    confirmed_hit: '命中确认',
    false_positive: '误报确认',
    watching: '继续观察',
    dismissed: '已忽略'
  }[outcome] || displayValue(outcome)
}

function validationStatusText(status) {
  return {
    risk_hit: '已命中',
    not_hit_yet: '暂未命中',
    needs_review: '待复核'
  }[status] || displayValue(status)
}

function validationEventTitle(event) {
  if (event?.title) return event.title
  if (event?.raw_title) return event.raw_title
  const parts = [event?.brand, event?.category, event?.event_type].filter(Boolean)
  if (parts.length) return parts.join(' / ')
  return `未命名事件 ${event?.event_id ?? ''}`.trim()
}

function validationRecordTitle(record) {
  const matched = validation.value?.events?.find(event => event.event_id === record.event_id)
  if (matched) return validationEventTitle(matched)
  return `未命名事件 ${record.event_id}`
}

function validationTriggerText(event) {
  return `验证状态 ${validationStatusText(event.validation_status)}，已命中 ${event.project_count ?? 0} 个项目 ${event.item_count ?? 0} 个物料`
}

function impactPrincipleText(event) {
  return `事件风险已命中 BOM 物料，需按影响项目数、物料数和风险等级确认采购优先级。当前影响 ${event.project_count ?? 0} 个项目、${event.item_count ?? 0} 个物料。`
}

function actionImpactPrincipleText(action) {
  return `事件风险已命中 BOM 物料，需按影响项目数、物料数和风险等级确认采购优先级。当前关联 ${action.project_count ?? 0} 个项目、${action.item_count ?? 0} 个物料。`
}

async function refreshValidation() {
  const { data } = await getTrendValidation()
  validation.value = data
}

async function createReviewRecord(event, outcome) {
  try {
    await createPredictionValidationRecord(event.event_id, {
      outcome,
      reviewer: validationForm.reviewer.trim() || '趋势复盘',
      notes: validationForm.notes.trim() || (outcome === 'confirmed_hit' ? '从趋势预警页确认该事件已命中风险' : '从趋势预警页记录复盘结论')
    })
    ElMessage.success('复盘记录已保存')
    await refreshValidation()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '复盘记录保存失败')
  }
}

async function loadTimeline() {
  try {
    const { data } = await getTrendTimeline({ days: Number(days.value) })
    timeline.value = data
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '趋势分布加载失败')
  }
}

async function loadAll() {
  loading.value = true
  try {
    const [{ data: summaryData }, { data: timelineData }, { data: validationData }, { data: actionsData }] = await Promise.all([
      getTrendSummary(),
      getTrendTimeline({ days: Number(days.value) }),
      getTrendValidation(),
      getTrendActions()
    ])
    summary.value = summaryData
    timeline.value = timelineData
    validation.value = validationData
    actions.value = actionsData.actions || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '趋势预警加载失败')
  } finally {
    loading.value = false
  }
}

function eventIdFromAction(action) {
  return action?.event_ids?.[0]
}

function openActionEvent(action) {
  const eventId = eventIdFromAction(action)
  if (eventId) openEventDetail(eventId)
}

function openValidationEvent(event) {
  const eventId = event?.event_id
  if (!eventId) {
    ElMessage.warning('未找到可查看的事件源头')
    return
  }
  openEventDetail(eventId)
}

function goEvents(action) {
  const query = { ...(action?.target_query || {}) }
  const eventId = eventIdFromAction(action)
  if (eventId) query.eventId = eventId
  router.push({
    path: action?.target_route || '/events',
    query
  })
}

onMounted(loadAll)
</script>

<style scoped>
.market-trends-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header,
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.page-header p {
  color: #606266;
  margin-top: 6px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.summary-card span {
  color: #606266;
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 24px;
  color: #303133;
}

.section-card {
  width: 100%;
}

.trend-columns {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.rank-row,
.action-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  margin-top: 8px;
  background: #fff;
}

.rank-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.validation-grid,
.validation-audit-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.validation-audit-form {
  margin-top: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #606266;
}

.field.wide {
  grid-column: span 2;
}

.native-input,
.native-textarea {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 8px;
  font: inherit;
}

.validation-events,
.validation-records {
  margin-top: 16px;
}

.record-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 10px;
  margin-top: 8px;
  background: #f8fbff;
}

.event-title-button {
  margin-left: 8px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #1f5eff;
  font-weight: 700;
  cursor: pointer;
}

.event-title-button:hover {
  text-decoration: underline;
}

.record-card div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.record-actions {
  margin-top: 8px;
  flex-wrap: wrap;
}

.record-card p,
.empty-hint {
  margin-top: 8px;
  color: #606266;
}

.action-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 12px;
}

.action-card div {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-card p {
  margin-top: 8px;
  color: #606266;
}

@media (max-width: 900px) {
  .trend-columns {
    grid-template-columns: 1fr;
  }

  .page-header,
  .section-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
