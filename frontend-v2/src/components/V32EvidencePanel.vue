<template>
  <div class="v32-evidence-panel">
    <div v-if="!hasEvidence" class="v32-empty">
      <el-empty description="暂无 v3.2 依据链数据" :image-size="72" />
      <span class="empty-text">暂无 v3.2 依据链数据</span>
    </div>

    <template v-else>
      <div class="v32-header">
        <div>
          <div class="v32-title">{{ categoryDisplay }}</div>
          <div class="v32-subtitle">主导轨道：{{ trackLabel }}</div>
        </div>
        <el-tag :type="riskTagType" effect="dark" size="small">
          {{ riskLabel }} / {{ scoreText }}分
        </el-tag>
      </div>

      <el-alert
        v-if="item.v32_evidence_summary"
        class="v32-alert"
        :title="item.v32_evidence_summary"
        type="info"
        :closable="false"
        show-icon
      />

      <div v-if="item.v32_action_suggestion" class="v32-action">
        <strong>处置建议：</strong>{{ item.v32_action_suggestion }}
      </div>

      <el-timeline class="v32-timeline">
        <el-timeline-item
          v-for="(node, index) in evidenceNodes"
          :key="`${node.type || 'node'}-${index}`"
          :type="timelineType(node.type)"
          :timestamp="node.source || node.type || ''"
        >
          <div class="node-title">{{ node.title || node.type || '依据节点' }}</div>
          <div class="node-detail">{{ node.detail || node.summary || node.reason || '-' }}</div>
        </el-timeline-item>
      </el-timeline>
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  item: { type: Object, default: () => ({}) }
})

const evidenceNodes = computed(() => Array.isArray(props.item.v32_evidence_chain) ? props.item.v32_evidence_chain : [])

const hasEvidence = computed(() => Boolean(
  props.item.v32_evidence_summary ||
  props.item.v32_action_suggestion ||
  props.item.v32_risk_level ||
  evidenceNodes.value.length
))

const categoryDisplay = computed(() => props.item.v32_category_display || props.item.v32_category || '未识别品类')
const scoreText = computed(() => props.item.v32_risk_score ?? '-')

const trackLabel = computed(() => {
  const map = {
    demand_supply: '需求/供应轨',
    material: '材料传导轨',
    information_insufficient: '信息不足',
    buffer: '缓冲因素'
  }
  return map[props.item.v32_primary_track] || props.item.v32_primary_track || '未判定'
})

const riskTagType = computed(() => {
  const map = { red: 'danger', orange: 'warning', yellow: 'warning', green: 'success', gray: 'info' }
  return map[props.item.v32_risk_level] || 'info'
})

const riskLabel = computed(() => {
  const map = { red: '红色高风险', orange: '橙色较高风险', yellow: '黄色关注', green: '绿色安全', gray: '灰色信息不足' }
  return map[props.item.v32_risk_level] || props.item.v32_risk_level || '未知风险'
})

function timelineType(type) {
  const map = {
    market_event: 'warning',
    dual_track: 'danger',
    supply_snapshot: 'primary',
    buffer: 'success',
    information_status: 'info'
  }
  return map[type] || 'primary'
}
</script>

<style scoped>
.v32-evidence-panel {
  min-width: 320px;
}

.v32-empty {
  text-align: center;
  color: #909399;
}

.empty-text {
  font-size: 13px;
}

.v32-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.v32-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.v32-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: #909399;
}

.v32-alert {
  margin: 8px 0;
}

.v32-action {
  margin: 10px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fdf6ec;
  color: #6b4f1d;
  font-size: 13px;
  line-height: 1.5;
}

.v32-timeline {
  margin-top: 12px;
  padding-left: 2px;
}

.node-title {
  font-weight: 600;
  color: #303133;
}

.node-detail {
  margin-top: 3px;
  color: #606266;
  font-size: 12px;
  line-height: 1.5;
}
</style>
