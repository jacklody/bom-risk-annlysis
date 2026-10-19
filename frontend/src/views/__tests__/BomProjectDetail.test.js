import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { reactive, nextTick } from 'vue'
import BomProjectDetail from '../BomProjectDetail.vue'
import * as bomApi from '../../api/bom'
import * as eventApi from '../../api/events'

vi.mock('../../api/bom', () => ({
  getBomProject: vi.fn(),
  getProjectRiskReportHtmlUrl: vi.fn((projectId) => `/api/risk/report/${projectId}/export.html`),
  getProjectRiskReportXlsxUrl: vi.fn((projectId) => `/api/risk/report/${projectId}/export.xlsx`),
  getProjectRiskReport: vi.fn(() => Promise.resolve({
    data: {
      project: { id: 7, project_name: '历史BOM-A', filename: 'history-a.xlsx', status: 'active', total_items: 1, items_red: 1, items_yellow: 0, items_green: 0, items_gray: 0, last_analysis_at: '2026-06-28T09:55:31' },
      risk_summary: { total_items: 1, red: 1, yellow: 0, green: 0, gray: 0, risk_rate: 100, has_urgent: true },
      category_risk: [{ category: 'MCU', total: 1, red: 1, yellow: 0 }],
      intel_sources: { active_event_count: 22, source_count: 3, sources: ['lcsc_jlcsearch', 'guanxintai_search', 'xinshiyeye_wechat'], registered_media_sources: 8, recent_runs: [] },
      actions: { urgent: ['STM32F103C8T6（ST）：行情紧缺，建议锁单或评估GD32替代'], watch: [], all_suggestions_count: 1 },
      high_risk_items: [{ id: 99, part_number: 'STM32F103C8T6', brand: 'ST', category: 'MCU', risk_level: 'red', risk_reason: 'MCU缺货 | [行情] STM32系列MCU交期延长', suggestion: '行情紧缺，建议锁单或评估GD32替代', total_stock: 0, supplier_count: 1, lead_time_days: 52, unit_price: 12.34, lifecycle_status: 'Active', supply_sources_summary: 'lcsc:库存0' }],
      last_analysis_at: '2026-06-28T09:55:31'
    }
  }))
}))

vi.mock('../../api/events', () => ({
  getEvent: vi.fn(),
  getEventImpact: vi.fn(),
  getEventSourceSignal: vi.fn()
}))

const push = vi.fn()
const mockRoute = reactive({ params: { id: '7' }, query: {} })
vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ push })
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() }
}))

