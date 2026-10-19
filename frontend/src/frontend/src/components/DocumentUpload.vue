<template>
  <div class="document-upload">
    <!-- 拖拽上传区域 -->
    <div
      class="upload-area"
      :class="{ 'drag-over': isDragOver, 'has-file': selectedFile }"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        accept=".txt,.md,.pdf"
        class="file-input"
        @change="handleFileSelect"
      />
      <div v-if="!selectedFile" class="upload-placeholder">
        <el-icon :size="48"><UploadFilled /></el-icon>
        <p class="upload-title">拖拽文件到此处，或点击选择文件</p>
        <p class="upload-hint">支持 .txt / .md / .pdf 格式，最大 10MB</p>
      </div>
      <div v-else class="file-info">
        <el-icon :size="24"><Document /></el-icon>
        <span class="file-name">{{ selectedFile.name }}</span>
        <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
        <el-button
          type="danger"
          :icon="Close"
          circle
          size="small"
          @click.stop="clearFile"
        />
      </div>
    </div>

    <!-- 文档类型选择 -->
    <div class="doc-type-selector">
      <span class="label">文档类型：</span>
      <el-radio-group v-model="docType" size="small">
        <el-radio-button value="auto">自动识别</el-radio-button>
        <el-radio-button value="price_increase">涨价函</el-radio-button>
        <el-radio-button value="shortage">缺货通知</el-radio-button>
        <el-radio-button value="report">行业报告</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 解析按钮 -->
    <div class="action-bar">
      <el-button
        type="primary"
        :loading="parsing"
        :disabled="!selectedFile"
        @click="parseDocument"
      >
        {{ parsing ? '解析中...' : '开始解析' }}
      </el-button>
      <el-button v-if="parseResult" @click="clearResult">清除结果</el-button>
    </div>

    <!-- 解析状态 -->
    <div v-if="parseResult" class="parse-info">
      <el-tag :type="parseResult.degraded ? 'warning' : 'success'" size="small">
        {{ parseResult.degraded ? '降级模式（正则提取）' : 'LLM 解析' }}
      </el-tag>
      <span class="latency">耗时 {{ parseResult.latency_ms?.toFixed(0) }}ms</span>
      <el-tag type="info" size="small">{{ parseResult.doc_type_classified }}</el-tag>
    </div>

    <!-- 文档摘要 -->
    <div v-if="parseResult?.doc_summary" class="doc-summary">
      <h4>文档摘要</h4>
      <p>{{ parseResult.doc_summary }}</p>
    </div>

    <!-- 解析结果：事件卡片列表 -->
    <div v-if="parseResult?.events?.length" class="events-list">
      <h4>提取的风险事件（{{ parseResult.events.length }} 个）</h4>
      <div
        v-for="(event, index) in parseResult.events"
        :key="index"
        class="event-card"
        :class="`impact-${event.impact_level}`"
      >
        <!-- 事件头部 -->
        <div class="event-header">
          <el-tag
            :type="getEventTypeTagType(event.event_type)"
            size="small"
            effect="dark"
          >
            {{ getEventTypeLabel(event.event_type) }}
          </el-tag>
          <el-tag
            :type="getImpactTagType(event.impact_level)"
            size="small"
          >
            {{ getImpactLabel(event.impact_level) }}
          </el-tag>
          <span class="confidence">置信度: {{ (event.confidence * 100).toFixed(0) }}%</span>
        </div>

        <!-- 事件标题与描述 -->
        <div class="event-body">
          <h5 class="event-title">{{ event.title }}</h5>
          <p class="event-description">{{ event.description }}</p>
        </div>

        <!-- 影响范围 -->
        <div class="event-details">
          <div v-if="event.affected_categories?.length" class="detail-item">
            <span class="detail-label">影响品类：</span>
            <el-tag
              v-for="cat in event.affected_categories"
              :key="cat"
              size="small"
              class="tag-item"
            >
              {{ cat }}
            </el-tag>
          </div>
          <div v-if="event.affected_manufacturers?.length" class="detail-item">
            <span class="detail-label">影响厂商：</span>
            <el-tag
              v-for="mfr in event.affected_manufacturers"
              :key="mfr"
              size="small"
              type="info"
              class="tag-item"
            >
              {{ mfr }}
            </el-tag>
          </div>
          <div v-if="event.effective_date" class="detail-item">
            <span class="detail-label">生效日期：</span>
            <span>{{ event.effective_date }}</span>
          </div>
          <div v-if="event.price_change_pct != null" class="detail-item">
            <span class="detail-label">涨幅：</span>
            <span class="price-change">+{{ event.price_change_pct }}%</span>
          </div>
        </div>

        <!-- 原文证据 -->
        <div v-if="event.evidence_text" class="event-evidence">
          <span class="detail-label">原文依据：</span>
          <p class="evidence-text">「{{ event.evidence_text }}」</p>
        </div>

        <!-- 手动确认/修正 -->
        <div class="event-actions">
          <el-button
            :type="event._confirmed ? 'success' : 'default'"
            size="small"
            @click="confirmEvent(index)"
          >
            {{ event._confirmed ? '已确认' : '确认事件' }}
          </el-button>
          <el-button
            size="small"
            @click="editEvent(index)"
          >
            修正
          </el-button>
        </div>
      </div>
    </div>

    <!-- 无事件结果 -->
    <div v-else-if="parseResult && !parseResult.events?.length" class="no-events">
      <el-empty description="未从文档中提取到供应链风险事件" />
    </div>

    <!-- 修正对话框 -->
    <el-dialog v-model="editDialogVisible" title="修正事件信息" width="600px">
      <el-form
        v-if="editingEvent"
        :model="editingEvent"
        label-width="100px"
      >
        <el-form-item label="事件标题">
          <el-input v-model="editingEvent.title" />
        </el-form-item>
        <el-form-item label="事件类型">
          <el-select v-model="editingEvent.event_type">
            <el-option value="price_increase" label="涨价" />
            <el-option value="shortage" label="缺货" />
            <el-option value="supply_disruption" label="供应中断" />
            <el-option value="natural_disaster" label="自然灾害" />
            <el-option value="policy_change" label="政策变化" />
          </el-select>
        </el-form-item>
        <el-form-item label="影响等级">
          <el-select v-model="editingEvent.impact_level">
            <el-option value="high" label="高" />
            <el-option value="medium" label="中" />
            <el-option value="low" label="低" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editingEvent.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Close } from '@element-plus/icons-vue'

