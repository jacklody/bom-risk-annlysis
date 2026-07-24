<template>
  <div class="intel-center" data-testid="intel-center">
    <div class="page-header">
      <div>
        <h2>行情情报中心</h2>
        <p>管理市场行情事件、录入情报通知、监控采集源。所有行情信息最终汇聚到事件库，支撑上游材料链路和BOM风险分析。</p>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card" class="intel-tabs" @tab-change="onTabChange">
      <!-- ====== Tab 1: 行情事件库 ====== -->
      <el-tab-pane name="events">
        <template #label><span class="tl"><el-icon><Bell /></el-icon>行情事件库</span></template>

        <div class="filter-bar">
          <el-input v-model="ef.brand" clearable placeholder="品牌" size="small" style="width:120px" />
          <el-input v-model="ef.category" clearable placeholder="品类" size="small" style="width:140px" />
          <el-select v-model="ef.event_type" clearable placeholder="事件类型" size="small" style="width:110px">
            <el-option v-for="t in eventTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <el-select v-model="ef.severity" clearable placeholder="严重度" size="small" style="width:100px">
            <el-option v-for="s in severities" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
          <el-button type="primary" size="small" @click="loadEvents">查询</el-button>
          <el-button size="small" :loading="eventsLoading" @click="loadEvents">刷新</el-button>
          <el-button size="small" type="success" :loading="collecting" @click="doCollect">触发采集</el-button>
        </div>

        <el-empty v-if="!eventsLoading && !events.length" description="暂无行情事件" :image-size="40" />
        <el-table v-else :data="events" stripe size="small" v-loading="eventsLoading" @row-click="openEventDetail">
          <el-table-column prop="brand" label="品牌" width="80" />
          <el-table-column label="品类" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ dv(row.category) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="80">
            <template #default="{ row }"><el-tag size="small">{{ etLabel(row.event_type) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="严重度" width="70">
            <template #default="{ row }"><el-tag :type="sevTag(row.severity)" size="small">{{ sevLabel(row.severity) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="置信度" width="75">
            <template #default="{ row }">{{ fp(row.confidence) }}</template>
          </el-table-column>
          <el-table-column label="涨价" width="65">
            <template #default="{ row }">{{ fi(row.estimated_price_impact_pct, '%') }}</template>
          </el-table-column>
          <el-table-column label="交期" width="65">
            <template #default="{ row }">{{ fi(row.estimated_lead_time_impact_weeks, '周') }}</template>
          </el-table-column>
          <el-table-column prop="source_name" label="来源" min-width="100" show-overflow-tooltip />
          <el-table-column label="标题" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">{{ dv(row.raw_title) }}</template>
          </el-table-column>
          <el-table-column label="时间" width="140">
            <template #default="{ row }">{{ fd(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click.stop="openEventDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="table-foot"><span>共 {{ eventTotal }} 条</span></div>
      </el-tab-pane>

      <!-- ====== Tab 2: 情报录入 ====== -->
      <el-tab-pane name="intake">
        <template #label>
          <span class="tl">
            <el-icon><EditPen /></el-icon>情报录入
            <el-badge v-if="pendingCount" :value="pendingCount" class="badge" />
          </span>
        </template>

        <el-card class="sec-card">
          <template #header><div class="sec-title"><span>提交行情通知</span><el-tag type="success" size="small">自动识别 & 扫描历史BOM</el-tag></div></template>
          <el-alert title="粘贴邮件涨价函、微信消息、公众号文章、官网公告即可" description="系统自动抽取品牌、品类、型号、涨幅、交期信息。高置信度信号自动生成事件。" type="info" show-icon :closable="false" />
          <div class="intake-form">
            <div class="form-row-3">
              <label class="fi"><span>标题</span><input v-model="nf.title" class="ni" placeholder="例：TDK高容MLCC缺货涨价通知" /></label>
              <label class="fi"><span>来源类型</span><select v-model="nf.source_type" class="ni"><option value="email">邮件</option><option value="wechat">微信</option><option value="wechat_mp">公众号</option><option value="website">官网</option><option value="supplier_notice">供应商通知</option><option value="manual">手动粘贴</option></select></label>
              <label class="fi"><span>来源名称</span><input v-model="nf.source_name" class="ni" placeholder="例：TDK代理商邮件" /></label>
            </div>
            <label class="fi block"><span>原文内容</span><textarea v-model="nf.raw_text" class="nt" rows="4" placeholder="直接粘贴涨价函、微信消息或通知原文..." /></label>
            <div class="form-acts">
              <el-button type="primary" :loading="submitting" :disabled="!nf.raw_text.trim()" @click="doSubmit">一键识别并扫描历史BOM</el-button>
              <span class="hint">保存原文，抽取信号，高置信度自动生成市场事件。</span>
            </div>
          </div>

          <div v-if="intakeResult" class="intake-result">
            <h4>识别结果</h4>
            <div class="result-stats">
              <div class="rs"><strong>{{ intakeResult.events_created }}</strong>生成事件</div>
              <div class="rs"><strong>{{ intakeResult.events_skipped }}</strong>跳过/观察</div>
              <div class="rs"><strong>{{ intakeResult.scan_summary?.projects_scanned || 0 }}</strong>扫描项目</div>
              <div class="rs"><strong>{{ intakeResult.scan_summary?.affected_projects || 0 }}</strong>受影响项目</div>
            </div>
            <el-table v-if="intakeResult.signals?.length" :data="intakeResult.signals" size="small" stripe>
              <el-table-column prop="brand" label="品牌" width="80" />
              <el-table-column prop="category" label="品类" width="140" />
              <el-table-column prop="mpn" label="型号" min-width="150" />
              <el-table-column prop="increase_max_pct" label="涨价%" width="80" />
              <el-table-column prop="confidence" label="置信度" width="80" />
              <el-table-column prop="review_status" label="状态" width="100" />
            </el-table>
          </div>
        </el-card>

        <el-card class="sec-card">
          <template #header><div class="sec-title"><span>待复核队列</span><el-button size="small" @click="loadReviews">刷新</el-button></div></template>
          <div v-if="revSummary" class="rev-stats">
            <el-tag type="warning">待复核 {{ revSummary.need_review || 0 }}</el-tag>
            <el-tag type="info">观察 {{ revSummary.observation || 0 }}</el-tag>
            <el-tag type="success">已确认 {{ revSummary.confirmed || 0 }}</el-tag>
            <el-tag type="danger">已驳回 {{ revSummary.rejected || 0 }}</el-tag>
          </div>
          <el-empty v-if="!revQueue.length" description="暂无待复核信号" :image-size="40" />
          <el-table v-else :data="revQueue" size="small" stripe>
            <el-table-column prop="brand" label="品牌" width="80" />
            <el-table-column prop="category" label="品类" width="130" />
            <el-table-column prop="mpn" label="型号" min-width="130" />
            <el-table-column prop="event_type" label="类型" width="70" />
            <el-table-column prop="confidence" label="置信度" width="70" />
            <el-table-column label="原文" min-width="160">
              <template #default="{ row }"><span class="ref">{{ row.raw_notice_title || '未命名' }}</span></template>
            </el-table-column>
            <el-table-column label="操作" width="260">
              <template #default="{ row }">
                <el-button size="small" @click="showTrace(row)">溯源</el-button>
                <el-button size="small" type="success" :loading="reviewingId === row.id" @click="doReview(row, 'confirm')">确认</el-button>
                <el-button size="small" type="danger" :loading="reviewingId === row.id" @click="doReview(row, 'reject')">驳回</el-button>
                <el-button size="small" @click="doReview(row, 'observe')">观察</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- ====== Tab 3: 采集监控 ====== -->
      <el-tab-pane name="monitor">
        <template #label><span class="tl"><el-icon><Monitor /></el-icon>采集监控</span></template>

        <div class="monitor-grid">
          <el-card class="sec-card">
            <template #header><div class="sec-title"><span>关注指令</span></div></template>
            <div class="watch-row">
              <el-input v-model="watchInput" placeholder="例：关注 STM32 全系列交期 / 监控高容MLCC价格" size="small" maxlength="500" @keyup.enter="doWatch" />
              <el-button type="primary" size="small" :loading="watchSub" :disabled="!watchInput.trim()" @click="doWatch">提交</el-button>
            </div>
            <div class="quick-row">
              <el-tag v-for="tag in ['关注 STM32 全系列交期','监控 高容MLCC 价格','排查 长晶 分立器件库存']" :key="tag" size="small" effect="plain" class="qt" @click="watchInput = tag">{{ tag }}</el-tag>
            </div>
            <el-table v-if="watchList.length" :data="watchList" size="small" stripe max-height="220" class="mt">
              <el-table-column prop="raw_input" label="指令" min-width="200" show-overflow-tooltip />
              <el-table-column label="状态" width="70"><template #default="{ row }"><el-tag size="small" :type="row.status==='done'?'success':'warning'">{{ row.status==='done'?'完成':'调研中' }}</el-tag></template></el-table-column>
              <el-table-column prop="research_summary" label="结论" min-width="160" show-overflow-tooltip />
              <el-table-column label="时间" width="130"><template #default="{ row }">{{ fd(row.created_at) }}</template></el-table-column>
            </el-table>
          </el-card>

          <el-card class="sec-card">
            <template #header><div class="sec-title"><span>媒体源状态</span><div class="sec-acts"><el-button size="small" @click="loadSources">刷新</el-button><el-button size="small" type="success" :loading="collAll" @click="doCollectAll">全量采集</el-button></div></div></template>
            <el-empty v-if="!sources.length" description="暂无媒体源" :image-size="40" />
            <el-table v-else :data="sources" size="small" stripe max-height="260">
              <el-table-column label="渠道" min-width="140"><template #default="{ row }"><strong>{{ row.name }}</strong><br><span class="dim">{{ row.source_id }}</span></template></el-table-column>
              <el-table-column label="类型" width="100"><template #default="{ row }"><el-tag size="small" effect="plain">{{ row.channel_type }}</el-tag></template></el-table-column>
              <el-table-column label="状态" width="90"><template #default="{ row }"><el-tag size="small" :type="row.enabled?'success':'info'">{{ row.enabled?'可采集':'暂停' }}</el-tag></template></el-table-column>
              <el-table-column label="说明" min-width="180" show-overflow-tooltip prop="notes" />
              <el-table-column label="操作" width="80"><template #default="{ row }"><el-button v-if="row.enabled" size="small" type="primary" link :loading="collId===row.source_id" @click="doCollectOne(row)">采集</el-button><span v-else class="dim">暂停</span></template></el-table-column>
            </el-table>
          </el-card>
        </div>

        <el-card class="sec-card" style="margin-top:14px">
          <template #header><div class="sec-title"><span>手动转发文章</span></div></template>
          <div class="fwd-form">
            <div class="fwd-row">
              <select v-model="fwdSid" class="ni" style="min-width:150px"><option value="">选择媒体源</option><option v-for="s in sources" :key="s.source_id" :value="s.source_id">{{ s.name }}</option></select>
              <input v-model="fwdTitle" class="ni" style="flex:1" placeholder="文章标题（选填）" />
            </div>
            <textarea v-model="fwdText" class="nt" rows="3" placeholder="粘贴文章全文..." />
            <el-button type="primary" size="small" :disabled="!fwdSid||!fwdText.trim()" :loading="fwdSub" @click="doFwd">提交解析</el-button>
          </div>
        </el-card>

        <el-card class="sec-card" style="margin-top:14px">
          <template #header><div class="sec-title"><span>采集运行记录</span><el-button size="small" @click="loadRuns">刷新</el-button></div></template>
          <el-empty v-if="!runs.length" description="暂无运行记录" :image-size="40" />
          <el-table v-else :data="runs" size="small" stripe max-height="200">
            <el-table-column prop="source_id" label="源" width="130" show-overflow-tooltip />
            <el-table-column label="状态" width="70"><template #default="{ row }"><el-tag size="small" :type="row.status==='success'?'success':'danger'">{{ row.status }}</el-tag></template></el-table-column>
            <el-table-column label="文章/信号/事件" width="120"><template #default="{ row }">{{ row.articles_crawled }}/{{ row.signals_parsed }}/{{ row.events_created }}</template></el-table-column>
            <el-table-column label="详情" min-width="140" show-overflow-tooltip><template #default="{ row }">{{ row.error_message||'成功' }}</template></el-table-column>
            <el-table-column label="时间" width="140"><template #default="{ row }">{{ fd(row.completed_at) }}</template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 抽屉 -->
    <el-drawer v-model="traceVis" title="信号溯源" size="440px">
      <div v-if="traced" class="trace-body">
        <h4>信号 #{{ traced.id }}</h4>
        <p><span>品牌：</span>{{ dv(traced.brand) }}</p><p><span>品类：</span>{{ dv(traced.category) }}</p>
        <p><span>型号：</span>{{ dv(traced.mpn) }}</p><p><span>类型：</span>{{ dv(traced.event_type) }}</p>
        <p><span>置信度：</span>{{ traced.confidence ?? '暂无' }}</p><p><span>状态：</span>{{ dv(traced.review_status) }}</p>
        <h4>原始通知</h4>
        <p><span>标题：</span>{{ dv(traced.raw_notice_title) }}</p>
        <p><span>来源：</span>{{ dv(traced.raw_notice_source_type) }} / {{ dv(traced.raw_notice_source_name) }}</p>
        <p class="ex">{{ dv(traced.raw_notice_excerpt) }}</p>
        <el-button v-if="traced.generated_event_id" type="primary" @click="openGen(traced)">查看市场事件</el-button>
      </div>
    </el-drawer>

    <MarketEventDetailDrawer v-model="detailVis" :event="selEvent" :impact="evImpact" :source-signal="srcSignal" :operating-status="false" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, EditPen, Monitor } from '@element-plus/icons-vue'
