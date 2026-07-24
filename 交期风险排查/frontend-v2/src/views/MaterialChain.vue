<template>
  <div class="material-chain-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>上游材料链路</h2>
        <p>追踪从原材料 → 二级组份 → 器件品类 → BOM物料的风险传导路径。数据来自后端品类知识库和实时BOM统计。</p>
      </div>
      <div class="header-actions">
        <el-select v-model="viewMode" size="small" style="width:140px">
          <el-option label="按品类查看" value="category" />
          <el-option label="按材料查看" value="material" />
          <el-option label="按BOM项目查看" value="project" />
        </el-select>
        <el-button size="small" @click="loadData">刷新</el-button>
      </div>
    </div>

    <!-- ====== 视图1：按品类 ====== -->
    <template v-if="viewMode === 'category'">
      <div class="category-overview">
        <div v-for="cat in categories" :key="cat.key" class="category-card" :class="{ selected: selectedCategory === cat.key, [cat.riskLevel]: true }" @click="selectedCategory = cat.key">
          <div class="cat-header"><strong>{{ cat.name }}</strong><el-tag :type="riskTagType(cat.riskLevel)" size="small">{{ riskLabel(cat.riskLevel) }}</el-tag></div>
          <div class="cat-stats"><span>物料 {{ cat.itemCount }}</span><span>项目 {{ cat.projectCount }}</span></div>
          <div class="cat-driver"><el-tag size="small" effect="plain">{{ cat.driverType }}</el-tag></div>
        </div>
      </div>

      <div v-if="activeCategory" class="chain-detail">
        <el-card class="chain-card">
          <template #header>
            <div class="chain-header">
              <h3>{{ activeCategory.name }} · 风险传导链路</h3>
              <div class="chain-meta">
                <el-tag size="small" effect="plain">{{ activeCategory.driverType }}</el-tag>
                <el-tag v-if="activeCategory.reliability" size="small">{{ activeCategory.reliability }}</el-tag>
                <el-tag v-if="activeCategory.lag" size="small">滞后：{{ activeCategory.lag }}</el-tag>
                <el-tag v-if="activeCategory.passThrough" size="small">转嫁率：{{ activeCategory.passThrough }}</el-tag>
              </div>
            </div>
          </template>

          <div class="chain-flow">
            <!-- L1: 原材料 -->
            <div class="chain-layer"><div class="layer-title"><el-icon><Box /></el-icon><span>原材料</span></div>
              <div class="layer-nodes"><div v-for="(n,i) in activeCategory.rawMaterials" :key="'rm-'+i" class="chain-node raw-material" :class="{alert:n.alert}"><div class="node-name">{{ n.name }}</div><div class="node-source" v-if="n.source">{{ n.source }}</div><el-tag size="small" type="info" effect="plain">{{ n.dataLevel }}级</el-tag></div></div>
            </div>
            <div class="chain-arrows"><span class="arrow-text">材料传导</span><div class="arrow-line"></div></div>
            <!-- L2: 二级组份 -->
            <div class="chain-layer"><div class="layer-title"><el-icon><Connection /></el-icon><span>二级组份</span></div>
              <div class="layer-nodes"><div v-for="(n,i) in activeCategory.midComponents" :key="'mc-'+i" class="chain-node mid-component"><div class="node-name">{{ n.name }}</div><div class="node-from" v-if="n.from">← {{ n.from }}</div><div class="node-cost" v-if="n.costShare">成本 {{ n.costShare }}</div></div></div>
            </div>
            <div class="chain-arrows"><span class="arrow-text">工艺</span><div class="arrow-line"></div></div>
            <!-- L3: 器件 -->
            <div class="chain-layer"><div class="layer-title"><el-icon><Cpu /></el-icon><span>器件品类</span></div>
              <div class="layer-nodes"><div class="chain-node device-category"><div class="node-name device-name">{{ activeCategory.name }}</div><div class="node-pass-through" v-if="activeCategory.passThrough">转嫁率 {{ activeCategory.passThrough }}</div></div></div>
            </div>
            <div class="chain-arrows"><span class="arrow-text">BOM匹配</span><div class="arrow-line"></div></div>
            <!-- L4: BOM物料 -->
            <div class="chain-layer"><div class="layer-title"><el-icon><List /></el-icon><span>BOM物料</span></div>
              <div class="layer-nodes bom-nodes">
                <div v-for="(bi,i) in activeCategory.bomItems" :key="'bi-'+i" class="chain-node bom-item" :class="bi.riskLevel">
                  <div class="node-name">{{ bi.mpn }}</div><div class="node-brand" v-if="bi.brand">{{ bi.brand }}</div><div class="node-project">{{ bi.projectName }}</div><el-tag :type="riskTagType(bi.riskLevel)" size="small">{{ riskLabel(bi.riskLevel) }}</el-tag>
                </div>
                <div v-if="!activeCategory.bomItems?.length" class="chain-node empty-node"><span>暂无命中BOM物料</span></div>
              </div>
            </div>
          </div>

          <!-- 行情信号 + AI判断 + 建议 -->
          <div class="signal-board" v-if="activeCategory.marketSignals?.length"><h4>行情信号</h4><div class="signal-list"><div v-for="(sig,i) in activeCategory.marketSignals" :key="'sig-'+i" class="signal-item" :class="sig.evidenceLevel"><div class="signal-header"><el-tag :type="sig.evidenceLevel==='strong'?'danger':'warning'" size="small">{{ sig.evidenceLevel==='strong'?'强证据':'中证据' }}</el-tag><strong>{{ sig.title }}</strong></div><div class="signal-detail"><span>来源：{{ sig.source }}</span><span v-if="sig.date">时间：{{ sig.date }}</span></div></div></div></div>
          <div class="ai-judgement" v-if="activeCategory.aiJudgement"><h4>AI综合判断</h4><p>{{ activeCategory.aiJudgement }}</p></div>
          <div class="action-suggestions" v-if="activeCategory.suggestions?.length"><h4>处置建议</h4><ul><li v-for="(s,i) in activeCategory.suggestions" :key="'as-'+i" :class="s.urgency">{{ s.text }}</li></ul></div>
        </el-card>
      </div>
      <el-empty v-else-if="categories.length" description="点击上方品类卡片查看详细链路" :image-size="80" />
      <el-empty v-else description="暂无数据，请确保后端已启动并已上传BOM分析" :image-size="80" />
    </template>

    <!-- ====== 视图2：按材料 ====== -->
    <template v-if="viewMode === 'material'">
      <div class="material-overview">
        <div v-for="mat in materials" :key="mat.key" class="material-card" :class="{ selected: selectedMaterial === mat.key }" @click="selectedMaterial = mat.key">
          <div class="mat-header"><strong>{{ mat.name }}</strong><span v-if="mat.source" class="mat-source">{{ mat.source }}</span></div>
          <div class="mat-level"><el-tag size="small" type="info" effect="plain">{{ mat.dataLevel }}级数据</el-tag></div>
          <div class="mat-impact">影响品类：{{ mat.affectedCategories?.join('、') || '暂无' }}</div>
        </div>
      </div>
      <div v-if="activeMaterial" class="material-chains">
        <el-card v-for="chain in activeMaterial.chains" :key="chain.category" class="chain-card">
          <template #header><div class="chain-header"><h3>{{ activeMaterial.name }} → {{ chain.category }}</h3><el-tag size="small">可靠性：{{ chain.reliability }}</el-tag></div></template>
          <div class="propagation-flow">
            <div class="flow-node material">{{ activeMaterial.name }}</div><span class="flow-arrow">→</span>
            <div class="flow-node mid" v-for="(mid,i) in chain.midNodes" :key="'mn-'+i">{{ mid }}</div>
            <span class="flow-arrow">→</span><div class="flow-node category">{{ chain.category }}</div>
            <span class="flow-arrow">→</span><div class="flow-node bom">BOM</div>
          </div>
          <div class="chain-stats"><span>物料 {{ chain.itemCount }}</span><span>项目 {{ chain.projectCount }}</span><span>转嫁率 {{ chain.passThrough }}</span><span>滞后 {{ chain.lag }}</span></div>
        </el-card>
      </div>
      <el-empty v-else-if="materials.length" description="点击上方材料卡片查看详细传导" :image-size="60" />
      <el-empty v-else description="暂无材料数据" :image-size="60" />
    </template>

    <!-- ====== 视图3：按项目 ====== -->
    <template v-if="viewMode === 'project'">
      <el-card class="section-card"><template #header><h3>项目上游风险总览</h3></template>
        <div v-if="projectRisks.length" class="project-risk-grid">
          <div v-for="proj in projectRisks" :key="proj.id" class="project-risk-card" @click="router.push('/projects/'+proj.id)">
            <div class="proj-header"><strong>{{ proj.name }}</strong><el-tag :type="proj.overallRisk==='red'?'danger':'warning'" size="small">{{ proj.overallRisk==='red'?'red':'orange' }}</el-tag></div>
            <div class="proj-exposure">
              <div class="exposure-item"><span class="exposure-label">材料传导</span><div class="exposure-tags"><el-tag v-for="m in proj.materialExposures" :key="m" size="small" effect="plain">{{ m }}</el-tag></div></div>
              <div class="exposure-item"><span class="exposure-label">供需信号</span><div class="exposure-tags"><el-tag v-for="s in proj.supplyExposures" :key="s" size="small" effect="plain" type="warning">{{ s }}</el-tag></div></div>
            </div>
            <div class="proj-stats"><span>物料 {{ proj.itemCount }} / 红{{ proj.redCount }} 橙{{ proj.orangeCount }} 黄{{ proj.yellowCount }}</span></div>
          </div>
        </div>
        <el-empty v-else description="暂无BOM项目数据" :image-size="60" />
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Box, Connection, Cpu, List } from '@element-plus/icons-vue'
import axios from 'axios'

