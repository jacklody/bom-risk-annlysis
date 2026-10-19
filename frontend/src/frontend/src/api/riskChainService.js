/**
 * 风险链路驾驶舱 - 数据服务层
 * 
 * 数据接口抽象层，当前使用 Mock 数据源。
 * 后续对接真实后端时，只需将 mock 函数替换为 client HTTP 调用即可。
 * 
 * @typedef {'S'|'A'|'B'|'C'} SignalLevel
 * @typedef {'market'|'policy'|'disaster'|'inventory'|'pcn'} SignalType
 * @typedef {'red'|'orange'|'yellow'} SignalSeverity
 * @typedef {'material'|'component'|'bom_item'} NodeLevel
 * @typedef {'red'|'orange'|'yellow'|'green'|'gray'} RiskLevel
 * @typedef {'up'|'down'|'stable'} PriceTrend
 * @typedef {'Active'|'NRND'|'EOL'|'Unknown'} LifecycleStatus
 * @typedef {'purchase'|'rd'|'pm'} SuggestionRole
 */

import client from './client'

// ──────────────────────────────────────
// 接口类型定义 (JSDoc)
// ──────────────────────────────────────

/**
 * @typedef {Object} RiskSignal
 * @property {string} id
 * @property {SignalLevel} level
 * @property {SignalType} type
 * @property {string} title
 * @property {string} category
 * @property {string[]} affected_brands
 * @property {SignalSeverity} severity
 * @property {string} timestamp
 * @property {string} description
 * @property {string[]} impact_chain
 */

/**
 * @typedef {Object} ChainNode
 * @property {string} id
 * @property {string} name
 * @property {NodeLevel} level
 * @property {RiskLevel} risk_level
 * @property {PriceTrend} price_trend
 * @property {number} [price_change_pct]
 * @property {number} bom_line_count
 * @property {string[]} [children]
 */

/**
 * @typedef {Object} ChainEdge
 * @property {string} from
 * @property {string} to
 * @property {number} weight - 影响程度 1~5
 */

/**
 * @typedef {Object} BomImpactItem
 * @property {string} mpn
 * @property {string} manufacturer
 * @property {string} category
 * @property {RiskLevel} risk_level
 * @property {number} risk_score
 * @property {string[]} trigger_events
 * @property {LifecycleStatus} lifecycle_status
 * @property {{role: SuggestionRole, action: string}[]} suggestions
 */

/**
 * @typedef {Object} DashboardData
 * @property {RiskSignal[]} signals
 * @property {ChainNode[]} nodes
 * @property {ChainEdge[]} edges
 * @property {BomImpactItem[]} bomImpacts
 */

// ──────────────────────────────────────
// Mock 数据生成器
// ──────────────────────────────────────

