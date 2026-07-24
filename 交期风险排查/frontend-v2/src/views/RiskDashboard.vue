<template>
  <div class="dashboard-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>风险仪表盘</h2>
        <p>双轨风险总览：材料传导轨（铜/银/铝 → PCB/继电器/电容）+ 供需信号轨（交期/库存/产能/行业需求）</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadAll">刷新</el-button>
    </div>

    <!-- 总览卡片 -->
    <div class="overview-grid">
      <div v-for="card in overviewCards" :key="card.label" class="overview-card" :class="card.cssClass">
        <span class="ov-label">{{ card.label }}</span>
        <strong class="ov-value">{{ card.value }}</strong>
      </div>
    </div>

    <!-- ====== 双轨风险看板 ====== -->
    <div class="dual-track-board">
      <!-- 第一轨：材料传导 -->
      <el-card class="track-card material-track">
        <template #header>
          <div class="track-header">
            <h3>🔗 材料传导轨</h3>
            <span class="track-desc">原材料 → 组份 → 器件成本</span>
          </div>
        </template>
        <div class="track-chains">
          <div v-for="chain in materialChains" :key="chain.key" class="track-chain-row" @click="goMaterialChain(chain.key)">
            <div class="chain-left">
              <span class="chain-material" :class="{ alert: chain.materialAlert }">{{ chain.material }}</span>
              <span class="chain-arrow">→</span>
              <span class="chain-mid">{{ chain.midNode }}</span>
              <span class="chain-arrow">→</span>
              <span class="chain-category">{{ chain.category }}</span>
            </div>
            <div class="chain-right">
              <span v-if="chain.priceChange" class="chain-change" :class="chain.priceChange > 0 ? 'up' : 'down'">
                {{ chain.priceChange > 0 ? '+' : '' }}{{ chain.priceChange }}%
              </span>
              <el-tag :type="riskTag(chain.riskLevel)" size="small">
                {{ riskLabel(chain.riskLevel) }}
              </el-tag>
              <span class="chain-impact">命中 {{ chain.itemCount }} 物料 / {{ chain.projectCount }} 项目</span>
            </div>
          </div>
        </div>
        <el-empty v-if="!materialChains.length" description="暂无材料传导数据" :image-size="40" />
      </el-card>

      <!-- 第二轨：供需信号 -->
      <el-card class="track-card demand-track">
        <template #header>
          <div class="track-header">
            <h3>📡 供需信号轨</h3>
            <span class="track-desc">交期 · 库存 · 产能 · 行业需求 · 同行联动</span>
          </div>
        </template>
        <div class="track-signals">
          <div v-for="sig in demandSignals" :key="sig.key" class="track-signal-row">
            <div class="signal-left">
              <el-tag :type="sig.severity === 'critical' ? 'danger' : 'warning'" size="small">{{ sig.category }}</el-tag>
              <strong>{{ sig.title }}</strong>
            </div>
            <div class="signal-right">
              <span class="signal-evidence">{{ sig.evidence }}</span>
              <span class="signal-impact">影响 {{ sig.itemCount }} 物料 / {{ sig.projectCount }} 项目</span>
            </div>
          </div>
        </div>
        <el-empty v-if="!demandSignals.length" description="暂无供需异常信号" :image-size="40" />
      </el-card>
    </div>

    <!-- 项目风险列表 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header-row">
          <h3>项目风险</h3>
          <span class="card-hint">{{ summary?.overview?.risk_stat_note || '高风险 = 红色物料 > 0' }}</span>
        </div>
      </template>
      <el-empty v-if="!projectRisks.length" description="暂无项目风险数据" :image-size="40" />
      <el-table v-else :data="projectRisks" size="small" stripe>
        <el-table-column prop="project_name" label="项目" show-overflow-tooltip />
        <el-table-column label="风险分布" width="220">
          <template #default="{ row }">
            <span class="risk-tag rt-red">红{{ riskCount(row, 'red') }}</span>
            <span class="risk-tag rt-yellow">黄{{ riskCount(row, 'yellow') }}</span>
            <span class="risk-tag rt-green">绿{{ riskCount(row, 'green') }}</span>
            <span class="risk-tag rt-gray">灰{{ riskCount(row, 'gray') }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openProject(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 风险变化 + 近期事件 -->
    <div class="two-col">
      <el-card class="section-card change-card">
        <template #header><h3>风险变化 · 近 {{ riskChanges.window_days || 7 }} 天</h3></template>
        <div class="change-stats">
          <div class="change-stat danger">+{{ riskChanges.new_red_item_count || 0 }}<span>红色</span></div>
          <div class="change-stat warning">+{{ riskChanges.new_yellow_item_count || 0 }}<span>黄色</span></div>
          <div class="change-stat">{{ riskChanges.changed_project_count || 0 }}<span>变化项目</span></div>
          <div class="change-stat">{{ riskChanges.recent_event_count_7d || 0 }}<span>7天事件</span></div>
        </div>
        <div v-if="riskChangeProjects.length" class="change-list">
          <div v-for="p in riskChangeProjects.slice(0, 5)" :key="p.project_id" class="change-row">
            <span>{{ p.project_name }}</span>
            <span class="change-detail">+红{{ p.new_red_count || 0 }} +黄{{ p.new_yellow_count || 0 }}</span>
            <el-button link type="primary" size="small" @click="openProject(p)">查看</el-button>
          </div>
        </div>
      </el-card>

      <el-card class="section-card">
        <template #header><h3>近期活跃事件</h3></template>
        <el-empty v-if="!recentEvents.length" description="暂无活跃事件" :image-size="40" />
        <div v-else class="event-list">
          <div v-for="e in recentEvents.slice(0, 8)" :key="e.id" class="event-row">
            <span class="event-title">{{ e.title }}</span>
            <span class="event-source">{{ e.source_name || '未知来源' }}</span>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 供应源状态 -->
    <el-card class="section-card" v-if="supplySources.length">
      <template #header><h3>供应源状态</h3></template>
      <el-table :data="supplySources" size="small" stripe>
        <el-table-column label="来源">
          <template #default="{ row }">{{ row.name || row.source || row.source_id }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag size="small" :type="row.status === 'active' ? 'success' : 'danger'">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="说明" show-overflow-tooltip>
          <template #default="{ row }">{{ row.failure_reason || '正常运行' }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getDashboardSummary } from '../api/dashboard'
import axios from 'axios'

const router = useRouter()
const loading = ref(false)
const summary = ref(null)

const overview = computed(() => summary.value?.overview || {})
const projectRisks = computed(() => summary.value?.project_risks || [])
const recentEvents = computed(() => summary.value?.recent_events || [])
const riskChanges = computed(() => summary.value?.risk_changes || {})
const riskChangeProjects = computed(() => riskChanges.value.projects || [])
const supplySources = computed(() => summary.value?.supply_sources || [])

const overviewCards = computed(() => [
  { label: '项目总数', value: overview.value.project_count ?? 0, cssClass: '' },
  { label: '高风险项目', value: overview.value.high_risk_project_count ?? 0, cssClass: 'danger' },
  { label: '红色物料', value: overview.value.red_item_count ?? 0, cssClass: 'danger' },
  { label: '活跃事件(30天)', value: overview.value.active_event_count_30d ?? 0, cssClass: 'warning' },
  { label: '待处理行动', value: overview.value.pending_action_count ?? 0, cssClass: 'info' }
])

// 双轨数据（从后端 /api/dashboard/dual-track 获取）
const materialChains = ref([])
const demandSignals = ref([])

onMounted(loadAll)

async function loadAll() {
  loading.value = true
  try {
    const [{ data: summaryData }, dualTrackResp] = await Promise.all([
      getDashboardSummary(),
      axios.get('/api/dashboard/dual-track').catch(() => ({ data: null }))
    ])
    summary.value = summaryData

    const dt = dualTrackResp?.data
    if (dt?.material_chains?.length) {
      materialChains.value = dt.material_chains.map(c => ({
        key: c.key,
        material: c.material,
        materialAlert: c.material_alert,
        midNode: c.mid_node,
        category: c.category,
        riskLevel: c.risk_level,
        riskLabel: { red: 'red', orange: 'orange', yellow: 'yellow', green: 'green' }[c.risk_level] || c.risk_level,
        itemCount: c.item_count,
        projectCount: c.project_count,
        passThrough: c.pass_through,
        lag: c.lag,
        events: c.events || [],
      }))
    }
    if (dt?.demand_signals?.length) {
      demandSignals.value = dt.demand_signals.map(s => ({
        key: `${s.category}_${s.event_type}`,
        category: s.category,
        severity: s.severity,
        title: s.title,
        evidence: s.evidence,
        itemCount: s.item_count,
        projectCount: s.project_count,
      }))
    }
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '加载失败') } finally { loading.value = false }
}

function riskTag(level) {
  const m = { red: 'danger', orange: 'warning', yellow: 'warning', green: 'success', gray: 'info' }
  return m[level] || 'info'
}
function riskLabel(level) {
  const m = { red: '高风险', orange: '中高风险', yellow: '关注', green: '安全', gray: '无数据' }
  return m[level] || level
}

function riskCount(row, key) { return row?.risk_counts?.[key] ?? row?.[`${key}_count`] ?? row?.[key] ?? 0 }
function openProject(row) { router.push(row?.target_route || `/projects/${row.project_id}`) }
function goMaterialChain(key) { router.push(`/material-chain?category=${key}`) }
</script>

<style scoped>
.dashboard-page { display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-header h2 { margin: 0; font-size: 22px; color: #1f2d3d; }
.page-header p { margin: 6px 0 0; color: #909399; font-size: 13px; max-width: 600px; }

.overview-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.overview-card { padding: 16px; border-radius: 12px; background: #fff; border: 1px solid #ebeef5; }
.overview-card.danger { border-left: 3px solid #f56c6c; }
.overview-card.warning { border-left: 3px solid #e6a23c; }
.overview-card.info { border-left: 3px solid #409eff; }
.ov-label { font-size: 13px; color: #909399; }
.ov-value { display: block; margin-top: 8px; font-size: 26px; color: #303133; font-weight: 700; }
.overview-card.danger .ov-value { color: #f56c6c; }

/* 双轨看板 */
.dual-track-board { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.track-card { border-radius: 12px; }
.material-track { border-top: 3px solid #e6a23c; }
.demand-track { border-top: 3px solid #409eff; }
.track-header { display: flex; justify-content: space-between; align-items: center; }
.track-header h3 { margin: 0; font-size: 15px; }
.track-desc { font-size: 12px; color: #909399; }

.track-chain-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; cursor: pointer; transition: background 0.2s; }
.track-chain-row:hover { background: #f5f7fa; margin: 0 -12px; padding-left: 12px; padding-right: 12px; border-radius: 6px; }
.chain-left { display: flex; align-items: center; gap: 8px; font-size: 13px; flex-wrap: wrap; }
.chain-material { font-weight: 600; color: #303133; }
.chain-material.alert { color: #f56c6c; }
.chain-arrow { color: #c0c4cc; }
.chain-mid { color: #606266; }
.chain-category { color: #409eff; font-weight: 600; }
.chain-right { display: flex; align-items: center; gap: 10px; }
.chain-change { font-weight: 600; font-size: 13px; }
.chain-change.up { color: #f56c6c; }
.chain-change.down { color: #67c23a; }
.chain-impact { font-size: 11px; color: #909399; }

.track-signal-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f5f5f5; }
.signal-left { display: flex; align-items: center; gap: 8px; }
.signal-left strong { font-size: 14px; color: #303133; }
.signal-right { display: flex; flex-direction: column; gap: 2px; align-items: flex-end; }
.signal-evidence { font-size: 12px; color: #606266; }
.signal-impact { font-size: 11px; color: #909399; }

.two-col { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.section-card { border-radius: 12px; }
.card-header-row { display: flex; justify-content: space-between; align-items: center; }
.card-header-row h3, .section-card h3 { margin: 0; font-size: 15px; color: #303133; }
.card-hint { font-size: 12px; color: #909399; }

.risk-tag { margin-right: 8px; font-size: 12px; color: #909399; }
.rt-red { color: #f56c6c; font-weight: 600; }
.rt-yellow { color: #e6a23c; font-weight: 600; }
.rt-green { color: #67c23a; }
.rt-gray { color: #909399; }

.change-card { border-left: 4px solid #409eff; }
.change-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }
.change-stat { padding: 10px; border-radius: 8px; background: #f5f7fa; text-align: center; font-size: 20px; font-weight: 700; color: #303133; }
.change-stat span { display: block; font-size: 11px; color: #909399; font-weight: 400; margin-top: 2px; }
.change-stat.danger { color: #f56c6c; }
.change-stat.warning { color: #e6a23c; }
.change-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 6px 0; border-top: 1px solid #f5f5f5; font-size: 13px; }
.change-detail { font-size: 12px; color: #f56c6c; }

.event-list { display: flex; flex-direction: column; gap: 4px; }
.event-row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f5f5f5; font-size: 13px; }
.event-title { color: #303133; flex: 1; }
.event-source { color: #909399; font-size: 12px; }

@media (max-width: 1200px) { .dual-track-board, .two-col, .overview-grid { grid-template-columns: 1fr; } }
</style>