const router = useRouter()
const loading = ref(false)
const viewMode = ref('category')
const selectedCategory = ref(null)
const selectedMaterial = ref(null)
const categories = ref([])
const materials = ref([])
const projectRisks = ref([])

const activeCategory = computed(() => categories.value.find(c => c.key === selectedCategory.value))
const activeMaterial = computed(() => materials.value.find(m => m.key === selectedMaterial.value))

function riskTagType(level) {
  return { red: 'danger', orange: 'warning', yellow: 'warning', green: 'success', gray: 'info' }[level] || 'info'
}
function riskLabel(level) {
  return { red: 'red', orange: 'orange', yellow: 'yellow', green: 'green', gray: 'gray' }[level] || level
}

function mapChainFromApi(apiChain) {
  return {
    key: apiChain.category_key,
    name: apiChain.display_name,
    riskLevel: apiChain.risk_level,
    driverType: apiChain.driver_type === 'material_cost' ? '成本驱动型' : apiChain.driver_type === 'demand_supply' ? '供需驱动型' : '混合驱动型',
    reliability: { verified: '已验证传导', high_theory: '高可信理论传导', theory: '理论传导', weak: '弱关联' }[apiChain.reliability] || apiChain.reliability || '',
    lag: apiChain.lag || '',
    passThrough: apiChain.pass_through || '',
    itemCount: apiChain.total_items,
    projectCount: apiChain.project_count,
    rawMaterials: (apiChain.raw_materials || []).map(rm => ({ name: rm.name, source: rm.source, priceChange: null, dataLevel: rm.data_level, alert: false })),
    midComponents: (apiChain.mid_components || []).map(mc => ({ name: mc.name, from: mc.from, costShare: mc.cost_share })),
    marketSignals: (apiChain.market_events || []).map(ev => ({ title: ev.title || '事件', source: ev.source_name || '', date: ev.created_at?.slice(0,10) || '', evidenceLevel: (ev.severity === 'critical' || ev.severity === 'high') ? 'strong' : 'medium', desc: '' })),
    aiJudgement: apiChain.ai_judgement || '',
    suggestions: (apiChain.suggestions || []).map(s => ({ text: s.text, urgency: s.urgency })),
    bomItems: (apiChain.bom_items || []).map(bi => ({ mpn: bi.mpn, brand: bi.brand, projectName: bi.project_name, riskLevel: bi.risk_level })),
    note: apiChain.note || ''
  }
}

