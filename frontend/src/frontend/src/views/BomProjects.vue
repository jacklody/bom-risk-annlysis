<template>
  <div class="page-container bom-projects-page">
    <el-card class="projects-card" v-loading="loading">
      <template #header>
        <div class="card-header">
          <div>
            <h2>BOM 项目</h2>
            <p class="sub-title">查看已上传/已分析的历史 BOM，并进入详情复查风险项</p>
          </div>
          <el-button type="primary" :loading="loading" data-testid="refresh-projects" @click="loadProjects">
            刷新列表
          </el-button>
        </div>
      </template>

      <div class="summary-strip">
        <div class="summary-item">
          <span class="summary-value">{{ projects.length }}</span>
          <span class="summary-label">历史BOM</span>
        </div>
        <div class="summary-item danger">
          <span class="summary-value">{{ totalRed }}</span>
          <span class="summary-label">高风险项</span>
        </div>
        <div class="summary-item warning">
          <span class="summary-value">{{ totalYellow }}</span>
          <span class="summary-label">关注项</span>
        </div>
        <div class="summary-item success">
          <span class="summary-value">{{ totalGreen }}</span>
          <span class="summary-label">安全项</span>
        </div>
      </div>

      <el-empty v-if="!loading && projects.length === 0" description="暂无历史 BOM 项目，请先在上传分析页导入 BOM" />

      <el-table v-else :data="projects" stripe row-key="id" class="projects-table">
        <el-table-column label="BOM项目" min-width="260">
          <template #default="{ row }">
            <div class="project-name">{{ row.project_name }}</div>
            <div class="project-file">{{ row.filename }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="物料数量" width="110">
          <template #default="{ row }">
            共 {{ row.total_items || 0 }} 项
          </template>
        </el-table-column>
        <el-table-column label="风险概览" min-width="240">
          <template #default="{ row }">
            <div class="risk-tags">
              <el-tag type="danger" size="small">高风险 {{ row.items_red || 0 }}</el-tag>
              <el-tag type="warning" size="small">关注 {{ row.items_yellow || 0 }}</el-tag>
              <el-tag type="success" size="small">安全 {{ row.items_green || 0 }}</el-tag>
              <el-tag type="info" size="small">无数据 {{ row.items_gray || 0 }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="新增风险" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.has_new_risks" type="danger" size="small">
              新增风险 {{ (row.new_red_count || 0) + (row.new_yellow_count || 0) }}
            </el-tag>
            <span v-else class="muted">无</span>
          </template>
        </el-table-column>
        <el-table-column label="最近分析" width="180">
          <template #default="{ row }">
            {{ formatDate(row.last_analysis_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              size="small"
              :data-testid="`open-project-${row.id}`"
              @click="openProject(row.id)"
            >
              查看详情
            </el-button>
            <el-button
              link
              type="warning"
              size="small"
              :data-testid="`risk-report-${row.id}`"
              @click="openReport(row.id)"
            >
              风险报告
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { listBomProjects } from '../api/bom'

const router = useRouter()
const loading = ref(false)
const projects = ref([])

const totalRed = computed(() => projects.value.reduce((sum, p) => sum + (p.items_red || 0), 0))
const totalYellow = computed(() => projects.value.reduce((sum, p) => sum + (p.items_yellow || 0), 0))
const totalGreen = computed(() => projects.value.reduce((sum, p) => sum + (p.items_green || 0), 0))

onMounted(loadProjects)

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await listBomProjects()
    projects.value = data.projects || []
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '历史BOM项目加载失败')
  } finally {
    loading.value = false
  }
}

function openProject(id) {
  router.push(`/projects/${id}`)
}

function openReport(id) {
  router.push(`/projects/${id}`)
}

function formatDate(value) {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.page-container {
  min-height: 100%;
}

.projects-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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

.projects-table {
  margin-top: 8px;
}

.project-name {
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
}

.project-file {
  margin-top: 4px;
  color: #909399;
  font-size: 12px;
  word-break: break-all;
}

.risk-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.muted {
  color: #909399;
}
</style>
