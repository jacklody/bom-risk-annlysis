<template>
  <div class="industry-chain-graph" ref="containerRef">
    <div class="panel-header">
      <h2 class="panel-title">EMS产业链风险图谱</h2>
      <div class="header-actions">
        <el-tag size="small" effect="plain">基础材料</el-tag>
        <span class="header-arrow">→</span>
        <el-tag size="small" effect="plain">器件品类</el-tag>
        <span class="header-arrow">→</span>
        <el-tag size="small" effect="plain">BOM物料</el-tag>
      </div>
    </div>

    <div class="legend-bar">
      <span class="legend-item"><span class="legend-dot" style="background:#F56C6C" />高风险</span>
      <span class="legend-item"><span class="legend-dot" style="background:#E6A23C" />中风险</span>
      <span class="legend-item"><span class="legend-dot" style="background:#E6D23C" />低风险</span>
      <span class="legend-item"><span class="legend-dot" style="background:#67C23A" />安全</span>
      <span class="legend-item"><span class="legend-dot" style="background:#909399" />未知</span>
    </div>

    <div class="graph-viewport" ref="viewportRef" @wheel.prevent="onWheel">
      <svg
        ref="svgRef"
        :width="svgWidth"
        :height="svgHeight"
        :viewBox="`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`"
        class="graph-svg"
      >
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 7" refX="10" refY="3.5"
            markerWidth="8" markerHeight="6" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#c0c6d0" />
          </marker>
          <filter id="node-shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.1" />
          </filter>
        </defs>

        <!-- Edges -->
        <g class="edges-layer">
          <path
            v-for="edge in renderedEdges"
            :key="`${edge.from}-${edge.to}`"
            :d="edge.path"
            :stroke="edge.color"
            :stroke-width="edge.strokeWidth"
            fill="none"
            stroke-opacity="0.6"
            marker-end="url(#arrowhead)"
            class="edge-path"
            :class="{ highlighted: isEdgeHighlighted(edge) }"
          />
        </g>

        <!-- Column labels -->
        <g class="column-labels">
          <text :x="colX.material" :y="30" text-anchor="middle" class="col-label">基础材料</text>
          <text :x="colX.component" :y="30" text-anchor="middle" class="col-label">器件品类</text>
          <text :x="colX.bom_item" :y="30" text-anchor="middle" class="col-label">BOM物料</text>
        </g>

        <!-- Nodes -->
        <g
          v-for="node in renderedNodes"
          :key="node.id"
          class="node-group"
          :class="{ expanded: expandedNode === node.id }"
          :transform="`translate(${node.x}, ${node.y})`"
          @click="handleNodeClick(node)"
          @mouseenter="hoveredNode = node.id"
          @mouseleave="hoveredNode = null"
        >
          <rect
            :width="nodeWidth"
            :height="nodeHeight"
            :rx="8"
            :ry="8"
            :fill="getNodeBg(node)"
            :stroke="getRiskColor(node.risk_level)"
            :stroke-width="hoveredNode === node.id || expandedNode === node.id ? 2.5 : 1.5"
            filter="url(#node-shadow)"
            class="node-rect"
          />
          <!-- Risk indicator bar on left -->
          <rect
            x="0" y="0" width="4" :height="nodeHeight"
            :rx="2"
            :fill="getRiskColor(node.risk_level)"
          />
          <!-- Node name -->
          <text :x="14" :y="20" class="node-name" fill="#1f2937">{{ node.name }}</text>
          <!-- Price trend -->
          <text :x="14" :y="38" class="node-trend" :fill="trendColor(node.price_trend)">
            {{ trendIcon(node.price_trend) }}
            <tspan v-if="node.price_change_pct != null"> {{ node.price_change_pct > 0 ? '+' : '' }}{{ node.price_change_pct }}%</tspan>
          </text>
          <!-- BOM line count -->
          <text :x="14" :y="54" class="node-bom-count">
            影响BOM: {{ node.bom_line_count }}行
          </text>
          <!-- Risk badge -->
          <g :transform="`translate(${nodeWidth - 28}, 6)`">
            <rect width="22" height="18" rx="4" :fill="getRiskColor(node.risk_level)" opacity="0.9" />
            <text x="11" y="13" text-anchor="middle" class="risk-badge-text">{{ riskLabel(node.risk_level) }}</text>
          </g>
        </g>
      </svg>
    </div>

    <!-- Zoom controls -->
    <div class="zoom-controls">
      <el-button size="small" circle @click="zoomIn">
        <el-icon><Plus /></el-icon>
      </el-button>
      <el-button size="small" circle @click="zoomOut">
        <el-icon><Minus /></el-icon>
      </el-button>
      <el-button size="small" circle @click="resetView">
        <el-icon><FullScreen /></el-icon>
      </el-button>
    </div>

    <!-- Node detail tooltip -->
    <transition name="fade">
      <div v-if="expandedNode && expandedNodeData" class="node-tooltip">
        <div class="tooltip-header">
          <strong>{{ expandedNodeData.name }}</strong>
          <el-tag :color="getRiskColor(expandedNodeData.risk_level)" size="small" effect="dark"
            style="color: #fff; border: none;">
            {{ riskLabel(expandedNodeData.risk_level) }}
          </el-tag>
        </div>
        <div class="tooltip-body">
          <p>价格趋势：{{ trendLabel(expandedNodeData.price_trend) }}
            <span v-if="expandedNodeData.price_change_pct != null">
              ({{ expandedNodeData.price_change_pct > 0 ? '+' : '' }}{{ expandedNodeData.price_change_pct }}%)
            </span>
          </p>
          <p>影响BOM行数：{{ expandedNodeData.bom_line_count }}</p>
          <p v-if="expandedNodeData.children && expandedNodeData.children.length > 0">
            下游节点：{{ expandedNodeData.children.length }}个
          </p>
        </div>
        <el-button size="small" text type="primary" @click="expandedNode = null">关闭</el-button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Plus, Minus, FullScreen } from '@element-plus/icons-vue'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] }
})

