<template>
  <div class="page-container material-watch-page" v-loading="loading">
    <!-- 头部 -->
    <div class="dashboard-header">
      <div>
        <h2>原材料价格追踪</h2>
        <p>上游有色金属 · 稀土小金属 · 化工非金属 实时价格监控与交期风险预警</p>
      </div>
      <div class="header-actions">
        <el-select v-model="domainFilter" placeholder="全部数据域" clearable style="width:150px" @change="loadData">
          <el-option label="有色金属" value="metals" />
          <el-option label="稀土&小金属" value="rare_earth" />
          <el-option label="化工&非金属" value="chemical" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- 概览卡片 -->
    <div class="overview-grid">
      <el-card class="overview-card">
        <span class="overview-label">监控材料总数</span>
        <strong class="overview-value">{{ summary.total_materials || 0 }}</strong>
      </el-card>
      <el-card class="overview-card alert-red">
        <span class="overview-label">红色预警</span>
        <strong class="overview-value">{{ summary.red || 0 }}</strong>
      </el-card>
      <el-card class="overview-card alert-orange">
        <span class="overview-label">橙色预警</span>
        <strong class="overview-value">{{ summary.orange || 0 }}</strong>
      </el-card>
      <el-card class="overview-card alert-yellow">
        <span class="overview-label">黄色关注</span>
        <strong class="overview-value">{{ summary.yellow || 0 }}</strong>
      </el-card>
      <el-card class="overview-card alert-green">
        <span class="overview-label">绿色利好</span>
        <strong class="overview-value">{{ summary.green || 0 }}</strong>
      </el-card>
    </div>

    <!-- 主体区域：左右两栏 -->
    <div class="main-grid">
      <!-- 左栏：风险分布图 + 域概览 -->
      <div class="left-panel">
        <!-- 风险分布条形图 -->
        <el-card class="panel-card">
          <template #header><h3>风险分布</h3></template>
          <div class="risk-bars">
            <div class="risk-bar-row" v-for="bar in riskBars" :key="bar.level">
              <span class="risk-bar-label" :class="bar.cssClass">{{ bar.label }}</span>
              <div class="risk-bar-track">
                <div class="risk-bar-fill" :class="bar.cssClass"
                  :style="{ width: bar.pct + '%' }"></div>
              </div>
              <span class="risk-bar-count">{{ bar.count }}</span>
            </div>
          </div>
        </el-card>

        <!-- 域概览 -->
        <el-card class="panel-card">
          <template #header><h3>数据域概览</h3></template>
          <div class="domain-cards">
            <div class="domain-item" v-for="dom in domainSummaries" :key="dom.name">
              <div class="domain-header">
                <strong :class="`domain-${dom.key}`">{{ dom.name }}</strong>
                <el-tag size="small" :type="dom.healthy ? 'success' : 'warning'">
                  {{ dom.healthy ? '正常' : '降级' }}
                </el-tag>
              </div>
              <div class="domain-counts">
                <span>材料数 {{ dom.total }}</span>
                <span class="dot-red" v-if="dom.red">🔴 {{ dom.red }}</span>
                <span class="dot-orange" v-if="dom.orange">🟠 {{ dom.orange }}</span>
                <span class="dot-yellow" v-if="dom.yellow">🟡 {{ dom.yellow }}</span>
              </div>
              <div class="domain-bar">
                <div class="domain-bar-seg seg-red" :style="{ width: dom.redPct + '%' }" v-if="dom.red"></div>
                <div class="domain-bar-seg seg-orange" :style="{ width: dom.orangePct + '%' }" v-if="dom.orange"></div>
                <div class="domain-bar-seg seg-yellow" :style="{ width: dom.yellowPct + '%' }" v-if="dom.yellow"></div>
                <div class="domain-bar-seg seg-green" :style="{ width: dom.greenPct + '%' }" v-if="dom.green"></div>
                <div class="domain-bar-seg seg-normal" :style="{ flex: 1 }"></div>
              </div>
            </div>
          </div>
        </el-card>
      </div>

      <!-- 右栏：Top 涨跌快照 -->
      <div class="right-panel">
        <el-card class="panel-card">
          <template #header><h3>涨幅 Top-5</h3></template>
          <div class="top-list">
            <div v-if="!topSummary.top_rising || topSummary.top_rising.length === 0" class="empty-hint">暂无数据</div>
            <div class="top-item rising" v-for="item in topSummary.top_rising" :key="item.material_key">
              <span class="top-name">{{ item.material_name_zh }}</span>
              <el-tag size="small" :type="item.risk_level === 'RED' ? 'danger' : item.risk_level === 'ORANGE' ? 'warning' : ''">
                {{ item.risk_level }}
              </el-tag>
              <span class="top-pct up">{{ formatPct(item.change_pct) }}</span>
            </div>
          </div>
        </el-card>

        <el-card class="panel-card">
          <template #header><h3>跌幅 Top-5</h3></template>
          <div class="top-list">
            <div v-if="!topSummary.top_dropping || topSummary.top_dropping.length === 0" class="empty-hint">暂无数据</div>
            <div class="top-item dropping" v-for="item in topSummary.top_dropping" :key="item.material_key">
              <span class="top-name">{{ item.material_name_zh }}</span>
              <el-tag size="small" type="success" v-if="item.risk_level === 'GREEN'">GREEN</el-tag>
              <span class="top-pct down">{{ formatPct(item.change_pct) }}</span>
            </div>
          </div>
        </el-card>

        <!-- 缓存状态 -->
        <el-card class="panel-card cache-card">
          <template #header><h3>数据源状态</h3></template>
          <div class="cache-grid" v-if="cacheStats">
            <div class="cache-item">
              <span class="cache-label">缓存总数</span>
              <strong>{{ cacheStats.total_cached || 0 }}</strong>
            </div>
            <div class="cache-item">
              <span class="cache-label">新鲜缓存</span>
              <strong class="text-success">{{ cacheStats.fresh || 0 }}</strong>
            </div>
            <div class="cache-item">
              <span class="cache-label">过期缓存</span>
              <strong class="text-warning">{{ cacheStats.stale || 0 }}</strong>
            </div>
            <div class="cache-item">
              <span class="cache-label">Metal API 配额</span>
              <strong>{{ cacheStats.metals_api_calls_this_month || 0 }} / {{ cacheStats.metals_api_quota || 60 }}</strong>
            </div>
          </div>
          <el-alert v-if="cacheStats && cacheStats.degraded > 0" title="部分数据源降级" type="warning" :closable="false" show-icon style="margin-top:8px" />
        </el-card>
      </div>
    </div>

    <!-- 原材料预警列表 -->
    <el-card class="panel-card full-width">
      <template #header>
        <div class="table-header-row">
          <h3>原材料预警明细</h3>
          <div class="table-filters">
            <el-select v-model="riskFilter" placeholder="风险等级" clearable size="small" style="width:110px" @change="loadAlerts">
              <el-option label="红色" value="RED" />
              <el-option label="橙色" value="ORANGE" />
              <el-option label="黄色" value="YELLOW" />
              <el-option label="绿色" value="GREEN" />
            </el-select>
            <el-input v-model="searchKeyword" placeholder="搜索材料名称" clearable size="small" style="width:180px" @input="filterAlerts" />
          </div>
        </div>
      </template>
      <el-table :data="paginatedAlerts" stripe size="small" :default-sort="{ prop: 'risk_sort', order: 'ascending' }">
        <el-table-column prop="material_name_zh" label="材料名称" min-width="120" />
        <el-table-column prop="domain" label="数据域" width="110">
          <template #default="{ row }">{{ domainLabel(row.domain) }}</template>
        </el-table-column>
        <el-table-column prop="current_price" label="当前价格" width="110" align="right">
          <template #default="{ row }">{{ row.current_price?.toLocaleString() }} {{ row.price_unit || '' }}</template>
        </el-table-column>
        <el-table-column prop="change_pct" label="变动%" width="90" align="right" sortable>
          <template #default="{ row }">
            <span :class="row.change_pct > 0 ? 'text-up' : row.change_pct < 0 ? 'text-down' : ''">
              {{ formatPct(row.change_pct) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="risk_level" label="风险等级" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="riskTagType(row.risk_level)" size="small">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source_name" label="数据来源" width="130" />
        <el-table-column label="操作" width="80" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openTrend(row)">趋势</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-row">
        <span class="total-hint">共 {{ filteredAlerts.length }} 条</span>
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="filteredAlerts.length"
          layout="prev, pager, next"
          small
          background
        />
      </div>
    </el-card>

    <!-- 趋势详情抽屉 -->
    <el-drawer v-model="trendDrawer" title="价格趋势" size="500px">
      <template #header>
        <h3>{{ trendMaterial?.material_name_zh }} 价格趋势</h3>
      </template>
      <div v-loading="trendLoading">
        <div class="trend-stats" v-if="trendData?.stats">
          <div class="trend-stat-item">
            <span>最新价格</span>
            <strong>{{ trendData.stats.latest_price?.toLocaleString() }} {{ trendData.unit }}</strong>
          </div>
          <div class="trend-stat-item">
            <span>期间均价</span>
            <strong>{{ trendData.stats.avg_price_period?.toLocaleString() }}</strong>
          </div>
          <div class="trend-stat-item">
            <span>期间最高</span>
            <strong class="text-up">{{ trendData.stats.max_price_period?.toLocaleString() }}</strong>
          </div>
          <div class="trend-stat-item">
            <span>期间最低</span>
            <strong class="text-down">{{ trendData.stats.min_price_period?.toLocaleString() }}</strong>
          </div>
          <div class="trend-stat-item">
            <span>波动率</span>
            <strong>{{ trendData.stats.volatility_pct }}%</strong>
          </div>
        </div>

        <!-- CSS 迷你趋势图 -->
        <div class="mini-trend-chart" v-if="trendData?.daily_trends?.length">
          <div class="chart-bars">
            <div class="chart-bar-item" v-for="(day, i) in trendBars" :key="i"
              :style="{ height: day.height + '%' }"
              :title="`${day.date}: ¥${day.avg_price}`">
              <div class="chart-bar-date">{{ day.shortDate }}</div>
            </div>
          </div>
        </div>

        <!-- 30日基线对比 -->
        <div class="baseline-compare" v-if="trendData?.current_vs_30d_baseline">
          <div class="compare-row">
            <span>当前价格</span>
            <strong>{{ trendData.current_vs_30d_baseline.current_price?.toLocaleString() }}</strong>
          </div>
          <div class="compare-row">
            <span>30日均价</span>
            <strong>{{ trendData.current_vs_30d_baseline.baseline_30d?.toLocaleString() }}</strong>
          </div>
          <div class="compare-row">
            <span>偏离幅度</span>
            <strong :class="trendData.current_vs_30d_baseline.change_pct > 0 ? 'text-up' : 'text-down'">
              {{ formatPct(trendData.current_vs_30d_baseline.change_pct) }}
            </strong>
          </div>
        </div>

        <div v-if="trendData?.data_points === 0" class="empty-hint">暂无历史价格数据</div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import {
  getMaterialAlerts,
  getMaterialSummary,
  getMaterialTrends,
  getMaterialCacheStats
} from '../api/materialAlerts'
import { ElMessage } from 'element-plus'

// ── 状态 ──
const loading = ref(false)
const trendLoading = ref(false)
const domainFilter = ref('')
const riskFilter = ref('')
const searchKeyword = ref('')
const currentPage = ref(1)
const pageSize = ref(20)

const alerts = ref([])
const summary = reactive({})
const topSummary = reactive({ top_rising: [], top_dropping: [] })
const cacheStats = ref(null)
const domainSummaries = ref([])

// 趋势抽屉
const trendDrawer = ref(false)
const trendMaterial = ref(null)
const trendData = ref(null)
const trendDays = ref(90)

// ── 计算属性 ──
const filteredAlerts = computed(() => {
  let list = alerts.value
  if (riskFilter.value) {
    list = list.filter(a => a.risk_level === riskFilter.value)
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(a => a.material_name_zh && a.material_name_zh.includes(kw))
  }
  // 添加排序字段
  const order = { RED: 0, ORANGE: 1, YELLOW: 2, GREEN: 3, NORMAL: 4 }
  list = [...list].sort((a, b) => (order[a.risk_level] || 99) - (order[b.risk_level] || 99))
  return list
})

const paginatedAlerts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredAlerts.value.slice(start, start + pageSize.value)
})