const stubs = {
  RiskDetailTable: {
    props: ['items'],
    template: '<div data-testid="risk-detail"><div v-for="item in items" :key="item.id"><span>{{ item.part_number || item.raw_part_number }}</span><span v-if="item.trace_highlight">行动命中</span></div></div>'
  },
  'el-card': { template: '<section><slot name="header" /><slot /></section>' },
  'el-button': { props: ['loading'], emits: ['click'], template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>' },
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-descriptions': { template: '<dl><slot /></dl>' },
  'el-descriptions-item': { props: ['label'], template: '<div><dt>{{ label }}</dt><dd><slot /></dd></div>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' }
}

describe('BomProjectDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    push.mockReset()
    window.open = vi.fn()
    mockRoute.params.id = '7'
    mockRoute.query = {}
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('加载项目详情并展示历史物料风险明细', async () => {
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: {
          id: 7,
          project_name: '历史BOM-A',
          filename: 'history-a.xlsx',
          status: 'active',
          total_items: 1,
          items_red: 1,
          items_yellow: 0,
          items_green: 0,
          items_gray: 0,
          last_analysis_at: '2026-06-28T09:55:31'
        },
        items: [
          {
            id: 99,
            row_number: 1,
            part_number: 'STM32F103C8T6',
            brand: 'ST',
            category: 'MCU',
            risk_level: 'red',
            total_stock: 0,
            lifecycle_status: 'Active'
          }
        ]
      }
    })

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(bomApi.getBomProject).toHaveBeenCalledWith('7')
    expect(wrapper.text()).toContain('历史BOM-A')
    expect(wrapper.text()).toContain('history-a.xlsx')
    expect(wrapper.text()).toContain('高风险')
    expect(wrapper.text()).toContain('1')
    expect(wrapper.text()).toContain('STM32F103C8T6')
  })

  it('点击导出Excel报告时通过下载链接触发项目Excel导出', async () => {
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: {
          id: 7,
          project_name: '历史BOM-A',
          filename: 'history-a.xlsx',
          status: 'active',
          total_items: 1,
          items_red: 1,
          items_yellow: 0,
          items_green: 0,
          items_gray: 0,
          last_analysis_at: '2026-06-28T09:55:31'
        },
        items: []
      }
    })
    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    const link = { href: '', download: '', click: vi.fn(), remove: vi.fn(), style: {} }
    const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(link)
    const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => link)

    await wrapper.find('[data-testid="open-xlsx-report"]').trigger('click')

    expect(bomApi.getProjectRiskReportXlsxUrl).toHaveBeenCalledWith(7)
    expect(link.href).toContain('/api/risk/report/7/export.xlsx')
    expect(link.download).toBe('历史BOM-A-风险报告.xlsx')
    expect(link.click).toHaveBeenCalled()
    expect(link.remove).toHaveBeenCalled()

    createElementSpy.mockRestore()
    appendChildSpy.mockRestore()
  })

  it('点击导出HTML报告时打开项目报告导出页面', async () => {
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: {
          id: 7,
          project_name: '历史BOM-A',
          filename: 'history-a.xlsx',
          status: 'active',
          total_items: 1,
          items_red: 1,
          items_yellow: 0,
          items_green: 0,
          items_gray: 0,
          last_analysis_at: '2026-06-28T09:55:31'
        },
        items: []
      }
    })

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.find('[data-testid="open-html-report"]').trigger('click')

    expect(bomApi.getProjectRiskReportHtmlUrl).toHaveBeenCalledWith(7)
    expect(window.open).toHaveBeenCalledWith('/api/risk/report/7/export.html', '_blank', 'noopener')
  })

  it('路由参数变化时重新加载对应 BOM，避免 keep-alive 缓存旧项目', async () => {
    bomApi.getProjectRiskReport.mockResolvedValue({ data: null })
    bomApi.getBomProject.mockImplementation((id) => Promise.resolve({
      data: {
        project: {
          id: Number(id),
          project_name: `历史BOM-${id}`,
          filename: `history-${id}.xlsx`,
          status: 'active',
          total_items: 1,
          items_red: Number(id),
          items_yellow: 0,
          items_green: 0,
          items_gray: 0,
          last_analysis_at: '2026-06-28T09:55:31'
        },
        items: [
          {
            id: Number(id) * 10,
            row_number: 1,
            part_number: `PART-${id}`,
            brand: 'ST',
            category: 'MCU',
            risk_level: 'red',
            total_stock: 0,
            lifecycle_status: 'Active'
          }
        ]
      }
    }))

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(bomApi.getBomProject).toHaveBeenLastCalledWith('7')
    expect(wrapper.text()).toContain('历史BOM-7')
    expect(wrapper.text()).toContain('PART-7')

    mockRoute.params.id = '8'
    await nextTick()
    await flushPromises()

    expect(bomApi.getBomProject).toHaveBeenLastCalledWith('8')
    expect(wrapper.text()).toContain('历史BOM-8')
    expect(wrapper.text()).toContain('PART-8')
    expect(wrapper.text()).not.toContain('历史BOM-7')
  })

  it('根据行动队列传入的 item_ids 标记命中的 BOM 物料', async () => {
    mockRoute.query = { item_ids: '99,100' }
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: {
          id: 7,
          project_name: '历史BOM-A',
          filename: 'history-a.xlsx',
          status: 'active',
          total_items: 2,
          items_red: 1,
          items_yellow: 0,
          items_green: 1,
          items_gray: 0,
          last_analysis_at: '2026-06-28T09:55:31'
        },
        items: [
          { id: 99, row_number: 1, part_number: 'STM32F103C8T6', brand: 'ST', category: 'MCU', risk_level: 'red' },
          { id: 101, row_number: 2, part_number: 'SAFE-PART', brand: 'TDK', category: 'MLCC', risk_level: 'green' }
        ]
      }
    })

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('行动追踪物料')
    expect(text).toContain('命中 1 个')
    expect(text).toContain('STM32F103C8T6')
    expect(text).toContain('行动命中')
  })

  it('展示项目风险行动报告：风险概况、品类风险、行情来源和业务建议', async () => {
    bomApi.getProjectRiskReport.mockResolvedValue({
      data: {
        project: { id: 7, project_name: '历史BOM-A', filename: 'history-a.xlsx', status: 'active', total_items: 1, items_red: 1, items_yellow: 0, items_green: 0, items_gray: 0, last_analysis_at: '2026-06-28T09:55:31' },
        risk_summary: { total_items: 1, red: 1, yellow: 0, green: 0, gray: 0, risk_rate: 100, has_urgent: true },
        category_risk: [{ category: 'MCU', total: 1, red: 1, yellow: 0 }],
        intel_sources: { active_event_count: 22, source_count: 3, sources: ['lcsc_jlcsearch', 'guanxintai_search', 'xinshiyeye_wechat'], registered_media_sources: 8, recent_runs: [] },
        actions: { urgent: ['STM32F103C8T6（ST）：行情紧缺，建议锁单或评估GD32替代'], watch: [], all_suggestions_count: 1 },
        high_risk_items: [{
          id: 99,
          part_number: 'STM32F103C8T6',
          brand: 'ST',
          category: 'MCU',
          risk_level: 'red',
          risk_reason: 'MCU缺货 | [行情] STM32系列MCU交期延长',
          suggestion: '行情紧缺，建议锁单或评估GD32替代',
          total_stock: 0,
          supplier_count: 1,
          lead_time_days: 52,
          unit_price: 12.34,
          lifecycle_status: 'Active',
          supply_sources_summary: 'lcsc:库存0',
          v32_evidence_summary: 'MCU当前为red风险，主导轨道为demand_supply。',
          v32_action_suggestion: '优先核查MCU库存、供应商报价和替代料，必要时提前锁单。',
          v32_evidence_chain: [
            { type: 'market_event', title: 'STM32系列MCU交期延长' },
            { type: 'dual_track', title: '双轨风险评分', primary_track: 'demand_supply' }
          ]
        }],
        last_analysis_at: '2026-06-28T09:55:31'
      }
    })
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: {
          id: 7,
          project_name: '历史BOM-A',
          filename: 'history-a.xlsx',
          status: 'active',
          total_items: 1,
          items_red: 1,
          items_yellow: 0,
          items_green: 0,
          items_gray: 0,
          last_analysis_at: '2026-06-28T09:55:31'
        },
        items: [
          {
            id: 99,
            row_number: 1,
            part_number: 'STM32F103C8T6',
            brand: 'ST',
            category: 'MCU',
            risk_level: 'red',
            total_stock: 0,
            lifecycle_status: 'Active'
          }
        ]
      }
    })

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    // 风险行动报告板块应可见
    expect(wrapper.text()).toContain('风险行动报告')
    expect(wrapper.text()).toContain('风险率')
    expect(wrapper.text()).toContain('100%')
    expect(wrapper.text()).toContain('行情来源')
    expect(wrapper.text()).toContain('lcsc_jlcsearch')
    expect(wrapper.text()).toContain('业务建议')
    expect(wrapper.text()).toContain('锁单')
    expect(wrapper.text()).toContain('依据链')
    expect(wrapper.text()).toContain('MCU当前为red风险')
    expect(wrapper.text()).toContain('STM32系列MCU交期延长')
    expect(wrapper.text()).toContain('双轨风险评分')
  })

  it('在风险报告高风险物料中展示行情证据与风险标签', async () => {
    bomApi.getProjectRiskReport.mockResolvedValue({
      data: {
        project: { id: 7, project_name: '历史BOM-A', filename: 'history-a.xlsx', status: 'active', total_items: 1, items_red: 1, items_yellow: 0, items_green: 0, items_gray: 0, last_analysis_at: '2026-06-28T09:55:31' },
        risk_summary: { total_items: 1, red: 1, yellow: 0, green: 0, gray: 0, risk_rate: 100, has_urgent: true },
        category_risk: [],
        intel_sources: { active_event_count: 1, source_count: 1, sources: ['采购邮箱'], registered_media_sources: 8, recent_runs: [] },
        actions: { urgent: ['提前锁单'], watch: [], all_suggestions_count: 1 },
        high_risk_items: [{
          id: 99,
          part_number: 'C3216X5R1A476M160AC',
          brand: 'TDK',
          category: 'high_cap_mlcc',
          risk_level: 'red',
          risk_reason: '高容MLCC缺货涨价',
          total_stock: 0,
          supplier_count: 1,
          lead_time_days: 112,
          unit_price: 1.68,
          lifecycle_status: 'Active',
          supply_sources_summary: 'lcsc:库存0',
          supply_risk_tags: 'stockout,lead_time_long,lifecycle_risk',
          procurement_suggestion: '建议提前锁单并准备替代料',
          market_evidence: [
            {
              id: 3,
              title: 'TDK高容MLCC涨价缺货',
              source_name: '采购邮箱',
              event_type: 'price_increase',
              severity: 'high',
              confidence: 0.92,
              price_impact_pct: 18,
              lead_time_impact_weeks: 16
            }
          ]
        }],
        last_analysis_at: '2026-06-28T09:55:31'
      }
    })
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: { id: 7, project_name: '历史BOM-A', filename: 'history-a.xlsx', status: 'active', total_items: 1, items_red: 1, items_yellow: 0, items_green: 0, items_gray: 0 },
        items: [{ id: 99, row_number: 1, part_number: 'C3216X5R1A476M160AC', brand: 'TDK', category: 'high_cap_mlcc', risk_level: 'red' }]
      }
    })

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('风险标签')
    expect(text).toContain('库存断供')
    expect(text).toContain('交期过长')
    expect(text).toContain('生命周期风险')
    expect(text).toContain('行情证据')
    expect(text).toContain('TDK高容MLCC涨价缺货')
    expect(text).toContain('采购邮箱')
    expect(text).toContain('涨价')
    expect(text).toContain('影响 18% / 16周')
    expect(text).toContain('建议提前锁单并准备替代料')
  })

  it('可从风险报告行情证据当前页打开市场事件详情', async () => {
    bomApi.getProjectRiskReport.mockResolvedValue({
      data: {
        project: { id: 7, project_name: '历史BOM-A', filename: 'history-a.xlsx', status: 'active', total_items: 1, items_red: 1, items_yellow: 0, items_green: 0, items_gray: 0 },
        risk_summary: { total_items: 1, red: 1, yellow: 0, green: 0, gray: 0, risk_rate: 100, has_urgent: true },
        category_risk: [],
        intel_sources: { active_event_count: 1, source_count: 1, sources: ['采购邮箱'], registered_media_sources: 8, recent_runs: [] },
        actions: { urgent: ['提前锁单'], watch: [], all_suggestions_count: 1 },
        high_risk_items: [{
          id: 99,
          part_number: 'C3216X5R1A476M160AC',
          brand: 'TDK',
          category: 'high_cap_mlcc',
          risk_level: 'red',
          market_evidence: [{ id: 3, title: 'TDK高容MLCC涨价缺货', source_name: '采购邮箱', event_type: 'price_increase', severity: 'high', confidence: 0.92, price_impact_pct: 18, lead_time_impact_weeks: 16 }]
        }]
      }
    })
    bomApi.getBomProject.mockResolvedValue({
      data: {
        project: { id: 7, project_name: '历史BOM-A', filename: 'history-a.xlsx', status: 'active', total_items: 1, items_red: 1, items_yellow: 0, items_green: 0, items_gray: 0 },
        items: [{ id: 99, row_number: 1, part_number: 'C3216X5R1A476M160AC', brand: 'TDK', category: 'high_cap_mlcc', risk_level: 'red' }]
      }
    })
    eventApi.getEvent.mockResolvedValue({ data: { id: 3, raw_title: 'TDK高容MLCC涨价缺货详情', severity: 'high', confidence: 0.92 } })
    eventApi.getEventImpact.mockResolvedValue({ data: { project_count: 1, item_count: 1, projects: [] } })
    eventApi.getEventSourceSignal.mockResolvedValue({ data: null })

    const wrapper = mount(BomProjectDetail, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.find('[data-testid="open-market-evidence-3"]').trigger('click')
    await flushPromises()

    expect(eventApi.getEvent).toHaveBeenCalledWith(3)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('TDK高容MLCC涨价缺货详情')
  })
})
