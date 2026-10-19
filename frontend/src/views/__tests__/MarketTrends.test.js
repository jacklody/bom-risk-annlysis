import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MarketTrends from '../MarketTrends.vue'
import * as api from '../../api/marketTrends'
import * as eventApi from '../../api/events'

vi.mock('../../api/marketTrends', () => ({
  getTrendSummary: vi.fn(),
  getTrendTimeline: vi.fn(),
  getTrendValidation: vi.fn(),
  getTrendActions: vi.fn(),
  createPredictionValidationRecord: vi.fn()
}))

vi.mock('../../api/events', () => ({
  getEvent: vi.fn(),
  getEventImpact: vi.fn(),
  getEventSourceSignal: vi.fn()
}))

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), success: vi.fn() }
}))

const stubs = {
  'el-card': { template: '<div class="el-card"><slot name="header" /><slot /></div>' },
  'el-button': {
    props: ['loading', 'size', 'type', 'disabled'],
    emits: ['click'],
    template: '<button v-bind="$attrs" :disabled="loading || disabled" @click="$emit(\'click\', $event)"><slot /></button>'
  },
  'el-select': {
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
    template: '<select v-bind="$attrs" :value="modelValue" @change="$emit(\'update:modelValue\', Number($event.target.value)); $emit(\'change\', Number($event.target.value))"><slot /></select>'
  },
  'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
  'el-tag': { props: ['type'], template: '<span><slot /></span>' },
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' }
}

function mockData({ empty = false } = {}) {
  api.getTrendSummary.mockResolvedValue({
    data: empty
      ? {
          active_event_count: 0,
          high_severity_event_count: 0,
          new_events_7d: 0,
          new_events_30d: 0,
          affected_project_count: 0,
          affected_item_count: 0,
          red_item_count: 0,
          yellow_item_count: 0,
          action_count: 0,
          generated_at: '2026-06-27T00:00:00+00:00'
        }
      : {
          active_event_count: 3,
          high_severity_event_count: 1,
          new_events_7d: 2,
          new_events_30d: 3,
          affected_project_count: 1,
          affected_item_count: 2,
          red_item_count: 1,
          yellow_item_count: 1,
          action_count: 2,
          generated_at: '2026-06-27T00:00:00+00:00'
        }
  })
  api.getTrendTimeline.mockResolvedValue({
    data: empty
      ? { days: 30, daily_events: [], brand_rank: [], category_rank: [], severity_counts: {} }
      : {
          days: 30,
          daily_events: [{ date: '2026-06-27', event_count: 2, high_severity_event_count: 1 }],
          brand_rank: [{ brand: 'TDK', event_count: 2, project_count: 1, item_count: 2 }],
          category_rank: [{ category: 'high_cap_mlcc', event_count: 2, project_count: 1, item_count: 2 }],
          severity_counts: { critical: 1, high: 1, medium: 1, unknown: 1 }
        }
  })
  api.getTrendValidation.mockResolvedValue({
    data: empty
      ? { risk_hit_count: 0, not_hit_yet_count: 0, needs_review_count: 0, hit_rate: 0, review_needed_rate: 0, events: [], recent_records: [] }
      : {
          risk_hit_count: 1,
          not_hit_yet_count: 1,
          needs_review_count: 1,
          hit_rate: 0.33,
          review_needed_rate: 0.33,
          events: [
            { event_id: 1, raw_title: 'TDK高容MLCC涨价', brand: 'TDK', category: 'high_cap_mlcc', event_type: 'price_increase', severity: 'high', validation_status: 'risk_hit', project_count: 1, item_count: 2, trigger_reason: '严重度 high，命中 1 个项目 2 个物料' }
          ],
          recent_records: [
            {
              id: 8,
              event_id: 1,
              validation_status: 'risk_hit',
              outcome: 'confirmed_hit',
              reviewer: '采购A',
              notes: 'BOM 中两颗高容 MLCC 已确认受影响',
              affected_project_count: 1,
              affected_item_count: 2,
              created_at: '2026-06-29T10:00:00+00:00'
            }
          ]
        }
  })
  api.getTrendActions.mockResolvedValue({
    data: empty
      ? { actions: [] }
      : {
          actions: [
            {
              id: 'review_event:1',
              action_type: 'review_event',
              priority: 'high',
              title: '建议复核高风险事件',
              reason: '事件严重度较高',
              trigger_reason: '严重度 high，已命中 1 个项目 2 个物料',
              brand: 'TDK',
              category: 'high_cap_mlcc',
              event_ids: [1],
              project_ids: [7],
              item_ids: [101, 102],
              project_count: 1,
              item_count: 2,
              target_route: '/events',
              target_query: { event_ids: '1', project_ids: '7', item_ids: '101,102' }
            }
          ]
        }
  })
}

function mountPage() {
  return mount(MarketTrends, { global: { stubs } })
}

