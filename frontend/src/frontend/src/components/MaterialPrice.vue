<template>
  <div class="material-price-monitor">
    <div class="monitor-header">
      <h3>数据新鲜度监控</h3>
      <el-button type="primary" size="small" :loading="refreshing" @click="handleRefresh">
        <el-icon><Refresh /></el-icon>
        手动刷新
      </el-button>
    </div>

    <!-- 数据源健康状态汇总 -->
    <div class="source-health-grid">
      <div
        v-for="(health, source) in sourceHealth"
        :key="source"
        class="source-health-card"
        :class="healthClass(health)"
      >
        <div class="source-name">{{ sourceLabel(source) }}</div>
        <div class="source-stats">
          <span class="stat-fresh">
            <el-icon :color="'#67c23a'"><CircleCheck /></el-icon>
            {{ health.fresh_count }} 正常
          </span>
          <span class="stat-stale">
            <el-icon :color="health.stale_count > 0 ? '#f56c6c' : '#909399'"><Warning /></el-icon>
            {{ health.stale_count }} 过期
          </span>
        </div>
        <div class="source-meta">
          <span>平均新鲜度: {{ health.avg_freshness_hours.toFixed(1) }}h</span>
          <span v-if="health.last_success_at">
            最后更新: {{ formatTime(health.last_success_at) }}
          </span>
        </div>
        <div v-if="health.degraded" class="degraded-badge">降级中</div>
      </div>
    </div>

    <!-- 过期预警列表 -->
    <div v-if="alerts.length > 0" class="alerts-section">
      <h4>过期预警 ({{ alerts.length }})</h4>
      <el-table :data="alerts" size="small" :row-class-name="alertRowClass">
        <el-table-column prop="material_key" label="材料代码" width="160" />
        <el-table-column prop="source" label="数据源" width="120">
          <template #default="{ row }">{{ sourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column prop="hours_since_update" label="距上次更新" width="140">
          <template #default="{ row }">{{ row.hours_since_update.toFixed(1) }} 小时</template>
        </el-table-column>
        <el-table-column prop="threshold_hours" label="阈值" width="100">
          <template #default="{ row }">{{ row.threshold_hours }}h</template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度" width="100">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'critical' ? 'danger' : 'warning'" size="small">
              {{ row.severity === 'critical' ? '严重' : '警告' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 无预警提示 -->
    <div v-else-if="!loading" class="all-fresh">
      <el-icon :size="32" color="#67c23a"><CircleCheck /></el-icon>
      <span>所有数据源状态正常</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh, CircleCheck, Warning } from '@element-plus/icons-vue'

const props = defineProps({
  apiUrl: { type: String, default: '/api/v1/material-freshness' }
})

const loading = ref(false)
const refreshing = ref(false)
const freshnessData = ref([])
const sourceHealth = ref({})
const alerts = ref([])

const sourceLabels = {
  smm: 'SMM 上海有色网',
  mysteel: 'Mysteel 我的钢铁',
  lme: 'LME 伦敦金属',
  metals_api: 'Metals-API',
  asian_metal: 'Asian Metal',
  none: '无数据'
}

function sourceLabel(source) {
  return sourceLabels[source] || source
}

function healthClass(health) {
  if (health.degraded) return 'health-critical'
  if (health.stale_count > 0) return 'health-warning'
  return 'health-ok'
}

function alertRowClass({ row }) {
  if (row.severity === 'critical') return 'alert-row-critical'
  return 'alert-row-warning'
}

function formatTime(isoStr) {
  if (!isoStr) return '-'
  const d = new Date(isoStr)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

async function fetchFreshness() {
  loading.value = true
  try {
    const res = await fetch(props.apiUrl)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    freshnessData.value = data.freshness || []
    sourceHealth.value = data.source_health || {}
    alerts.value = data.alerts || []
  } catch (e) {
    console.warn('[MaterialPrice] 获取新鲜度数据失败:', e)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  await fetchFreshness()
}

onMounted(() => {
  fetchFreshness()
})
</script>

<style scoped>
.material-price-monitor {
  padding: 16px;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.monitor-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.source-health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.source-health-card {
  padding: 14px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  position: relative;
  transition: border-color 0.2s;
}

.source-health-card.health-ok {
  border-left: 3px solid #67c23a;
}

.source-health-card.health-warning {
  border-left: 3px solid #e6a23c;
}

.source-health-card.health-critical {
  border-left: 3px solid #f56c6c;
}

.source-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
}

.source-stats {
  display: flex;
  gap: 12px;
  font-size: 13px;
  margin-bottom: 6px;
}

.stat-fresh, .stat-stale {
  display: flex;
  align-items: center;
  gap: 4px;
}

.source-meta {
  display: flex;
  flex-direction: column;
  font-size: 12px;
  color: #909399;
  gap: 2px;
}

.degraded-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  background: #fef0f0;
  color: #f56c6c;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 500;
}

.alerts-section {
  margin-top: 16px;
}

.alerts-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #303133;
}

.all-fresh {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px;
  color: #67c23a;
  font-size: 14px;
}

:deep(.alert-row-critical) {
  background-color: #fef0f0;
}

:deep(.alert-row-warning) {
  background-color: #fdf6ec;
}
</style>
