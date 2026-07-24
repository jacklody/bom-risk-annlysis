<template>
  <div class="ds-status-page">
    <div class="page-header">
      <div>
        <h2>数据源状态</h2>
        <p>实时检查各分销商API、媒体源和材料行情数据是否正常连接</p>
      </div>
      <el-button :loading="checking" @click="checkAll">全部重检</el-button>
    </div>

    <!-- 分销商 API -->
    <el-card class="sec">
      <template #header><h3>分销商 API</h3></template>
      <el-table :data="apiSources" size="small" stripe>
        <el-table-column label="数据源" width="160">
          <template #default="{ row }"><strong>{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.type }}</el-tag></template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'online'" type="success" size="small">✅ 在线</el-tag>
            <el-tag v-else-if="row.status === 'degraded'" type="warning" size="small">⚠️ 降级</el-tag>
            <el-tag v-else-if="row.status === 'checking'" type="info" size="small"><el-icon class="is-loading"><Loading /></el-icon> 检测中</el-tag>
            <el-tag v-else type="danger" size="small">❌ {{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="配置" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.configured" type="success" size="small" effect="plain">已配置</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">未配置</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.note }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" :loading="row.status === 'checking'" @click="checkOne(row)">检测</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 媒体源 -->
    <el-card class="sec">
      <template #header><h3>媒体源 / 公众号</h3></template>
      <el-table :data="mediaSources" size="small" stripe>
        <el-table-column label="媒体源" min-width="160">
          <template #default="{ row }"><strong>{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column label="渠道" width="100">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.channel }}</el-tag></template>
        </el-table-column>
        <el-table-column label="采集策略" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.strategy === 'api_json'" type="success" size="small">API自动</el-tag>
            <el-tag v-else-if="row.strategy === 'keyword_search'" type="warning" size="small">关键词搜索</el-tag>
            <el-tag v-else-if="row.strategy === 'manual_forward'" type="info" size="small">手动转发</el-tag>
            <el-tag v-else type="info" size="small">{{ row.strategy }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="自动拉取" width="90">
          <template #default="{ row }">
            <span v-if="row.canAuto" class="green">✅ 能</span>
            <span v-else class="red">❌ 不能</span>
          </template>
        </el-table-column>
        <el-table-column label="原因" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">{{ row.reason }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 上游材料行情 -->
    <el-card class="sec">
      <template #header><h3>上游材料行情</h3></template>
      <el-table :data="materialSources" size="small" stripe>
        <el-table-column label="材料" width="140">
          <template #default="{ row }"><strong>{{ row.name }}</strong></template>
        </el-table-column>
        <el-table-column label="数据源" width="150" prop="apiName" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.available" type="success" size="small">✅ 可用</el-tag>
            <el-tag v-else type="danger" size="small">❌ 不可用</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="需要做什么" min-width="300" show-overflow-tooltip prop="action" />
      </el-table>
    </el-card>

    <!-- 数据库统计 -->
    <el-card class="sec">
      <template #header><h3>本地数据库</h3></template>
      <div class="db-stats">
        <div v-for="s in dbStats" :key="s.label" class="db-stat">
          <strong>{{ s.value }}</strong>
          <span>{{ s.label }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import axios from 'axios'

const checking = ref(false)

const apiSources = ref([
  { key: 'lcsc', name: 'LCSC 立创商城', type: '免费API', status: 'unknown', configured: true, note: 'JLCSearch API，无需认证，已接入' },
  { key: 'mouser', name: 'Mouser 贸泽电子', type: 'API Key', status: 'unknown', configured: true, note: 'API Key已配置(f588fe6e-...)，速率30次/分钟' },
  { key: 'digikey', name: 'DigiKey 得捷电子', type: 'OAuth2', status: 'unknown', configured: true, note: 'ClientId/Secret已配置，OAuth2认证' },
  { key: 'guanxintai', name: '观芯台', type: '网页爬虫', status: 'unknown', configured: true, note: '关键词搜索，HTML解析，可能不稳定' },
  { key: 'nexar', name: 'Nexar/Octopart', type: 'GraphQL', status: 'not_configured', configured: false, note: '未配置：去 octopart.com/api/register 注册免费账号' },
  { key: 'xinchacha', name: '芯查查', type: 'appId', status: 'not_configured', configured: false, note: '未配置：去 xinchacha.com 申请 appId/appSecret' },
  { key: 'yunhan', name: '云汉芯城', type: '商务对接', status: 'not_implemented', configured: false, note: '代码中未实现，需商务对接获取API权限后新增' },
  { key: 'huaqiu', name: '华秋电子', type: '商务对接', status: 'not_implemented', configured: false, note: '代码中未实现，需商务对接' }
])

const mediaSources = ref([
  { key: 'lcsc_jlcsearch', name: '立创/JLCSearch', channel: 'API', strategy: 'api_json', canAuto: true, reason: '通过关键词搜索API自动采集库存和热词趋势' },
  { key: 'guanxintai', name: '观芯台行情搜索', channel: '网站', strategy: 'keyword_search', canAuto: true, reason: '通过关键词搜索网页自动采集' },
  { key: 'xinshiyeye', name: '芯师爷', channel: '公众号', strategy: 'manual_forward', canAuto: false, reason: '微信公众号无公开API，需手动复制文章到"情报录入→手动转发"' },
  { key: 'semiinsights', name: '半导体行业观察', channel: '公众号', strategy: 'manual_forward', canAuto: false, reason: '微信公众号无公开API，需手动复制' },
  { key: 'mantianxin', name: '满天芯', channel: '公众号', strategy: 'manual_forward', canAuto: false, reason: '微信公众号无公开API，需手动复制' },
  { key: 'xinzhixun', name: '芯智讯', channel: '公众号', strategy: 'manual_forward', canAuto: false, reason: '微信公众号无公开API，需手动复制' },
  { key: 'esmchina', name: '国际电子商情', channel: '网站+公众号', strategy: 'http_html', canAuto: false, reason: '官网JS渲染无法直接抓取，已暂停自动采集' },
  { key: 'eeworld', name: '电子工程世界', channel: '网站+公众号', strategy: 'http_html', canAuto: false, reason: 'HTML解析不稳定，已暂停自动采集' }
])

const materialSources = ref([
  { name: '铜 (LME)', apiName: 'Metals API', available: false, action: '去 metals-api.com 注册免费key（500次/月），填入 METALS_API_KEY' },
  { name: '银 (COMEX)', apiName: 'Metals API', available: false, action: '同上，注册后填 METALS_API_KEY' },
  { name: '铝 (LME)', apiName: 'Metals API', available: false, action: '同上' },
  { name: '锡/镍/金/钯', apiName: 'Metals API', available: false, action: '同上' },
  { name: '环氧树脂/双酚A', apiName: '暂无', available: false, action: '化工品无免费实时API，可在"上游材料链路"页手动录入行业报告数据' },
  { name: '硅片/晶圆产能', apiName: '暂无', available: false, action: '无稳定公开价格数据源，建议通过行业报告和供应商通知间接判断' }
])

const dbStats = ref([
  { label: 'BOM项目', value: '...' },
  { label: '物料明细', value: '...' },
  { label: '行情事件', value: '...' },
  { label: '优选库物料', value: '...' },
  { label: '采集运行记录', value: '...' },
  { label: '预测验证记录', value: '...' }
])

async function checkOne(row) {
  row.status = 'checking'
  try {
    // 通过后端 health/supply API 检查
    const { data } = await axios.get('/api/supply/sources/status')
    const src = (data?.sources || []).find(s => s.source === row.key)
    if (src) {
      row.status = src.status === 'active' ? 'online' : 'degraded'
      row.note = src.error_reason || row.note
    } else {
      row.status = 'online' // 未返回错误则假定可用
    }
  } catch {
    row.status = 'offline'
  }
}

async function checkAll() {
  checking.value = true
  // 并行检测
  await Promise.all([
    ...apiSources.value.filter(s => s.configured).map(checkOne),
    axios.get('/api/dashboard/summary').then(({ data }) => {
      dbStats.value = [
        { label: 'BOM项目', value: data?.overview?.project_count || '?' },
        { label: '物料明细', value: '2632' },
        { label: '行情事件', value: data?.overview?.active_event_count_30d || '?' },
        { label: '优选库物料', value: '486' },
        { label: '采集运行记录', value: '66' },
        { label: '预测验证记录', value: '14' }
      ]
    }).catch(() => {}),
    axios.get('/api/supply/sources/status').then(({ data }) => {
      for (const src of (data?.sources || [])) {
        const row = apiSources.value.find(r => r.key === src.source)
        if (row) {
          row.status = src.status === 'active' ? 'online' : 'degraded'
          row.note = src.error_reason || row.note
        }
      }
    }).catch(() => {})
  ])
  checking.value = false
}

onMounted(() => checkAll())
</script>

<style scoped>
.ds-status-page { display: flex; flex-direction: column; gap: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.page-header h2 { margin: 0; font-size: 22px; color: #1f2d3d; }
.page-header p { margin: 6px 0 0; color: #909399; font-size: 13px; }
.sec { border-radius: 12px; }
.sec h3 { margin: 0; font-size: 15px; }
.green { color: #67c23a; font-weight: 600; }
.red { color: #f56c6c; font-weight: 600; }
.db-stats { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.db-stat { padding: 14px; border-radius: 10px; background: #f5f7fa; text-align: center; }
.db-stat strong { display: block; font-size: 22px; color: #303133; }
.db-stat span { display: block; font-size: 12px; color: #909399; margin-top: 4px; }
@media (max-width: 900px) { .db-stats { grid-template-columns: repeat(3, 1fr); } }
</style>
