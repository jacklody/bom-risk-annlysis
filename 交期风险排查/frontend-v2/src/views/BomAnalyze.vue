<template>
  <div class="bom-analyze">
    <div class="page-header">
      <h2>BOM 风险分析</h2>
      <p class="page-desc">上传 BOM 文件（支持单文件或批量），自动匹配市场事件，输出风险等级</p>
    </div>

    <!-- 状态：空闲 → 选择文件上传 -->
    <div v-if="phase === 'idle'">
      <BomUploader
        @upload="handleUpload"
        @upload-batch="handleUploadBatch"
        :disabled="false"
      />
    </div>

    <!-- 状态：分析中 -->
    <div v-if="phase === 'analyzing'">
      <el-alert
        :title="batchMode ? `批量分析中（${batchFiles.length}个文件）` : '正在分析中...'"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />
      <ProgressSteps :current="progressStep" />
      <div class="loading-hint">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
        <span>{{ progressText }}</span>
      </div>
    </div>

    <!-- 单文件结果 -->
    <div v-if="phase === 'done' && result && !batchMode">
      <div class="result-header">
        <h3>分析完成</h3>
        <el-tag type="success">{{ result.total_items }} 个物料已分析</el-tag>
        <el-button size="small" style="margin-left:12px" @click="resetAnalyze">
          继续上传
        </el-button>
        <el-button
          size="small"
          data-testid="refresh-supply-project"
          :loading="refreshingProjectSupply"
          @click="refreshCurrentProjectSupply"
        >
          刷新供应数据
        </el-button>
      </div>

      <el-alert
        v-if="supplyRefreshSummary"
        :title="`供应数据刷新：处理 ${supplyRefreshSummary.processed_count} 条，更新 ${supplyRefreshSummary.updated_count} 条，失败 ${supplyRefreshSummary.failed_count} 条`"
        type="info"
        show-icon
        :closable="false"
        style="margin: 12px 0"
      />

      <section v-if="supplySourceStatus" class="supply-source-status" data-testid="supply-source-status">
        <div class="supply-source-title">
          <strong>供应源状态</strong>
          <span>样例：{{ supplySourceStatus.sample_mpn }}</span>
        </div>
        <div class="supply-source-summary">
          <el-tag size="small" type="success">活跃 {{ supplySourceStatus.summary?.active_sources || 0 }}</el-tag>
          <el-tag size="small" type="info">未配置 {{ supplySourceStatus.summary?.not_configured_sources || 0 }}</el-tag>
          <el-tag size="small" type="warning">异常 {{ supplySourceStatus.summary?.degraded_sources || 0 }}</el-tag>
        </div>
        <div class="supply-source-list">
          <span v-for="source in supplySourceStatus.sources || []" :key="source.source" class="supply-source-item">
            {{ source.source }} · {{ sourceStatusLabel(source.status) }}
            <em v-if="source.error_reason">（{{ source.error_reason }}）</em>
          </span>
        </div>
      </section>

      <el-divider />

      <RiskSummary
        :summary="result.summary"
        :active="filterLevel"
        @click-card="filterLevel = $event"
      />

      <ManualEventQuickAdd
        :default-item="manualEventDefaultItem"
        @submitted="handleManualEventSubmitted"
      />

      <el-alert
        v-if="manualEventSubmitted"
        title="人工事件已进入行情事件库"
        description="如该事件会影响当前 BOM，请点击“重新分析当前BOM”刷新 v3.2 风险轨道与依据链。"
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      >
        <template #default>
          <el-button size="small" type="warning" :loading="reanalyzing" @click="reanalyzeCurrentUpload">
            重新分析当前BOM
          </el-button>
        </template>
      </el-alert>

      <el-divider />

      <RiskDetailTable :items="filteredItems" @supply-refreshed="handleSupplyRefreshed" />

      <div class="export-bar" v-if="result.items.length">
        <el-button data-testid="export-csv-button" @click="exportTable" size="small">
          <el-icon><Download /></el-icon> 导出 CSV
        </el-button>
      </div>
    </div>

    <!-- 批量结果 -->
    <div v-if="phase === 'done' && batchResult && batchMode">
      <div class="result-header">
        <h3>批量分析完成</h3>
        <el-tag type="success">
          {{ batchResult.total_projects }} 个BOM，
          共 {{ batchTotalItems }} 个物料
        </el-tag>
        <el-button size="small" style="margin-left:12px" @click="resetAnalyze">
          继续上传
        </el-button>
      </div>

      <el-divider />

      <!-- 批量汇总卡片 -->
      <RiskSummary :summary="batchAggregateSummary" />

      <el-divider />

      <!-- 按项目展示 -->
      <h4 class="section-title">各BOM明细</h4>
      <el-table :data="batchResult.projects" stripe>
        <el-table-column prop="project_name" label="BOM名称" min-width="200" />
        <el-table-column prop="total" label="物料数" width="80" align="right" />
        <el-table-column label="🔴 高风险" width="100" align="right">
          <template #default="{ row }">
            <span :class="{ 'risk-red': row.red > 0 }">{{ row.red }}</span>
          </template>
        </el-table-column>
        <el-table-column label="🟡 关注" width="100" align="right">
          <template #default="{ row }">
            <span :class="{ 'risk-yellow': row.yellow > 0 }">{{ row.yellow }}</span>
          </template>
        </el-table-column>
        <el-table-column label="🟢 安全" width="100" align="right">
          <template #default="{ row }">{{ row.green }}</template>
        </el-table-column>
        <el-table-column label="EOL" width="80" align="right">
          <template #default="{ row }">
            <span :class="{ 'risk-red': row.eol_count > 0 }">{{ row.eol_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="交期风险" width="100" align="right">
          <template #default="{ row }">
            <span :class="{ 'risk-yellow': row.lead_time_risk_count > 0 }">{{ row.lead_time_risk_count || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="风险率" width="100" align="right">
          <template #default="{ row }">
            <el-tag :type="riskRateTagType(row.risk_rate)" size="small">
              {{ row.risk_rate }}%
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button size="small" link @click="viewProject(row.project_id)">
              查看明细
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 错误状态 -->
    <div v-if="phase === 'error'">
      <el-result icon="error" title="分析失败" :sub-title="errorMsg">
        <template #extra>
          <el-button type="primary" @click="resetAnalyze">重试</el-button>
        </template>
      </el-result>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import BomUploader from '../components/BomUploader.vue'
import ProgressSteps from '../components/ProgressSteps.vue'
import RiskSummary from '../components/RiskSummary.vue'
import RiskDetailTable from '../components/RiskDetailTable.vue'
import ManualEventQuickAdd from '../components/ManualEventQuickAdd.vue'
import { uploadBom, uploadBomBatch, analyzeBom, analyzeAll } from '../api/bom'
import { getSupplySourcesStatus, refreshSupplyProject } from '../api/supply'

const router = useRouter()
const phase = ref('idle')
const progressStep = ref(0)
const progressText = ref('')
const result = ref(null)
const batchResult = ref(null)
const errorMsg = ref('')
const filterLevel = ref('')
const batchMode = ref(false)
const batchFiles = ref([])
const currentUploadId = ref(null)
const manualEventSubmitted = ref(false)
const reanalyzing = ref(false)
const refreshingProjectSupply = ref(false)
const supplyRefreshSummary = ref(null)
const loadingSupplySources = ref(false)
const supplySourceStatus = ref(null)

const filteredItems = computed(() => {
  if (!result.value) return []
  if (!filterLevel.value) return result.value.items
  return result.value.items.filter(i => i.risk_level === filterLevel.value)
})

const manualEventDefaultItem = computed(() => {
  const items = result.value?.items || []
  return items.find(i => ['red', 'orange', 'yellow'].includes(i.v32_risk_level)) ||
    items.find(i => ['red', 'yellow'].includes(i.risk_level)) ||
    items[0] ||
    {}
})

const batchTotalItems = computed(() => {
  if (!batchResult.value?.projects) return 0
  return batchResult.value.projects.reduce((sum, p) => sum + p.total, 0)
})

const batchAggregateSummary = computed(() => {
  if (!batchResult.value?.projects) return { red: 0, yellow: 0, green: 0, gray: 0 }
  return batchResult.value.projects.reduce((acc, p) => ({
    red: acc.red + p.red,
    yellow: acc.yellow + p.yellow,
    green: acc.green + p.green,
    gray: acc.gray + p.gray,
  }), { red: 0, yellow: 0, green: 0, gray: 0 })
})

function riskRateTagType(rate) {
  if (rate >= 40) return 'danger'
  if (rate >= 20) return 'warning'
  if (rate > 0) return 'info'
  return 'success'
}

function sourceStatusLabel(status) {
  return {
    active: '活跃',
    not_configured: '未配置',
    degraded: '异常'
  }[status] || status || '未知'
}

function firstSupplySampleMpn() {
  return result.value?.items?.find(item => item.raw_part_number)?.raw_part_number || 'STM32F103C8T6'
}

async function loadSupplySourceStatus() {
  loadingSupplySources.value = true
  try {
    const { data } = await getSupplySourcesStatus(firstSupplySampleMpn())
    supplySourceStatus.value = data
  } catch (error) {
    supplySourceStatus.value = null
    ElMessage.warning(error?.response?.data?.detail || '供应源状态获取失败')
  } finally {
    loadingSupplySources.value = false
  }
}

async function handleUpload(file, projectName) {
  batchMode.value = false
  phase.value = 'analyzing'
  errorMsg.value = ''
  filterLevel.value = ''
  manualEventSubmitted.value = false
  supplyRefreshSummary.value = null
  supplySourceStatus.value = null

  try {
    progressStep.value = 1
    progressText.value = '正在解析 BOM 文件...'
    const uploadRes = await uploadBom(file, projectName)
    const uploadId = uploadRes.data.upload_id
    currentUploadId.value = uploadId

    progressStep.value = 2
    progressText.value = '正在匹配市场事件...'
    await new Promise(r => setTimeout(r, 200))

    progressStep.value = 3
    progressText.value = '正在计算风险等级...'
    const analyzeRes = await analyzeBom(uploadId)
    result.value = analyzeRes.data
    await loadSupplySourceStatus()

    progressStep.value = 4
    progressText.value = '分析完成'
    await new Promise(r => setTimeout(r, 300))
    phase.value = 'done'

    ElMessage.success(`分析完成：${result.value.total_items}个物料，${result.value.summary.red}个高风险`)
  } catch (err) {
    errorMsg.value = err.response?.data?.error || err.message || '未知错误'
    phase.value = 'error'
    ElMessage.error('分析失败：' + errorMsg.value)
  }
}

async function handleUploadBatch(files) {
  batchMode.value = true
  batchFiles.value = files
  phase.value = 'analyzing'
  errorMsg.value = ''
  currentUploadId.value = null
  manualEventSubmitted.value = false
  supplyRefreshSummary.value = null
  supplySourceStatus.value = null

  try {
    progressStep.value = 1
    progressText.value = `正在解析 ${files.length} 个 BOM 文件...`
    await uploadBomBatch(files)

    progressStep.value = 2
    progressText.value = '正在匹配市场事件...'
    await new Promise(r => setTimeout(r, 200))

    progressStep.value = 3
    progressText.value = '正在批量计算风险等级...'
    const analyzeRes = await analyzeAll()
    batchResult.value = analyzeRes.data

    progressStep.value = 4
    progressText.value = '批量分析完成'
    await new Promise(r => setTimeout(r, 300))
    phase.value = 'done'

    const totalRed = batchAggregateSummary.value.red
    const totalYellow = batchAggregateSummary.value.yellow
    ElMessage.success(`批量分析完成：${files.length}个BOM，${totalRed}红/${totalYellow}黄`)
  } catch (err) {
    errorMsg.value = err.response?.data?.error || err.message || '未知错误'
    phase.value = 'error'
    ElMessage.error('批量分析失败：' + errorMsg.value)
  }
}

function handleManualEventSubmitted() {
  manualEventSubmitted.value = true
}

function handleSupplyRefreshed(updatedItem) {
  if (!result.value?.items || !updatedItem?.id) return
  result.value.items = result.value.items.map(item => item.id === updatedItem.id ? { ...item, ...updatedItem } : item)
}

function applyProjectSupplyItems(items = []) {
  if (!result.value?.items?.length) return
  const updatedById = new Map(
    items
      .filter(entry => entry.updated && entry.item?.id)
      .map(entry => [entry.item.id, entry.item])
  )
  if (!updatedById.size) return
  result.value.items = result.value.items.map(item => {
    const updated = updatedById.get(item.id)
    return updated ? { ...item, ...updated } : item
  })
}

async function refreshCurrentProjectSupply() {
  if (!currentUploadId.value) return
  refreshingProjectSupply.value = true
  try {
    const { data } = await refreshSupplyProject(currentUploadId.value, { limit: 50, concurrency: 3 })
    supplyRefreshSummary.value = data
    applyProjectSupplyItems(data.items || [])
    ElMessage.success(`供应数据刷新完成：更新 ${data.updated_count} 条，失败 ${data.failed_count} 条`)
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '项目供应数据刷新失败')
  } finally {
    refreshingProjectSupply.value = false
  }
}

async function reanalyzeCurrentUpload() {
  if (!currentUploadId.value) return
  reanalyzing.value = true
  try {
    const analyzeRes = await analyzeBom(currentUploadId.value)
    result.value = analyzeRes.data
    manualEventSubmitted.value = false
    ElMessage.success('已基于最新人工事件重新分析BOM')
  } catch (err) {
    ElMessage.error(err.response?.data?.error || err.message || '重新分析失败')
  } finally {
    reanalyzing.value = false
  }
}

function viewProject(id) {
  router.push(`/projects/${id}`)
}

function resetAnalyze() {
  phase.value = 'idle'
  progressStep.value = 0
  result.value = null
  batchResult.value = null
  batchMode.value = false
  currentUploadId.value = null
  manualEventSubmitted.value = false
  refreshingProjectSupply.value = false
  supplyRefreshSummary.value = null
  supplySourceStatus.value = null
}

function csvText(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

function exportTable() {
  if (!result.value?.items?.length) return
  const header = '序号,型号,品牌,标准化品牌,品类,风险等级,评分,v3.2品类,v3.2主导轨道,v3.2风险等级,v3.2评分,v3.2依据摘要,v3.2处置建议,交期风险等级,预计影响周数,EOL状态,排产交期原因,采购建议,综合原因\n'
  const rows = result.value.items.map(i => [
    i.row_number,
    csvText(i.raw_part_number),
    csvText(i.raw_brand),
    csvText(i.normalized_brand || ''),
    csvText(i.normalized_category || i.raw_category || ''),
    i.risk_level,
    i.risk_score,
    csvText(i.v32_category_display || i.v32_category || ''),
    csvText(i.v32_primary_track || ''),
    i.v32_risk_level || '',
    i.v32_risk_score ?? '',
    csvText(i.v32_evidence_summary || ''),
    csvText(i.v32_action_suggestion || ''),
    i.production_risk_level || '',
    i.lead_time_risk_weeks || '',
    i.eol_status || '',
    csvText(i.supply_risk_reason || ''),
    csvText(i.procurement_suggestion || ''),
    csvText(i.risk_reason || ''),
  ].join(',')).join('\n')

  const csv = '\uFEFF' + header + rows
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'BOM风险分析结果.csv'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style scoped>
.page-header { margin-bottom: 24px; }
.page-header h2 { font-size: 22px; color: #303133; }
.page-desc { color: #909399; margin-top: 4px; }

.loading-hint {
  display: flex; align-items: center; justify-content: center;
  gap: 10px; margin-top: 24px; color: #909399; font-size: 15px;
}

.result-header { display: flex; align-items: center; gap: 10px; }
.result-header h3 { font-size: 18px; color: #303133; }

.section-title { font-size: 16px; color: #303133; margin: 16px 0; }
.risk-red { color: #f56c6c; font-weight: 600; }
.risk-yellow { color: #e6a23c; font-weight: 600; }

.export-bar { margin-top: 16px; text-align: right; }

.supply-source-status {
  margin: 12px 0;
  padding: 12px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: #f8fbff;
}

.supply-source-title,
.supply-source-summary,
.supply-source-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.supply-source-title {
  justify-content: space-between;
  color: #303133;
}

.supply-source-title span,
.supply-source-item {
  color: #606266;
  font-size: 12px;
}

.supply-source-summary,
.supply-source-list {
  margin-top: 8px;
}
</style>