const SIGNAL_TEMPLATES = [
  { type: 'market', title: '铜价突破9800美元/吨，创18个月新高', category: '铜材', severity: 'red', affected_brands: ['电解铜板', '铜箔'], level: 'S' },
  { type: 'policy', title: '欧盟REACH法规更新，限制邻苯二甲酸酯使用', category: '塑胶原料', severity: 'orange', affected_brands: ['ABS', 'PC', 'PVC'], level: 'S' },
  { type: 'disaster', title: '台风影响华南地区，部分物流线路中断', category: '被动元器件', severity: 'orange', affected_brands: ['Murata', 'TDK', 'YAGEO'], level: 'A' },
  { type: 'inventory', title: 'MLCC库存周降至4.2周，低于安全线', category: 'MLCC', severity: 'red', affected_brands: ['Samsung', 'Murata', 'TDK'], level: 'S' },
  { type: 'pcn', title: 'TI发布LM358 PCN，封装变更通知', category: '运放IC', severity: 'yellow', affected_brands: ['Texas Instruments'], level: 'B' },
  { type: 'market', title: '锂碳酸期货价格上涨12%，影响电池模组成本', category: '电池', severity: 'orange', affected_brands: ['CATL', 'BYD'], level: 'A' },
  { type: 'policy', title: '美国商务部更新实体清单，涉及3家半导体企业', category: '芯片', severity: 'red', affected_brands: ['SMIC', '华为', '寒武纪'], level: 'S' },
  { type: 'disaster', title: '日本能登半岛地震后续，部分晶圆厂产能恢复中', category: '晶圆', severity: 'orange', affected_brands: ['TSMC', 'Renesas'], level: 'A' },
  { type: 'inventory', title: 'STM32F103渠道库存回升至8周，价格企稳', category: 'MCU', severity: 'yellow', affected_brands: ['STMicroelectronics'], level: 'B' },
  { type: 'market', title: '黄金价格持续走强，连接器镀金成本上升', category: '连接器', severity: 'yellow', affected_brands: ['TE', 'Molex', 'JST'], level: 'A' },
  { type: 'pcn', title: 'NXP通知TJA1050 T/R版本停产，推荐替代TJA1042', category: 'CAN收发器', severity: 'orange', affected_brands: ['NXP'], level: 'A' },
  { type: 'inventory', title: '电阻0402系列交期延长至10周', category: '电阻', severity: 'yellow', affected_brands: ['YAGEO', 'Uniroyal'], level: 'B' },
  { type: 'market', title: '硅钢片价格季度环比上涨8%，电机成本承压', category: '硅钢', severity: 'orange', affected_brands: ['宝钢', '武钢'], level: 'A' },
  { type: 'policy', title: '印度BIS认证新规实施，出口需重新认证', category: '电源适配器', severity: 'yellow', affected_brands: ['Mean Well', 'Delta'], level: 'B' },
  { type: 'disaster', title: '泰国洪水预警，部分硬盘工厂转移产线', category: '存储', severity: 'orange', affected_brands: ['Seagate', 'WD'], level: 'A' }
]

function generateMockSignals() {
  const now = Date.now()
  return SIGNAL_TEMPLATES.map((tpl, idx) => ({
    id: `SIG-${String(idx + 1).padStart(3, '0')}`,
    level: tpl.level,
    type: tpl.type,
    title: tpl.title,
    category: tpl.category,
    affected_brands: tpl.affected_brands,
    severity: tpl.severity,
    timestamp: new Date(now - idx * 1800000 - Math.random() * 3600000).toISOString(),
    description: `这是关于"${tpl.title}"的详细描述。该事件来源于${tpl.level}级信源，影响${tpl.category}品类，涉及品牌：${tpl.affected_brands.join('、')}。`,
    impact_chain: generateImpactChain(tpl.category)
  }))
}

function generateImpactChain(category) {
  const chains = {
    '铜材': ['铜矿石', '电解铜', '铜箔', 'PCB覆铜板', 'PCB成品'],
    'MLCC': ['钛酸钡', 'MLCC陶瓷粉', 'MLCC生坯', 'MLCC烧结', 'MLCC成品'],
    '芯片': ['硅晶圆', '光刻胶', '晶圆制造', '封测', 'IC成品'],
    '塑胶原料': ['石油', '石脑油', '乙烯/丙烯', '聚合树脂', '改性塑料'],
    '连接器': ['铜合金', '镀金液', '冲压件', '注塑件', '连接器成品'],
    '电池': ['锂矿石', '碳酸锂', '正极材料', '电芯', '电池模组'],
    'MCU': ['硅晶圆', 'IP核授权', '晶圆代工', '封装测试', 'MCU成品'],
    '电阻': ['氧化铝基板', '电阻浆料', '厚膜印刷', '激光调阻', '电阻成品'],
    '硅钢': ['铁矿石', '生铁', '硅钢坯', '冷轧硅钢片', '铁芯'],
    '存储': ['硅晶圆', 'NAND Flash颗粒', '控制器', 'PCB组装', 'SSD成品'],
    'CAN收发器': ['硅晶圆', '模拟IC设计', '晶圆代工', '封装测试', 'CAN芯片'],
    '电源适配器': ['MOSFET', '变压器', '电解电容', 'PCB', '电源成品'],
    '被动元器件': ['陶瓷粉体', '电极浆料', '生坯成型', '高温烧结', '被动元器件'],
    '晶圆': ['多晶硅', '硅晶圆', '光刻胶', '晶圆加工', '晶圆成品'],
    '运放IC': ['硅晶圆', '模拟IC设计', '晶圆代工', '封装测试', '运放芯片']
  }
  return chains[category] || ['原材料', '中间品', '器件', '模组', '成品']
}

