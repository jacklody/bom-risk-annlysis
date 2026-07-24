<template>
  <div class="impact-chain" data-testid="impact-chain">
    <!-- 链路总览标题 -->
    <div class="chain-header">
      <h4>📋 涨价影响链路溯源</h4>
      <span class="chain-subtitle">从原始情报 → 市场事件 → BOM风险物料 的完整追踪</span>
    </div>

    <!-- 可视化链路步骤条 -->
    <div class="chain-steps">
      <div
        v-for="(step, idx) in chainSteps"
        :key="idx"
        class="chain-step"
        :class="{
          active: step.active,
          skipped: step.skipped,
          'has-detail': step.detail
        }"
        @click="step.clickable && step.onClick()"
      >
        <div class="step-marker">
          <span class="step-num">{{ idx + 1 }}</span>
          <el-icon v-if="step.active" class="step-icon"><Check /></el-icon>
        </div>
        <div class="step-body">
          <div class="step-title">{{ step.title }}</div>
          <div v-if="step.subtitle" class="step-subtitle">{{ step.subtitle }}</div>
          <div v-if="step.detail" class="step-detail">
            <span v-if="step.sourceType" class="detail-chip">{{ step.sourceType }}</span>
            <span v-if="step.statusTag" class="detail-chip" :class="step.statusClass">{{ step.statusTag }}</span>
            <span v-if="step.confidence" class="detail-chip confidence">{{ step.confidence }}</span>
          </div>
        </div>
        <div v-if="idx < chainSteps.length - 1" class="step-connector" :class="{ active: step.active }"></div>
      </div>
    </div>

    <!-- 链路详情区域 -->
    <div v-if="chainData" class="chain-detail-panels">
      <!-- 步骤1: 原始情报 -->
      <div v-if="chainData.rawSource" class="detail-panel" :class="{ collapsed: panels.rawSource }">
        <div class="panel-header" @click="panels.rawSource = !panels.rawSource">
          <div class="panel-title">
            <el-tag size="small" type="info">步骤1</el-tag>
            <strong>原始情报来源</strong>
          </div>
          <el-icon><ArrowDown v-if="!panels.rawSource" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-if="!panels.rawSource" class="panel-body">
          <table class="info-table">
            <tr><td class="label">来源类型</td><td>{{ chainData.rawSource.sourceType || '暂无' }}</td></tr>
            <tr><td class="label">来源名称</td><td>{{ chainData.rawSource.sourceName || '暂无' }}</td></tr>
            <tr><td class="label">原始标题</td><td>{{ chainData.rawSource.title || '暂无' }}</td></tr>
            <tr><td class="label">发送人/渠道</td><td>{{ chainData.rawSource.sender || '暂无' }}</td></tr>
            <tr v-if="chainData.rawSource.sourceUrl"><td class="label">原始链接</td><td><a :href="chainData.rawSource.sourceUrl" target="_blank" rel="noopener noreferrer">打开原始信息 →</a></td></tr>
          </table>
          <div v-if="chainData.rawSource.excerpt" class="excerpt-box">
            <div class="excerpt-label">原文摘要</div>
            <p>{{ chainData.rawSource.excerpt }}</p>
          </div>
        </div>
      </div>

      <!-- 步骤2: 信号抽取 -->
      <div v-if="chainData.signal" class="detail-panel" :class="{ collapsed: panels.signal }">
        <div class="panel-header" @click="panels.signal = !panels.signal">
          <div class="panel-title">
            <el-tag size="small" type="warning">步骤2</el-tag>
            <strong>行情信号抽取</strong>
          </div>
          <el-icon><ArrowDown v-if="!panels.signal" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-if="!panels.signal" class="panel-body">
          <table class="info-table">
            <tr><td class="label">品牌</td><td>{{ chainData.signal.brand || '暂无' }}</td></tr>
            <tr><td class="label">品类</td><td>{{ chainData.signal.category || '暂无' }}</td></tr>
            <tr><td class="label">型号</td><td>{{ chainData.signal.mpn || '暂无' }}</td></tr>
            <tr><td class="label">事件类型</td><td>{{ chainData.signal.eventType || '暂无' }}</td></tr>
            <tr><td class="label">置信度</td><td><el-tag :type="confidenceTag(chainData.signal.confidence)" size="small">{{ formatPercent(chainData.signal.confidence) }}</el-tag></td></tr>
            <tr><td class="label">复核状态</td><td><el-tag :type="reviewStatusTag(chainData.signal.reviewStatus)" size="small">{{ chainData.signal.reviewStatus || '暂无' }}</el-tag></td></tr>
            <tr v-if="chainData.signal.reviewer"><td class="label">复核人</td><td>{{ chainData.signal.reviewer }}</td></tr>
          </table>
        </div>
      </div>

      <!-- 步骤3: 市场事件 -->
      <div v-if="chainData.event" class="detail-panel" :class="{ collapsed: panels.event }">
        <div class="panel-header" @click="panels.event = !panels.event">
          <div class="panel-title">
            <el-tag size="small" type="danger">步骤3</el-tag>
            <strong>市场事件</strong>
          </div>
          <el-icon><ArrowDown v-if="!panels.event" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-if="!panels.event" class="panel-body">
          <table class="info-table">
            <tr><td class="label">事件标题</td><td>{{ chainData.event.title || '暂无' }}</td></tr>
            <tr><td class="label">事件类型</td><td><el-tag size="small">{{ chainData.event.eventType || '暂无' }}</el-tag></td></tr>
            <tr><td class="label">严重度</td><td><el-tag :type="severityTag(chainData.event.severity)" size="small">{{ chainData.event.severity || '暂无' }}</el-tag></td></tr>
            <tr><td class="label">涨价幅度</td><td class="highlight-red">{{ chainData.event.priceImpact ? chainData.event.priceImpact + '%' : '暂无' }}</td></tr>
            <tr><td class="label">交期影响</td><td class="highlight-orange">{{ chainData.event.leadTimeImpact ? chainData.event.leadTimeImpact + ' 周' : '暂无' }}</td></tr>
            <tr><td class="label">风险等级</td><td><el-tag :type="severityTag(chainData.event.severity)" size="small">{{ chainData.event.severity || '暂无' }}</el-tag></td></tr>
            <tr><td class="label">创建时间</td><td>{{ chainData.event.createdAt || '暂无' }}</td></tr>
          </table>
          <div v-if="chainData.event.description" class="excerpt-box">
            <div class="excerpt-label">事件描述</div>
            <p>{{ chainData.event.description }}</p>
          </div>
        </div>
      </div>

      <!-- 步骤4: BOM匹配 -->
      <div v-if="chainData.bomMatch" class="detail-panel" :class="{ collapsed: panels.bomMatch }">
        <div class="panel-header" @click="panels.bomMatch = !panels.bomMatch">
          <div class="panel-title">
            <el-tag size="small" type="success">步骤4</el-tag>
            <strong>BOM 匹配结果</strong>
          </div>
          <el-icon><ArrowDown v-if="!panels.bomMatch" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-if="!panels.bomMatch" class="panel-body">
          <div class="match-summary">
            <div class="match-stat"><span class="num">{{ chainData.bomMatch.affectedProjects || 0 }}</span>受影响项目</div>
            <div class="match-stat"><span class="num">{{ chainData.bomMatch.affectedItems || 0 }}</span>受影响物料</div>
            <div class="match-stat danger"><span class="num">{{ chainData.bomMatch.redItems || 0 }}</span>高风险物料</div>
            <div class="match-stat warning"><span class="num">{{ chainData.bomMatch.yellowItems || 0 }}</span>关注物料</div>
          </div>

          <!-- 受影响项目列表 -->
          <div v-if="chainData.bomMatch.projects?.length" class="match-projects">
            <h5>受影响项目</h5>
            <div v-for="project in chainData.bomMatch.projects" :key="project.id" class="match-project-row">
              <span class="project-name">{{ project.name }}</span>
              <span class="project-risk">
                <el-tag v-for="level in ['red', 'yellow', 'green', 'gray']" :key="level" size="small" :type="level === 'red' ? 'danger' : level === 'yellow' ? 'warning' : level === 'green' ? 'success' : 'info'">
                  {{ level === 'red' ? '红' : level === 'yellow' ? '黄' : level === 'green' ? '绿' : '灰' }}{{ project[level] || 0 }}
                </el-tag>
              </span>
            </div>
          </div>

          <!-- 受影响物料列表 -->
          <div v-if="chainData.bomMatch.items?.length" class="match-items">
            <h5>受影响物料 Top {{ chainData.bomMatch.items.length }}</h5>
            <div v-for="item in chainData.bomMatch.items" :key="item.id" class="match-item-row">
              <span>{{ item.partNumber || '未知型号' }}</span>
              <span class="item-brand">{{ item.brand || '' }}</span>
              <el-tag :type="item.riskLevel === 'red' ? 'danger' : item.riskLevel === 'yellow' ? 'warning' : 'success'" size="small">
                {{ item.riskLevel === 'red' ? '高风险' : item.riskLevel === 'yellow' ? '关注' : '安全' }}
              </el-tag>
              <span v-if="item.projectName" class="item-project">项目: {{ item.projectName }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤5: 处置建议 -->
      <div v-if="chainData.actionAdvice" class="detail-panel" :class="{ collapsed: panels.actionAdvice }">
        <div class="panel-header" @click="panels.actionAdvice = !panels.actionAdvice">
          <div class="panel-title">
            <el-tag size="small" type="">步骤5</el-tag>
            <strong>处置建议</strong>
          </div>
          <el-icon><ArrowDown v-if="!panels.actionAdvice" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-if="!panels.actionAdvice" class="panel-body">
          <div class="advice-box urgent" v-if="chainData.actionAdvice.urgent?.length">
            <h5>🔴 紧急行动</h5>
            <ul><li v-for="(a, i) in chainData.actionAdvice.urgent" :key="i">{{ a }}</li></ul>
          </div>
          <div class="advice-box watch" v-if="chainData.actionAdvice.watch?.length">
            <h5>🟡 需要关注</h5>
            <ul><li v-for="(a, i) in chainData.actionAdvice.watch" :key="i">{{ a }}</li></ul>
          </div>
          <p v-if="!chainData.actionAdvice.urgent?.length && !chainData.actionAdvice.watch?.length" class="no-data">暂无处置建议</p>
        </div>
      </div>
    </div>

    <!-- 无数据状态 -->
    <el-empty v-if="!hasData" description="暂无涨价影响链路数据" :image-size="80" />
  </div>
</template>

<script setup>
import { computed, reactive } from 'vue'
import { ArrowDown, ArrowUp, Check } from '@element-plus/icons-vue'

const props = defineProps({
  chainData: { type: Object, default: null }
})

const emit = defineEmits(['navigate'])

const panels = reactive({
  rawSource: false,
  signal: false,
  event: false,
  bomMatch: false,
  actionAdvice: false
})

const hasData = computed(() => {
  const d = props.chainData
  return d && (d.rawSource || d.signal || d.event || d.bomMatch || d.actionAdvice)
})

const chainSteps = computed(() => {
  const d = props.chainData || {}
  return [
    {
      title: '原始情报',
      subtitle: d.rawSource ? `${d.rawSource.sourceType || '未知渠道'} · ${d.rawSource.sourceName || '未填写来源'}` : '暂无',
      active: !!d.rawSource,
      skipped: !d.rawSource,
      sourceType: d.rawSource?.sourceType,
      detail: !!d.rawSource,
      clickable: !!d.rawSource,
      onClick: () => { panels.rawSource = !panels.rawSource }
    },
    {
      title: '信号抽取',
      subtitle: d.signal ? `${d.signal.brand || ''} ${d.signal.category || ''} ${d.signal.mpn || ''}`.trim() || '已抽取' : '暂无',
      active: !!d.signal,
      skipped: !d.signal,
      statusTag: d.signal?.reviewStatus,
      statusClass: d.signal?.reviewStatus === 'confirmed' ? 'status-confirmed' : d.signal?.reviewStatus === 'need_review' ? 'status-review' : '',
      confidence: d.signal?.confidence != null ? formatPercent(d.signal.confidence) : '',
      detail: !!d.signal,
      clickable: !!d.signal,
      onClick: () => { panels.signal = !panels.signal }
    },
    {
      title: '市场事件',
      subtitle: d.event ? `${d.event.title || ''} · ${d.event.eventType || ''}` : '暂无',
      active: !!d.event,
      skipped: !d.event,
      statusTag: d.event?.severity,
      statusClass: d.event?.severity === 'critical' || d.event?.severity === 'high' ? 'status-danger' : '',
      detail: !!d.event,
      clickable: !!d.event,
      onClick: () => { panels.event = !panels.event }
    },
    {
      title: 'BOM匹配',
      subtitle: d.bomMatch ? `命中 ${d.bomMatch.affectedProjects || 0} 个项目 ${d.bomMatch.affectedItems || 0} 个物料` : '暂无',
      active: !!d.bomMatch,
      skipped: !d.bomMatch,
      detail: !!d.bomMatch,
      clickable: !!d.bomMatch,
      onClick: () => { panels.bomMatch = !panels.bomMatch }
    },
    {
      title: '处置建议',
      subtitle: d.actionAdvice ? `${(d.actionAdvice.urgent?.length || 0) + (d.actionAdvice.watch?.length || 0)} 条建议` : '暂无',
      active: !!(d.actionAdvice?.urgent?.length || d.actionAdvice?.watch?.length),
      skipped: !(d.actionAdvice?.urgent?.length || d.actionAdvice?.watch?.length),
      detail: !!(d.actionAdvice?.urgent?.length || d.actionAdvice?.watch?.length),
      clickable: !!(d.actionAdvice?.urgent?.length || d.actionAdvice?.watch?.length),
      onClick: () => { panels.actionAdvice = !panels.actionAdvice }
    }
  ]
})

function formatPercent(value) {
  if (value === null || value === undefined) return '暂无'
  const num = Number(value)
  if (num <= 1) return `${Math.round(num * 100)}%`
  return `${Math.round(num)}%`
}

function confidenceTag(conf) {
  if (conf == null) return 'info'
  const num = Number(conf)
  if (num >= 0.8) return 'success'
  if (num >= 0.5) return 'warning'
  return 'danger'
}

function reviewStatusTag(status) {
  if (status === 'confirmed') return 'success'
  if (status === 'need_review') return 'warning'
  if (status === 'rejected') return 'danger'
  return 'info'
}

function severityTag(severity) {
  if (severity === 'critical' || severity === 'high') return 'danger'
  if (severity === 'medium') return 'warning'
  return 'info'
}
</script>

<style scoped>
.impact-chain {
  border: 1px solid #e4e7ed;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
}

.chain-header {
  padding: 16px 20px;
  border-bottom: 1px solid #ebeef5;
  background: linear-gradient(135deg, #f0f7ff 0%, #f5f7fa 100%);
}

.chain-header h4 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #1f2d3d;
}

.chain-subtitle {
  font-size: 12px;
  color: #909399;
}

/* 步骤条 */
.chain-steps {
  display: flex;
  align-items: flex-start;
  padding: 20px 24px;
  gap: 0;
  overflow-x: auto;
}

.chain-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  min-width: 110px;
  flex: 1;
  cursor: default;
}

