<template>
  <div class="risk-chain-page">
    <div class="page-header">
      <div>
        <p class="eyebrow">供应链风险全景</p>
        <h1>风险链路驾驶舱</h1>
        <p class="subtitle">从风险信号到产业链传导，再到BOM物料影响和执行策略的实时全景视图。</p>
      </div>
      <div class="header-actions">
        <span class="status-indicator" :class="{ active: isLive }">
          <span class="status-dot" />
          {{ isLive ? '实时监控中' : '已暂停' }}
        </span>
        <el-button :type="isLive ? 'default' : 'primary'" @click="toggleLive">
          {{ isLive ? '暂停刷新' : '恢复刷新' }}
        </el-button>
        <el-button type="primary" :loading="loading" @click="refreshAll">刷新链路</el-button>
      </div>
    </div>

    <el-alert v-if="error" type="error" :title="error" show-icon closable class="section-gap" @close="error = ''" />

    <el-empty v-if="isEmpty && !loading" description="暂无风险链路数据，请先上传BOM或检查数据源" />

    <div v-else class="three-col-layout section-gap">
      <!-- 左侧：风险信号流 -->
      <div class="col-panel left-panel">
        <RiskSignalFlow :signals="signals" @refresh="refreshAll" />
      </div>

      <!-- 中间：EMS产业链风险图谱 -->
      <div class="col-panel center-panel">
        <IndustryChainGraph :nodes="chainNodes" :edges="chainEdges" />
      </div>

      <!-- 右侧：BOM影响和处理建议 -->
      <div class="col-panel right-panel">
        <BomImpactPanel :bomImpacts="bomImpacts" @open-detail="openMaterialDetail" />
      </div>
    </div>

    <!-- 物料风险详情抽屉 -->
    <el-drawer v-model="detailVisible" title="物料风险详情" size="480px" direction="rtl">
      <template v-if="selectedMaterial">
        <div class="detail-drawer">
          <div class="detail-header-card">
            <div class="detail-mpn">{{ selectedMaterial.mpn }}</div>
            <div class="detail-manufacturer">{{ selectedMaterial.manufacturer }} · {{ selectedMaterial.category }}</div>
            <div class="detail-badges">
              <el-tag :color="getRiskColor(selectedMaterial.risk_level)" size="small"
                effect="dark" style="color: #fff; border: none;">
                风险评分：{{ selectedMaterial.risk_score }}
              </el-tag>
              <el-tag :type="lifecycleType(selectedMaterial.lifecycle_status)" size="small">
                {{ selectedMaterial.lifecycle_status }}
              </el-tag>
            </div>
          </div>

          <h4>触发事件</h4>
          <div class="detail-events">
            <div v-for="(evt, idx) in selectedMaterial.trigger_events" :key="idx" class="detail-event-item">
              <el-icon><Warning /></el-icon>
              <span>{{ evt }}</span>
            </div>
          </div>

          <h4>分角色处理建议</h4>
          <div class="detail-suggestions">
            <div v-for="(sug, idx) in selectedMaterial.suggestions" :key="idx" class="detail-sug-item">
              <el-tag :type="roleTagType(sug.role)" size="small" effect="dark" class="sug-role">
                {{ roleLabel(sug.role) }}
              </el-tag>
              <p>{{ sug.action }}</p>
            </div>
          </div>

          <h4>产业链关联信号</h4>
          <div class="detail-related-signals">
            <div v-for="sig in relatedSignals" :key="sig.id" class="related-signal">
              <span class="signal-severity-dot" :class="sig.severity" />
              <span class="signal-title">{{ sig.title }}</span>
            </div>
            <el-empty v-if="relatedSignals.length === 0" description="暂无关联信号" :image-size="40" />
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Warning } from '@element-plus/icons-vue'
import RiskSignalFlow from '../components/RiskSignalFlow.vue'
import IndustryChainGraph from '../components/IndustryChainGraph.vue'
import BomImpactPanel from '../components/BomImpactPanel.vue'
import { riskChainService } from '../api/riskChainService'

// ─── State ───
const loading = ref(false)
const error = ref('')
const isLive = ref(true)
const detailVisible = ref(false)
const selectedMaterial = ref(null)

const signals = ref([])
const chainNodes = ref([])
const chainEdges = ref([])
const bomImpacts = ref([])

