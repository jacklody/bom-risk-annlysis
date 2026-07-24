<template>
  <div class="page-container project-detail-page">
    <el-card v-loading="loading" class="detail-card">
      <template #header>
        <div class="card-header">
          <div>
            <el-button link type="primary" class="back-button" @click="goBack">返回项目列表</el-button>
            <h2>{{ project?.project_name || 'BOM 项目详情' }}</h2>
            <p class="sub-title">{{ project?.filename || '加载历史 BOM 明细与风险结果' }}</p>
          </div>
          <div class="header-actions">
            <el-button data-testid="open-html-report" @click="openHtmlReport">
              打开HTML报告
            </el-button>
            <el-button data-testid="open-xlsx-report" @click="openXlsxReport">
              导出Excel报告
            </el-button>
            <el-button type="primary" :loading="loading" data-testid="refresh-project-detail" @click="loadProject()">
              刷新详情
            </el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!loading && !project" description="未找到该 BOM 项目" />

      <template v-else>
        <el-descriptions :column="4" border class="project-meta">
          <el-descriptions-item label="状态">
            <el-tag :type="project?.status === 'active' ? 'success' : 'info'" size="small">
              {{ project?.status === 'active' ? '活跃' : project?.status || '未知' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="物料数量">{{ project?.total_items || items.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="最近分析">{{ formatDate(project?.last_analysis_at) }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatDate(project?.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <div class="summary-strip">
          <div class="summary-item danger">
            <span class="summary-value">{{ project?.items_red || 0 }}</span>
            <span class="summary-label">高风险</span>
          </div>
          <div class="summary-item warning">
            <span class="summary-value">{{ project?.items_yellow || 0 }}</span>
            <span class="summary-label">关注</span>
          </div>
          <div class="summary-item success">
            <span class="summary-value">{{ project?.items_green || 0 }}</span>
            <span class="summary-label">安全</span>
          </div>
          <div class="summary-item">
            <span class="summary-value">{{ project?.items_gray || 0 }}</span>
            <span class="summary-label">无数据</span>
          </div>
        </div>

        <div v-if="traceItemIds.length" class="trace-hit-summary" data-testid="project-trace-summary">
          <el-tag type="warning" size="small">行动追踪物料</el-tag>
          <span>来自趋势预警行动队列，传入 {{ traceItemIds.length }} 个物料 ID，当前项目命中 {{ traceHitCount }} 个。</span>
        </div>

        <el-empty v-if="items.length === 0" description="该项目暂无物料明细" />
        <RiskDetailTable v-else :items="normalizedItems" @supply-refreshed="handleSupplyRefreshed" @open-event-detail="openEventDetail" />
      </template>
    </el-card>

    <!-- 风险行动报告 -->
    <el-card v-if="riskReport" class="report-card" data-testid="risk-report-card">
      <template #header>
        <div class="card-header">
          <h3>风险行动报告</h3>
          <span class="report-subtitle">基于行情情报、市场事件和供应链数据生成的采购建议</span>
        </div>
      </template>

      <div class="report-grid">
        <!-- 风险概况 -->
        <div class="report-section">
          <h4>风险概况</h4>
          <div class="summary-strip">
            <div class="summary-item danger">
              <span class="summary-value">{{ riskReport.risk_summary.red }}</span>
              <span class="summary-label">高风险</span>
            </div>
            <div class="summary-item warning">
              <span class="summary-value">{{ riskReport.risk_summary.yellow }}</span>
              <span class="summary-label">关注</span>
            </div>
            <div class="summary-item success">
              <span class="summary-value">{{ riskReport.risk_summary.green }}</span>
              <span class="summary-label">安全</span>
            </div>
            <div class="summary-item">
              <span class="summary-value">{{ riskReport.risk_summary.risk_rate }}%</span>
              <span class="summary-label">风险率</span>
            </div>
          </div>
          <el-tag v-if="riskReport.risk_summary.has_urgent" type="danger" size="small">有紧急风险</el-tag>
          <el-tag v-else type="success" size="small">暂无需紧急处理</el-tag>
        </div>

        <!-- 品类风险 -->
        <div v-if="riskReport.category_risk?.length" class="report-section">
          <h4>品类风险分布</h4>
          <div class="category-risk-list">
            <div v-for="cat in riskReport.category_risk" :key="cat.category" class="category-risk-row">
              <span class="cat-name">{{ cat.category }}</span>
              <span class="cat-bar">
                <span class="bar-red" :style="{ flex: cat.red }" v-if="cat.red > 0" />
                <span class="bar-yellow" :style="{ flex: cat.yellow }" v-if="cat.yellow > 0" />
                <span class="bar-rest" :style="{ flex: cat.total - cat.red - cat.yellow }" />
              </span>
              <span class="cat-stats">红{{ cat.red }} / 黄{{ cat.yellow }} / 共{{ cat.total }}</span>
            </div>
          </div>
        </div>

        <!-- 行情来源 -->
        <div class="report-section">
          <h4>行情来源</h4>
          <div class="source-stats">
            <div class="source-stat">
              <span class="source-num">{{ riskReport.intel_sources.active_event_count }}</span>
              <span class="source-label">本项目关联事件</span>
            </div>
            <div class="source-stat">
              <span class="source-num">{{ riskReport.intel_sources.source_count }}</span>
              <span class="source-label">情报来源</span>
            </div>
            <div class="source-stat">
              <span class="source-num">{{ riskReport.intel_sources.registered_media_sources }}</span>
              <span class="source-label">已登记媒体</span>
            </div>
          </div>
          <div class="source-tags">
            <el-tag v-for="src in riskReport.intel_sources.sources?.slice(0, 8)" :key="src" size="small" effect="plain">
              {{ src }}
            </el-tag>
          </div>
        </div>

        <!-- 供应来源证据 -->
        <div v-if="riskReport.high_risk_items?.length" class="report-section">
          <h4>供应来源证据</h4>
          <div class="supply-evidence-list">
            <div v-for="item in riskReport.high_risk_items.slice(0, 8)" :key="item.id" class="supply-evidence-row">
              <div class="evidence-title">
                <strong>{{ item.part_number || '未知型号' }}</strong>
                <el-tag size="small" :type="item.risk_level === 'red' ? 'danger' : 'warning'">
                  {{ item.risk_level === 'red' ? '高风险' : '关注' }}
                </el-tag>
              </div>
              <div class="evidence-meta">
                库存 {{ item.total_stock ?? 0 }} · 供应商 {{ item.supplier_count ?? 0 }} ·
                交期 {{ item.lead_time_days ?? '未知' }} 天 · 单价 {{ item.unit_price ?? '未知' }} ·
                生命周期 {{ item.lifecycle_status || 'Unknown' }}
              </div>
              <div v-if="item.supply_sources_summary" class="evidence-summary">
                {{ item.supply_sources_summary }}
              </div>
              <div v-if="riskTags(item).length" class="risk-tags">
                <span class="tag-title">风险标签</span>
                <el-tag v-for="tag in riskTags(item)" :key="tag" size="small" type="warning">{{ riskTagLabel(tag) }}</el-tag>
              </div>
              <div v-if="item.procurement_suggestion || item.suggestion" class="procurement-suggestion">
                {{ item.procurement_suggestion || item.suggestion }}
              </div>
              <div v-if="item.market_evidence?.length" class="market-evidence">
                <div class="evidence-chain-title">行情证据</div>
                <div v-for="event in item.market_evidence" :key="event.id" class="market-event-row">
                  <strong>{{ event.title }}</strong>
                  <span>{{ event.source_name || '未知来源' }}</span>
                  <el-tag size="small" type="danger">{{ eventTypeLabel(event.event_type) }}</el-tag>
                  <span>影响 {{ event.price_impact_pct ?? '未知' }}% / {{ event.lead_time_impact_weeks ?? '未知' }}周</span>
                  <el-button size="small" :data-testid="`open-market-evidence-${event.id}`" @click="openMarketEvidence(event)">查看详情</el-button>
                </div>
              </div>
              <div v-if="item.v32_evidence_summary || item.v32_evidence_chain?.length" class="evidence-chain-block">
                <div class="evidence-chain-title">v3.2 依据链</div>
                <div v-if="item.v32_evidence_summary" class="evidence-summary">
                  {{ item.v32_evidence_summary }}
                </div>
                <div v-if="item.v32_action_suggestion" class="evidence-summary">
                  建议：{{ item.v32_action_suggestion }}
                </div>
                <ol v-if="item.v32_evidence_chain?.length" class="evidence-chain-list">
                  <li v-for="(node, idx) in item.v32_evidence_chain.slice(0, 5)" :key="`${item.id}-evidence-${idx}`">
                    <strong>{{ node.title || node.type }}</strong>
                    <span v-if="node.primary_track"> · {{ node.primary_track }}</span>
                    <span v-else-if="node.display_name"> · {{ node.display_name }}</span>
                  </li>
                </ol>
              </div>
            </div>
          </div>
        </div>

        <!-- 紧急行动 -->
        <div class="report-section">
          <h4>业务建议 · 紧急</h4>
          <ul v-if="riskReport.actions.urgent?.length" class="action-list">
            <li v-for="(action, idx) in riskReport.actions.urgent" :key="idx" class="action-item urgent">
              {{ action }}
            </li>
          </ul>
          <p v-else class="no-actions">暂无紧急建议</p>
        </div>

        <!-- 关注事项 -->
        <div v-if="riskReport.actions.watch?.length" class="report-section">
          <h4>业务建议 · 关注</h4>
          <ul class="action-list">
            <li v-for="(action, idx) in riskReport.actions.watch" :key="idx" class="action-item watch">
              {{ action }}
            </li>
          </ul>
        </div>
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
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import RiskDetailTable from '../components/RiskDetailTable.vue'
import MarketEventDetailDrawer from '../components/MarketEventDetailDrawer.vue'
import { getBomProject, getProjectRiskReport, getProjectRiskReportHtmlUrl, getProjectRiskReportXlsxUrl } from '../api/bom'
import { useMarketEventDetail } from '../composables/useMarketEventDetail'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const project = ref(null)
const items = ref([])
const riskReport = ref(null)
const {
  detailVisible,
  selectedEvent,
  eventImpact,
  sourceSignal,
  openEventDetail
} = useMarketEventDetail()

const traceItemIds = computed(() => parseQueryIds(route.query?.item_ids))
const traceItemIdSet = computed(() => new Set(traceItemIds.value))

const normalizedItems = computed(() => items.value.map(item => ({
  ...item,
  raw_part_number: item.raw_part_number ?? item.part_number,
  raw_brand: item.raw_brand ?? item.brand,
  raw_category: item.raw_category ?? item.category,
  trace_highlight: traceItemIdSet.value.has(String(item.id))
})))

const traceHitCount = computed(() => normalizedItems.value.filter(item => item.trace_highlight).length)

watch(
  () => route.params.id,
  (projectId) => {
    loadProject(projectId)
  },
  { immediate: true }
)

async function loadProject(projectId = route.params.id) {
  loading.value = true
  project.value = null
  items.value = []
  riskReport.value = null
  try {
    const { data } = await getBomProject(projectId)
    if (data.error) {
      project.value = null
      items.value = []
      ElMessage.error(data.error)
      return
    }
    project.value = data.project
    items.value = data.items || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || 'BOM项目详情加载失败')
  } finally {
    loading.value = false
  }

  // 加载风险报告（独立请求，失败不阻塞详情）
  try {
    const { data: report } = await getProjectRiskReport(projectId)
    riskReport.value = report
  } catch {
    riskReport.value = null
  }
}

function parseQueryIds(value) {
  if (!value) return []
  const raw = Array.isArray(value) ? value.join(',') : String(value)
  return raw.split(',').map(part => part.trim()).filter(Boolean)
}

function riskTags(item) {
  if (!item?.supply_risk_tags) return []
  return String(item.supply_risk_tags).split(',').map(tag => tag.trim()).filter(Boolean)
}

function riskTagLabel(tag) {
  const labels = {
    stockout: '库存断供',
    lead_time_long: '交期过长',
    lifecycle_risk: '生命周期风险',
    price_high: '价格异常',
    supplier_single: '供应商单一'
  }
  return labels[tag] || tag
}

function eventTypeLabel(type) {
  const labels = {
    price_increase: '涨价',
    shortage: '缺货',
    allocation: '配额',
    lifecycle: '生命周期',
    logistics_delay: '物流延迟'
  }
  return labels[type] || type || '未知事件'
}

function handleSupplyRefreshed(updatedItem) {
  items.value = items.value.map(item => item.id === updatedItem.id ? { ...item, ...updatedItem } : item)
}

function goBack() {
  router.push('/projects')
}

function openHtmlReport() {
  const projectId = project.value?.id || route.params.id
  if (!projectId) return
  window.open(getProjectRiskReportHtmlUrl(projectId), '_blank', 'noopener')
}

function openXlsxReport() {
  const projectId = project.value?.id || route.params.id
  if (!projectId) return
  const link = document.createElement('a')
  link.href = getProjectRiskReportXlsxUrl(projectId)
  link.download = `${project.value?.project_name || `BOM-${projectId}`}-风险报告.xlsx`
  link.style.display = 'none'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

function openMarketEvidence(event) {
  if (event?.id) openEventDetail(event.id)
}

function formatDate(value) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.project-detail-page {
  min-height: 100%;
}

.detail-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.back-button {
  padding-left: 0;
  margin-bottom: 8px;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 22px;
  color: #1f2d3d;
}

.sub-title {
  margin: 6px 0 0;
  color: #7a8494;
  font-size: 13px;
  word-break: break-all;
}

.project-meta {
  margin-bottom: 18px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-item {
  padding: 14px 16px;
  border-radius: 10px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
}

.summary-value {
  display: block;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.summary-label {
  display: block;
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}

.summary-item.danger .summary-value { color: #f56c6c; }
.summary-item.warning .summary-value { color: #e6a23c; }
.summary-item.success .summary-value { color: #67c23a; }

.trace-hit-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding: 10px 12px;
  border: 1px solid #f3d19e;
  border-radius: 8px;
  background: #fff7ed;
  color: #b88230;
  font-size: 13px;
}

.report-card { margin-top: 20px; border-radius: 12px; }
.report-subtitle { font-size: 13px; color: #909399; margin-left: 12px; }
.report-grid { display: flex; flex-direction: column; gap: 24px; }
.report-section h4 { margin: 0 0 10px; font-size: 15px; color: #303133; }
.report-section .summary-strip { grid-template-columns: repeat(4, 1fr); }

.category-risk-row {
  display: flex; align-items: center; gap: 12px; padding: 6px 0; border-bottom: 1px solid #f0f0f0;
}
.cat-name { min-width: 100px; font-weight: 600; font-size: 13px; color: #303133; }
.cat-bar { flex: 1; display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #f0f0f0; }
.bar-red { background: #f56c6c; }
.bar-yellow { background: #e6a23c; }
.bar-rest { background: #e4e7ed; }
.cat-stats { min-width: 140px; font-size: 12px; color: #909399; text-align: right; }

.source-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 10px; }
.source-stat { padding: 12px; border-radius: 8px; background: #f5f7fa; text-align: center; }
.source-num { display: block; font-size: 22px; font-weight: 700; color: #409eff; }
.source-label { display: block; font-size: 12px; color: #909399; margin-top: 4px; }
.source-tags { display: flex; flex-wrap: wrap; gap: 6px; }

.supply-evidence-list { display: flex; flex-direction: column; gap: 10px; }
.supply-evidence-row { padding: 12px; border-radius: 8px; background: #fff7ed; border: 1px solid #f3d19e; }
.evidence-title { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #303133; }
.evidence-meta { margin-top: 6px; font-size: 12px; color: #606266; line-height: 1.6; }
.evidence-summary { margin-top: 6px; font-size: 12px; color: #909399; line-height: 1.5; word-break: break-all; }
.risk-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 8px; }
.tag-title { font-size: 12px; font-weight: 600; color: #b88230; }
.procurement-suggestion { margin-top: 8px; padding: 8px; border-radius: 6px; background: #fff; font-size: 12px; color: #606266; line-height: 1.5; }
.market-evidence { margin-top: 10px; padding: 10px; border-radius: 6px; background: #ffffff; border: 1px dashed #f3d19e; }
.market-event-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; font-size: 12px; color: #606266; }
.evidence-chain-block { margin-top: 10px; padding: 10px; border-radius: 6px; background: #ffffff; border: 1px dashed #f3d19e; }
.evidence-chain-title { font-size: 12px; font-weight: 600; color: #b88230; }
.evidence-chain-list { margin: 8px 0 0; padding-left: 18px; font-size: 12px; color: #606266; line-height: 1.7; }

.action-list { margin: 0; padding-left: 20px; }
.action-item { padding: 6px 0; font-size: 13px; line-height: 1.6; }
.action-item.urgent { color: #f56c6c; }
.action-item.urgent::marker { color: #f56c6c; }
.action-item.watch { color: #e6a23c; }
.action-item.watch::marker { color: #e6a23c; }
.no-actions { color: #909399; font-size: 13px; }
.summary-item.warning .summary-value { color: #e6a23c; }
.summary-item.success .summary-value { color: #67c23a; }
</style>
