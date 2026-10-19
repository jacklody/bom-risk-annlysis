<template>
  <div class="intel-watch-page">
    <div class="page-header">
      <h2>情报监控</h2>
      <p>提交关注指令，自动解析品牌/品类，匹配已有BOM并生成市场事件。支持自然语言（如"关注STM32F103交期"）。</p>
    </div>

    <!-- 输入区 -->
    <el-card class="section-card">
      <template #header>
        <span>提交关注指令</span>
      </template>
      <div class="input-row">
        <el-input
          v-model="rawInput"
          placeholder="例如：关注 STM32 全系列交期 / 监控高容MLCC价格走势 / 排查长晶分立器件库存"
          clearable
          size="large"
          maxlength="500"
          show-word-limit
          data-testid="watch-input"
          @keyup.enter="submitWatch"
        />
        <el-button
          type="primary"
          size="large"
          :loading="submitting"
          :disabled="!rawInput.trim()"
          data-testid="watch-submit"
          @click="submitWatch"
        >
          提交监控
        </el-button>
      </div>
      <div class="quick-tags">
        <span class="tag-label">快捷指令：</span>
        <el-tag
          v-for="tag in quickTags"
          :key="tag"
          class="quick-tag"
          effect="plain"
          @click="rawInput = tag"
        >
          {{ tag }}
        </el-tag>
      </div>
    </el-card>

    <!-- 当前活跃市场事件统计 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-title-row">
          <span>市场事件监控概况</span>
          <el-button size="small" :loading="loadingStats" @click="loadStats">刷新</el-button>
        </div>
      </template>
      <div class="stats-grid">
        <div class="stat-item">
          <span class="stat-value danger">{{ stats.active_events ?? '...' }}</span>
          <span class="stat-label">活跃市场事件</span>
        </div>
        <div class="stat-item">
          <span class="stat-value warning">{{ stats.high_severity ?? '...' }}</span>
          <span class="stat-label">高严重度事件</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ stats.affected_items ?? '...' }}</span>
          <span class="stat-label">受影响物料</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ stats.affected_projects ?? '...' }}</span>
          <span class="stat-label">受影响BOM项目</span>
        </div>
      </div>

      <!-- 品类风险分布 -->
      <div v-if="stats.categories && stats.categories.length" style="margin-top:16px">
        <h4>品类风险分布</h4>
        <div class="tag-cloud">
          <el-tag
            v-for="cat in stats.categories"
            :key="cat.category"
            :type="cat.risk === 'red' ? 'danger' : cat.risk === 'yellow' ? 'warning' : 'success'"
            size="small"
            class="cloud-tag"
          >
            {{ cat.category || '未分类' }} {{ cat.count }}条
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 媒体源接入状态 -->
    <el-card class="section-card" data-testid="media-sources-card">
      <template #header>
        <div class="card-title-row">
          <span>媒体源接入状态</span>
          <div class="card-title-actions">
            <el-button size="small" :loading="loadingSources" @click="loadMediaSources">刷新</el-button>
            <el-button size="small" type="success" :loading="collectingAll" data-testid="collect-all-media-sources" @click="collectAllSources">全量采集</el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!loadingSources && mediaSources.length === 0" description="暂无媒体源配置" />
      <div v-if="Object.keys(sourceResults).length" class="source-result-summary">
        <el-tag
          v-for="(result, sourceId) in sourceResults"
          :key="sourceId"
          type="success"
          effect="plain"
        >
          {{ sourceId }}：文章 {{ result.articles_crawled || 0 }} / 信号 {{ result.signals_parsed || 0 }} / 新增事件 {{ result.events_created || 0 }}<span v-if="result.skipped_count"> / 跳过来源 {{ result.skipped_count }}</span>
        </el-tag>
      </div>

      <el-table v-if="mediaSources.length" :data="mediaSources" stripe row-key="source_id" max-height="360">
        <el-table-column label="渠道" min-width="170">
          <template #default="{ row }">
            <div class="source-name">{{ row.name }}</div>
            <div class="source-id">{{ row.source_id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="140">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.channel_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="采集策略" width="150">
          <template #default="{ row }">
            <el-tag :type="strategyTagType(row.crawler_strategy)" size="small">
              {{ row.crawler_strategy }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="sourceStatusTagType(row)" size="small">
              {{ sourceStatusLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'disabled-note': !row.enabled }">
              {{ row.notes || row.access_method || '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近采集" min-width="170">
          <template #default="{ row }">
            <span v-if="row.status && row.status !== 'active'" class="disabled-hint">{{ sourceStatusHint(row) }}</span>
            <span v-else-if="!row.enabled" class="disabled-hint">暂停自动采集，可通过手动转发输入</span>
            <span v-else>{{ sourceResultText(row.source_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              link
              :data-testid="`open-source-detail-${row.source_id}`"
              @click="openDetail('source', row)"
            >
              详情
            </el-button>
            <el-button
              v-if="sourceCanCollect(row)"
              size="small"
              type="primary"
              link
              :loading="collectingSourceId === row.source_id"
              :data-testid="`collect-source-${row.source_id}`"
              @click="collectSource(row)"
            >
              采集
            </el-button>
            <span v-else class="disabled-hint">
              {{ sourceStatusAction(row) }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 采集运行记录 -->
    <el-card class="section-card" data-testid="run-history-card">
      <template #header>
        <div class="card-title-row">
          <span>采集运行记录</span>
          <el-button size="small" :loading="loadingRuns" @click="loadRunHistory">刷新</el-button>
        </div>
      </template>

      <el-empty v-if="!loadingRuns && runHistory.length === 0" description="暂无采集运行记录" />
      <el-table v-else :data="runHistory" stripe row-key="id" max-height="300">
        <el-table-column label="源" width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.source_id }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : row.status === 'empty' ? 'info' : 'danger'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="文章" width="70" align="center">
          <template #default="{ row }">
            {{ row.articles_crawled }}
          </template>
        </el-table-column>
        <el-table-column label="信号" width="70" align="center">
          <template #default="{ row }">
            {{ row.signals_parsed }}
          </template>
        </el-table-column>
        <el-table-column label="事件" width="70" align="center">
          <template #default="{ row }">
            {{ row.events_created }}
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_message" class="run-error">{{ row.error_message }}</span>
            <span v-else class="run-ok">{{ runStatusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="完成时间" min-width="160">
          <template #default="{ row }">
            {{ formatDate(row.completed_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" link :data-testid="`open-run-detail-${row.id}`" @click="openDetail('run', row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 手动转发文章 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-title-row">
          <span>手动转发文章</span>
          <span class="card-hint">将公众号文章粘贴到此处，选择来源后解析为市场事件</span>
        </div>
      </template>

      <div class="paste-form">
        <div class="paste-row">
          <select
            v-model="pasteSourceId"
            class="paste-source-select"
            data-testid="paste-source-select"
          >
            <option value="">选择媒体源</option>
            <option
              v-for="ms in mediaSources"
              :key="ms.source_id"
              :value="ms.source_id"
            >
              {{ ms.name }}
            </option>
          </select>
          <el-input
            v-model="pasteTitle"
            placeholder="文章标题（选填）"
            class="paste-title-input"
            maxlength="200"
          />
        </div>
        <el-input
          v-model="pasteText"
          type="textarea"
          :rows="5"
          placeholder="粘贴文章全文..."
          maxlength="5000"
          show-word-limit
          data-testid="paste-text-input"
        />
        <div class="paste-actions">
          <el-button
            type="primary"
            :disabled="!pasteSourceId || !pasteText.trim()"
            :loading="pasting"
            data-testid="paste-submit"
            @click="submitPaste"
          >
            提交解析
          </el-button>
          <el-tag v-if="pasteSourceId" type="info" effect="plain" size="small">
            来源：
            {{ mediaSources.find(s => s.source_id === pasteSourceId)?.name || pasteSourceId }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 关注指令历史 -->
    <el-card class="section-card" data-testid="watch-history">
      <template #header>
        <div class="card-title-row">
          <span>关注指令历史</span>
          <el-button size="small" :loading="loadingHistory" @click="loadHistory">刷新</el-button>
        </div>
      </template>

      <el-empty v-if="!loadingHistory && history.length === 0" description="暂无关注指令记录" />

      <el-table v-else :data="history" stripe row-key="id" max-height="500">
        <el-table-column label="指令内容" min-width="260">
          <template #default="{ row }">
            <div class="cmd-input">{{ row.raw_input }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="调研结论" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.research_summary || '处理中...' }}
          </template>
        </el-table-column>
        <el-table-column label="影响BOM" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.affected_project_count > 0" type="warning" size="small">
              {{ row.affected_project_count }} 个项目
            </el-tag>
            <span v-else class="text-muted">未影响</span>
          </template>
        </el-table-column>
        <el-table-column label="建议" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.suggestion || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" link :data-testid="`open-watch-detail-${row.id}`" @click="openDetail('watch', row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="detailVisible" :title="detailTitle" size="560px">
      <div v-if="detailRecord" class="detail-drawer-body">
        <p v-for="row in detailRows" :key="row.key">
          <span>{{ row.key }}：</span>{{ row.value }}
        </p>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { submitWatch as apiSubmit, getWatchHistory } from '../api/intelWatch'
import { collectMediaSource, forwardArticle, listMediaSourceRuns, listMediaSources } from '../api/events'
import axios from 'axios'

const rawInput = ref('')
const submitting = ref(false)
const loadingHistory = ref(false)
const loadingStats = ref(false)
const loadingSources = ref(false)
const loadingRuns = ref(false)
const pasting = ref(false)
const collectingSourceId = ref('')
const collectingAll = ref(false)
const history = ref([])
const mediaSources = ref([])
const sourceResults = ref({})
const runHistory = ref([])
const pasteSourceId = ref('')
const pasteTitle = ref('')
const pasteText = ref('')
const detailVisible = ref(false)
const detailType = ref('')
const detailRecord = ref(null)
const stats = ref({
  active_events: 0,
  high_severity: 0,
  affected_items: 0,
  affected_projects: 0,
  categories: []
})

const quickTags = [
  '关注 STM32 全系列交期',
  '监控 高容MLCC 价格走势',
  '排查 长晶 分立器件库存',
  '关注 英飞凌 IGBT模块 供应',
  '监控 高端PCB 交货周期'
]

const detailTitle = computed(() => ({
  source: '媒体源详情',
  run: '采集运行详情',
  watch: '关注指令详情',
  stats: '市场事件监控概况详情'
})[detailType.value] || '详情')

const detailRows = computed(() => Object.entries(detailRecord.value || {}).map(([key, value]) => ({
  key,
  value: formatDetailValue(value)
})))

onMounted(() => {
  loadHistory()
  loadStats()
  loadMediaSources()
  loadRunHistory()
})

async function submitWatch() {
  const text = rawInput.value.trim()
  if (!text) return
  submitting.value = true
  try {
    await apiSubmit(text)
    ElMessage.success('关注指令已提交，智能体正在调研...')
    rawInput.value = ''
    await loadHistory()
    await loadStats()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const { data } = await getWatchHistory()
    history.value = data.commands || []
  } catch {
    history.value = []
  } finally {
    loadingHistory.value = false
  }
}

async function loadMediaSources() {
  loadingSources.value = true
  try {
    const { data } = await listMediaSources()
    mediaSources.value = data.sources || []
  } catch {
    mediaSources.value = []
  } finally {
    loadingSources.value = false
  }
}

async function loadRunHistory() {
  loadingRuns.value = true
  try {
    const { data } = await listMediaSourceRuns({ limit: 20 })
    runHistory.value = data.runs || []
  } catch {
    runHistory.value = []
  } finally {
    loadingRuns.value = false
  }
}

async function submitPaste() {
  if (!pasteSourceId.value || !pasteText.value.trim()) return
  pasting.value = true
  try {
    const { data } = await forwardArticle({
      source_id: pasteSourceId.value,
      title: pasteTitle.value,
      text: pasteText.value
    })
    ElMessage.success(`解析完成：${data.source_name}，提取信号 ${data.signals_parsed}，新增事件 ${data.events_created}`)
    pasteText.value = ''
    pasteTitle.value = ''
    await loadRunHistory()
    await loadStats()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '文章解析失败，请重试')
  } finally {
    pasting.value = false
  }
}

async function collectSource(row) {
  if (!row?.source_id) return
  collectingSourceId.value = row.source_id
  try {
    const { data } = await collectMediaSource(row.source_id)
    sourceResults.value = {
      ...sourceResults.value,
      [row.source_id]: data
    }
    ElMessage.success(`采集完成：${row.name}，新增事件 ${data.events_created || 0}`)
    await loadRunHistory()
    await loadStats()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '媒体源采集失败，请稍后重试')
  } finally {
    collectingSourceId.value = ''
  }
}

async function collectAllSources() {
  collectingAll.value = true
  try {
    const { data } = await collectMediaSource()
    sourceResults.value = {
      ...sourceResults.value,
      全量采集: data
    }
    const skippedText = data.skipped_count ? `，跳过来源 ${data.skipped_count}` : ''
    ElMessage.success(`全量采集完成，新增事件 ${data.events_created || 0}${skippedText}`)
    await loadRunHistory()
    await loadStats()
  } catch (error) {
    ElMessage.error('全量采集失败，部分源可能超时')
  } finally {
    collectingAll.value = false
  }
}

function openDetail(type, record) {
  detailType.value = type
  detailRecord.value = record
  detailVisible.value = true
}

function formatDetailValue(value) {
  if (value === null || value === undefined || value === '') return '暂无'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function sourceResultText(sourceId) {
  const result = sourceResults.value[sourceId]
  if (!result) return '尚未采集'
  return `文章 ${result.articles_crawled || 0} / 信号 ${result.signals_parsed || 0} / 新增事件 ${result.events_created || 0}`
}

function sourceCanCollect(row) {
  return row?.enabled && (row.status ? row.status === 'active' : row.crawler_strategy !== 'manual_forward')
}

function sourceStatusLabel(row) {
  const status = row?.status || (row?.enabled ? 'active' : 'disabled')
  return {
    active: '可采集',
    disabled: '暂停采集',
    waiting_for_manual_forward: '需手动转发',
    waiting_for_configuration: '待配置'
  }[status] || status
}

function sourceStatusTagType(row) {
  const status = row?.status || (row?.enabled ? 'active' : 'disabled')
  return {
    active: 'success',
    disabled: 'info',
    waiting_for_manual_forward: 'warning',
    waiting_for_configuration: 'warning'
  }[status] || 'info'
}

function sourceStatusHint(row) {
  const status = row?.status
  if (status === 'waiting_for_manual_forward') return '请通过手动转发文章入口录入'
  if (status === 'waiting_for_configuration') return '待配置授权或采集参数'
  if (status === 'disabled') return '暂停自动采集，可手动录入'
  return sourceResultText(row?.source_id)
}

function sourceStatusAction(row) {
  const status = row?.status
  if (status === 'waiting_for_manual_forward') return '需手动转发'
  if (status === 'waiting_for_configuration') return '待配置'
  if (!row?.enabled || status === 'disabled') return '已暂停'
  return '不可采集'
}

function strategyTagType(strategy) {
  if (strategy === 'api_json' || strategy === 'keyword_search') return 'success'
  if (strategy === 'http_html') return 'warning'
  if (strategy === 'manual_forward' || strategy === 'wechat_feed') return 'info'
  return 'info'
}

async function loadStats() {
  loadingStats.value = true
  try {
    // 趋势汇总作为统计数据
    const [trendRes, eventsRes] = await Promise.all([
      axios.get('/api/market-trends/summary'),
      axios.get('/api/events?active=1&limit=200')
    ])
    const ts = trendRes.data || {}
    const evts = eventsRes.data?.events || []

    stats.value.active_events = ts.active_event_count ?? evts.length
    stats.value.high_severity = ts.high_severity_event_count ?? evts.filter(e => e.severity === 'critical' || e.severity === 'high').length
    stats.value.affected_items = ts.affected_item_count ?? 0
    stats.value.affected_projects = ts.affected_project_count ?? 0

    // 品类分布
    const catMap = {}
    for (const e of evts) {
      const cat = e.category || '未分类'
      if (!catMap[cat]) catMap[cat] = { category: cat, count: 0, risk: 'green' }
      catMap[cat].count++
      if (e.severity === 'critical' || e.severity === 'high') catMap[cat].risk = 'red'
      else if (e.severity === 'medium') catMap[cat].risk = 'yellow'
    }
    stats.value.categories = Object.values(catMap).sort((a, b) => b.count - a.count).slice(0, 15)
  } catch {
    // ignore
  } finally {
    loadingStats.value = false
  }
}

function statusLabel(status) {
  return { done: '已完成', researching: '调研中', pending: '待处理', failed: '失败' }[status] || status
}

function statusTagType(status) {
  return { done: 'success', researching: 'warning', pending: 'info', failed: 'danger' }[status] || 'info'
}

function runStatusLabel(status) {
  return { success: '采集成功', empty: '无数据', failed: '采集失败', running: '采集中' }[status] || status
}

function formatDate(value) {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.intel-watch-page { padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.page-header { margin-bottom: 4px; }
.page-header h2 { margin: 0 0 8px; font-size: 22px; color: #1f2d3d; }
.page-header p { margin: 0; color: #667085; font-size: 14px; }
.section-card { border-radius: 12px; }
.card-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-title-actions { display: flex; gap: 8px; }

.input-row { display: flex; gap: 12px; }
.input-row .el-input { flex: 1; }

.quick-tags { margin-top: 12px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tag-label { font-size: 13px; color: #909399; }
.quick-tag { cursor: pointer; }

.stats-grid { display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; }
.stat-item { padding: 16px; border-radius: 10px; background: #f5f7fa; border: 1px solid #ebeef5; text-align: center; }
.stat-value { display: block; font-size: 26px; font-weight: 700; color: #303133; }
.stat-value.danger { color: #f56c6c; }
.stat-value.warning { color: #e6a23c; }
.stat-label { display: block; margin-top: 6px; font-size: 13px; color: #909399; }

.tag-cloud { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.cloud-tag { margin: 0; }

.cmd-input { font-family: 'Consolas', monospace; color: #303133; font-size: 13px; line-height: 1.5; }
.source-name { font-weight: 600; color: #303133; }
.source-id { margin-top: 4px; font-size: 12px; color: #909399; font-family: 'Consolas', monospace; }
.source-result-summary { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.card-hint { font-size: 13px; color: #909399; }
.paste-form { display: flex; flex-direction: column; gap: 12px; }
.paste-row { display: flex; gap: 12px; align-items: center; }
.paste-source-select { min-width: 180px; height: 34px; border: 1px solid #dcdfe6; border-radius: 4px; padding: 0 8px; font-size: 14px; color: #303133; background: #fff; }
.paste-title-input { flex: 1; }
.paste-actions { display: flex; align-items: center; gap: 12px; }
.disabled-note { color: #909399; font-style: italic; }
.disabled-hint { color: #c0c4cc; font-size: 12px; }
.run-error { color: #f56c6c; font-size: 12px; }
.run-ok { color: #909399; font-size: 12px; }
.text-muted { color: #c0c4cc; }
</style>
