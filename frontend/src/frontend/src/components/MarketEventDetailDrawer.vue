<template>
  <el-drawer :model-value="modelValue" title="事件详情" size="42%" data-testid="events-detail-drawer" @update:model-value="emit('update:modelValue', $event)">
    <div v-if="event" class="detail-body">
      <section>
        <h4>基本信息</h4>
        <p><span>品牌：</span>{{ displayValue(event.brand) }}</p>
        <p><span>品类：</span>{{ displayValue(event.category) }}</p>
        <p><span>事件类型：</span>{{ labelFor(eventTypeOptions, event.event_type) }}</p>
        <p><span>严重度：</span>{{ labelFor(severityOptions, event.severity) }}</p>
        <p><span>风险等级：</span>{{ labelFor(severityOptions, event.severity) }}</p>
        <p><span>置信度：</span>{{ formatPercent(event.confidence) }}</p>
        <p><span>触发条件：</span>{{ eventTriggerText(event) }}</p>
        <p><span>影响触发原则：</span>{{ impactPrincipleText(event, impact) }}</p>
        <p><span>交叉验证：</span>{{ event.cross_validated ? '是' : '否' }}</p>
        <p><span>状态：</span>{{ isActive(event) ? '活跃' : '停用' }}</p>
        <div class="detail-actions">
          <el-button v-if="isActive(event)" type="danger" size="small" data-testid="events-disable" :loading="operatingStatus" @click="emit('status-change', 'disable')">停用事件</el-button>
          <el-button v-else type="success" size="small" data-testid="events-enable" :loading="operatingStatus" @click="emit('status-change', 'enable')">启用事件</el-button>
        </div>
      </section>

      <section>
        <h4>来源信息</h4>
        <p><span>来源名称：</span>{{ displayValue(event.source_name) }}</p>
        <p><span>来源链接：</span><a v-if="event.source_url" :href="event.source_url" target="_blank" rel="noopener noreferrer">{{ event.source_url }}</a><span v-else>暂无</span></p>
        <p><span>原始标题：</span>{{ displayValue(event.raw_title) }}</p>
        <p><span>原文摘要：</span>{{ displayValue(event.raw_text_excerpt) }}</p>
      </section>

      <section>
        <h4>风险影响</h4>
        <p><span>交期影响：</span>{{ formatImpact(event.estimated_lead_time_impact_weeks, '周') }}</p>
        <p><span>价格影响：</span>{{ formatImpact(event.estimated_price_impact_pct, '%') }}</p>
        <p><span>命中原则：</span>{{ matchPrincipleText(event, impact) }}</p>
        <p><span>创建时间：</span>{{ formatDate(event.created_at) }}</p>
      </section>

      <section>
        <h4>影响项目</h4>
        <p><span>项目数：</span>{{ impact?.project_count ?? 0 }}</p>
        <p><span>受影响物料：</span>{{ impact?.item_count ?? 0 }}</p>
        <p><span>风险分布：</span>红 {{ impact?.risk_counts?.red ?? 0 }} / 黄 {{ impact?.risk_counts?.yellow ?? 0 }} / 绿 {{ impact?.risk_counts?.green ?? 0 }} / 灰 {{ impact?.risk_counts?.gray ?? 0 }}</p>
        <div v-if="impact?.projects?.length" class="impact-projects">
          <div v-for="project in impact.projects" :key="project.project_id" class="impact-project">
            <strong>{{ project.project_name }}</strong>
            <span>受影响物料：{{ project.affected_item_count }}</span>
            <span>最高风险：{{ riskText(project.highest_risk_level) }}</span>
          </div>
        </div>
        <p v-else>暂无已记录影响项目</p>
      </section>

      <section>
        <h4>复核来源</h4>
        <template v-if="sourceSignal?.signal">
          <p><span>复核状态：</span>{{ displayValue(sourceSignal.signal.review_status) }}</p>
          <p><span>复核人：</span>{{ displayValue(sourceSignal.signal.reviewed_by) }}</p>
          <p><span>复核备注：</span>{{ displayValue(sourceSignal.signal.review_notes) }}</p>
          <p><span>证据文本：</span>{{ displayValue(sourceSignal.signal.evidence_text) }}</p>
          <p><span>原始通知：</span>{{ displayValue(sourceSignal.raw_notice?.title) }}</p>
          <p><span>通知来源：</span>{{ noticeSourceText(sourceSignal.raw_notice) }}</p>
          <p><span>通知发送人：</span>{{ displayValue(sourceSignal.raw_notice?.sender) }}</p>
          <p><span>原文摘录：</span>{{ displayValue(sourceSignal.raw_notice?.raw_text_excerpt) }}</p>
        </template>
        <p v-else>暂无行情收件箱复核来源</p>
      </section>
    </div>
  </el-drawer>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, default: false },
  event: { type: Object, default: null },
  impact: { type: Object, default: null },
  sourceSignal: { type: Object, default: null },
  operatingStatus: { type: Boolean, default: false }
})