const riskBars = computed(() => {
  const s = summary
  const max = Math.max(s.red || 0, s.orange || 0, s.yellow || 0, s.green || 0, s.normal || 0, 1)
  return [
    { level: 'RED', label: '红色 ≥20%', count: s.red || 0, pct: ((s.red || 0) / max * 100).toFixed(0), cssClass: 'bar-red' },
    { level: 'ORANGE', label: '橙色 ≥10%', count: s.orange || 0, pct: ((s.orange || 0) / max * 100).toFixed(0), cssClass: 'bar-orange' },
    { level: 'YELLOW', label: '黄色 ≥5%', count: s.yellow || 0, pct: ((s.yellow || 0) / max * 100).toFixed(0), cssClass: 'bar-yellow' },
    { level: 'GREEN', label: '绿色 ≤-10%', count: s.green || 0, pct: ((s.green || 0) / max * 100).toFixed(0), cssClass: 'bar-green' },
    { level: 'NORMAL', label: '正常', count: s.normal || 0, pct: ((s.normal || 0) / max * 100).toFixed(0), cssClass: 'bar-normal' },
  ]
})

const trendBars = computed(() => {
  if (!trendData.value?.daily_trends) return []
  const prices = trendData.value.daily_trends.map(d => d.avg_price)
  const max = Math.max(...prices)
  const min = Math.min(...prices)
  const range = max - min || 1
  return trendData.value.daily_trends.slice(-60).map(d => ({
    ...d,
    height: ((d.avg_price - min) / range * 90 + 5).toFixed(0),
    shortDate: d.date.slice(5),
  }))
})

