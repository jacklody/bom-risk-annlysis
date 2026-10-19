<template>
  <div class="market-inbox" data-testid="market-inbox-page">
    <el-card class="inbox-card">
      <template #header>
        <div class="header-row">
          <div>
            <h2>行情情报收件箱</h2>
            <p>粘贴邮件涨价函、微信消息、公众号或官网通知原文，系统自动识别、入库并扫描历史 BOM。</p>
          </div>
        </div>
      </template>

      <el-alert
        title="你不需要整理结构化字段"
        description="保留原始通知，自动抽取品牌、品类、型号、涨价、交期、缺货和置信度；低置信度消息进入复核/观察。"
        type="info"
        show-icon
        :closable="false"
      />

      <div class="form-grid">
        <label class="field">
          <span>标题</span>
          <input v-model="form.title" data-testid="market-notice-title" class="native-input" placeholder="例如：TDK高容MLCC缺货涨价通知" />
        </label>
        <label class="field">
          <span>来源类型</span>
          <select v-model="form.source_type" data-testid="market-notice-source-type" class="native-input">
            <option value="email">邮件</option>
            <option value="wechat">微信</option>
            <option value="wechat_mp">公众号</option>
            <option value="website">官网</option>
            <option value="supplier_notice">供应商通知</option>
            <option value="manual">手动粘贴</option>
          </select>
        </label>
        <label class="field">
          <span>来源名称</span>
          <input v-model="form.source_name" data-testid="market-notice-source-name" class="native-input" placeholder="例如：TDK代理商邮件 / 微信群 / 官网" />
        </label>
        <label class="field wide">
          <span>原文</span>
          <textarea
            v-model="form.raw_text"
            data-testid="market-notice-raw-text"
            class="native-textarea"
            rows="8"
            placeholder="直接粘贴涨价函、微信消息、公众号或官网通知原文"
          />
        </label>
      </div>

      <div class="action-row">
        <el-button data-testid="market-notice-submit" type="primary" :loading="submitting" @click="submit">
          一键识别并扫描历史 BOM
        </el-button>
        <span class="hint">系统会保存原文，方便后续追溯和重新解析。</span>
      </div>
    </el-card>

    <el-card v-if="result" class="result-card" data-testid="market-inbox-result">
      <template #header>
        <div class="header-row">
          <h3>识别结果</h3>
          <el-tag :type="result.notice?.parse_status === 'parsed' ? 'success' : 'warning'">
            {{ result.notice?.parse_status }}
          </el-tag>
        </div>
      </template>

      <div class="summary-grid">
        <div>生成事件 <strong>{{ result.events_created }}</strong> 条</div>
        <div>跳过/观察 <strong>{{ result.events_skipped }}</strong> 条</div>
        <div>扫描项目 <strong>{{ result.scan_summary?.projects_scanned || 0 }}</strong> 个</div>
        <div>受影响项目 <strong>{{ result.scan_summary?.affected_projects || 0 }}</strong> 个</div>
      </div>

      <h4>抽取信号</h4>
      <el-table :data="result.signals || []" stripe style="width: 100%">
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="category" label="品类" width="160" />
        <el-table-column prop="mpn" label="型号" min-width="180" />
        <el-table-column prop="increase_max_pct" label="涨价%" width="90" />
        <el-table-column prop="lead_time_weeks" label="交期周" width="90" />
        <el-table-column prop="confidence" label="置信度" width="90" />
        <el-table-column prop="review_status" label="状态" width="130" />
      </el-table>

      <h4>受影响物料</h4>
      <div v-if="!result.scan_summary?.top_impacted_items?.length" class="empty-tip">暂无命中历史 BOM。</div>
      <el-table v-else :data="result.scan_summary.top_impacted_items" stripe style="width: 100%">
        <el-table-column prop="project_name" label="项目" min-width="160" />
        <el-table-column prop="brand" label="品牌" width="100" />
        <el-table-column prop="mpn" label="型号" min-width="180" />
        <el-table-column prop="risk_level" label="风险" width="90" />
        <el-table-column prop="reason" label="原因" min-width="260" />
      </el-table>
    </el-card>

    <el-card class="result-card">
      <template #header>
        <div class="header-row">
          <h3>待复核队列</h3>
          <el-button size="small" data-testid="review-queue-refresh" @click="loadReviewQueue">刷新</el-button>
        </div>
      </template>
      <div v-if="reviewSummary" class="review-summary">
        <el-tag type="warning">待处理 {{ reviewSummary.queue_total || 0 }}</el-tag>
        <el-tag type="warning">待复核 {{ reviewSummary.need_review || 0 }}</el-tag>
        <el-tag type="info">观察中 {{ reviewSummary.observation || 0 }}</el-tag>
        <el-tag type="success">已确认 {{ reviewSummary.confirmed || 0 }}</el-tag>
        <el-tag type="danger">已驳回 {{ reviewSummary.rejected || 0 }}</el-tag>
      </div>
      <div class="review-audit-form">
        <label class="field">
          <span>复核人</span>
          <input v-model="reviewForm.reviewer" data-testid="reviewer-input" class="native-input" placeholder="例如：采购张三" />
        </label>
        <label class="field wide">
          <span>复核备注</span>
          <textarea v-model="reviewForm.notes" data-testid="review-notes-input" class="native-textarea" rows="3" placeholder="记录供应商确认、原厂通知或驳回原因" />
        </label>
      </div>
      <div v-if="!reviewQueue.length" class="empty-tip">暂无待复核信号。</div>
      <el-table v-else :data="reviewQueue" stripe style="width: 100%">
        <el-table-column prop="brand" label="品牌" width="80" />
        <el-table-column prop="category" label="品类" width="140" />
        <el-table-column prop="mpn" label="型号" min-width="160" />
        <el-table-column prop="event_type" label="事件类型" width="90" />
        <el-table-column prop="confidence" label="置信度" width="80" />
        <el-table-column prop="review_status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.review_status === 'need_review' ? 'warning' : 'info'">
              {{ scope.row.review_status === 'need_review' ? '待复核' : scope.row.review_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原文依据" min-width="260">
          <template #default="scope">
            <div class="notice-context">
              <strong>{{ scope.row.raw_notice_title || '未命名通知' }}</strong>
              <span>{{ scope.row.raw_notice_source_type || '未知来源' }} / {{ scope.row.raw_notice_source_name || '未填写来源' }}</span>
              <p>{{ scope.row.raw_notice_excerpt }}</p>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="scope">
            <el-button size="small" data-testid="open-signal-trace" @click="openSignalTrace(scope.row)">查看溯源</el-button>
            <el-button size="small" type="success" data-testid="review-confirm" :loading="reviewingId === scope.row.id" @click="doReview(scope.row, 'confirm')">确认生成事件</el-button>
            <el-button size="small" type="danger" data-testid="review-reject" :loading="reviewingId === scope.row.id" @click="doReview(scope.row, 'reject')">驳回</el-button>
            <el-button size="small" data-testid="review-observe" @click="doReview(scope.row, 'observe')">观察</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="traceVisible" title="信号溯源详情" size="520px">
      <div v-if="selectedSignal" class="trace-detail">
        <h3>信号 #{{ selectedSignal.id }}</h3>
        <p>品牌：{{ selectedSignal.brand || '暂无' }}</p>
        <p>品类：{{ selectedSignal.category || '暂无' }}</p>
        <p>型号：{{ selectedSignal.mpn || '暂无' }}</p>
        <p>事件类型：{{ selectedSignal.event_type || '暂无' }}</p>
        <p>置信度：{{ selectedSignal.confidence ?? '暂无' }}</p>
        <p>复核状态：{{ selectedSignal.review_status || '暂无' }}</p>
        <h4>原始通知</h4>
        <p>原始通知：{{ selectedSignal.raw_notice_title || '未命名通知' }}</p>
        <p>来源：{{ selectedSignal.raw_notice_source_type || '未知来源' }} / {{ selectedSignal.raw_notice_source_name || '未填写来源' }}</p>
        <p>{{ selectedSignal.raw_notice_excerpt || '暂无原文摘要' }}</p>
        <el-button
          v-if="selectedSignal.generated_event_id"
          type="primary"
          data-testid="open-generated-event"
          @click="openGeneratedEvent(selectedSignal)"
        >
          查看市场事件
        </el-button>
        <el-button
          v-if="selectedSignal.generated_event_id"
          data-testid="go-generated-event"
          @click="goGeneratedEvent(selectedSignal)"
        >
          前往事件库
        </el-button>
      </div>
    </el-drawer>

    <MarketEventDetailDrawer
      v-model="detailVisible"
      :event="selectedEvent"
      :impact="eventImpact"
      :source-signal="sourceSignal"
      :operating-status="false"
    />
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { submitMarketNotice, listReviewQueue, reviewSignal } from '../api/marketInbox'
import MarketEventDetailDrawer from '../components/MarketEventDetailDrawer.vue'
import { useMarketEventDetail } from '../composables/useMarketEventDetail'

const router = useRouter()
const submitting = ref(false)
const result = ref(null)
const reviewQueue = ref([])
const reviewSummary = ref(null)
const selectedSignal = ref(null)
const traceVisible = ref(false)
const reviewForm = reactive({ reviewer: '采购复核', notes: '' })
const reviewingId = ref(null)
const {
  detailVisible,
  selectedEvent,
  eventImpact,
  sourceSignal,
  openEventDetail
} = useMarketEventDetail()
const form = reactive({
  title: '',
  raw_text: '',
  source_type: 'email',
  source_name: '',
  source_url: '',
  sender: '',
  auto_scan: true
})

async function submit() {
  if (!form.raw_text.trim()) {
    ElMessage.warning('请先粘贴行情通知原文')
    return
  }
  submitting.value = true
  try {
    const { data } = await submitMarketNotice({ ...form, auto_scan: true })
    result.value = data
    ElMessage.success('行情通知已识别并完成历史 BOM 扫描')
    loadReviewQueue()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '行情通知识别失败')
  } finally {
    submitting.value = false
  }
}

async function loadReviewQueue() {
  try {
    const { data } = await listReviewQueue()
    reviewQueue.value = data.signals || []
    reviewSummary.value = data.summary || null
  } catch {
    reviewQueue.value = []
    reviewSummary.value = null
  }
}

function openSignalTrace(signal) {
  selectedSignal.value = signal
  traceVisible.value = true
}

function openGeneratedEvent(signal) {
  if (signal.generated_event_id) openEventDetail(signal.generated_event_id)
}

function goGeneratedEvent(signal) {
  router.push({ path: '/events', query: { eventId: signal.generated_event_id } })
}

async function doReview(signal, action) {
  reviewingId.value = signal.id
  try {
    await reviewSignal(signal.id, {
      action,
      notes: reviewForm.notes.trim(),
      reviewer: reviewForm.reviewer.trim() || '采购复核'
    })
    if (action === 'confirm') {
      ElMessage.success(`已确认信号 #${signal.id} 并生成市场事件`)
    } else if (action === 'reject') {
      ElMessage.info(`已驳回信号 #${signal.id}`)
    } else {
      ElMessage.info(`信号 #${signal.id} 已标记为观察`)
    }
    loadReviewQueue()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '复核操作失败')
  } finally {
    reviewingId.value = null
  }
}

onMounted(loadReviewQueue)
</script>

<style scoped>
.market-inbox {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.inbox-card,
.result-card {
  border-radius: 12px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.header-row h2,
.header-row h3 {
  margin: 0;
}

.header-row p {
  margin: 6px 0 0;
  color: #606266;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(180px, 1fr));
  gap: 14px;
  margin-top: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #606266;
  font-size: 13px;
}

.field.wide {
  grid-column: 1 / -1;
}

.native-input,
.native-textarea {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  padding: 9px 11px;
  font-size: 14px;
  color: #303133;
  background: #fff;
}

.native-textarea {
  resize: vertical;
  line-height: 1.5;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}

.hint,
.empty-tip {
  color: #909399;
  font-size: 13px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-grid > div {
  padding: 12px;
  border-radius: 8px;
  background: #f5f7fa;
  color: #606266;
}

h4 {
  margin: 16px 0 8px;
}
</style>
