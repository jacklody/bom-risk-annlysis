<template>
  <el-drawer
    :model-value="modelValue"
    :title="drawerTitle"
    size="48%"
    data-testid="event-detail-drawer"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-if="event" class="detail-body">
      <!-- 涨价影响链路溯源 (放在最前面，最重要的信息) -->
      <ImpactChain
        v-if="showChain"
        :chain-data="chainData"
        data-testid="event-impact-chain"
      />

      <!-- 基本信息 -->
      <section class="detail-section">
        <h4>📌 基本信息</h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">品牌</span>
            <span class="info-value">{{ displayValue(event.brand) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">品类</span>
            <span class="info-value">{{ displayValue(event.category) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">事件类型</span>
            <el-tag size="small">{{ eventTypeLabel(event.event_type) }}</el-tag>
          </div>
          <div class="info-item">
            <span class="info-label">严重度</span>
            <el-tag :type="severityTagType(event.severity)" size="small">{{ severityLabel(event.severity) }}</el-tag>
          </div>
          <div class="info-item">
            <span class="info-label">置信度</span>
            <el-tag :type="confidenceTagType(event.confidence)" size="small">{{ formatPercent(event.confidence) }}</el-tag>
          </div>
          <div class="info-item">
            <span class="info-label">状态</span>
            <el-tag :type="isActive(event) ? 'success' : 'info'" size="small">{{ isActive(event) ? '活跃' : '停用' }}</el-tag>
          </div>
        </div>
      </section>

      <!-- 触发条件 -->
      <section class="detail-section">
        <h4>⚡ 触发条件</h4>
        <div class="trigger-conditions">
          <div class="condition-chip" :class="event.severity === 'critical' || event.severity === 'high' ? 'danger' : ''">
            <span class="condition-value">{{ severityLabel(event.severity) }}</span>
            <span class="condition-key">严重度</span>
          </div>
          <div class="condition-chip">
            <span class="condition-value">{{ formatPercent(event.confidence) }}</span>
            <span class="condition-key">置信度</span>
          </div>
          <div class="condition-chip" :class="(event.estimated_lead_time_impact_weeks || 0) > 8 ? 'warning' : ''">
            <span class="condition-value">{{ formatImpact(event.estimated_lead_time_impact_weeks, '周') }}</span>
            <span class="condition-key">交期影响</span>
          </div>
          <div class="condition-chip" :class="(event.estimated_price_impact_pct || 0) > 10 ? 'danger' : ''">
            <span class="condition-value">{{ formatImpact(event.estimated_price_impact_pct, '%') }}</span>
            <span class="condition-key">价格影响</span>
          </div>
        </div>
      </section>

      <!-- 信息来源 -->
      <section class="detail-section">
        <h4>🔗 信息来源</h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">来源类型</span>
            <span class="info-value">{{ displayValue(event.source_type || (sourceSignal?.raw_notice?.source_type)) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">来源名称</span>
            <span class="info-value">{{ displayValue(event.source_name) }}</span>
          </div>
          <div class="info-item full-width" v-if="event.source_url">
            <span class="info-label">来源链接</span>
            <a :href="event.source_url" target="_blank" rel="noopener noreferrer" class="source-link">打开原始信息 →</a>
          </div>
          <div class="info-item">
            <span class="info-label">原始标题</span>
            <span class="info-value">{{ displayValue(event.raw_title) }}</span>
          </div>
          <div class="info-item full-width" v-if="event.raw_text_excerpt">
            <span class="info-label">原文摘要</span>
            <p class="excerpt-text">{{ event.raw_text_excerpt }}</p>
          </div>
        </div>
      </section>

      <!-- 影响项目 -->
      <section class="detail-section">
        <h4>📊 影响范围</h4>
        <div class="impact-stats">
          <div class="impact-stat-item">
            <span class="impact-stat-num">{{ impact?.project_count ?? 0 }}</span>
            <span class="impact-stat-label">影响项目</span>
          </div>
          <div class="impact-stat-item">
            <span class="impact-stat-num">{{ impact?.item_count ?? 0 }}</span>
            <span class="impact-stat-label">影响物料</span>
          </div>
          <div class="impact-stat-item danger">
            <span class="impact-stat-num">{{ impact?.risk_counts?.red ?? 0 }}</span>
            <span class="impact-stat-label">高风险</span>
          </div>
          <div class="impact-stat-item warning">
            <span class="impact-stat-num">{{ impact?.risk_counts?.yellow ?? 0 }}</span>
            <span class="impact-stat-label">关注</span>
          </div>
        </div>
        <div v-if="impact?.projects?.length" class="impact-project-list">
          <div v-for="project in impact.projects" :key="project.project_id" class="impact-project-row">
            <strong>{{ project.project_name }}</strong>
            <span>{{ project.affected_item_count }} 个物料受影响</span>
            <el-tag :type="project.highest_risk_level === 'red' ? 'danger' : 'warning'" size="small">{{ project.highest_risk_level === 'red' ? '高风险' : '关注' }}</el-tag>
          </div>
        </div>
        <p v-else class="no-data">暂无已记录影响项目</p>
      </section>

      <!-- 复核来源（行情收件箱链路） -->
      <section v-if="sourceSignal?.signal" class="detail-section">
        <h4>📥 复核来源（行情收件箱）</h4>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">复核状态</span>
            <el-tag :type="reviewTag(sourceSignal.signal.review_status)" size="small">{{ sourceSignal.signal.review_status || '暂无' }}</el-tag>
          </div>
          <div class="info-item">
            <span class="info-label">复核人</span>
            <span class="info-value">{{ displayValue(sourceSignal.signal.reviewed_by) }}</span>
          </div>
          <div class="info-item full-width">
            <span class="info-label">复核备注</span>
            <span class="info-value">{{ displayValue(sourceSignal.signal.review_notes) }}</span>
          </div>
          <div class="info-item full-width">
            <span class="info-label">证据文本</span>
            <span class="info-value">{{ displayValue(sourceSignal.signal.evidence_text) }}</span>
          </div>
        </div>
      </section>

      <!-- 操作按钮 -->
      <div class="detail-actions">
        <el-button v-if="isActive(event)" type="danger" size="small" data-testid="event-disable" :loading="operatingStatus" @click="emit('status-change', 'disable')">
          停用事件
        </el-button>
        <el-button v-else type="success" size="small" data-testid="event-enable" :loading="operatingStatus" @click="emit('status-change', 'enable')">
          启用事件
        </el-button>
      </div>
    </div>

    <el-empty v-else description="事件数据加载中..." :image-size="80" />
  </el-drawer>
</template>

<script setup>
import { computed } from 'vue'
import ImpactChain from './ImpactChain.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  event: { type: Object, default: null },
  impact: { type: Object, default: null },
  sourceSignal: { type: Object, default: null },
  operatingStatus: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'status-change'])

const drawerTitle = computed(() => props.event?.title || props.event?.raw_title || '事件详情')

// 构建涨价影响链路数据
const chainData = computed(() => {
  const event = props.event
  const signal = props.sourceSignal?.signal
  const notice = props.sourceSignal?.raw_notice
  const impact = props.impact

  if (!event) return null

  return {
    rawSource: (notice || event.source_name || event.raw_title) ? {
      sourceType: notice?.source_type || event.source_type || '事件直接来源',
      sourceName: notice?.source_name || event.source_name || '未填写来源',
      title: notice?.title || event.raw_title || '',
      sender: notice?.sender || '',
      sourceUrl: event.source_url || '',
      excerpt: notice?.raw_text_excerpt || event.raw_text_excerpt || ''
    } : null,

    signal: signal ? {
      brand: signal.brand || event.brand,
      category: signal.category || event.category,
      mpn: signal.mpn || '',
      eventType: signal.event_type || event.event_type,
      confidence: signal.confidence ?? event.confidence,
      reviewStatus: signal.review_status || 'pending',
      reviewer: signal.reviewed_by || ''
    } : (event.brand || event.confidence != null ? {
      brand: event.brand,
      category: event.category,
      mpn: event.mpn || '',
      eventType: event.event_type,
      confidence: event.confidence,
      reviewStatus: 'confirmed',
      reviewer: ''
    } : null),

    event: {
      title: event.title || event.raw_title || '',
      eventType: eventTypeLabel(event.event_type),
      severity: severityLabel(event.severity),
      priceImpact: event.estimated_price_impact_pct,
      leadTimeImpact: event.estimated_lead_time_impact_weeks,
      createdAt: formatDate(event.created_at),
      description: event.description || event.raw_text_excerpt || ''
    },

    bomMatch: impact ? {
      affectedProjects: impact.project_count || 0,
      affectedItems: impact.item_count || 0,
      redItems: impact.risk_counts?.red || 0,
      yellowItems: impact.risk_counts?.yellow || 0,
      projects: (impact.projects || []).map(p => ({
        id: p.project_id,
        name: p.project_name,
        red: p.risk_counts?.red || 0,
        yellow: p.risk_counts?.yellow || 0,
        green: p.risk_counts?.green || 0,
        gray: p.risk_counts?.gray || 0
      }))
    } : null,

    actionAdvice: event.severity === 'critical' || event.severity === 'high' ? {
      urgent: [`${eventTypeLabel(event.event_type)}事件严重度为${severityLabel(event.severity)}，影响${impact?.project_count || 0}个项目，建议优先评估替代料或提前备货。`],
      watch: (event.estimated_price_impact_pct || 0) > 5 ? [`价格涨幅 ${event.estimated_price_impact_pct}%，持续关注价格走势和供应商报价。`] : []
    } : {
      watch: impact?.project_count > 0 ? [`该事件已匹配 ${impact.project_count} 个项目，建议关注后续变化。`] : []
    }
  }
})

const showChain = computed(() => {
  const d = chainData.value
  return d && (d.rawSource || d.signal || d.event || d.bomMatch || d.actionAdvice?.urgent?.length || d.actionAdvice?.watch?.length)
})

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '暂无' : value
}

function formatPercent(value) {
  if (value === null || value === undefined) return '暂无'
  const num = Number(value)
  if (num <= 1) return `${Math.round(num * 100)}%`
  return `${Math.round(num)}%`
}

function formatImpact(value, unit) {
  if (value === null || value === undefined || value === '') return '暂无'
  return unit === '%' ? `${value}${unit}` : `${value} ${unit}`
}

function formatDate(value) {
  if (!value) return '暂无'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('zh-CN', { hour12: false })
}

function eventTypeLabel(type) {
  const map = {
    shortage: '缺货', price_increase: '涨价', capacity_issue: '产能问题',
    lead_time: '交期延长', eol: '停产', policy: '政策', disaster: '灾害', other: '其他'
  }
  return map[type] || displayValue(type)
}

function severityLabel(severity) {
  const map = { critical: '严重', high: '高', medium: '中', low: '低', unknown: '未知' }
  return map[severity] || displayValue(severity)
}

function severityTagType(severity) {
  if (severity === 'critical' || severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}

function confidenceTagType(conf) {
  if (conf == null) return 'info'
  const num = Number(conf)
  if (num >= 0.8) return 'success'
  if (num >= 0.5) return 'warning'
  return 'danger'
}

function reviewTag(status) {
  if (status === 'confirmed') return 'success'
  if (status === 'need_review') return 'warning'
  return 'info'
}

function isActive(event) {
  return Number(event?.is_active ?? 1) === 1
}
</script>

<style scoped>
.detail-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.detail-section {
  padding: 14px 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #ebeef5;
}

.detail-section h4 {
  margin: 0 0 12px;
  font-size: 15px;
  color: #303133;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item.full-width {
  grid-column: 1 / -1;
}

.info-label {
  font-size: 12px;
  color: #909399;
  font-weight: 500;
}

.info-value {
  font-size: 14px;
  color: #303133;
}

.source-link {
  color: #409eff;
  text-decoration: none;
  font-size: 14px;
}

.source-link:hover {
  text-decoration: underline;
}

.excerpt-text {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 6px;
}

/* 触发条件 */
.trigger-conditions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.condition-chip {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 16px;
  border-radius: 8px;
  background: #f5f7fa;
  min-width: 80px;
}

.condition-chip.danger {
  background: #fef0f0;
}

.condition-chip.warning {
  background: #fdf6ec;
}

.condition-value {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
}

.condition-chip.danger .condition-value { color: #f56c6c; }
.condition-chip.warning .condition-value { color: #e6a23c; }

.condition-key {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

/* 影响范围 */
.impact-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.impact-stat-item {
  text-align: center;
  padding: 10px;
  border-radius: 8px;
  background: #f5f7fa;
}

.impact-stat-item.danger { background: #fef0f0; }
.impact-stat-item.warning { background: #fdf6ec; }

.impact-stat-num {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.impact-stat-item.danger .impact-stat-num { color: #f56c6c; }
.impact-stat-item.warning .impact-stat-num { color: #e6a23c; }

.impact-stat-label {
  display: block;
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

.impact-project-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.impact-project-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #f8fafc;
  font-size: 13px;
}

.impact-project-row strong {
  color: #303133;
  flex: 1;
}

.no-data {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 8px;
}

.detail-actions {
  padding-top: 8px;
}
</style>