import MarketEventDetailDrawer from '../components/MarketEventDetailDrawer.vue'
import { useMarketEventDetail } from '../composables/useMarketEventDetail'
import { listEvents, collectEvents, updateEventStatus, listMediaSources, listMediaSourceRuns, collectMediaSource, forwardArticle } from '../api/events'
import { submitMarketNotice, listReviewQueue, reviewSignal } from '../api/marketInbox'
import { submitWatch, getWatchHistory } from '../api/intelWatch'

const route = useRoute(); const router = useRouter()
const activeTab = ref('events')

// ── 事件库 ──
const eventsLoading = ref(false); const collecting = ref(false); const events = ref([]); const eventTotal = ref(0)
const ef = reactive({ brand: '', category: '', event_type: '', severity: '' })
const eventTypes = [{ label: '缺货', value: 'shortage' }, { label: '涨价', value: 'price_increase' }, { label: '产能问题', value: 'capacity_issue' }, { label: '交期延长', value: 'lead_time' }, { label: '停产', value: 'eol' }, { label: '政策', value: 'policy' }, { label: '灾害', value: 'disaster' }, { label: '其他', value: 'other' }]
const severities = [{ label: '严重', value: 'critical' }, { label: '高', value: 'high' }, { label: '中', value: 'medium' }, { label: '低', value: 'low' }]
const { detailVisible: detailVis, selectedEvent: selEvent, eventImpact: evImpact, sourceSignal: srcSignal, openEventDetail } = useMarketEventDetail()

