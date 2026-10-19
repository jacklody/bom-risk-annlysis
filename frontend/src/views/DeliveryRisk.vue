<template>
  <div class="delivery-risk-page">
    <div class="page-header">
      <div>
        <p class="eyebrow">Delivery Risk Warning · T2-010</p>
        <h1>交付风险预警</h1>
        <p class="subtitle">老项目执行过程中的物料交付风险实时总览与处置建议。</p>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 200px" @change="refreshAll">
          <el-option v-for="p in projectList" :key="p.id" :label="p.project_name" :value="p.id" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="refreshAll">刷新数据</el-button>
        <el-button @click="exportReport">导出报告</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :title="error" show-icon closable class="section-gap" @close="error = ''" />

    <el-empty v-if="!selectedProjectId && !loading" description="请先选择一个项目以查看交付风险" />

    <template v-else-if="selectedProjectId">
      <!-- 顶部：项目风险总览 -->
      <div class="overview-section section-gap">
        <el-row :gutter="16">
          <el-col :span="6">
            <div class="overview-card" :class="'risk-' + overview.overall_risk_level">
              <div class="card-label">整体风险等级</div>
              <div class="risk-light">
                <span class="light-dot" :class="'dot-' + overview.overall_risk_level" />
                <span class="light-text">{{ riskLevelLabel(overview.overall_risk_level) }}</span>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="overview-card">
              <div class="card-label">物料风险分布</div>
              <div class="risk-distribution">
                <span class="dist-item dist-red">红 {{ overview.red_count }}</span>
                <span class="dist-item dist-orange">橙 {{ overview.orange_count }}</span>
                <span class="dist-item dist-yellow">黄 {{ overview.yellow_count }}</span>
                <span class="dist-item dist-green">绿 {{ overview.green_count }}</span>
              </div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="overview-card">
              <div class="card-label">物料总数</div>
              <div class="big-number">{{ overview.total_materials }}</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="overview-card">
              <div class="card-label">近30天事件数</div>
              <div class="big-number">{{ overview.recent_event_count }}</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 中部 + 右侧：物料表格 + 时间线 -->
      <div class="main-content section-gap">
        <div class="content-left">
          <el-table :data="materials" stripe style="width: 100%" :row-class-name="tableRowClassName" v-loading="loading">
            <el-table-column prop="mpn" label="物料" min-width="160" />
            <el-table-column prop="category" label="品类" width="120" />
            <el-table-column label="当前风险" width="140">
              <template #default="{ row }">
                <el-tag :color="getRiskColor(row.risk_level)" effect="dark" size="small" style="color: #fff; border: none;">
                  {{ row.risk_score.toFixed(0) }}分
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="趋势" width="80" align="center">
              <template #default="{ row }">
                <span class="trend-arrow" :class="'trend-' + row.trend">
                  {{ row.trend === 'up' ? '↑' : row.trend === 'down' ? '↓' : '→' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="交期影响" width="120">
              <template #default="{ row }">
                {{ row.lead_time_impact_weeks.toFixed(1) }} 周
              </template>
            </el-table-column>
            <el-table-column prop="suggestion" label="建议" min-width="220" show-overflow-tooltip />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="!row.is_acknowledged"
                  size="small"
                  type="success"
                  link
                  @click="handleAck(row)"
                >确认已处理</el-button>
                <el-tag v-else size="small" type="success">已处理</el-tag>
              </template>
            </el-table-column>
          </el-table>

          <!-- 底部批量操作 -->
          <div class="batch-actions">
            <el-button @click="batchAck" :disabled="!hasUnacked">批量确认已处理</el-button>
            <el-button @click="exportReport">导出风险报告</el-button>
          </div>
        </div>

        <div class="content-right">
          <div class="timeline-panel">
            <h3>风险时间线</h3>
            <el-timeline v-if="timeline.length > 0">
              <el-timeline-item
                v-for="evt in timeline"
                :key="evt.event_id"
                :timestamp="formatTime(evt.timestamp)"
                :type="timelineType(evt.severity)"
                placement="top"
              >
                <div class="timeline-card">
                  <div class="timeline-title">{{ evt.title }}</div>
                  <div class="timeline-meta">
                    <el-tag size="small" :type="timelineType(evt.severity)">{{ evt.severity }}</el-tag>
                    <span class="timeline-source">{{ evt.source }}</span>
                  </div>
                  <div v-if="evt.affected_materials.length" class="timeline-materials">
                    影响: {{ evt.affected_materials.join(', ') }}
                  </div>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无风险事件" :image-size="60" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ── 状态 ──
const loading = ref(false)
const error = ref('')
const selectedProjectId = ref(null)
const projectList = ref([])
const overview = ref({
  project_id: 0,
  project_name: '',
  overall_risk_level: 'green',
  total_materials: 0,
  red_count: 0,
  orange_count: 0,
  yellow_count: 0,
  green_count: 0,
  recent_event_count: 0,
})
const materials = ref([])
const timeline = ref([])
const recommendations = ref([])

// ── 计算属性 ──
const hasUnacked = computed(() => materials.value.some(m => !m.is_acknowledged))

// ── API 调用 ──
const API_BASE = '/api/v1/delivery-risk'

async function fetchProjects() {
  try {
    const resp = await fetch('/api/bom/projects')
    if (resp.ok) {
      const data = await resp.json()
      projectList.value = (data.projects || data || []).filter(p => p.status === 'active')
      if (projectList.value.length > 0 && !selectedProjectId.value) {
        selectedProjectId.value = projectList.value[0].id
      }
    }
  } catch (e) {
    console.warn('获取项目列表失败:', e)
  }
}

async function fetchOverview() {
  if (!selectedProjectId.value) return
  const resp = await fetch(`${API_BASE}/overview?project_id=${selectedProjectId.value}`)
  if (!resp.ok) throw new Error('获取风险总览失败')
  overview.value = await resp.json()
}

async function fetchMaterials() {
  if (!selectedProjectId.value) return
  const resp = await fetch(`${API_BASE}/materials?project_id=${selectedProjectId.value}`)
  if (!resp.ok) throw new Error('获取物料风险列表失败')
  const data = await resp.json()
  materials.value = data.materials || []
}

async function fetchTimeline() {
  if (!selectedProjectId.value) return
  const resp = await fetch(`${API_BASE}/timeline?project_id=${selectedProjectId.value}`)
  if (!resp.ok) throw new Error('获取风险时间线失败')
  const data = await resp.json()
  timeline.value = data.events || []
}

async function fetchRecommendations() {
  if (!selectedProjectId.value) return
  const resp = await fetch(`${API_BASE}/recommendations?project_id=${selectedProjectId.value}`)
  if (!resp.ok) throw new Error('获取建议措施失败')
  const data = await resp.json()
  recommendations.value = data.recommendations || []
}

async function refreshAll() {
  if (!selectedProjectId.value) return
  loading.value = true
  error.value = ''
  try {
    await Promise.all([fetchOverview(), fetchMaterials(), fetchTimeline(), fetchRecommendations()])
  } catch (e) {
    error.value = e.message || '数据加载失败'
  } finally {
    loading.value = false
  }
}

async function handleAck(row) {
  try {
    const resp = await fetch(`${API_BASE}/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ material_id: row.material_id }),
    })
    if (!resp.ok) throw new Error('确认失败')
    row.is_acknowledged = true
    ElMessage.success('已确认处理')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

async function batchAck() {
  try {
    await ElMessageBox.confirm('确认将所有未处理风险标记为已处理？', '批量确认', { type: 'warning' })
    const unacked = materials.value.filter(m => !m.is_acknowledged)
    for (const m of unacked) {
      await handleAck(m)
    }
    ElMessage.success(`已批量确认 ${unacked.length} 条`)
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('批量确认失败')
  }
}

function exportReport() {
  ElMessage.info('报告导出功能开发中')
}

// ── 辅助函数 ──
function riskLevelLabel(level) {
  const map = { red: '极高风险', orange: '高风险', yellow: '中风险', green: '低风险' }
  return map[level] || '未知'
}

function getRiskColor(level) {
  const map = { red: '#F56C6C', orange: '#E6A23C', yellow: '#D4A017', green: '#67C23A', gray: '#909399' }
  return map[level] || '#909399'
}

function tableRowClassName({ row }) {
  return `risk-row-${row.risk_level}`
}

function timelineType(severity) {
  const map = { red: 'danger', orange: 'warning', yellow: 'warning', green: 'success' }
  return map[severity] || 'info'
}

function formatTime(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ts
  }
}

// ── 生命周期 ──
onMounted(async () => {
  await fetchProjects()
  if (selectedProjectId.value) {
    await refreshAll()
  }
})
</script>

<style scoped>
.delivery-risk-page {
  padding: 24px;
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 4px 0;
  font-size: 24px;
  font-weight: 600;
  color: #1a1a2e;
}

.eyebrow {
  font-size: 12px;
  color: #7c7c8a;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0;
}

.subtitle {
  font-size: 14px;
  color: #6b7280;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.section-gap {
  margin-bottom: 20px;
}

/* ── 总览卡片 ── */
.overview-card {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  border-left: 4px solid #e5e7eb;
}

.overview-card.risk-red { border-left-color: #F56C6C; }
.overview-card.risk-orange { border-left-color: #E6A23C; }
.overview-card.risk-yellow { border-left-color: #D4A017; }
.overview-card.risk-green { border-left-color: #67C23A; }

.card-label {
  font-size: 12px;
  color: #7c7c8a;
  margin-bottom: 8px;
}

.risk-light {
  display: flex;
  align-items: center;
  gap: 8px;
}

.light-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  display: inline-block;
}

.light-dot.dot-red { background: #F56C6C; box-shadow: 0 0 8px #F56C6C; }
.light-dot.dot-orange { background: #E6A23C; box-shadow: 0 0 8px #E6A23C; }
.light-dot.dot-yellow { background: #D4A017; box-shadow: 0 0 8px #D4A017; }
.light-dot.dot-green { background: #67C23A; box-shadow: 0 0 8px #67C23A; }

.light-text {
  font-size: 18px;
  font-weight: 600;
}

.risk-distribution {
  display: flex;
  gap: 12px;
}

.dist-item {
  font-size: 13px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
}

.dist-red { color: #F56C6C; background: #fef0f0; }
.dist-orange { color: #E6A23C; background: #fdf6ec; }
.dist-yellow { color: #D4A017; background: #fef9e7; }
.dist-green { color: #67C23A; background: #f0f9eb; }

.big-number {
  font-size: 28px;
  font-weight: 700;
  color: #1a1a2e;
}

/* ── 主内容区 ── */
.main-content {
  display: flex;
  gap: 20px;
}

.content-left {
  flex: 1;
  min-width: 0;
}

.content-right {
  width: 320px;
  flex-shrink: 0;
}

/* ── 趋势箭头 ── */
.trend-arrow {
  font-size: 18px;
  font-weight: 700;
}

.trend-up { color: #F56C6C; }
.trend-down { color: #67C23A; }
.trend-flat { color: #909399; }

/* ── 批量操作 ── */
.batch-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

/* ── 时间线面板 ── */
.timeline-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  max-height: 600px;
  overflow-y: auto;
}

.timeline-panel h3 {
  margin: 0 0 16px 0;
  font-size: 15px;
  font-weight: 600;
  color: #1a1a2e;
}

.timeline-card {
  padding: 4px 0;
}

.timeline-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.timeline-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.timeline-source {
  font-size: 11px;
  color: #909399;
}

.timeline-materials {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

/* ── 表格行样式 ── */
:deep(.risk-row-red) {
  background-color: #fef0f0 !important;
}

:deep(.risk-row-orange) {
  background-color: #fdf6ec !important;
}
</style>