let refreshTimer = null

// ─── Computed ───
const isEmpty = computed(() =>
  signals.value.length === 0 &&
  chainNodes.value.length === 0 &&
  bomImpacts.value.length === 0
)

const relatedSignals = computed(() => {
  if (!selectedMaterial.value) return []
  const category = selectedMaterial.value.category.toLowerCase()
  return signals.value.filter(s =>
    s.category.toLowerCase().includes(category) ||
    category.includes(s.category.toLowerCase()) ||
    s.affected_brands.some(b => b.toLowerCase().includes(selectedMaterial.value.manufacturer.toLowerCase()))
  ).slice(0, 5)
})

// ─── Data Loading ───
async function refreshAll() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await riskChainService.getDashboardData()
    signals.value = data.signals || []
    chainNodes.value = data.nodes || []
    chainEdges.value = data.edges || []
    bomImpacts.value = data.bomImpacts || []
  } catch (err) {
    error.value = '风险链路驾驶舱数据加载失败，请检查数据源。'
  } finally {
    loading.value = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshTimer = setInterval(() => {
    if (isLive.value) {
      refreshAll()
    }
  }, 5 * 60 * 1000) // 5 minutes
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function toggleLive() {
  isLive.value = !isLive.value
}

// ─── Detail Drawer ───
function openMaterialDetail(item) {
  selectedMaterial.value = item
  detailVisible.value = true
}

function getRiskColor(level) {
  return { red: '#F56C6C', orange: '#E6A23C', yellow: '#E6D23C', green: '#67C23A', gray: '#909399' }[level] || '#909399'
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

// ─── Lifecycle ───
onMounted(() => {
  refreshAll()
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.risk-chain-page {
  color: #1f2937;
  min-height: 100vh;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #5b4bb7;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
}

h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.subtitle {
  margin: 8px 0 0;
  color: #667085;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

.status-indicator.active {
  color: #67C23A;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #909399;
}

.status-indicator.active .status-dot {
  background: #67C23A;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.section-gap {
  margin-top: 20px;
}

/* ─── Three Column Layout ─── */
.three-col-layout {
  display: grid;
  grid-template-columns: 300px 1fr 340px;
  gap: 16px;
  height: calc(100vh - 160px);
  min-height: 600px;
}

.col-panel {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.left-panel {
  min-width: 280px;
}

.center-panel {
  min-width: 400px;
}

.right-panel {
  min-width: 300px;
}

/* ─── Detail Drawer ─── */
.detail-drawer {
  padding: 4px;
}

.detail-header-card {
  padding: 16px;
  background: #fafbfc;
  border-radius: 10px;
  margin-bottom: 16px;
}

.detail-mpn {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  word-break: break-all;
}

.detail-manufacturer {
  font-size: 13px;
  color: #667085;
  margin-top: 4px;
}

.detail-badges {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.detail-drawer h4 {
  margin: 16px 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
}

.detail-events {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-event-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  background: #fef9f0;
  border-radius: 8px;
  border: 1px solid #fdecd0;
  font-size: 13px;
  color: #667085;
}

.detail-event-item .el-icon {
  color: #E6A23C;
  flex-shrink: 0;
  margin-top: 2px;
}

.detail-suggestions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-sug-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.detail-sug-item p {
  margin: 0;
  font-size: 13px;
  color: #1f2937;
  line-height: 1.6;
}

.sug-role {
  flex-shrink: 0;
  margin-top: 2px;
}

.detail-related-signals {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.related-signal {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: #fafbfc;
  border-radius: 6px;
  border: 1px solid #f0f2f5;
}

.signal-severity-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.signal-severity-dot.red { background: #F56C6C; }
.signal-severity-dot.orange { background: #E6A23C; }
.signal-severity-dot.yellow { background: #E6D23C; }

.related-signal .signal-title {
  font-size: 12px;
  color: #1f2937;
}

/* ─── Responsive ─── */
@media (max-width: 1400px) {
  .three-col-layout {
    grid-template-columns: 260px 1fr 300px;
  }
}

@media (max-width: 1100px) {
  .three-col-layout {
    grid-template-columns: 1fr;
    height: auto;
  }
  .col-panel {
    min-height: 500px;
  }
}
</style>