// ── 方法 ──
function domainLabel(domain) {
  const map = { metals: '有色金属', rare_earth: '稀土&小金属', chemical: '化工&非金属' }
  return map[domain] || domain
}

function formatPct(val) {
  if (val == null) return '-'
  return (val > 0 ? '+' : '') + Number(val).toFixed(2) + '%'
}

function riskTagType(level) {
  const map = { RED: 'danger', ORANGE: 'warning', YELLOW: '', GREEN: 'success', NORMAL: 'info' }
  return map[level] || 'info'
}

function filterAlerts() {
  currentPage.value = 1
}

async function loadData() {
  loading.value = true
  try {
    const params = { limit: 200 }
    if (domainFilter.value) params.domain = domainFilter.value

    const [alertsRes, summaryRes, cacheRes] = await Promise.all([
      getMaterialAlerts(params),
      getMaterialSummary(domainFilter.value || undefined),
      getMaterialCacheStats(),
    ])

    alerts.value = alertsRes.data.alerts || []
    Object.assign(summary, alertsRes.data.summary || {})
    Object.assign(topSummary, summaryRes.data || {})
    cacheStats.value = cacheRes.data

    // 构建域概览
    const byDomain = summaryRes.data.by_domain || {}
    domainSummaries.value = ['metals', 'rare_earth', 'chemical'].map(key => {
      const d = byDomain[key] || {}
      const t = d.total || 0
      return {
        key,
        name: domainLabel(key),
        total: t,
        red: d.red || 0, orange: d.orange || 0, yellow: d.yellow || 0, green: d.green || 0,
        healthy: (d.red || 0) + (d.orange || 0) === 0,
        redPct: t ? ((d.red || 0) / t * 100).toFixed(0) : 0,
        orangePct: t ? ((d.orange || 0) / t * 100).toFixed(0) : 0,
        yellowPct: t ? ((d.yellow || 0) / t * 100).toFixed(0) : 0,
        greenPct: t ? ((d.green || 0) / t * 100).toFixed(0) : 0,
      }
    })

    currentPage.value = 1
  } catch (e) {
    ElMessage.error('加载数据失败: ' + (e.response?.data?.detail || e.message))
  } finally {
    loading.value = false
  }
}