const emit = defineEmits(['update:modelValue', 'status-change'])

const eventTypeOptions = [
  { label: '缺货', value: 'shortage' },
  { label: '涨价', value: 'price_increase' },
  { label: '产能问题', value: 'capacity_issue' },
  { label: '交期延长', value: 'lead_time' },
  { label: '停产', value: 'eol' },
  { label: '政策', value: 'policy' },
  { label: '灾害', value: 'disaster' },
  { label: '其他', value: 'other' }
]

const severityOptions = [
  { label: '严重', value: 'critical' },
  { label: '高', value: 'high' },
  { label: '中', value: 'medium' },
  { label: '低', value: 'low' },
  { label: '未知', value: 'unknown' }
]

function displayValue(value) {
  return value === null || value === undefined || value === '' ? '暂无' : value
}

function noticeSourceText(notice) {
  if (!notice) return '暂无'
  const sourceType = displayValue(notice.source_type)
  const sourceName = displayValue(notice.source_name)
  if (sourceType === '暂无' && sourceName === '暂无') return '暂无'
  return `${sourceType} / ${sourceName}`
}

function formatPercent(value) {
  if (value === null || value === undefined) return '暂无'
  return `${Math.round(Number(value) * 100)}%`
}

function formatImpact(value, unit) {
  if (value === null || value === undefined || value === '') return '暂无'
  return unit === '%' ? `${value}${unit}` : `${value} ${unit}`
}

function formatDate(value) {
  if (!value) return '暂无'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function labelFor(options, value) {
  return options.find((item) => item.value === value)?.label || displayValue(value)
}

function riskText(level) {
  const map = { red: '红色', yellow: '黄色', green: '绿色', gray: '灰色' }
  return map[level] || displayValue(level)
}

function eventTriggerText(event) {
  if (!event) return '暂无'
  return `严重度 ${labelFor(severityOptions, event.severity)}，置信度 ${formatPercent(event.confidence)}，交期影响 ${formatImpact(event.estimated_lead_time_impact_weeks, '周')}，价格影响 ${formatImpact(event.estimated_price_impact_pct, '%')}`
}

function impactPrincipleText(event, impact) {
  if (!event) return '暂无'
  const severity = labelFor(severityOptions, event.severity)
  const confidence = formatPercent(event.confidence)
  const scope = impact ? `当前命中 ${impact.project_count ?? 0} 个项目、${impact.item_count ?? 0} 个物料` : '影响范围待系统匹配'
  return `当事件达到${severity}风险、置信度为${confidence}，并存在交期或价格影响时，系统按品牌、品类、型号与 BOM 明细匹配，${scope}。`
}

function matchPrincipleText(event, impact) {
  if (!event) return '暂无'
  const eventType = labelFor(eventTypeOptions, event.event_type)
  const scope = impact ? `影响范围按已匹配项目/物料统计：项目 ${impact.project_count ?? 0}、物料 ${impact.item_count ?? 0}` : '暂未取得影响范围统计'
  return `${eventType}事件优先匹配同品牌、同品类及型号关键词；红/黄风险由事件严重度、置信度、交期周数、价格涨幅和 BOM 命中范围共同决定。${scope}。`
}

function isActive(event) {
  return Number(event?.is_active ?? 1) === 1
}
</script>

<style scoped>
.detail-body section {
  padding-bottom: 16px;
  margin-bottom: 16px;
  border-bottom: 1px solid #edf2f7;
}

.detail-body h4 {
  margin: 0 0 12px;
}

.detail-body p {
  margin: 8px 0;
  line-height: 1.6;
}

.detail-body span:first-child {
  color: #6b7280;
}

.detail-actions {
  margin-top: 10px;
}

.impact-projects {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.impact-project {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  background: #f8fafc;
  border-radius: 6px;
  font-size: 13px;
}
</style>