const containerRef = ref(null)
const viewportRef = ref(null)
const svgRef = ref(null)

const nodeWidth = 180
const nodeHeight = 64
const colPadding = 60
const rowPadding = 20

const hoveredNode = ref(null)
const expandedNode = ref(null)

const zoom = ref(1)
const viewBox = ref({ x: 0, y: 0, w: 900, h: 700 })
const svgWidth = ref(900)
const svgHeight = ref(700)

const riskColors = {
  red: '#F56C6C',
  orange: '#E6A23C',
  yellow: '#E6D23C',
  green: '#67C23A',
  gray: '#909399'
}

const colX = computed(() => {
  const totalW = nodeWidth * 3 + colPadding * 4
  return {
    material: colPadding + nodeWidth / 2,
    component: colPadding * 2 + nodeWidth + colPadding + nodeWidth / 2,
    bom_item: colPadding * 3 + nodeWidth * 2 + colPadding + nodeWidth / 2
  }
})

function getRiskColor(level) {
  return riskColors[level] || riskColors.gray
}

function getNodeBg(node) {
  const c = getRiskColor(node.risk_level)
  // Light tint of the risk color
  return `${c}10`
}

function trendIcon(trend) {
  return { up: '↑', down: '↓', stable: '→' }[trend] || '→'
}

function trendColor(trend) {
  return { up: '#F56C6C', down: '#67C23A', stable: '#909399' }[trend] || '#909399'
}

function trendLabel(trend) {
  return { up: '上涨', down: '下跌', stable: '平稳' }[trend] || '未知'
}

function riskLabel(level) {
  return { red: '高', orange: '中', yellow: '低', green: '安', gray: '?' }[level] || '?'
}

const expandedNodeData = computed(() => {
  if (!expandedNode.value) return null
  return props.nodes.find(n => n.id === expandedNode.value)
})

function handleNodeClick(node) {
  expandedNode.value = expandedNode.value === node.id ? null : node.id
}

function isEdgeHighlighted(edge) {
  if (!expandedNode.value) return false
  return edge.from === expandedNode.value || edge.to === expandedNode.value
}

// ─── Layout computation ───
const renderedNodes = computed(() => {
  const levels = ['material', 'component', 'bom_item']
  const groups = {}
  levels.forEach(l => { groups[l] = [] })
  props.nodes.forEach(n => {
    if (groups[n.level]) groups[n.level].push(n)
  })

  const result = []
  levels.forEach(level => {
    const group = groups[level]
    const x = colX.value[level] - nodeWidth / 2
    const totalHeight = group.length * (nodeHeight + rowPadding) - rowPadding
    const startY = Math.max(50, (svgHeight.value - totalHeight) / 2)

    group.forEach((node, idx) => {
      result.push({
        ...node,
        x,
        y: startY + idx * (nodeHeight + rowPadding)
      })
    })
  })
  return result
})