async function loadEvents() {
  eventsLoading.value = true
  try {
    const p = { active_status: 'active', limit: 100 }
    if (ef.brand) p.brand = ef.brand; if (ef.category) p.category = ef.category; if (ef.event_type) p.event_type = ef.event_type; if (ef.severity) p.severity = ef.severity
    const { data } = await listEvents(p)
    events.value = data.events || []; eventTotal.value = data.total || 0
    if (route.query?.eventId) await openEventDetail(route.query.eventId)
  } catch (e) { ElMessage.error(e?.response?.data?.detail || '加载失败') } finally { eventsLoading.value = false }
}
async function doCollect() { collecting.value = true; try { const { data } = await collectEvents(); ElMessage.success(`采集完成，新增 ${data.collected||0} 条`); loadEvents() } catch(e){ ElMessage.error('采集失败') } finally { collecting.value = false } }

// ── 情报录入 ──
const submitting = ref(false); const intakeResult = ref(null); const revQueue = ref([]); const revSummary = ref(null); const traced = ref(null); const traceVis = ref(false); const reviewingId = ref(null)
const nf = reactive({ title: '', raw_text: '', source_type: 'email', source_name: '', auto_scan: true })
const pendingCount = computed(() => revSummary.value?.need_review || null)

async function doSubmit() {
  if (!nf.raw_text.trim()) { ElMessage.warning('请先粘贴行情通知原文'); return }
  submitting.value = true
  try { const { data } = await submitMarketNotice({ ...nf, auto_scan: true }); intakeResult.value = data; ElMessage.success('已识别并扫描历史BOM'); loadReviews() } catch(e) { ElMessage.error(e?.response?.data?.detail || '识别失败') } finally { submitting.value = false }
}
async function loadReviews() { try { const { data } = await listReviewQueue(); revQueue.value = data.signals||[]; revSummary.value = data.summary||null } catch { revQueue.value=[]; revSummary.value=null } }
function showTrace(s) { traced.value = s; traceVis.value = true }
function openGen(s) { if (s.generated_event_id) { activeTab.value = 'events'; openEventDetail(s.generated_event_id) } }
async function doReview(s, action) {
  reviewingId.value = s.id
  try { await reviewSignal(s.id, { action, notes: '从情报中心复核', reviewer: '采购复核' }); ElMessage.success(action==='confirm'?'已确认并生成事件':action==='reject'?'已驳回':'已标记为观察'); loadReviews(); if(action==='confirm') activeTab.value='events' } catch(e) { ElMessage.error('复核失败') } finally { reviewingId.value=null }
}