async function loadData() {
  loading.value = true
  try {
    const [cRes, mRes, pRes] = await Promise.all([
      axios.get('/api/risk-chain/material-chain').catch(() => ({ data: null })),
      axios.get('/api/risk-chain/material-chain/by-material').catch(() => ({ data: null })),
      axios.get('/api/risk-chain/material-chain/by-project').catch(() => ({ data: null }))
    ])
    if (cRes?.data?.chains?.length) categories.value = cRes.data.chains.map(mapChainFromApi)
    if (mRes?.data?.materials?.length) materials.value = mRes.data.materials.map(mat => ({
      key: mat.material_name, name: mat.material_name, dataLevel: mat.data_level, source: mat.source, price: '', change30d: null,
      affectedCategories: (mat.affected_categories || []).map(c => c.display_name),
      chains: (mat.affected_categories || []).map(c => ({
        category: c.display_name, reliability: c.reliability, passThrough: c.pass_through, lag: c.lag, midNodes: [],
        itemCount: c.total_items, projectCount: c.project_count
      }))
    }))
    if (pRes?.data?.projects?.length) projectRisks.value = pRes.data.projects.map(p => ({
      id: p.id, name: p.name, overallRisk: p.overall_risk, itemCount: p.item_count,
      redCount: p.red_count, orangeCount: p.orange_count, yellowCount: p.yellow_count,
      materialExposures: p.material_exposures || [], supplyExposures: p.supply_exposures || []
    }))
  } finally { loading.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.material-chain-page{display:flex;flex-direction:column;gap:16px}
.page-header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.page-header h2{margin:0;font-size:22px;color:#1f2d3d}
.page-header p{margin:6px 0 0;color:#909399;font-size:13px;max-width:700px}
.header-actions{display:flex;gap:8px;align-items:center}

.category-overview{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px}
.category-card{padding:14px;border-radius:10px;border:2px solid #ebeef5;background:#fff;cursor:pointer;transition:all .2s}
.category-card:hover{border-color:#409eff;box-shadow:0 2px 8px rgba(64,158,255,.15)}
.category-card.selected{border-color:#409eff;background:#ecf5ff}
.category-card.red{border-left:4px solid #f56c6c}.category-card.orange{border-left:4px solid #e6a23c}.category-card.yellow{border-left:4px solid #f2d643}
.cat-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}.cat-header strong{font-size:14px;color:#303133}
.cat-stats{display:flex;gap:12px;font-size:12px;color:#909399;margin-bottom:6px}.cat-driver{margin-top:4px}

.chain-card{border-radius:12px}
.chain-header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.chain-header h3{margin:0;font-size:16px}
.chain-meta{display:flex;gap:6px;flex-wrap:wrap}

.chain-flow{padding:16px 0}
.chain-layer{margin-bottom:4px}
.layer-title{display:flex;align-items:center;gap:6px;margin-bottom:8px;font-size:13px;color:#606266;font-weight:600}
.layer-nodes{display:flex;gap:10px;flex-wrap:wrap}
.chain-node{padding:10px 14px;border-radius:8px;background:#f5f7fa;border:1px solid #e4e7ed;min-width:110px;transition:all .2s}
.chain-node.alert{border-color:#f56c6c;background:#fef0f0}
.chain-node .node-name{font-size:14px;font-weight:600;color:#303133;margin-bottom:4px}
.chain-node .node-source,.chain-node .node-from,.chain-node .node-cost{font-size:11px;color:#909399}
.chain-node .node-brand{font-size:11px;color:#909399}.chain-node .node-project{font-size:11px;color:#606266;margin-top:2px}
.chain-node .node-pass-through{font-size:12px;color:#409eff;font-weight:500}
.device-category{border-color:#409eff;border-width:2px;background:#ecf5ff;min-width:140px}
.device-name{font-size:16px!important}
.bom-item{cursor:pointer}.bom-item:hover{border-color:#409eff}
.bom-item.red{border-left:3px solid #f56c6c}.bom-item.orange{border-left:3px solid #e6a23c}
.empty-node{color:#909399;font-style:italic;text-align:center;min-width:140px}

.chain-arrows{display:flex;align-items:center;padding:6px 0 6px 60px}
.arrow-text{font-size:11px;color:#909399;min-width:55px}
.arrow-line{flex:1;height:2px;background:linear-gradient(to right,#409eff,#c0c4cc);position:relative}
.arrow-line::after{content:'';position:absolute;right:-4px;top:-3px;border:5px solid transparent;border-left-color:#409eff}

.signal-board{margin-top:16px;padding:16px;border-radius:10px;background:#fafbfc;border:1px solid #ebeef5}
.signal-board h4{margin:0 0 10px}
.signal-item{padding:10px 12px;border-radius:8px;border-left:3px solid #c0c4cc;background:#fff;margin-bottom:6px}
.signal-item.strong{border-left-color:#f56c6c}.signal-item.medium{border-left-color:#e6a23c}
.signal-header{display:flex;align-items:center;gap:8px;margin-bottom:4px}.signal-header strong{font-size:14px;color:#303133}
.signal-detail{display:flex;gap:12px;font-size:12px;color:#909399}

.ai-judgement{margin-top:14px;padding:14px;border-radius:10px;background:linear-gradient(135deg,#f0f7ff,#f5f7fa);border:1px solid #d9ecff}
.ai-judgement h4{margin:0 0 8px}.ai-judgement p{margin:0;font-size:14px;color:#303133;line-height:1.6}

.action-suggestions{margin-top:14px}.action-suggestions h4{margin:0 0 8px}
.action-suggestions ul{margin:0;padding-left:20px}.action-suggestions li{padding:6px 0;font-size:13px;line-height:1.5}
.action-suggestions li.urgent{color:#f56c6c}.action-suggestions li.watch{color:#e6a23c}

.material-overview{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px}
.material-card{padding:14px;border-radius:10px;border:2px solid #ebeef5;background:#fff;cursor:pointer;transition:all .2s}
.material-card:hover{border-color:#409eff}.material-card.selected{border-color:#409eff;background:#ecf5ff}
.mat-header{display:flex;justify-content:space-between;align-items:center}.mat-source{font-size:12px;color:#909399}
.mat-level{margin:6px 0}.mat-impact{font-size:12px;color:#909399;line-height:1.4}
.material-chains{display:flex;flex-direction:column;gap:14px;margin-top:14px}

.propagation-flow{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px 0}
.flow-node{padding:8px 14px;border-radius:20px;font-size:13px;font-weight:600}
.flow-node.material{background:#fef0f0;color:#f56c6c;border:1px solid #fbc4c4}
.flow-node.mid{background:#fdf6ec;color:#e6a23c;border:1px solid #faecd8}
.flow-node.category{background:#ecf5ff;color:#409eff;border:1px solid #d9ecff}
.flow-node.bom{background:#f0f9eb;color:#67c23a;border:1px solid #e1f3d8}
.flow-arrow{font-size:18px;color:#909399;font-weight:700}
.chain-stats{display:flex;gap:16px;font-size:13px;color:#606266;margin-top:8px}

.project-risk-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.project-risk-card{padding:14px;border-radius:10px;border:2px solid #ebeef5;background:#fff;cursor:pointer;transition:all .2s}
.project-risk-card:hover{border-color:#409eff;box-shadow:0 2px 8px rgba(64,158,255,.15)}
.proj-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.proj-exposure{display:flex;flex-direction:column;gap:6px}
.exposure-item{display:flex;flex-direction:column;gap:4px}.exposure-label{font-size:12px;color:#909399}
.exposure-tags{display:flex;gap:4px;flex-wrap:wrap}.proj-stats{margin-top:8px;font-size:12px;color:#606266}
.section-card{border-radius:12px}
@media(max-width:1200px){.category-overview,.material-overview{grid-template-columns:repeat(3,1fr)}}
@media(max-width:768px){.category-overview,.material-overview{grid-template-columns:1fr}.propagation-flow{flex-direction:column;align-items:flex-start}}
</style>
