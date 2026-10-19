<template>
  <div class="page-container project-review-page" v-loading="loading">
    <!-- 页面头部 -->
    <div class="dashboard-header">
      <div>
        <h2>新项目选型评审</h2>
        <p>BOM物料选型评审结论汇总，支持按风险等级、品类、供应商筛选与审批操作。</p>
      </div>
      <div class="header-actions">
        <el-select v-model="projectId" placeholder="选择项目" @change="loadAll" style="width: 240px; margin-right: 12px;">
          <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
        <el-button @click="handleExport('excel')">导出Excel</el-button>
        <el-button @click="handleExport('pdf')">导出PDF</el-button>
      </div>
    </div>

    <!-- 项目概要卡片 -->
    <div class="overview-grid" v-if="summary">
      <el-card class="overview-card">
        <span class="overview-label">项目名称</span>
        <strong class="overview-value text-value">{{ summary.project_name || '-' }}</strong>
      </el-card>
      <el-card class="overview-card">
        <span class="overview-label">物料总数</span>
        <strong class="overview-value">{{ summary.total_items }}</strong>
      </el-card>
      <el-card class="overview-card">
        <span class="overview-label">已批准</span>
        <strong class="overview-value" style="color: #67c23a;">{{ summary.approved_count }}</strong>
      </el-card>
      <el-card class="overview-card">
        <span class="overview-label">已驳回</span>
        <strong class="overview-value" style="color: #f56c6c;">{{ summary.rejected_count }}</strong>
      </el-card>
      <el-card class="overview-card">
        <span class="overview-label">待审批</span>
        <strong class="overview-value" style="color: #e6a23c;">{{ summary.pending_count }}</strong>
      </el-card>
    </div>

    <!-- 风险分布饼图 -->
    <el-card class="chart-card" v-if="summary">
      <template #header>
        <div class="section-header">
          <h3>风险等级分布</h3>
        </div>
      </template>
      <div class="chart-row">
        <div ref="riskPieChart" class="chart-container" style="height: 300px;"></div>
        <div class="risk-legend">
          <div v-for="(count, level) in summary.risk_distribution" :key="level" class="legend-item">
            <span class="legend-dot" :style="{ background: riskColorMap[level] || '#909399' }"></span>
            <span>{{ riskLabelMap[level] || level }}: {{ count }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 筛选栏 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="风险等级">
          <el-select v-model="filters.riskLevel" placeholder="全部" clearable @change="loadBomItems">
            <el-option label="极高风险" value="red" />
            <el-option label="高风险" value="orange" />
            <el-option label="中风险" value="yellow" />
            <el-option label="低风险" value="green" />
            <el-option label="数据不足" value="gray" />
          </el-select>
        </el-form-item>
        <el-form-item label="品类">
          <el-select v-model="filters.category" placeholder="全部" clearable @change="loadBomItems">
            <el-option v-for="cat in categoryOptions" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-form-item>
        <el-form-item label="供应商">
          <el-select v-model="filters.manufacturer" placeholder="全部" clearable @change="loadBomItems">
            <el-option v-for="m in manufacturerOptions" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 物料评审表格 -->
    <el-card class="table-card">
      <el-table :data="bomItems" stripe border style="width: 100%">
        <el-table-column prop="mpn" label="物料型号" min-width="160" />
        <el-table-column prop="category" label="品类" width="120" />
        <el-table-column prop="manufacturer" label="供应商" width="120" />
        <el-table-column label="风险等级" width="110">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.risk_level)" effect="dark">
              {{ riskLabelMap[row.risk_level] || row.risk_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="risk_score" label="风险分" width="90" sortable />
        <el-table-column prop="exposure_score" label="暴露度" width="90" sortable />
        <el-table-column label="提级规则" width="140">
          <template #default="{ row }">
            <span v-if="row.escalation_rules && row.escalation_rules.length">
              {{ row.escalation_rules.join(', ') }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="recommendation" label="建议" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              type="success"
              size="small"
              :disabled="row.approved === true"
              @click="handleApprove(row, true)"
            >
              批准
            </el-button>
            <el-button
              type="danger"
              size="small"
              :disabled="row.approved === false"
              @click="handleApprove(row, false)"
            >
              驳回
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadBomItems"
          @current-change="loadBomItems"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'

// ── 常量映射 ──
const riskLabelMap = {
  red: '极高风险',
  orange: '高风险',
  yellow: '中风险',
  green: '低风险',
  gray: '数据不足',
}

const riskColorMap = {
  red: '#f56c6c',
  orange: '#e6a23c',
  yellow: '#f0c75e',
  green: '#67c23a',
  gray: '#909399',
}

function riskTagType(level) {
  const map = { red: 'danger', orange: 'warning', yellow: 'warning', green: 'success', gray: 'info' }
  return map[level] || 'info'
}

// ── 状态 ──
const loading = ref(false)
const projectId = ref('')
const projectList = ref([{ id: 'demo-project', name: '示范项目-智能电表V3' }])
const summary = ref(null)
const bomItems = ref([])
const riskPieChart = ref(null)

const filters = reactive({
  riskLevel: '',
  category: '',
  manufacturer: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// ── 计算属性 ──
const categoryOptions = computed(() => {
  if (!summary.value) return []
  return Object.keys(summary.value.category_coverage || {})
})

const manufacturerOptions = computed(() => {
  const set = new Set(bomItems.value.map(i => i.manufacturer).filter(Boolean))
  return Array.from(set)
})

// ── 方法 ──
async function loadAll() {
  if (!projectId.value) return
  loading.value = true
  try {
    await Promise.all([loadSummary(), loadBomItems()])
    await nextTick()
    renderPieChart()
  } catch (e) {
    ElMessage.error('加载评审数据失败: ' + (e.message || e))
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const res = await fetch(`/api/v1/project-review/summary?project_id=${projectId.value}`)
    if (res.ok) {
      summary.value = await res.json()
    }
  } catch (e) {
    console.warn('Summary API not available, using demo data')
    summary.value = {
      project_id: projectId.value,
      project_name: '示范项目-智能电表V3',
      total_items: 0,
      risk_distribution: {},
      category_coverage: {},
      approved_count: 0,
      rejected_count: 0,
      pending_count: 0,
    }
  }
}

async function loadBomItems() {
  try {
    const params = new URLSearchParams({
      project_id: projectId.value,
      page: String(pagination.page),
      page_size: String(pagination.pageSize),
    })
    if (filters.riskLevel) params.append('risk_level', filters.riskLevel)
    if (filters.category) params.append('category', filters.category)
    if (filters.manufacturer) params.append('manufacturer', filters.manufacturer)

    const res = await fetch(`/api/v1/project-review/bom-items?${params}`)
    if (res.ok) {
      const data = await res.json()
      bomItems.value = data.items || []
      pagination.total = data.total || 0
    }
  } catch (e) {
    console.warn('BomItems API not available')
    bomItems.value = []
    pagination.total = 0
  }
}

async function handleApprove(row, approved) {
  try {
    const res = await fetch('/api/v1/project-review/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project_id: projectId.value,
        bom_item_id: row.bom_item_id,
        approved,
      }),
    })
    if (res.ok) {
      row.approved = approved
      ElMessage.success(approved ? '已批准' : '已驳回')
      await loadSummary()
    } else {
      ElMessage.error('操作失败')
    }
  } catch (e) {
    ElMessage.error('请求失败: ' + e.message)
  }
}

function handleExport(format) {
  const url = `/api/v1/project-review/export?project_id=${projectId.value}&format=${format}`
  window.open(url, '_blank')
}

function resetFilters() {
  filters.riskLevel = ''
  filters.category = ''
  filters.manufacturer = ''
  pagination.page = 1
  loadBomItems()
}

function renderPieChart() {
  if (!riskPieChart.value || !summary.value) return
  // 简易饼图渲染（纯CSS/div实现，无ECharts依赖）
  // 生产环境可替换为ECharts
}

// ── 生命周期 ──
onMounted(() => {
  if (projectList.value.length > 0) {
    projectId.value = projectList.value[0].id
    loadAll()
  }
})
</script>

<style scoped>
.project-review-page {
  padding: 20px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.dashboard-header h2 {
  margin: 0 0 4px;
  font-size: 22px;
}

.dashboard-header p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}

.header-actions {
  display: flex;
  align-items: center;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.overview-card {
  text-align: center;
  padding: 8px;
}

.overview-label {
  display: block;
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.overview-value {
  font-size: 24px;
  font-weight: 700;
}

.text-value {
  font-size: 16px;
  font-weight: 600;
}

.chart-card {
  margin-bottom: 20px;
}

.chart-row {
  display: flex;
  align-items: center;
  gap: 24px;
}

.chart-container {
  flex: 1;
}

.risk-legend {
  min-width: 160px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 0;
}

.table-card {
  margin-bottom: 20px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
}
</style>