describe('MarketTrends', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    push.mockReset()
  })

  it('loads summary timeline validation and action queue', async () => {
    mockData()
    const wrapper = mountPage()
    await flushPromises()

    expect(api.getTrendSummary).toHaveBeenCalled()
    expect(api.getTrendTimeline).toHaveBeenCalledWith({ days: 30 })
    expect(api.getTrendValidation).toHaveBeenCalled()
    expect(api.getTrendActions).toHaveBeenCalled()
    expect(wrapper.text()).toContain('趋势预警')
    expect(wrapper.text()).toContain('活跃事件')
    expect(wrapper.text()).toContain('TDK')
    expect(wrapper.text()).toContain('严重度分布')
    expect(wrapper.text()).toContain('严重 1')
    expect(wrapper.text()).toContain('高 1')
    expect(wrapper.text()).toContain('中 1')
    expect(wrapper.text()).toContain('未知 1')
    expect(wrapper.text()).toContain('预测验证')
    expect(wrapper.text()).toContain('复盘记录')
    expect(wrapper.text()).toContain('命中确认')
    expect(wrapper.text()).toContain('采购A')
    expect(wrapper.text()).toContain('BOM 中两颗高容 MLCC 已确认受影响')
    expect(wrapper.text()).toContain('建议复核高风险事件')
    expect(wrapper.text()).toContain('TDK高容MLCC涨价')
    expect(wrapper.text()).not.toContain('事件 1')
    expect(wrapper.text()).toContain('触发条件：严重度 high，已命中 1 个项目 2 个物料')
    expect(wrapper.text()).toContain('影响原则：事件风险已命中 BOM 物料，需按影响项目数、物料数和风险等级确认采购优先级。')
  })

  it('refreshes all data when clicking refresh', async () => {
    mockData()
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="trends-refresh"]').trigger('click')
    await flushPromises()

    expect(api.getTrendSummary).toHaveBeenCalledTimes(2)
    expect(api.getTrendActions).toHaveBeenCalledTimes(2)
  })

  it('reloads timeline when days changes', async () => {
    mockData()
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="trends-days"]').setValue('7')
    await flushPromises()

    expect(api.getTrendTimeline).toHaveBeenLastCalledWith({ days: 7 })
  })

  it('shows empty state for no trends and no actions', async () => {
    mockData({ empty: true })
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('暂无趋势数据')
    expect(wrapper.text()).toContain('暂无主动预警动作')
  })

  it('opens market event detail in current page from action queue', async () => {
    mockData()
    eventApi.getEvent.mockResolvedValue({ data: { id: 1, raw_title: 'TDK高容MLCC涨价', severity: 'high', confidence: 0.91 } })
    eventApi.getEventImpact.mockResolvedValue({ data: { project_count: 1, item_count: 2, projects: [] } })
    eventApi.getEventSourceSignal.mockResolvedValue({ data: null })
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="action-open-events"]').trigger('click')
    await flushPromises()

    expect(eventApi.getEvent).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('TDK高容MLCC涨价')
  })

  it('待复盘事件可打开事件源头详情', async () => {
    mockData()
    eventApi.getEvent.mockResolvedValue({ data: { id: 1, raw_title: 'TDK高容MLCC涨价源头', severity: 'high', confidence: 0.91 } })
    eventApi.getEventImpact.mockResolvedValue({ data: { project_count: 1, item_count: 2, projects: [] } })
    eventApi.getEventSourceSignal.mockResolvedValue({ data: null })
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="validation-open-event-1"]').trigger('click')
    await flushPromises()

    expect(eventApi.getEvent).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('TDK高容MLCC涨价源头')
    expect(wrapper.text()).toContain('影响触发原则')
  })

  it('jumps to events page with traceable context from action queue', async () => {
    mockData()
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="action-go-events"]').trigger('click')

    expect(push).toHaveBeenCalledWith({
      path: '/events',
      query: { eventId: 1, event_ids: '1', project_ids: '7', item_ids: '101,102' }
    })
  })

  it('creates prediction validation record with reviewer and notes from validation form', async () => {
    mockData()
    api.createPredictionValidationRecord.mockResolvedValue({ data: { id: 9 } })
    const wrapper = mountPage()
    await flushPromises()

    await wrapper.find('[data-testid="validation-reviewer"]').setValue('采购复盘张三')
    await wrapper.find('[data-testid="validation-notes"]').setValue('代理商确认两颗高容 MLCC 已受影响')
    await wrapper.find('[data-testid="validation-confirm-hit"]').trigger('click')
    await flushPromises()

    expect(api.createPredictionValidationRecord).toHaveBeenCalledWith(1, {
      outcome: 'confirmed_hit',
      reviewer: '采购复盘张三',
      notes: '代理商确认两颗高容 MLCC 已受影响'
    })
    expect(api.getTrendValidation).toHaveBeenCalledTimes(2)
  })
})