function generateMockNodes() {
  /** @type {ChainNode[]} */
  const nodes = [
    // 基础材料层 (material)
    { id: 'mat-copper', name: '电解铜', level: 'material', risk_level: 'red', price_trend: 'up', price_change_pct: 8.5, bom_line_count: 23, children: ['comp-pcb', 'comp-connector'] },
    { id: 'mat-ceramic', name: '陶瓷粉体', level: 'material', risk_level: 'orange', price_trend: 'up', price_change_pct: 5.2, bom_line_count: 18, children: ['comp-mlcc', 'comp-resistor'] },
    { id: 'mat-silicon', name: '硅晶圆', level: 'material', risk_level: 'red', price_trend: 'up', price_change_pct: 12.0, bom_line_count: 35, children: ['comp-ic', 'comp-mcu', 'comp-mosfet'] },
    { id: 'mat-resin', name: '聚合树脂', level: 'material', risk_level: 'orange', price_trend: 'up', price_change_pct: 6.8, bom_line_count: 15, children: ['comp-connector', 'comp-cap-electro'] },
    { id: 'mat-steel', name: '硅钢片', level: 'material', risk_level: 'orange', price_trend: 'up', price_change_pct: 8.0, bom_line_count: 8, children: ['comp-transformer'] },
    { id: 'mat-lithium', name: '碳酸锂', level: 'material', risk_level: 'orange', price_trend: 'up', price_change_pct: 12.0, bom_line_count: 6, children: ['comp-battery'] },
    { id: 'mat-gold', name: '黄金', level: 'material', risk_level: 'yellow', price_trend: 'up', price_change_pct: 3.5, bom_line_count: 12, children: ['comp-connector'] },
    { id: 'mat-poly', name: '光刻胶', level: 'material', risk_level: 'red', price_trend: 'up', price_change_pct: 15.0, bom_line_count: 28, children: ['comp-ic', 'comp-mcu'] },
    
    // 器件品类层 (component)
    { id: 'comp-pcb', name: 'PCB板', level: 'component', risk_level: 'red', price_trend: 'up', price_change_pct: 6.5, bom_line_count: 23, children: ['bom-pcb-main', 'bom-pcb-ctrl'] },
    { id: 'comp-mlcc', name: 'MLCC', level: 'component', risk_level: 'red', price_trend: 'up', price_change_pct: 9.0, bom_line_count: 42, children: ['bom-mlcc-0402', 'bom-mlcc-0603', 'bom-mlcc-0805'] },
    { id: 'comp-ic', name: '模拟IC', level: 'component', risk_level: 'red', price_trend: 'up', price_change_pct: 10.5, bom_line_count: 15, children: ['bom-lm358', 'bom-opamp'] },
    { id: 'comp-mcu', name: 'MCU', level: 'component', risk_level: 'orange', price_trend: 'stable', price_change_pct: 1.2, bom_line_count: 8, children: ['bom-stm32', 'bom-esp32'] },
    { id: 'comp-resistor', name: '电阻', level: 'component', risk_level: 'yellow', price_trend: 'stable', price_change_pct: 0.5, bom_line_count: 38, children: ['bom-res-0402', 'bom-res-0603'] },
    { id: 'comp-connector', name: '连接器', level: 'component', risk_level: 'yellow', price_trend: 'up', price_change_pct: 3.0, bom_line_count: 20, children: ['bom-usb-conn', 'bom-pin-header'] },
    { id: 'comp-cap-electro', name: '电解电容', level: 'component', risk_level: 'green', price_trend: 'stable', price_change_pct: -0.5, bom_line_count: 16, children: ['bom-cap-100uf', 'bom-cap-470uf'] },
    { id: 'comp-mosfet', name: 'MOSFET', level: 'component', risk_level: 'orange', price_trend: 'up', price_change_pct: 7.0, bom_line_count: 10, children: ['bom-mosfet-n', 'bom-mosfet-p'] },
    { id: 'comp-transformer', name: '变压器', level: 'component', risk_level: 'orange', price_trend: 'up', price_change_pct: 5.5, bom_line_count: 5, children: ['bom-transformer'] },
    { id: 'comp-battery', name: '电池模组', level: 'component', risk_level: 'orange', price_trend: 'up', price_change_pct: 8.0, bom_line_count: 3, children: ['bom-battery-pack'] },
    { id: 'comp-can', name: 'CAN收发器', level: 'component', risk_level: 'orange', price_trend: 'stable', price_change_pct: 0.0, bom_line_count: 4, children: ['bom-tja1050'] },

    // BOM物料层 (bom_item)
    { id: 'bom-pcb-main', name: 'PCB主板-4L', level: 'bom_item', risk_level: 'red', price_trend: 'up', price_change_pct: 7.0, bom_line_count: 1, children: [] },
    { id: 'bom-pcb-ctrl', name: 'PCB控制板-2L', level: 'bom_item', risk_level: 'red', price_trend: 'up', price_change_pct: 5.5, bom_line_count: 1, children: [] },
    { id: 'bom-mlcc-0402', name: 'MLCC 100nF 0402', level: 'bom_item', risk_level: 'red', price_trend: 'up', price_change_pct: 12.0, bom_line_count: 18, children: [] },
    { id: 'bom-mlcc-0603', name: 'MLCC 1uF 0603', level: 'bom_item', risk_level: 'red', price_trend: 'up', price_change_pct: 8.0, bom_line_count: 12, children: [] },
    { id: 'bom-mlcc-0805', name: 'MLCC 10uF 0805', level: 'bom_item', risk_level: 'orange', price_trend: 'up', price_change_pct: 5.0, bom_line_count: 6, children: [] },
    { id: 'bom-lm358', name: 'LM358DR 运放', level: 'bom_item', risk_level: 'yellow', price_trend: 'stable', price_change_pct: 0.0, bom_line_count: 2, children: [] },
    { id: 'bom-opamp', name: 'OPA2340 精密运放', level: 'bom_item', risk_level: 'red', price_trend: 'up', price_change_pct: 15.0, bom_line_count: 1, children: [] },
    { id: 'bom-stm32', name: 'STM32F103C8T6', level: 'bom_item', risk_level: 'orange', price_trend: 'stable', price_change_pct: 1.0, bom_line_count: 3, children: [] },
    { id: 'bom-esp32', name: 'ESP32-WROOM-32E', level: 'bom_item', risk_level: 'green', price_trend: 'down', price_change_pct: -3.0, bom_line_count: 2, children: [] },
    { id: 'bom-res-0402', name: '电阻 10K 0402', level: 'bom_item', risk_level: 'yellow', price_trend: 'stable', price_change_pct: 0.5, bom_line_count: 22, children: [] },
    { id: 'bom-res-0603', name: '电阻 4.7K 0603', level: 'bom_item', risk_level: 'green', price_trend: 'stable', price_change_pct: 0.0, bom_line_count: 15, children: [] },
    { id: 'bom-usb-conn', name: 'USB-C连接器', level: 'bom_item', risk_level: 'yellow', price_trend: 'up', price_change_pct: 3.5, bom_line_count: 2, children: [] },
    { id: 'bom-pin-header', name: '排针 2x10P', level: 'bom_item', risk_level: 'green', price_trend: 'stable', price_change_pct: 0.0, bom_line_count: 4, children: [] },
    { id: 'bom-cap-100uf', name: '电解电容 100uF/25V', level: 'bom_item', risk_level: 'green', price_trend: 'stable', price_change_pct: -1.0, bom_line_count: 8, children: [] },
    { id: 'bom-cap-470uf', name: '电解电容 470uF/16V', level: 'bom_item', risk_level: 'green', price_trend: 'stable', price_change_pct: 0.0, bom_line_count: 4, children: [] },
    { id: 'bom-mosfet-n', name: 'IRF540N N-MOSFET', level: 'bom_item', risk_level: 'orange', price_trend: 'up', price_change_pct: 8.0, bom_line_count: 6, children: [] },
    { id: 'bom-mosfet-p', name: 'IRF9540 P-MOSFET', level: 'bom_item', risk_level: 'orange', price_trend: 'up', price_change_pct: 6.0, bom_line_count: 3, children: [] },
    { id: 'bom-transformer', name: 'EE25电源变压器', level: 'bom_item', risk_level: 'orange', price_trend: 'up', price_change_pct: 5.5, bom_line_count: 2, children: [] },
    { id: 'bom-battery-pack', name: '18650电池组 4S2P', level: 'bom_item', risk_level: 'orange', price_trend: 'up', price_change_pct: 8.0, bom_line_count: 1, children: [] },
    { id: 'bom-tja1050', name: 'TJA1050 CAN收发器', level: 'bom_item', risk_level: 'orange', price_trend: 'stable', price_change_pct: 0.0, bom_line_count: 2, children: [] }
  ]
  return nodes
}

