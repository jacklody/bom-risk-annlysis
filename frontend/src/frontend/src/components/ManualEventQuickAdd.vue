<template>
  <el-card class="manual-event-card" shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <strong>人工行情事件快速录入</strong>
          <span class="header-hint">供应商涨价/缺货通知可在这里触发结构化识别</span>
        </div>
        <el-tag size="small" type="warning">v3.2</el-tag>
      </div>
    </template>

    <div class="quick-form">
      <label class="field">
        <span>事件标题</span>
        <input
          v-model="form.title"
          data-testid="manual-event-title"
          class="native-input wide"
          placeholder="例如：TDK高容MLCC缺货涨价通知"
        />
      </label>

      <label class="field">
        <span>品牌</span>
        <input v-model="form.brand" data-testid="manual-event-brand" class="native-input" placeholder="TDK / Murata" />
      </label>

      <label class="field">
        <span>品类</span>
        <input v-model="form.category" data-testid="manual-event-category" class="native-input" placeholder="high_cap_mlcc" />
      </label>

      <label class="field">
        <span>型号</span>
        <input v-model="form.mpn" data-testid="manual-event-mpn" class="native-input" placeholder="可选" />
      </label>

      <label class="field">
        <span>事件类型</span>
        <select v-model="form.event_type" data-testid="manual-event-type" class="native-input">
          <option value="price_increase">涨价</option>
          <option value="shortage">缺货</option>
          <option value="lead_time_increase">交期拉长</option>
        </select>
      </label>

      <label class="field narrow">
        <span>涨幅%</span>
        <input
          v-model.number="form.increase_max_pct"
          data-testid="manual-event-increase"
          class="native-input"
          type="number"
          min="0"
          placeholder="20"
        />
      </label>

      <label class="field narrow">
        <span>交期周数</span>
        <input
          v-model.number="form.lead_time_weeks"
          data-testid="manual-event-lead-time"
          class="native-input"
          type="number"
          min="0"
          placeholder="16"
        />
      </label>

      <label class="field wide">
        <span>来源链接/文件</span>
        <input
          v-model="form.source_url"
          data-testid="manual-event-source"
          class="native-input wide"
          placeholder="供应商通知、官网链接或文件路径"
        />
      </label>

      <label class="check-field">
        <input v-model="form.shortage_confirmed" data-testid="manual-event-shortage-confirmed" type="checkbox" />
        <span>已确认缺货</span>
      </label>

      <label class="check-field">
        <input v-model="form.confirmed_by_user" data-testid="manual-event-confirmed-by-user" type="checkbox" />
        <span>人工确认可信</span>
      </label>

      <button
        data-testid="manual-event-submit"
        class="submit-btn"
        type="button"
        :disabled="submitting || !form.title"
        @click="submit"
      >
        {{ submitting ? '提交中...' : '提交事件' }}
      </button>
    </div>

    <div v-if="lastResult" class="result-fallback">
      {{ resultTitle }}
      <span v-if="lastResult.confidence_reason || lastResult.reason">：{{ lastResult.confidence_reason || lastResult.reason }}</span>
    </div>
    <el-alert
      v-if="lastResult"
      class="result-alert"
      :title="resultTitle"
      :description="lastResult.confidence_reason || lastResult.reason || ''"
      :type="lastResult.status === 'ok' ? 'success' : 'warning'"
      :closable="false"
      show-icon
    />
  </el-card>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { addManualEvent } from '../api/events'

const props = defineProps({
  defaultItem: { type: Object, default: () => ({}) }
})

const emit = defineEmits(['submitted'])

const submitting = ref(false)
const lastResult = ref(null)

const form = reactive({
  title: '',
  brand: '',
  category: '',
  mpn: '',
  event_type: 'price_increase',
  increase_max_pct: null,
  lead_time_weeks: null,
  source_url: '',
  shortage_confirmed: true,
  confirmed_by_user: true
})

watch(
  () => props.defaultItem,
  (item) => {
    form.brand = item?.raw_brand || item?.normalized_brand || form.brand || ''
    form.category = item?.v32_category || item?.normalized_category || item?.raw_category || form.category || ''
    form.mpn = item?.raw_part_number || form.mpn || ''
    if (!form.title && (form.brand || form.category)) {
      form.title = `${form.brand || ''}${form.category || ''}涨价缺货通知`
    }
  },
  { immediate: true, deep: true }
)

const resultTitle = computed(() => {
  if (!lastResult.value) return ''
  return `后端处理：${lastResult.value.status || 'unknown'}，复核建议：${lastResult.value.review_recommendation || '未返回'}`
})

function cleanNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const num = Number(value)
  return Number.isFinite(num) ? num : null
}

async function submit() {
  if (!form.title) return
  submitting.value = true
  try {
    const payload = {
      title: form.title,
      brand: form.brand,
      category: form.category,
      mpn: form.mpn,
      event_type: form.event_type,
      increase_max_pct: cleanNumber(form.increase_max_pct),
      lead_time_weeks: cleanNumber(form.lead_time_weeks),
      source_url: form.source_url,
      shortage_confirmed: Boolean(form.shortage_confirmed),
      confirmed_by_user: Boolean(form.confirmed_by_user),
      source_type: 'manual'
    }
    const { data } = await addManualEvent(payload)
    lastResult.value = data
    emit('submitted', data)
    ElMessage.success('人工事件已提交，可重新分析BOM查看影响')
  } catch (err) {
    const message = err?.response?.data?.error || err?.message || '提交失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.manual-event-card {
  margin: 12px 0 16px;
  border-color: #f3d19e;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
  font-weight: 400;
}

.quick-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 150px;
  font-size: 12px;
  color: #606266;
}

.field.wide {
  width: 280px;
}

.field.narrow {
  width: 90px;
}

.native-input {
  height: 30px;
  box-sizing: border-box;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  padding: 0 8px;
  color: #303133;
  background: #fff;
}

.native-input:focus {
  border-color: #409eff;
  outline: none;
}

.check-field {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 30px;
  color: #606266;
  font-size: 13px;
}

.submit-btn {
  height: 30px;
  padding: 0 12px;
  border: 1px solid #409eff;
  border-radius: 4px;
  color: #fff;
  background: #409eff;
  cursor: pointer;
}

.submit-btn:disabled {
  border-color: #c0c4cc;
  background: #c0c4cc;
  cursor: not-allowed;
}

.result-fallback {
  margin-top: 12px;
  padding: 8px 10px;
  border-radius: 4px;
  background: #f0f9eb;
  color: #529b2e;
  font-size: 13px;
}

.result-alert {
  margin-top: 12px;
}
</style>