// ── 采集监控 ──
const watchInput = ref(''); const watchSub = ref(false); const watchList = ref([]); const sources = ref([]); const runs = ref([])
const collId = ref(''); const collAll = ref(false); const fwdSid = ref(''); const fwdTitle = ref(''); const fwdText = ref(''); const fwdSub = ref(false)

async function doWatch() { if(!watchInput.value.trim())return; watchSub.value=true; try{await submitWatch(watchInput.value.trim());ElMessage.success('已提交');watchInput.value='';loadWatches()}catch(e){ElMessage.error('提交失败')}finally{watchSub.value=false} }
async function loadWatches() { try{const{data}=await getWatchHistory();watchList.value=data.commands||[]}catch{watchList.value=[]} }
async function loadSources() { try{const{data}=await listMediaSources();sources.value=data.sources||[]}catch{sources.value=[]} }
async function loadRuns() { try{const{data}=await listMediaSourceRuns({limit:20});runs.value=data.runs||[]}catch{runs.value=[]} }
async function doCollectOne(row) { collId.value=row.source_id; try{const{data}=await collectMediaSource(row.source_id);ElMessage.success(`采集完成: ${row.name}`);loadRuns()}catch{ElMessage.error('采集失败')}finally{collId.value=''} }
async function doCollectAll() { collAll.value=true; try{await collectMediaSource();ElMessage.success('全量采集完成');loadRuns()}catch{ElMessage.error('采集失败')}finally{collAll.value=false} }
async function doFwd() { fwdSub.value=true; try{const{data}=await forwardArticle({source_id:fwdSid.value,title:fwdTitle.value,text:fwdText.value});ElMessage.success(`解析完成: 信号${data.signals_parsed} 事件${data.events_created}`);fwdText.value='';loadRuns()}catch{ElMessage.error('解析失败')}finally{fwdSub.value=false} }