function generateMockEdges() {
  const nodes = generateMockNodes()
  /** @type {ChainEdge[]} */
  const edges = []
  nodes.forEach(node => {
    if (node.children) {
      node.children.forEach(childId => {
        const child = nodes.find(n => n.id === childId)
        if (child) {
          // weight based on risk levels
          const riskWeights = { red: 5, orange: 4, yellow: 3, green: 2, gray: 1 }
          const w = Math.max(riskWeights[node.risk_level] || 2, riskWeights[child.risk_level] || 2)
          edges.push({ from: node.id, to: childId, weight: w })
        }
      })
    }
  })
  return edges
}

function generateMockBomImpacts() {
  return [
    {
      mpn: 'GRM155R71C104KA88D',
      manufacturer: 'Murata',
      category: 'MLCC 0402',
      risk_level: 'red',
      risk_score: 92,
      trigger_events: ['MLCC库存周降至4.2周', '陶瓷粉体价格上涨5.2%'],
      lifecycle_status: 'Active',
      suggestions: [
        { role: 'purchase', action: '立即锁定Q3库存，建议备货6周用量；联系3家以上代理商比价' },
        { role: 'rd', action: '评估0603替代方案，确认容值和耐压是否满足' },
        { role: 'pm', action: '更新项目风险登记册，通知客户可能的交期延长' }
      ]
    },
    {
      mpn: 'STM32F103C8T6',
      manufacturer: 'STMicroelectronics',
      category: 'MCU',
      risk_level: 'orange',
      risk_score: 78,
      trigger_events: ['硅晶圆价格上涨12%', '光刻胶供应紧张'],
      lifecycle_status: 'Active',
      suggestions: [
        { role: 'purchase', action: '与ST直签Long-term Agreement，锁定H2价格' },
        { role: 'rd', action: '评估GD32F103作为Pin-to-Pin替代方案' },
        { role: 'pm', action: '提前6个月forecast给供应商，确保产能预留' }
      ]
    },
    {
      mpn: 'LM358DR',
      manufacturer: 'Texas Instruments',
      category: '运放IC',
      risk_level: 'yellow',
      risk_score: 45,
      trigger_events: ['TI发布LM358 PCN，封装变更通知'],
      lifecycle_status: 'NRND',
      suggestions: [
        { role: 'rd', action: '尽快完成OPA2340替代验证，新设计不再使用LM358' },
        { role: 'purchase', action: '现有库存可满足18个月需求，暂不紧急采购' },
        { role: 'pm', action: '更新BOM替代清单，在下一版原理图中完成切换' }
      ]
    },
    {
      mpn: 'TJA1050T/CM',
      manufacturer: 'NXP',
      category: 'CAN收发器',
      risk_level: 'orange',
      risk_score: 72,
      trigger_events: ['NXP通知TJA1050停产，推荐替代TJA1042'],
      lifecycle_status: 'EOL',
      suggestions: [
        { role: 'rd', action: '立即启动TJA1042替代设计验证，注意引脚兼容性' },
        { role: 'purchase', action: '最后时间采购TJA1050，锁定lifetime buy' },
        { role: 'pm', action: '制定切换时间计划，预计2个版本完成替代' }
      ]
    },
    {
      mpn: 'IRF540NPBF',
      manufacturer: 'Infineon',
      category: 'N-MOSFET',
      risk_level: 'orange',
      risk_score: 68,
      trigger_events: ['硅晶圆价格上涨12%', '功率器件需求增长'],
      lifecycle_status: 'Active',
      suggestions: [
        { role: 'purchase', action: '评估Infineon/OnSemi/Vishay三家供应方案' },
        { role: 'rd', action: '确认RDS(on)和Vgs阈值是否可用国产MOSFET替代' },
        { role: 'pm', action: '关注功率器件市场Q3走势，准备应急预案' }
      ]
    },
    {
      mpn: 'EE25-12V',
      manufacturer: '三盛电子',
      category: '变压器',
      risk_level: 'orange',
      risk_score: 65,
      trigger_events: ['硅钢片价格季度环比上涨8%'],
      lifecycle_status: 'Active',
      suggestions: [
        { role: 'purchase', action: '与供应商协商半年度锁价协议' },
        { role: 'rd', action: '评估非晶合金铁芯替代方案的可行性' },
        { role: 'pm', action: '更新成本模型，预估变压器成本上升5-8%' }
      ]
    },
    {
      mpn: 'USB-C-16P',
      manufacturer: 'TE Connectivity',
      category: '连接器',
      risk_level: 'yellow',
      risk_score: 38,
      trigger_events: ['黄金价格持续走强，连接器镀金成本上升'],
      lifecycle_status: 'Active',
      suggestions: [
        { role: 'purchase', action: '评估国产连接器替代（如中航光电），成本可降低15%' },
        { role: 'rd', action: '确认替代品的插拔寿命和接触电阻指标' },
        { role: 'pm', action: '短期影响有限，持续关注即可' }
      ]
    },
    {
      mpn: 'GRM21BR71C106KE15L',
      manufacturer: 'Murata',
      category: 'MLCC 0805',
      risk_level: 'orange',
      risk_score: 70,
      trigger_events: ['MLCC库存周降至4.2周', '陶瓷粉体价格上涨5.2%'],
      lifecycle_status: 'Active',
      suggestions: [
        { role: 'purchase', action: '联系Samsung/TDK/YAGEO获取替代料号报价' },
        { role: 'rd', action: '确认10uF/16V规格是否可用2颗4.7uF并联替代' },
        { role: 'pm', action: '评估对BOM总成本的影响，预计增加0.3-0.5%' }
      ]
    }
  ]
}