// ── 状态 ──
const fileInput = ref(null)
const selectedFile = ref(null)
const isDragOver = ref(false)
const docType = ref('auto')
const parsing = ref(false)
const parseResult = ref(null)
const editDialogVisible = ref(false)
const editingEvent = ref(null)
const editingIndex = ref(-1)

// ── 文件选择 ──
function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
    parseResult.value = null
  }
}

function handleDrop(event) {
  const file = event.dataTransfer.files[0]
  if (file) {
    const ext = file.name.split('.').pop().toLowerCase()
    if (!['txt', 'md', 'pdf'].includes(ext)) {
      ElMessage.warning('仅支持 .txt / .md / .pdf 格式')
      return
    }
    selectedFile.value = file
    parseResult.value = null
  }
}

function clearFile() {
  selectedFile.value = null
  parseResult.value = null
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

// ── 解析 ──
async function parseDocument() {
  if (!selectedFile.value) return

  parsing.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('doc_type', docType.value)

    const response = await fetch('/api/v1/documents/upload', {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: '解析失败' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    const data = await response.json()

    // 为每个事件添加 UI 状态字段
    if (data.events) {
      data.events = data.events.map(e => ({
        ...e,
        _confirmed: false,
      }))
    }

    parseResult.value = data

    if (data.degraded) {
      ElMessage.warning('LLM 不可用，已使用正则降级提取')
    } else {
      ElMessage.success(`解析完成，提取到 ${data.events?.length || 0} 个事件`)
    }
  } catch (error) {
    ElMessage.error(`解析失败: ${error.message}`)
    console.error('Document parse error:', error)
  } finally {
    parsing.value = false
  }
}

function clearResult() {
  parseResult.value = null
}

// ── 事件操作 ──
function confirmEvent(index) {
  if (parseResult.value?.events?.[index]) {
    parseResult.value.events[index]._confirmed = true
  }
}

function editEvent(index) {
  editingIndex.value = index
  editingEvent.value = { ...parseResult.value.events[index] }
  editDialogVisible.value = true
}

function saveEdit() {
  if (parseResult.value?.events?.[editingIndex.value] && editingEvent.value) {
    // 保留 _confirmed 状态
    const confirmed = parseResult.value.events[editingIndex.value]._confirmed
    Object.assign(parseResult.value.events[editingIndex.value], editingEvent.value)
    parseResult.value.events[editingIndex.value]._confirmed = confirmed
  }
  editDialogVisible.value = false
  editingEvent.value = null
  editingIndex.value = -1
}

// ── 工具函数 ──
function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function getEventTypeLabel(type) {
  const labels = {
    price_increase: '涨价',
    shortage: '缺货',
    supply_disruption: '供应中断',
    natural_disaster: '自然灾害',
    policy_change: '政策变化',
  }
  return labels[type] || type
}

function getEventTypeTagType(type) {
  const types = {
    price_increase: 'danger',
    shortage: 'warning',
    supply_disruption: 'danger',
    natural_disaster: '',
    policy_change: 'info',
  }
  return types[type] || ''
}

function getImpactLabel(level) {
  const labels = { high: '高影响', medium: '中影响', low: '低影响' }
  return labels[level] || level
}

function getImpactTagType(level) {
  const types = { high: 'danger', medium: 'warning', low: 'info' }
  return types[level] || 'info'
}
</script>

<style scoped>
.document-upload {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.upload-area {
  border: 2px dashed #d9d9d9;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}

.upload-area:hover,
.upload-area.drag-over {
  border-color: #409eff;
  background: #ecf5ff;
}

.upload-area.has-file {
  padding: 20px;
  border-style: solid;
  border-color: #67c23a;
  background: #f0f9eb;
}

.file-input {
  display: none;
}

.upload-placeholder {
  color: #909399;
}

.upload-title {
  font-size: 16px;
  margin: 12px 0 8px;
}

.upload-hint {
  font-size: 13px;
  color: #c0c4cc;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}

.file-name {
  font-weight: 500;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  color: #909399;
  font-size: 13px;
}

.doc-type-selector {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.doc-type-selector .label {
  font-size: 14px;
  color: #606266;
}

.action-bar {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.parse-info {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.latency {
  font-size: 13px;
  color: #909399;
}

.doc-summary {
  margin-top: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  border-left: 3px solid #409eff;
}

.doc-summary h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #303133;
}

.doc-summary p {
  margin: 0;
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.events-list {
  margin-top: 24px;
}

.events-list h4 {
  font-size: 16px;
  margin-bottom: 16px;
  color: #303133;
}

.event-card {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  transition: box-shadow 0.3s;
}

.event-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.event-card.impact-high {
  border-left: 4px solid #f56c6c;
}

.event-card.impact-medium {
  border-left: 4px solid #e6a23c;
}

.event-card.impact-low {
  border-left: 4px solid #909399;
}

.event-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.confidence {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
}

.event-body {
  margin-bottom: 12px;
}

.event-title {
  font-size: 15px;
  margin: 0 0 8px;
  color: #303133;
}

.event-description {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
  margin: 0;
}

.event-details {
  margin-bottom: 12px;
}

.detail-item {
  display: flex;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 13px;
}

.detail-label {
  color: #909399;
  min-width: 70px;
  flex-shrink: 0;
}

.tag-item {
  margin-right: 4px;
}

.price-change {
  color: #f56c6c;
  font-weight: 600;
}

.event-evidence {
  padding: 8px 12px;
  background: #fdf6ec;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 13px;
}

.evidence-text {
  margin: 4px 0 0;
  color: #606266;
  font-style: italic;
  line-height: 1.5;
}

.event-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.no-events {
  margin-top: 24px;
}
</style>