const renderedEdges = computed(() => {
  const nodeMap = {}
  renderedNodes.value.forEach(n => { nodeMap[n.id] = n })

  return props.edges.map(edge => {
    const from = nodeMap[edge.from]
    const to = nodeMap[edge.to]
    if (!from || !to) return null

    const x1 = from.x + nodeWidth
    const y1 = from.y + nodeHeight / 2
    const x2 = to.x
    const y2 = to.y + nodeHeight / 2

    const midX = (x1 + x2) / 2
    const path = `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`

    const isHighlighted = isEdgeHighlighted(edge)
    const baseColor = isHighlighted
      ? getRiskColor(from.risk_level)
      : '#c0c6d0'
    const strokeWidth = isHighlighted
      ? Math.max(edge.weight * 0.8, 2)
      : Math.max(edge.weight * 0.5, 1)

    return { ...edge, path, color: baseColor, strokeWidth }
  }).filter(Boolean)
})

// ─── Zoom/Pan ───
function zoomIn() {
  zoom.value = Math.min(zoom.value * 1.2, 3)
  updateViewBox()
}

function zoomOut() {
  zoom.value = Math.max(zoom.value / 1.2, 0.5)
  updateViewBox()
}

function resetView() {
  zoom.value = 1
  viewBox.value = { x: 0, y: 0, w: 900, h: 700 }
}

function updateViewBox() {
  const baseW = 900 / zoom.value
  const baseH = 700 / zoom.value
  viewBox.value = {
    x: (900 - baseW) / 2,
    y: (700 - baseH) / 2,
    w: baseW,
    h: baseH
  }
}

function onWheel(e) {
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  zoom.value = Math.max(0.5, Math.min(3, zoom.value * delta))
  updateViewBox()
}

// ─── Resize handling ───
function handleResize() {
  if (containerRef.value) {
    const rect = containerRef.value.getBoundingClientRect()
    svgWidth.value = Math.max(rect.width - 24, 400)
    svgHeight.value = Math.max(rect.height - 120, 400)
  }
}

let resizeObserver = null

onMounted(() => {
  handleResize()
  resizeObserver = new ResizeObserver(handleResize)
  if (containerRef.value) resizeObserver.observe(containerRef.value)
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
})

watch(() => [props.nodes, props.edges], () => {
  // Reset view when data changes
  resetView()
}, { deep: true })
</script>

<style scoped>
.industry-chain-graph {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  position: relative;
  background: #fafbfc;
}

.panel-header {
  padding: 16px 16px 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  border-bottom: 1px solid #ebeef5;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-arrow {
  color: #c0c6d0;
  font-size: 14px;
}

.legend-bar {
  display: flex;
  gap: 14px;
  padding: 6px 16px;
  flex-shrink: 0;
  border-bottom: 1px solid #f0f2f5;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #667085;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.graph-viewport {
  flex: 1;
  overflow: hidden;
  position: relative;
  cursor: grab;
}

.graph-viewport:active {
  cursor: grabbing;
}

.graph-svg {
  display: block;
}

.col-label {
  font-size: 13px;
  font-weight: 600;
  fill: #5b4bb7;
  opacity: 0.7;
}

.node-group {
  cursor: pointer;
  transition: transform 0.15s ease;
}

.node-rect {
  transition: stroke-width 0.15s ease;
}

.node-name {
  font-size: 12px;
  font-weight: 600;
  pointer-events: none;
}

.node-trend {
  font-size: 11px;
  pointer-events: none;
}

.node-bom-count {
  font-size: 10px;
  fill: #909399;
  pointer-events: none;
}

.risk-badge-text {
  font-size: 10px;
  font-weight: 700;
  fill: #fff;
  pointer-events: none;
}

.edge-path {
  transition: stroke 0.2s ease, stroke-width 0.2s ease;
}

.edge-path.highlighted {
  stroke-opacity: 0.9;
}

.zoom-controls {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-tooltip {
  position: absolute;
  top: 80px;
  right: 16px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 14px;
  width: 220px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  z-index: 10;
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.tooltip-header strong {
  font-size: 14px;
  color: #1f2937;
}

.tooltip-body p {
  margin: 4px 0;
  font-size: 12px;
  color: #667085;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
