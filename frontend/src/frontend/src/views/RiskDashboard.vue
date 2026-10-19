<template>
  <div class="page-container risk-dashboard-page" v-loading="loading">
    <div class="dashboard-header">
      <div>
        <h2>风险仪表盘</h2>
        <p>汇总 BOM 项目、品类、近期事件、行动队列和供应源状态。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadSummary">刷新</el-button>
    </div>

    <div class="overview-grid">
      <el-card v-for="card in overviewCards" :key="card.label" class="overview-card">
        <span class="overview-label">{{ card.label }}</span>
        <strong class="overview-value">{{ card.value }}</strong>
      </el-card>
    </div>

    <el-card class="dashboard-card risk-change-card">
      <template #header>
        <div class="section-header">
          <h3>风险变化摘要</h3>
          <span>近 {{ riskChanges.window_days || 7 }} 天变化，可作为后续定时扫描与通知输入</span>
        </div>
      </template>
      <div class="change-summary-grid">
        <div v-for="card in riskChangeCards" :key="card.label" class="change-summary-item">
          <span class="overview-label">{{ card.label }}</span>
          <strong class="overview-value">{{ card.value }}</strong>
        </div>
      </div>
      <p class="notification-summary">{{ riskChanges.notification_summary || '暂无新增红黄风险或近7天活跃事件。' }}</p>
      <div class="notification-preview-box">
        <div>
          <h4>通知预览</h4>
          <strong>{{ notificationPreview.subject || 'BOM风险变化提醒：暂无预览' }}</strong>
          <p>{{ notificationPreview.body || '暂无可通知内容。' }}</p>
        </div>
        <el-button
          type="primary"
          plain
          data-testid="prepare-notification"
          :loading="notificationPreparing"
          :disabled="notificationPreview.ready === false"
          @click="prepareNotification"
        >
          准备手动通知
        </el-button>
      </div>
      <div class="notification-channel-box">
        <div class="channel-header">
          <h4>通知通道</h4>
          <div class="channel-actions">
            <el-button
              type="success"
              plain
              data-testid="send-test-notification"
              :loading="testNotificationSending"
              :disabled="notificationPreview.ready === false"
              @click="sendTestNotification"
            >
              发送测试通知
            </el-button>
            <el-button
              v-if="emailChannelAvailable"
              type="warning"
              plain
              data-testid="send-email-notification"
              :loading="emailNotificationSending"
              :disabled="notificationPreview.ready === false"
              @click="sendEmailNotification"
            >
              发送邮件通知
            </el-button>
          </div>
        </div>
        <div class="channel-list">
          <div v-for="channel in notificationChannels" :key="channel.channel" class="channel-row">
            <span>{{ channel.label }}</span>
            <span>{{ channel.configured ? '已配置' : '未配置' }}</span>
            <span>{{ channel.external_delivery ? '外发通道' : '人工处理' }}</span>
          </div>
        </div>
      </div>
      <div class="notification-history-box">
        <h4>通知执行历史</h4>
        <el-empty v-if="!notificationHistory.length" description="暂无通知执行记录" />
        <div v-else class="history-list">
          <div v-for="record in notificationHistory" :key="record.id" class="history-row">
            <span>{{ record.subject }}</span>
            <span>{{ record.idempotency_key || '未设置通知键' }}</span>
            <span>{{ record.status }}</span>
            <span>{{ record.delivered ? '已发送' : '未外发' }}</span>
            <span>{{ record.failure_reason || record.delivered_at || '无失败原因' }}</span>
          </div>
        </div>
      </div>
      <el-empty v-if="!riskChangeProjects.length && !riskChangeEvents.length" description="暂无风险变化数据" />
      <div v-else class="risk-change-lists">
        <div>
          <h4>变化项目</h4>
          <div v-for="project in riskChangeProjects" :key="project.project_id" class="change-row">
            <span>{{ project.project_name }}</span>
            <span>新增红色风险 {{ project.new_red_count || 0 }} 项 / 黄色风险 {{ project.new_yellow_count || 0 }} 项</span>
            <el-button link type="primary" @click="openProject(project)">查看项目</el-button>
          </div>
        </div>
        <div>
          <h4>新增事件</h4>
          <div v-for="event in riskChangeEvents" :key="event.id" class="change-row">
            <span>{{ event.title }}</span>
            <el-button link type="primary" @click="openEvent(event)">查看事件</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <el-card class="dashboard-card">
      <template #header>
        <div class="section-header">
          <h3>项目风险</h3>
          <span>统计口径：{{ summary?.overview?.risk_stat_note || '高风险项目定义为红色物料数大于 0 的项目' }}</span>
        </div>
      </template>
      <el-empty v-if="!projectRisks.length" description="暂无项目风险数据" />
      <el-table v-else :data="projectRisks">
        <el-table-column prop="project_name" label="项目" />
        <el-table-column label="红/黄/绿/灰">
          <template #default="{ row }">
            <span class="risk-count danger">红{{ riskCount(row, 'red') }}</span>
            <span class="risk-count warning">黄{{ riskCount(row, 'yellow') }}</span>
            <span class="risk-count success">绿{{ riskCount(row, 'green') }}</span>
            <span class="risk-count">灰{{ riskCount(row, 'gray') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作">
          <template #default="{ row }">
            <el-button link type="primary" @click="openProject(row)">查看项目</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="dashboard-two-col">
      <el-card class="dashboard-card">
        <template #header><h3>品类风险</h3></template>
        <el-empty v-if="!categoryRisks.length" description="暂无品类风险数据" />
        <el-table v-else :data="categoryRisks">
          <el-table-column prop="category" label="品类" />
          <el-table-column label="风险数">
            <template #default="{ row }">红{{ row.red_count ?? row.red ?? 0 }} / 黄{{ row.yellow_count ?? row.yellow ?? 0 }}</template>
          </el-table-column>
          <el-table-column label="关联事件">
            <template #default="{ row }">
              <span>{{ row.related_event_count ?? row.event_count ?? 0 }}</span>
              <el-button v-if="firstEventId(row)" link type="primary" @click="openCategoryEvents(row)">查看源头</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="dashboard-card">
        <template #header><h3>供应源状态</h3></template>
        <el-empty v-if="!supplySources.length" description="暂无供应源状态" />
        <el-table v-else :data="supplySources">
          <el-table-column label="来源">
            <template #default="{ row }">{{ row.name || row.source || row.source_id }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" />
          <el-table-column label="说明">
            <template #default="{ row }">{{ row.failure_reason || row.error_reason || '可用' }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <div class="dashboard-two-col">
      <el-card class="dashboard-card">
        <template #header><h3>近期活跃事件</h3></template>
        <el-empty v-if="!recentEvents.length" description="暂无近期活跃事件" />
        <el-table v-else :data="recentEvents">
          <el-table-column prop="title" label="事件" />
          <el-table-column prop="source_name" label="来源" />
          <el-table-column label="影响物料">
            <template #default="{ row }">{{ row.impact_item_count || 0 }}</template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEvent(row)">查看源头</el-button>
              <el-button link type="primary" @click="goEventLibrary(row)">前往事件库</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card class="dashboard-card">
        <template #header><h3>趋势行动摘要</h3></template>
        <el-empty v-if="!trendActions.length" description="暂无行动建议" />
        <el-table v-else :data="trendActions">
          <el-table-column prop="title" label="行动" />
          <el-table-column prop="priority" label="优先级" />
          <el-table-column label="影响范围">
            <template #default="{ row }">{{ row.project_count || 0 }} 项 / {{ row.item_count || 0 }} 物料</template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="{ row }"><el-button link type="primary" @click="openAction(row)">追踪</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { dispatchDashboardNotification, getDashboardNotificationChannels, getDashboardNotificationHistory, getDashboardNotificationPreview, getDashboardSummary } from '../api/dashboard'
import MarketEventDetailDrawer from '../components/MarketEventDetailDrawer.vue'
import { useMarketEventDetail } from '../composables/useMarketEventDetail'

const router = useRouter()
const loading = ref(false)
const notificationPreparing = ref(false)
const testNotificationSending = ref(false)
const emailNotificationSending = ref(false)
const summary = ref(null)
const notificationPreview = ref({})
const notificationHistory = ref([])
const notificationChannels = ref([])
const {
  detailVisible,
  selectedEvent,
  eventImpact,
  sourceSignal,
  openEventDetail
} = useMarketEventDetail()

const overview = computed(() => summary.value?.overview || {})
const projectRisks = computed(() => summary.value?.project_risks || [])
const categoryRisks = computed(() => summary.value?.category_risks || [])
const recentEvents = computed(() => summary.value?.recent_events || [])
const trendActions = computed(() => summary.value?.trend_actions || [])
const riskChanges = computed(() => summary.value?.risk_changes || {})
const riskChangeProjects = computed(() => riskChanges.value.projects || [])
const riskChangeEvents = computed(() => riskChanges.value.events || [])
const supplySources = computed(() => summary.value?.supply_sources || [])
const emailChannelAvailable = computed(() => notificationChannels.value.some(
  channel => channel.channel === 'email' && channel.enabled && channel.configured
))

const overviewCards = computed(() => [
  { label: '项目总数', value: overview.value.project_count ?? 0 },
  { label: '高风险项目', value: overview.value.high_risk_project_count ?? 0 },
  { label: '红色物料', value: overview.value.red_item_count ?? 0 },
  { label: '30天活跃事件', value: overview.value.active_event_count_30d ?? 0 },
  { label: '待处理行动', value: overview.value.pending_action_count ?? 0 }
])

const riskChangeCards = computed(() => [
  { label: '新增红色风险', value: riskChanges.value.new_red_item_count ?? 0 },
  { label: '新增黄色风险', value: riskChanges.value.new_yellow_item_count ?? 0 },
  { label: '变化项目', value: riskChanges.value.changed_project_count ?? 0 },
  { label: '近7天事件', value: riskChanges.value.recent_event_count_7d ?? 0 }
])

onMounted(loadSummary)

async function loadSummary() {
  loading.value = true
  try {
    const [{ data }, previewResp, historyResp, channelsResp] = await Promise.all([
      getDashboardSummary(),
      getDashboardNotificationPreview('manual'),
      getDashboardNotificationHistory(20),
      getDashboardNotificationChannels()
    ])
    summary.value = data
    notificationPreview.value = previewResp.data
    notificationHistory.value = historyResp.data?.records || []
    notificationChannels.value = channelsResp.data?.channels || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '风险仪表盘加载失败')
  } finally {
    loading.value = false
  }
}

function riskCount(row, key) {
  return row?.risk_counts?.[key] ?? row?.[`${key}_count`] ?? row?.[key] ?? 0
}

function openProject(row) {
  router.push(row?.target_route || `/projects/${row.project_id}`)
}

function firstEventId(row) {
  if (row?.id) return row.id
  if (Array.isArray(row?.related_event_ids) && row.related_event_ids.length) return row.related_event_ids[0]
  const raw = row?.target_query?.event_ids || row?.event_ids
  const first = String(raw || '').split(',').find(Boolean)
  return first ? Number(first) : null
}

function eventQuery(row) {
  const query = { ...(row?.target_query || {}) }
  const eventId = firstEventId(row)
  if (eventId) query.eventId = eventId
  if (eventId && !query.event_ids) query.event_ids = String(eventId)
  return query
}

function openEvent(row) {
  const eventId = firstEventId(row)
  if (eventId) return openEventDetail(eventId)
}

function goEventLibrary(row) {
  router.push({ path: row?.target_route || '/events', query: eventQuery(row) })
}

function openCategoryEvents(row) {
  router.push({ path: '/events', query: eventQuery(row) })
}

function openAction(row) {
  router.push({ path: row?.target_route || '/events', query: eventQuery(row) })
}

async function prepareNotification() {
  notificationPreparing.value = true
  try {
    const { data } = await dispatchDashboardNotification({ channel: 'manual' })
    ElMessage.success(data?.message || '通知内容已准备完成')
    notificationPreview.value = data?.preview || notificationPreview.value
    const historyResp = await getDashboardNotificationHistory(20)
    notificationHistory.value = historyResp.data?.records || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '通知准备失败')
  } finally {
    notificationPreparing.value = false
  }
}