.chain-step.has-detail {
  cursor: pointer;
}

.chain-step.has-detail:hover .step-body {
  background: #ecf5ff;
}

.step-marker {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e4e7ed;
  color: #909399;
  position: relative;
  z-index: 1;
  transition: all 0.3s;
}

.chain-step.active .step-marker {
  background: #409eff;
  color: #fff;
}

.chain-step.skipped .step-marker {
  background: #f5f7fa;
  border: 2px dashed #dcdfe6;
}

.step-num {
  font-size: 14px;
  font-weight: 700;
}

.chain-step.active .step-icon {
  position: absolute;
  font-size: 20px;
}

.step-body {
  text-align: center;
  padding: 8px 6px;
  border-radius: 8px;
  margin-top: 8px;
  transition: background 0.2s;
  width: 100%;
}

.step-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.step-subtitle {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
  word-break: break-all;
}

.step-detail {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
}

.detail-chip {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: #ecf5ff;
  color: #409eff;
}

.detail-chip.status-confirmed { background: #f0f9eb; color: #67c23a; }
.detail-chip.status-review { background: #fdf6ec; color: #e6a23c; }
.detail-chip.status-danger { background: #fef0f0; color: #f56c6c; }
.detail-chip.confidence { background: #f5f7fa; color: #606266; }

.step-connector {
  position: absolute;
  top: 18px;
  left: calc(50% + 18px);
  width: calc(100% - 36px);
  height: 2px;
  background: #e4e7ed;
  z-index: 0;
}

.step-connector.active {
  background: #409eff;
}

/* 详情面板 */
.chain-detail-panels {
  border-top: 1px solid #ebeef5;
}

.detail-panel {
  border-bottom: 1px solid #f0f0f0;
}

.detail-panel:last-child {
  border-bottom: none;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  cursor: pointer;
  transition: background 0.2s;
}

.panel-header:hover {
  background: #f5f7fa;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-body {
  padding: 12px 20px 16px;
  background: #fafbfc;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
}

.info-table tr {
  border-bottom: 1px solid #f0f0f0;
}

.info-table td {
  padding: 8px 0;
  font-size: 13px;
  color: #303133;
  vertical-align: top;
}

.info-table td.label {
  width: 100px;
  color: #909399;
  font-weight: 500;
}

.info-table a {
  color: #409eff;
  text-decoration: none;
}

.info-table a:hover {
  text-decoration: underline;
}

.excerpt-box {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #f5f7fa;
  border-left: 3px solid #409eff;
}

.excerpt-label {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 4px;
}

.excerpt-box p {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

/* 匹配统计 */
.match-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.match-stat {
  padding: 10px;
  border-radius: 8px;
  background: #f5f7fa;
  text-align: center;
  font-size: 12px;
  color: #606266;
}

.match-stat.danger .num { color: #f56c6c; }
.match-stat.warning .num { color: #e6a23c; }

.match-stat .num {
  display: block;
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}

.match-projects h5, .match-items h5 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #303133;
}

.match-project-row, .match-item-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 6px;
  background: #fff;
  margin-top: 4px;
  font-size: 13px;
}

.project-name { font-weight: 600; color: #303133; flex: 1; }
.project-risk { display: flex; gap: 4px; }
.item-brand { color: #909399; font-size: 12px; }
.item-project { color: #909399; font-size: 11px; margin-left: auto; }

.highlight-red { color: #f56c6c; font-weight: 600; }
.highlight-orange { color: #e6a23c; font-weight: 600; }

/* 建议 */
.advice-box {
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.advice-box.urgent {
  background: #fef0f0;
  border-left: 3px solid #f56c6c;
}

.advice-box.watch {
  background: #fdf6ec;
  border-left: 3px solid #e6a23c;
}

.advice-box h5 {
  margin: 0 0 6px;
  font-size: 13px;
}

.advice-box ul {
  margin: 0;
  padding-left: 18px;
}

.advice-box li {
  font-size: 13px;
  line-height: 1.6;
  color: #606266;
}

.no-data {
  color: #909399;
  font-size: 13px;
  text-align: center;
  padding: 12px;
}
</style>
