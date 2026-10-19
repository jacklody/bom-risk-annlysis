<template>
  <div class="upload-area">
    <!-- 模式切换 -->
    <el-radio-group v-model="mode" size="small" style="margin-bottom: 16px">
      <el-radio-button value="single">单文件分析</el-radio-button>
      <el-radio-button value="batch">批量分析</el-radio-button>
    </el-radio-group>

    <!-- 单文件模式 -->
    <template v-if="mode === 'single'">
      <el-upload
        ref="uploadRef"
        data-testid="bom-file-input"
        drag
        :auto-upload="false"
        :on-change="handleChange"
        :limit="1"
        accept=".xlsx,.xls,.csv"
        :disabled="disabled"
      >
        <el-icon class="el-icon--upload" :size="48">
          <UploadFilled />
        </el-icon>
        <div class="el-upload__text">
          拖拽 BOM 文件到此处，或 <em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .xlsx / .xls / .csv，需包含型号、品牌等物料列
          </div>
        </template>
      </el-upload>

      <div v-if="fileName" class="file-selected">
        <el-tag type="success" size="large" closable @close="clearFile">
          <el-icon><Document /></el-icon>
          {{ fileName }}
        </el-tag>
      </div>

      <div v-if="fileName" class="action-bar">
        <el-input
          v-model="projectName"
          data-testid="project-name-input"
          placeholder="项目名称（选填，默认用文件名）"
          style="max-width: 300px"
          size="default"
        />
        <el-button
          data-testid="start-analyze-button"
          type="primary"
          @click="startAnalyze"
          :loading="disabled"
          size="default"
        >
          <el-icon><VideoPlay /></el-icon> 开始分析
        </el-button>
      </div>
    </template>

    <!-- 批量模式 -->
    <template v-else>
      <el-upload
        ref="batchUploadRef"
        drag
        multiple
        :auto-upload="false"
        :on-change="handleBatchChange"
        :on-remove="handleBatchRemove"
        accept=".xlsx,.xls,.csv"
        :disabled="disabled"
      >
        <el-icon class="el-icon--upload" :size="48">
          <UploadFilled />
        </el-icon>
        <div class="el-upload__text">
          拖拽多个 BOM 文件到此处，或 <em>点击批量选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            一次最多上传 20 个BOM文件，所有项目分析完成后会汇总展示
          </div>
        </template>
      </el-upload>

      <div v-if="batchFiles.length" class="action-bar">
        <el-tag type="info" size="large">
          已选择 {{ batchFiles.length }} 个文件
        </el-tag>
        <el-button type="primary" @click="startBatchAnalyze" :loading="disabled" size="default">
          <el-icon><VideoPlay /></el-icon> 批量分析（{{ batchFiles.length }}个）
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['upload', 'upload-batch'])
defineProps({
  disabled: { type: Boolean, default: false }
})

const mode = ref('single')
const uploadRef = ref(null)
const batchUploadRef = ref(null)
const fileName = ref('')
const projectName = ref('')
const batchFiles = ref([])
let selectedFile = null

function handleChange(file) {
  selectedFile = file.raw
  fileName.value = file.name
}

function clearFile() {
  selectedFile = null
  fileName.value = ''
  projectName.value = ''
  uploadRef.value?.clearFiles()
}

function startAnalyze() {
  if (selectedFile) {
    emit('upload', selectedFile, projectName.value)
  }
}

function handleBatchChange(file, fileList) {
  batchFiles.value = fileList.map(f => f.raw).filter(Boolean)
}

function handleBatchRemove(file, fileList) {
  batchFiles.value = fileList.map(f => f.raw).filter(Boolean)
}

function startBatchAnalyze() {
  if (batchFiles.value.length) {
    emit('upload-batch', batchFiles.value)
  }
}
</script>

<style scoped>
.upload-area {
  max-width: 700px;
  margin: 0 auto;
}

.file-selected {
  text-align: center;
  margin-top: 16px;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 16px;
}
</style>