function loadAlerts() {
  currentPage.value = 1
}

async function openTrend(row) {
  trendMaterial.value = row
  trendDrawer.value = true
  trendLoading.value = true
  trendData.value = null
  try {
    const res = await getMaterialTrends(row.material_key, trendDays.value)
    trendData.value = res.data
  } catch (e) {
    ElMessage.error('加载趋势失败')
  } finally {
    trendLoading.value = false
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.material-watch-page {
  max-width: 1400px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}
.dashboard-header h2 { margin: 0 0 4px; font-size: 22px; }
.dashboard-header p { margin: 0; color: #909399; font-size: 14px; }
.header-actions { display: flex; gap: 10px; align-items: center; }

/* 概览卡片 */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}
.overview-card { text-align: center; padding: 10px; }
.overview-card.alert-red { border-left: 4px solid #f56c6c; }
.overview-card.alert-orange { border-left: 4px solid #e6a23c; }
.overview-card.alert-yellow { border-left: 4px solid #f2d024; }
.overview-card.alert-green { border-left: 4px solid #67c23a; }
.overview-label { display: block; font-size: 13px; color: #909399; }
.overview-value { font-size: 28px; font-weight: 700; }

/* 主网格 */
.main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
.panel-card { margin-bottom: 0; }
.panel-card h3 { margin: 0; font-size: 15px; }
.full-width { margin-bottom: 20px; }

/* 风险条形图 */
.risk-bars { display: flex; flex-direction: column; gap: 8px; }
.risk-bar-row {
  display: flex; align-items: center; gap: 10px;
}
.risk-bar-label { width: 90px; font-size: 13px; text-align: right; }
.risk-bar-track {
  flex: 1; height: 22px; background: #f0f0f0; border-radius: 4px; overflow: hidden;
}
.risk-bar-fill { height: 100%; border-radius: 4px; transition: width 0.4s; }
.risk-bar-fill.bar-red { background: #f56c6c; }
.risk-bar-fill.bar-orange { background: #e6a23c; }
.risk-bar-fill.bar-yellow { background: #f2d024; }
.risk-bar-fill.bar-green { background: #67c23a; }
.risk-bar-fill.bar-normal { background: #c0c4cc; }
.risk-bar-count { width: 30px; font-weight: 600; font-size: 14px; }

/* 域概览 */
.domain-cards { display: flex; flex-direction: column; gap: 12px; }
.domain-item {
  padding: 10px 12px; border: 1px solid #ebeef5; border-radius: 6px;
}
.domain-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.domain-counts { display: flex; gap: 12px; font-size: 13px; color: #606266; margin-bottom: 6px; }
.domain-bar {
  display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #f0f0f0;
}
.domain-bar-seg.seg-red { background: #f56c6c; }
.domain-bar-seg.seg-orange { background: #e6a23c; }
.domain-bar-seg.seg-yellow { background: #f2d024; }
.domain-bar-seg.seg-green { background: #67c23a; }
.domain-bar-seg.seg-normal { background: #e0e0e0; }

/* Top 列表 */
.top-list { display: flex; flex-direction: column; gap: 6px; }
.top-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-radius: 4px;
}
.top-item.rising { background: #fef0f0; }
.top-item.dropping { background: #f0f9eb; }
.top-name { flex: 1; font-size: 13px; }
.top-pct { font-weight: 600; font-size: 14px; }
.top-pct.up { color: #f56c6c; }
.top-pct.down { color: #67c23a; }

/* 缓存 */
.cache-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.cache-item { text-align: center; }
.cache-label { display: block; font-size: 12px; color: #909399; }
.cache-item strong { font-size: 18px; }

/* 表格 */
.table-header-row {
  display: flex; justify-content: space-between; align-items: center;
}
.table-filters { display: flex; gap: 8px; }
.pagination-row {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 12px;
}
.total-hint { font-size: 13px; color: #909399; }

/* 趋势图 */
.trend-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }
.trend-stat-item { text-align: center; padding: 8px; background: #f5f7fa; border-radius: 6px; }
.trend-stat-item span { display: block; font-size: 12px; color: #909399; }
.trend-stat-item strong { font-size: 16px; }

.mini-trend-chart { margin: 16px 0; }
.chart-bars {
  display: flex; align-items: flex-end; gap: 2px;
  height: 160px; padding: 8px; background: #fafafa; border-radius: 6px;
}
.chart-bar-item {
  flex: 1; min-width: 4px; background: linear-gradient(to top, #409eff, #79bbff);
  border-radius: 2px 2px 0 0; position: relative; transition: height 0.3s;
}
.chart-bar-item:hover { background: linear-gradient(to top, #337ecc, #409eff); }
.chart-bar-date {
  position: absolute; bottom: -18px; left: 50%; transform: translateX(-50%);
  font-size: 9px; color: #c0c4cc; white-space: nowrap; display: none;
}
.chart-bar-item:nth-child(5n+1) .chart-bar-date { display: block; }

.baseline-compare {
  background: #f5f7fa; border-radius: 6px; padding: 12px; margin-top: 12px;
}
.compare-row { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 14px; }

/* 工具类 */
.text-up { color: #f56c6c; }
.text-down { color: #67c23a; }
.text-success { color: #67c23a; }
.text-warning { color: #e6a23c; }
.empty-hint { text-align: center; color: #c0c4cc; padding: 20px; }

@media (max-width: 900px) {
  .overview-grid { grid-template-columns: repeat(3, 1fr); }
  .main-grid { grid-template-columns: 1fr; }
}
</style>