// ── utils ──
function dv(v){return v===null||v===undefined||v===''?'暂无':v}
function fp(v){if(v==null)return'暂无';const n=Number(v);return n<=1?`${Math.round(n*100)}%`:`${Math.round(n)}%`}
function fi(v,u){if(v==null||v==='')return'暂无';return u==='%'?`${v}${u}`:`${v} ${u}`}
function fd(v){if(!v)return'暂无';const d=new Date(v);return Number.isNaN(d.getTime())?v:d.toLocaleString('zh-CN',{hour12:false})}
function etLabel(t){const m={shortage:'缺货',price_increase:'涨价',capacity_issue:'产能',lead_time:'交期',eol:'停产',policy:'政策',disaster:'灾害',other:'其他'};return m[t]||dv(t)}
function sevLabel(s){const m={critical:'严重',high:'高',medium:'中',low:'低',unknown:'未知'};return m[s]||dv(s)}
function sevTag(s){return s==='critical'||s==='high'?'danger':s==='medium'?'warning':'info'}

function onTabChange(t) { if(t==='events')loadEvents(); else if(t==='monitor'){loadSources();loadRuns();loadWatches()} }
watch(()=>route.query?.tab, t=>{if(t)activeTab.value=t},{immediate:true})
onMounted(()=>{ loadReviews(); if(activeTab.value==='events')loadEvents() })
</script>

