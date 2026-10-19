<template>
  <div class="preferred-library" data-testid="preferred-library-page">
    <div class="page-header">
      <h1>优选库 · BOM 差异对比</h1>
      <p>对比实际 BOM 物料与优选库标准物料，差异一目了然。含库存、成本、交期数据。</p>
    </div>

    <el-card class="section-card">
      <template #header>BOM 选型对比</template>
      <div class="review-actions">
        <label>选择 BOM 项目</label>
        <el-select
          v-model="projectId"
          filterable
          remote
          reserve-keyword
          placeholder="输入项目名称搜索..."
          :remote-method="searchProjects"
          :loading="searching"
          clearable
          style="width: 380px"
          data-testid="bom-project-select"
        >
          <el-option
            v-for="p in projectOptions"
            :key="p.id"
            :label="p.project_name"
            :value="p.id"
          >
            <div class="option-project">
              <span class="option-name">{{ p.project_name }}</span>
              <span class="option-meta">ID:{{ p.id }} | {{ p.total_items }}项</span>
            </div>
          </el-option>
        </el-select>
        <el-button type="primary" :loading="reviewing" data-testid="run-selection-review" :disabled="!projectId" @click="runReview">
          执行对比
        </el-button>
        <el-button v-if="reviewResult" @click="exportCsv">导出 CSV</el-button>
      </div>
    </el-card>

    <!-- 导入优选库（仅在无对比结果时折叠） -->
    <el-card v-if="!reviewResult" class="section-card">
      <template #header>优选库导入</template>
      <el-upload :auto-upload="false" :show-file-list="true" :on-change="onFileChange" data-testid="preferred-upload">
        <el-button>选择优选库 Excel</el-button>
      </el-upload>
      <el-button type="primary" :disabled="!selectedFile" :loading="importing" @click="submitImport" style="margin-top:10px">
        导入优选库
      </el-button>
      <pre v-if="importResult" class="result-json">{{ importResult }}</pre>
    </el-card>

    <!-- 差异汇总条 -->
    <div v-if="reviewResult" class="summary-strip">
      <div class="summary-item">
        <span class="summary-value">{{ reviewResult.summary.total_items }}</span>
        <span class="summary-label">BOM物料</span>
      </div>
      <div class="summary-item success">
        <span class="summary-value">{{ reviewResult.summary.preferred_hit_count }}</span>
        <span class="summary-label">优选命中</span>
      </div>
      <div class="summary-item warning">
        <span class="summary-value">{{ reviewResult.summary.non_preferred_count }}</span>
        <span class="summary-label">非优选</span>
      </div>
      <div class="summary-item">
        <span class="summary-value">{{ reviewResult.summary.new_part_count }}</span>
        <span class="summary-label">历史新料</span>
      </div>
      <div class="summary-item danger">
        <span class="summary-value">{{ reviewResult.summary.red_count }}</span>
        <span class="summary-label">选型高风险</span>
      </div>
      <div class="summary-item warning2">
        <span class="summary-value">{{ reviewResult.summary.yellow_count }}</span>
        <span class="summary-label">选型关注</span>
      </div>
    </div>

    <!-- 差异对比表格 -->
    <el-card v-if="reviewResult" class="section-card" data-testid="selection-review-result">
      <template #header>
        <div class="card-title-row">
          <span>差异明细</span>
          <el-tag v-if="reviewing" type="warning" size="small">加载中...</el-tag>
        </div>
      </template>
      <el-table
        :data="reviewResult.items"
        stripe
        border
        row-key="id"
        max-height="700"
        :row-class-name="diffRowClass"
      >
        <el-table-column type="index" label="#" width="50" fixed="left" />
        <el-table-column label="BOM 型号" min-width="150" fixed="left">
          <template #default="{ row }">
            <div class="mpn-cell">{{ displayValue(row.bom_part_number) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="BOM 品牌" width="100">
          <template #default="{ row }">
            <span class="brand-text">{{ displayValue(row.bom_brand) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="优选型号" min-width="160">
          <template #default="{ row }">
            <div v-if="row.pref_mpn" class="mpn-cell pref">{{ row.pref_mpn }}</div>
            <div v-else class="not-matched">未命中优选库</div>
          </template>
        </el-table-column>
        <el-table-column label="优选品牌" width="100">
          <template #default="{ row }">
            <span v-if="row.pref_brand">{{ row.pref_brand }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="优选等级" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.pref_preferred_level" :type="prefLevelTagType(row.pref_preferred_level)" size="small">
              {{ prefLevelLabel(row.pref_preferred_level) }}
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="命中" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="matchTagType(row.match_status)" size="small">
              {{ matchLabel(row.match_status) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 成本/交期/库存差异 -->
        <el-table-column label="优选参考价" width="110" align="right">
          <template #default="{ row }">
            <span v-if="row.pref_cost" class="cost-value">
              {{ formatPrice(row.pref_cost) }}
            </span>
            <span v-else class="text-muted">未录入</span>
          </template>
        </el-table-column>
        <el-table-column label="实际库存" width="100" align="right" sortable prop="bom_total_stock">
          <template #default="{ row }">
            <el-tag :type="stockTagType(row.bom_total_stock)" size="small">
              {{ stockLabel(row.bom_total_stock) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="实际交期" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.bom_lead_time_days" :class="leadClass(row.bom_lead_time_days)">
              {{ row.bom_lead_time_days }}天
            </span>
            <span v-else class="text-muted">暂无</span>
          </template>
        </el-table-column>
        <el-table-column label="实际单价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.bom_unit_price">{{ formatPrice(row.bom_unit_price) }}</span>
            <span v-else class="text-muted">暂无</span>
          </template>
        </el-table-column>
        <el-table-column label="生命周期" width="95" align="center">
          <template #default="{ row }">
            <el-tag :type="lifecycleTagType(row.bom_lifecycle_status)" size="small">
              {{ row.bom_lifecycle_status || '-' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="选型风险" width="85" align="center" sortable prop="selection_risk_level">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.selection_risk_level)" size="small">
              {{ riskLabel(row.selection_risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="差异说明 / 处置建议" min-width="260">
          <template #default="{ row }">
            <div class="reason-cell">
              <div class="reason-main">{{ row.selection_reason || row.delivery_control_reason || '-' }}</div>
              <div v-if="row.selection_action" class="action-text">{{ row.selection_action }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="替代建议" min-width="180">
          <template #default="{ row }">
            <span class="alt-tag" v-for="alt in (row.recommended_alternatives || [])" :key="alt.id || alt.mpn">
              {{ alt.brand || alt.normalized_brand }} {{ alt.mpn || alt.part_number }}
            </span>
            <span v-if="!(row.recommended_alternatives || []).length" class="text-muted">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { getPreferredSummary, importPreferredLibrary, reviewBomSelection } from '../api/preferredLibrary'
import { listBomProjects } from '../api/bom'

const selectedFile = ref(null)
const importing = ref(false)
const reviewing = ref(false)
const searching = ref(false)
const importResult = ref(null)
const reviewResult = ref(null)
const summary = ref({})
const projectId = ref(null)
const projectOptions = ref([])

async function loadSummary() {
  try {
    const { data } = await getPreferredSummary()
    summary.value = data
  } catch { /* ignore */ }
}

async function loadProjects() {
  try {
    const { data } = await listBomProjects()
    projectOptions.value = (data.projects || []).filter(p => p.status === 'active')
  } catch { /* ignore */ }
}

async function searchProjects(query) {
  if (!query) { await loadProjects(); return }
  searching.value = true
  try {
    const { data } = await listBomProjects()
    const keyword = query.toLowerCase()
    projectOptions.value = (data.projects || []).filter(p =>
      p.status === 'active' && (
        (p.project_name || '').toLowerCase().includes(keyword) ||
        String(p.id).includes(keyword)
      )
    )
  } catch { projectOptions.value = [] }
  finally { searching.value = false }
}

function onFileChange(file) { selectedFile.value = file.raw }

async function submitImport() {
  if (!selectedFile.value) return
  importing.value = true
  try {
    const { data } = await importPreferredLibrary(selectedFile.value)
    importResult.value = data
    await loadSummary()
    ElMessage.success('优选库导入完成')
  } finally { importing.value = false }
}

async function runReview() {
  if (!projectId.value) {
    ElMessage.warning('请选择 BOM 项目')
    return
  }
  reviewing.value = true
  try {
    const { data } = await reviewBomSelection(projectId.value)
    reviewResult.value = data
  } finally { reviewing.value = false }
}

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '暂无' : value
}

function formatPrice(val) {
  if (val == null) return '-'
  return '¥' + Number(val).toFixed(4)
}

function stockLabel(count) {
  if (count == null || count === 0) return '0'
  if (count >= 1000000) return (count / 1000000).toFixed(1) + 'M'
  if (count >= 1000) return (count / 1000).toFixed(1) + 'K'
  return String(count)
}

function stockTagType(count) {
  if (!count || count === 0) return 'danger'
  if (count < 1000) return 'warning'
  return 'success'
}

function leadClass(days) {
  if (!days) return ''
  if (days > 56) return 'text-danger'
  if (days > 28) return 'text-warning'
  return 'text-success'
}

function lifecycleTagType(status) {
  const map = { Active: 'success', NRND: 'warning', EOL: 'danger', Obsolete: 'danger' }
  return map[status] || 'info'
}

function prefLevelLabel(level) {
  const map = { strong_recommended: '强推', medium_recommended: '推荐', pending_review: '待审' }
  return map[level] || level
}

function prefLevelTagType(level) {
  const map = { strong_recommended: 'success', medium_recommended: '', pending_review: 'warning' }
  return map[level] || 'info'
}

function matchLabel(status) {
  const map = { exact_part_number: '精确', exact_brand_mpn: '品牌+型号', exact_mpn_package: '型号+封装', not_found: '未命中' }
  return map[status] || status
}

function matchTagType(status) {
  if (status === 'not_found') return 'danger'
  if (status && status.startsWith('exact')) return 'success'
  return 'info'
}

function riskLabel(level) {
  const map = { red: '高风险', yellow: '关注', green: '安全', info: '正常' }
  return map[level] || level
}

function riskTagType(level) {
  const map = { red: 'danger', yellow: 'warning', green: 'success' }
  return map[level] || 'info'
}

function diffRowClass({ row }) {
  if (row.selection_risk_level === 'red') return 'row-danger'
  if (row.match_status === 'not_found') return 'row-warning'
  return ''
}

function exportCsv() {
  if (!reviewResult.value) return
  const rows = reviewResult.value.items
  const headers = ['BOM型号','BOM品牌','优选型号','优选品牌','优选等级','命中状态',
    '优选参考价','实际库存','实际交期(天)','实际单价','生命周期','选型风险','差异说明','处置建议']
  const lines = [headers.map(h => '"' + h + '"').join(',')]
  for (const r of rows) {
    lines.push([
      r.bom_part_number, r.bom_brand, r.pref_mpn || '', r.pref_brand || '',
      prefLevelLabel(r.pref_preferred_level || ''), matchLabel(r.match_status),
      r.pref_cost ?? '', r.bom_total_stock ?? '', r.bom_lead_time_days ?? '',
      r.bom_unit_price ?? '', r.bom_lifecycle_status || '',
      riskLabel(r.selection_risk_level), r.selection_reason || '',
      r.selection_action || ''
    ].map(v => '"' + String(v ?? '').replace(/"/g, '""') + '"').join(','))
  }
  const blob = new Blob(['\uFEFF' + lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = '优选库对比_' + (reviewResult.value.summary?.project_name || 'export') + '.csv'
  a.click()
}

onMounted(() => { loadSummary(); loadProjects() })
</script>

<style scoped>
.preferred-library { padding: 20px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { margin: 0 0 8px; }
.page-header p { margin: 0; color: #667085; }
.section-card { margin-bottom: 16px; }
.review-actions { display: flex; align-items: center; gap: 12px; }
.review-actions label { font-size: 14px; color: #606266; white-space: nowrap; }
.card-title-row { display: flex; align-items: center; gap: 12px; }
.result-json { background: #f7f9fc; padding: 12px; border-radius: 6px; white-space: pre-wrap; max-height: 200px; overflow: auto; }

.summary-strip { display: grid; grid-template-columns: repeat(6, minmax(100px, 1fr)); gap: 10px; margin-bottom: 14px; }
.summary-item { padding: 12px 14px; border-radius: 10px; background: #f5f7fa; border: 1px solid #ebeef5; }
.summary-item.success { border-left: 3px solid #67c23a; }
.summary-item.warning { border-left: 3px solid #e6a23c; }
.summary-item.warning2 { border-left: 3px solid #e6a23c; }
.summary-item.danger { border-left: 3px solid #f56c6c; }
.summary-value { display: block; font-size: 22px; font-weight: 700; color: #303133; }
.summary-label { display: block; margin-top: 3px; font-size: 12px; color: #909399; }

.mpn-cell { font-weight: 600; color: #303133; }
.mpn-cell.pref { color: #409eff; }
.brand-text { color: #303133; }
.not-matched { color: #f56c6c; font-style: italic; font-size: 12px; }
.text-muted { color: #c0c4cc; }
.text-danger { color: #f56c6c; font-weight: 600; }
.text-warning { color: #e6a23c; }
.text-success { color: #67c23a; }

.cost-value { font-family: 'Consolas', monospace; color: #303133; }
.reason-cell { font-size: 13px; }
.reason-main { color: #606266; }
.action-text { margin-top: 4px; color: #e6a23c; font-size: 12px; }
.alt-tag { display: inline-block; background: #ecf5ff; color: #409eff; padding: 1px 8px; border-radius: 4px; margin: 2px 4px 2px 0; font-size: 12px; }

.option-project { display: flex; flex-direction: column; }
.option-name { font-weight: 500; }
.option-meta { font-size: 12px; color: #909399; margin-top: 2px; }
</style>

<style>
.row-danger td { background: #fef0f0 !important; }
.row-warning td { background: #fdf6ec !important; }
</style>