async function sendTestNotification() {
  testNotificationSending.value = true
  try {
    const { data } = await dispatchDashboardNotification({ channel: 'mock' })
    ElMessage.success(data?.message || '测试通知已发送')
    notificationPreview.value = data?.preview || notificationPreview.value
    const historyResp = await getDashboardNotificationHistory(20)
    notificationHistory.value = historyResp.data?.records || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '测试通知发送失败')
  } finally {
    testNotificationSending.value = false
  }
}

async function sendEmailNotification() {
  emailNotificationSending.value = true
  try {
    const { data } = await dispatchDashboardNotification({ channel: 'email' })
    ElMessage.success(data?.message || '邮件通知已发送')
    notificationPreview.value = data?.preview || notificationPreview.value
    const historyResp = await getDashboardNotificationHistory(20)
    notificationHistory.value = historyResp.data?.records || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '邮件通知发送失败')
  } finally {
    emailNotificationSending.value = false
  }
}

defineExpose({ openProject, openEvent, goEventLibrary, openCategoryEvents, openAction, loadSummary, prepareNotification, sendTestNotification, sendEmailNotification })
</script>

<style scoped>
.risk-dashboard-page { display: flex; flex-direction: column; gap: 18px; }
.dashboard-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.dashboard-header h2 { margin: 0; font-size: 24px; color: #1f2d3d; }
.dashboard-header p { margin: 6px 0 0; color: #7a8494; }
.overview-grid { display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 12px; }
.overview-card { border-radius: 12px; }
.overview-label { display: block; color: #909399; font-size: 13px; }
.overview-value { display: block; margin-top: 8px; font-size: 26px; color: #303133; }
.dashboard-card { border-radius: 12px; }
.section-header { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.section-header h3, .dashboard-card h3 { margin: 0; font-size: 16px; color: #303133; }
.section-header span { color: #909399; font-size: 12px; }
.dashboard-two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.risk-change-card { border-left: 4px solid #409eff; }
.change-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin-bottom: 12px; }
.change-summary-item { padding: 12px; border-radius: 10px; background: #f7f9fc; }
.notification-summary { margin: 0 0 12px; color: #606266; line-height: 1.6; }
.notification-preview-box { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 12px; margin-bottom: 12px; border-radius: 10px; background: #f0f7ff; }
.notification-preview-box h4 { margin: 0 0 6px; color: #303133; }
.notification-preview-box p { margin: 6px 0 0; white-space: pre-line; color: #606266; line-height: 1.5; }
.notification-channel-box { padding: 12px; margin-bottom: 12px; border-radius: 10px; background: #f6ffed; }
.channel-header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 8px; }
.channel-header h4 { margin: 0; color: #303133; }
.channel-actions { display: flex; justify-content: flex-end; align-items: center; gap: 8px; flex-wrap: wrap; }
.channel-list { display: flex; flex-direction: column; gap: 6px; }
.channel-row { display: grid; grid-template-columns: 1fr 90px 90px; gap: 10px; padding: 8px 0; border-top: 1px solid #e1f3d8; color: #606266; }
.notification-history-box { padding: 12px; margin-bottom: 12px; border-radius: 10px; background: #fafafa; }
.notification-history-box h4 { margin: 0 0 8px; color: #303133; }
.history-list { display: flex; flex-direction: column; gap: 6px; }
.history-row { display: grid; grid-template-columns: 2fr 1fr 90px 90px 1.5fr; gap: 10px; padding: 8px 0; border-top: 1px solid #ebeef5; color: #606266; }
.risk-change-lists { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.risk-change-lists h4 { margin: 0 0 8px; color: #303133; }
.change-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 0; border-top: 1px solid #ebeef5; color: #606266; }
.risk-count { margin-right: 10px; color: #909399; }
.risk-count.danger { color: #f56c6c; }
.risk-count.warning { color: #e6a23c; }
.risk-count.success { color: #67c23a; }
@media (max-width: 1200px) { .overview-grid, .change-summary-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); } .dashboard-two-col, .risk-change-lists { grid-template-columns: 1fr; } }
</style>
