import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import RiskChainDashboard from '../RiskChainDashboard.vue'
import * as riskChainApi from '../../api/riskChain'

vi.mock('../../api/riskChain', () => ({
  getRiskChainDashboard: vi.fn()
}))

const stubs = {
  'el-card': { template: '<section><slot name="header" /><slot /></section>' },
  'el-button': { emits: ['click'], template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
  'el-alert': { props: ['title'], template: '<div>{{ title }}</div>' },
  'el-divider': { template: '<hr />' },
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' }
}

const dashboardData = {
  summary: {
    highRiskBomCount: 2,
    affectedItemCount: 3,
    affectedCategoryCount: 3,
    highConfidenceSignalCount: 2,
    pendingActionCount: 3,
    categoryCoverageCount: 8
  },
  categoryFilters: [
    { key: 'all', label: '全部' },
    { key: 'semiconductor', label: 'IC/半导体' },
    { key: 'pcb', label: 'PCB/FPC' },
    { key: 'passive', label: '被动件' }
  ],
  signals: [
    {
      id: 'sig-pcb-copper-001',
      group: 'pcb',
      title: 'PCB 成本上行预警',
      signalType: 'price',
      severity: 'red',
      sourceName: 'LME Copper',
      sourceLevel: 'S',
      sourceType: '交易所行情',
      sourceUrl: 'https://www.lme.com/en/Metals/Non-ferrous/LME-Copper',
      confidenceScore: 90,
      occurredAt: '2026-07-07',
      summary: '铜价上涨叠加树脂供应偏紧。',
      linkedMaterials: ['铜箔', '环氧树脂'],
      linkedCategories: ['PCB/FPC']
    },
    {
      id: 'sig-semi-001',
      group: 'semiconductor',
      title: '半导体产能影响 IC 交期',
      signalType: 'trade',
      severity: 'orange',
      sourceName: 'SEMI Market Data',
      sourceLevel: 'A',
      sourceType: '行业协会数据',
      sourceUrl: 'https://china.semi.org.cn/article/77',
      confidenceScore: 86,
      occurredAt: '2026-07-07',
      summary: '晶圆产能和封装材料影响 MCU 交期。',
      linkedMaterials: ['硅片', '封装基板'],
      linkedCategories: ['IC/半导体']
    }
  ],
  materialChains: [
    {
      id: 'chain-pcb-001',
      group: 'pcb',
      category: 'PCB/FPC',
      title: 'PCB → CCL → 铜箔/树脂/玻纤布',
      summary: 'PCB 成本通过 CCL 向下游传导。',
      sourceLinks: [
        { id: 'src-lme-copper', sourceName: 'LME Copper', sourceLevel: 'S', sourceType: '交易所行情', url: 'https://www.lme.com/en/Metals/Non-ferrous/LME-Copper', summary: '铜行情' }
      ],
      nodes: [
        { name: 'PCB/FPC', materialType: 'finished_category', riskLevel: 'red', evidence: 'BOM 类别命中', priceChangeText: '受影响', confidenceScore: 90 },
        { name: '铜箔', materialType: 'upstream_material', riskLevel: 'red', evidence: '铜价上涨', priceChangeText: '+8~12%', confidenceScore: 88 }
      ]
    },
    {
      id: 'chain-semiconductor-001',
      group: 'semiconductor',
      category: 'IC/半导体',
      title: 'IC → 晶圆制造 → 硅片/电子气体/光刻胶 → 封装材料',
      summary: 'IC 风险以晶圆产能和封装材料为主。',
      sourceLinks: [
        { id: 'src-semi', sourceName: 'SEMI Market Data', sourceLevel: 'A', sourceType: '行业协会数据', url: 'https://china.semi.org.cn/article/77', summary: '半导体数据' }
      ],
      nodes: [
        { name: 'IC/半导体', materialType: 'finished_category', riskLevel: 'orange', evidence: 'BOM 类别命中', priceChangeText: '供需敏感', confidenceScore: 88 }
      ]
    }
  ],
  bomImpacts: [
    {
      id: 'impact-pcb-8l-001',
      group: 'pcb',
      bomProjectName: '示例控制板 BOM',
      itemCode: 'PCB-8L-HDI-001',
      itemName: '8层 HDI 主控板',
      category: 'PCB/FPC',
      riskLevel: 'red',
      priceImpactText: '预计 +8~15%',
      leadTimeImpactText: '预计 +7 天',
      reasonSummary: '铜箔、树脂经 CCL 传导到 PCB。',
      linkedSignalIds: ['sig-pcb-copper-001'],
      linkedMaterials: ['铜箔', '环氧树脂'],
      suggestedStrategyIds: ['act-lock-pcb-001'],
      impactBreakdown: { materialCost: '高', supply: '中', policy: '低', substitution: '高' }
    },
    {
      id: 'impact-mcu-001',
      group: 'semiconductor',
      bomProjectName: '示例控制板 BOM',
      itemCode: 'MCU-STM32-ALT-001',
      itemName: '32位主控 MCU',
      category: 'IC/半导体',
      riskLevel: 'orange',
      priceImpactText: '预计 +3~8%',
      leadTimeImpactText: '预计 +2~6 周',
      reasonSummary: '晶圆产能、封装材料和出口管制共同影响 MCU 交期。',
      linkedSignalIds: ['sig-semi-001'],
      linkedMaterials: ['硅片', '封装基板'],
      suggestedStrategyIds: ['act-semi-alt-001'],
      impactBreakdown: { materialCost: '中', supply: '高', policy: '中', substitution: '高' }
    }
  ],
  strategies: [
    {
      id: 'act-lock-pcb-001',
      group: 'pcb',
      strategyType: 'price',
      priority: 'P0',
      title: '锁定关键 PCB 价格',
      detail: '优先锁定 4~8 周需求。',
      ownerRole: '采购',
      triggerReason: '铜箔和树脂价格上行。',
      expectedEffect: '降低短期涨价暴露。'
    },
    {
      id: 'act-semi-alt-001',
      group: 'semiconductor',
      strategyType: 'alternative',
      priority: 'P0',
      title: '启动关键 IC 替代料认证',
      detail: '对 MCU 建立二供清单。',
      ownerRole: '研发',
      triggerReason: '半导体产能信号命中。',
      expectedEffect: '降低断供风险。'
    }
  ]
}

describe('RiskChainDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('展示风险链路驾驶舱核心区域和来源链接', async () => {
    riskChainApi.getRiskChainDashboard.mockResolvedValue({ data: dashboardData })

    const wrapper = mount(RiskChainDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('风险链路驾驶舱')
    expect(wrapper.text()).toContain('已覆盖类别')
    expect(wrapper.text()).toContain('PCB 成本上行预警')
    expect(wrapper.text()).toContain('LME Copper')
    expect(wrapper.text()).toContain('PCB → CCL → 铜箔/树脂/玻纤布')
    expect(wrapper.text()).toContain('PCB-8L-HDI-001')
    expect(wrapper.text()).toContain('锁定关键 PCB 价格')
    expect(wrapper.find('a[href="https://www.lme.com/en/Metals/Non-ferrous/LME-Copper"]').exists()).toBe(true)
  })

  it('无数据时展示空状态', async () => {
    riskChainApi.getRiskChainDashboard.mockResolvedValue({
      data: {
        summary: { highRiskBomCount: 0, affectedItemCount: 0, affectedCategoryCount: 0, highConfidenceSignalCount: 0, pendingActionCount: 0, categoryCoverageCount: 0 },
        categoryFilters: [{ key: 'all', label: '全部' }],
        signals: [],
        materialChains: [],
        bomImpacts: [],
        strategies: []
      }
    })

    const wrapper = mount(RiskChainDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无风险链路数据')
  })

  it('点击 BOM 影响可以打开证据抽屉并展示官方来源', async () => {
    riskChainApi.getRiskChainDashboard.mockResolvedValue({ data: dashboardData })

    const wrapper = mount(RiskChainDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.find('[data-test="open-evidence-impact-pcb-8l-001"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('证据链路')
    expect(wrapper.text()).toContain('铜箔、树脂经 CCL 传导到 PCB。')
    expect(wrapper.text()).toContain('打开官方/权威来源')
    expect(wrapper.text()).toContain('材料成本：高')
  })

  it('可以按 IC/半导体筛选风险链路', async () => {
    riskChainApi.getRiskChainDashboard.mockResolvedValue({ data: dashboardData })

    const wrapper = mount(RiskChainDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.find('[data-test="category-filter-semiconductor"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('半导体产能影响 IC 交期')
    expect(wrapper.text()).toContain('IC → 晶圆制造')
    expect(wrapper.text()).toContain('MCU-STM32-ALT-001')
    expect(wrapper.text()).not.toContain('PCB-8L-HDI-001')
  })
})