<style scoped>
.intel-center{display:flex;flex-direction:column;gap:16px}
.page-header h2{margin:0;font-size:22px;color:#1f2d3d}
.page-header p{margin:6px 0 0;color:#909399;font-size:13px;max-width:700px}
.intel-tabs{border-radius:12px;overflow:hidden}
.tl{display:inline-flex;align-items:center;gap:6px}
.badge{margin-left:4px}
.sec-card{border-radius:10px;margin-bottom:14px}
.sec-card:last-child{margin-bottom:0}
.sec-title{display:flex;justify-content:space-between;align-items:center;gap:12px;font-weight:600}
.sec-acts{display:flex;gap:8px}

.filter-bar{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
.table-foot{margin-top:12px;font-size:13px;color:#909399}

.intake-form{display:flex;flex-direction:column;gap:12px;margin-top:14px}
.form-row-3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.fi{display:flex;flex-direction:column;gap:4px;font-size:13px;color:#606266}
.fi.block{grid-column:1/-1}
.form-acts{display:flex;align-items:center;gap:12px}
.hint{font-size:12px;color:#909399}
.ni,.nt{border:1px solid #dcdfe6;border-radius:6px;padding:8px 11px;font-size:14px;color:#303133;background:#fff;font-family:inherit}
.nt{resize:vertical;line-height:1.5}

.intake-result{margin-top:16px}
.intake-result h4{margin:12px 0 8px;font-size:14px}
.result-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.rs{padding:10px;border-radius:8px;background:#f5f7fa;text-align:center;font-size:13px;color:#606266}
.rs strong{display:block;font-size:20px;color:#303133}

.rev-stats{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.ref{font-size:12px;color:#909399}

.monitor-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.watch-row{display:flex;gap:8px;margin-bottom:8px}
.watch-row .el-input{flex:1}
.quick-row{display:flex;gap:6px;flex-wrap:wrap}
.qt{cursor:pointer}
.mt{margin-top:10px}
.dim{font-size:11px;color:#c0c4cc}
.fwd-form{display:flex;flex-direction:column;gap:10px}
.fwd-row{display:flex;gap:10px}
.trace-body p{margin:6px 0;font-size:14px;color:#303133}
.trace-body p span{color:#909399}
.trace-body .ex{padding:8px;background:#f5f7fa;border-radius:6px;font-size:13px;line-height:1.5}
@media(max-width:1200px){.form-row-3,.monitor-grid{grid-template-columns:1fr}}
</style>