// ──────────────────────────────────────
// 数据聚合函数
// ──────────────────────────────────────

/**
 * 获取驾驶舱完整数据
 * @returns {Promise<{data: DashboardData}>}
 */
function getDashboardData() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        data: {
          signals: generateMockSignals(),
          nodes: generateMockNodes(),
          edges: generateMockEdges(),
          bomImpacts: generateMockBomImpacts()
        }
      })
    }, 300 + Math.random() * 500)
  })
}

/**
 * 获取风险信号列表
 * @returns {Promise<{data: RiskSignal[]}>}
 */
function getRiskSignals() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ data: generateMockSignals() })
    }, 200 + Math.random() * 300)
  })
}

/**
 * 获取产业链节点和边
 * @returns {Promise<{data: {nodes: ChainNode[], edges: ChainEdge[]}}>}
 */
function getChainGraph() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        data: {
          nodes: generateMockNodes(),
          edges: generateMockEdges()
        }
      })
    }, 200 + Math.random() * 300)
  })
}

/**
 * 获取BOM影响列表
 * @returns {Promise<{data: BomImpactItem[]}>}
 */
function getBomImpacts() {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ data: generateMockBomImpacts() })
    }, 200 + Math.random() * 300)
  })
}

// ──────────────────────────────────────
// 导出 - 后续对接后端时只需修改此处
// ──────────────────────────────────────

export const riskChainService = {
  getDashboardData,
  getRiskSignals,
  getChainGraph,
  getBomImpacts,

  // ── 后端对接预留接口 ──
  // 当后端就绪后，将上述 mock 函数替换为：
  // getDashboardData: () => client.get('/risk-chain/dashboard'),
  // getRiskSignals: () => client.get('/risk-chain/signals'),
  // getChainGraph: () => client.get('/risk-chain/graph'),
  // getBomImpacts: () => client.get('/risk-chain/bom-impacts'),

  /**
   * 切换数据源：mock / api
   * @param {'mock'|'api'} source
   */
  switchDataSource(source) {
    // 预留：后续可实现运行时切换 mock/api
    console.log(`[riskChainService] 数据源切换为: ${source}（待实现）`)
  }
}

export default riskChainService
