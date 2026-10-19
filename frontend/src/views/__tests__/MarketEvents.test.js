import { h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import MarketEvents from '../MarketEvents.vue'
import * as api from '../../api/events'

let routeQuery = {}
const push = vi.fn()

vi.mock('../../api/events', () => ({
  listEvents: vi.fn(),
  getEvent: vi.fn(),
  collectEvents: vi.fn(),
  updateEventStatus: vi.fn(),
  getEventImpact: vi.fn(),
  getEventSourceSignal: vi.fn()
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: routeQuery }),
  useRouter: () => ({ push })
}))

const sampleEvent = {
  id: 1,
  brand: 'TDK',
  category: 'high_cap_mlcc',
  event_type: 'price_increase',
  severity: 'high',
  confidence: 0.91,
  source_name: 'TDK代理商邮件',
  source_url: 'mail://tdk-notice-001',
  raw_title: 'TDK高容MLCC缺货涨价通知',
  raw_text_excerpt: 'TDK 高容MLCC 缺货，预计涨价 10%-20%，交期延长至 16 周',
  estimated_lead_time_impact_weeks: 16,
  estimated_price_impact_pct: 20,
  cross_validated: 0,
  created_at: '2026-06-27T10:00:00+00:00'
}

const eventWithEmptyAndZeroValues = {
  id: 2,
  brand: '',
  category: null,
  event_type: 'shortage',
  severity: 'unknown',
  confidence: 0,
  source_name: '',
  source_url: '',
  raw_title: null,
  raw_text_excerpt: '',
  estimated_lead_time_impact_weeks: 0,
  estimated_price_impact_pct: 0,
  cross_validated: 0,
  created_at: null
}

const inactiveEvent = {
  ...sampleEvent,
  id: 3,
  is_active: 0,
  raw_title: '停用中的市场事件'
}

const secondEvent = {
  ...sampleEvent,
  id: 4,
  brand: 'Murata',
  category: 'mlcc',
  raw_title: 'Murata 事件'
}

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

let currentRows = []

const globalStubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-button': {
    props: ['loading', 'size', 'type', 'link', 'disabled'],
    emits: ['click'],
    template: '<button :disabled="loading || disabled" @click="$emit(\'click\', $event)"><slot /></button>'
  },
  'el-input': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  'el-select': {
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>'
  },
  'el-option': { props: ['label', 'value'], template: '<option :value="value">{{ label }}</option>' },
  'el-tag': { props: ['type'], template: '<span><slot /></span>' },
  'el-drawer': {
    props: ['modelValue', 'title'],
    template: '<div v-if="modelValue"><h3>{{ title }}</h3><slot /></div>'
  },
  'el-table': {
    props: ['data'],
    emits: ['row-click'],
    setup(props, { slots, emit }) {
      return () => {
        currentRows = props.data
        return h('table', [
          h(
            'tbody',
            props.data.map((row) =>
              h('tr', { class: 'market-event-row', onClick: () => emit('row-click', row) }, slots.default?.())
            )
          )
        ])
      }
    }
  },
  'el-table-column': {
    inheritAttrs: false,
    props: ['prop', 'label'],
    setup(props, { slots }) {
      return () => currentRows.map((row) => h('tr', { key: `${props.prop || props.label}-${row.id}` }, [h('td', slots.default ? slots.default({ row }) : row[props.prop])]))
    }
  }
}

function mountMarketEvents() {
  return mount(MarketEvents, {
    global: {
      stubs: globalStubs,
      directives: { loading: {} }
    }
  })
}

describe('MarketEvents', () => {
  beforeEach(() => {
    routeQuery = {}
    push.mockReset()
    vi.clearAllMocks()
    api.listEvents.mockResolvedValue({ data: { total: 1, events: [sampleEvent] } })
    api.getEvent.mockResolvedValue({ data: sampleEvent })
    api.collectEvents.mockResolvedValue({ data: { collected: 1, events: [sampleEvent] } })
    api.getEventImpact.mockResolvedValue({
      data: {
        event_id: 1,
        project_count: 1,
        item_count: 2,
        risk_counts: { red: 1, yellow: 1, green: 0, gray: 0 },
        projects: [{ project_id: 10, project_name: '真实项目A', affected_item_count: 2, highest_risk_level: 'red' }]
      }
    })
    api.getEventSourceSignal.mockResolvedValue({
      data: {
        event_id: 1,
        signal: {
          review_status: 'confirmed',
          reviewed_by: 'purchaser',
          review_notes: '电话复核属实',
          evidence_text: '供应商确认缺货涨价'
        },
        raw_notice: {
          source_type: 'email',
          source_name: '采购邮箱',
          sender: 'buyer@example.com',
          title: 'TDK MLCC 缺货涨价邮件',
          raw_text_excerpt: '供应商确认 TDK 高容 MLCC 缺货，交期 16 周。'
        }
      }
    })
    api.updateEventStatus.mockResolvedValue({ data: { event: { ...sampleEvent, is_active: 0 }, message: '事件已停用' } })
  })

  it('loads and renders market events', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    expect(api.listEvents).toHaveBeenCalledWith({ active_status: 'active' })
    expect(wrapper.text()).toContain('市场事件')
    expect(wrapper.text()).toContain('TDK')
    expect(wrapper.text()).toContain('high_cap_mlcc')
    expect(wrapper.text()).toContain('TDK高容MLCC缺货涨价通知')
  })

  it('loads traceable event ids from route query when opened by action queue', async () => {
    routeQuery = { event_ids: '1,4', project_ids: '7', item_ids: '101,102' }

    mountMarketEvents()
    await flushPromises()

    expect(api.listEvents).toHaveBeenCalledWith({ active_status: 'all', event_ids: '1,4' })
  })

  it('automatically opens event detail from eventId route query', async () => {
    routeQuery = { eventId: '88' }
    api.listEvents.mockResolvedValue({ data: { total: 0, events: [] } })
    api.getEvent.mockResolvedValue({ data: { ...sampleEvent, id: 88, raw_title: '自动打开事件' } })

    const wrapper = mountMarketEvents()
    await flushPromises()

    expect(api.getEvent).toHaveBeenCalledWith('88')
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('自动打开事件')
  })

  it('shows action trace context and jumps to traced project', async () => {
    routeQuery = { event_ids: '1,4', project_ids: '7,8', item_ids: '101,102' }

    const wrapper = mountMarketEvents()
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('行动追踪上下文')
    expect(text).toContain('事件 2 个')
    expect(text).toContain('项目 2 个')
    expect(text).toContain('物料 2 个')

    await wrapper.find('[data-testid="trace-project-7"]').trigger('click')

    expect(push).toHaveBeenCalledWith({
      path: '/projects/7',
      query: { item_ids: '101,102' }
    })
  })

  it('queries inactive events when active status filter is changed', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-filter-active"]').setValue('inactive')
    await wrapper.find('[data-testid="events-search"]').trigger('click')
    await flushPromises()

    expect(api.listEvents).toHaveBeenLastCalledWith({ active_status: 'inactive' })
  })

  it('queries with filter parameters', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-filter-brand"]').setValue('TDK')
    await wrapper.find('[data-testid="events-filter-category"]').setValue('high_cap_mlcc')
    await wrapper.find('[data-testid="events-filter-type"]').setValue('price_increase')
    await wrapper.find('[data-testid="events-filter-severity"]').setValue('high')
    await wrapper.find('[data-testid="events-search"]').trigger('click')
    await flushPromises()

    expect(api.listEvents).toHaveBeenLastCalledWith({
      active_status: 'active',
      brand: 'TDK',
      category: 'high_cap_mlcc',
      event_type: 'price_increase',
      severity: 'high'
    })
  })

  it('opens detail drawer by clicking the row detail button without also triggering row click', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()

    expect(api.getEvent).toHaveBeenCalledTimes(1)
    expect(api.getEvent).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('TDK代理商邮件')
    expect(wrapper.text()).toContain('TDK 高容MLCC 缺货')
  })

  it('opens detail drawer by clicking a table row', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('.market-event-row').trigger('click')
    await flushPromises()

    expect(api.getEvent).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('TDK代理商邮件')
  })

  it('renders placeholders while preserving zero values in event detail', async () => {
    api.listEvents.mockResolvedValue({ data: { total: 1, events: [eventWithEmptyAndZeroValues] } })
    api.getEvent.mockResolvedValue({ data: eventWithEmptyAndZeroValues })
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('事件详情')
    expect(text).toContain('置信度：0%')
    expect(text).toContain('交期影响：0 周')
    expect(text).toContain('价格影响：0%')
    expect(text).toContain('创建时间：暂无')
    expect(text).toContain('来源链接：暂无')
  })

  it('loads impact and source signal audit context when opening detail drawer', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()

    expect(api.getEventImpact).toHaveBeenCalledWith(1)
    expect(api.getEventSourceSignal).toHaveBeenCalledWith(1)
    const text = wrapper.text()
    expect(text).toContain('影响项目')
    expect(text).toContain('真实项目A')
    expect(text).toContain('受影响物料：2')
    expect(text).toContain('复核来源')
    expect(text).toContain('confirmed')
    expect(text).toContain('purchaser')
    expect(text).toContain('电话复核属实')
    expect(text).toContain('供应商确认缺货涨价')
    expect(text).toContain('TDK MLCC 缺货涨价邮件')
    expect(text).toContain('email / 采购邮箱')
    expect(text).toContain('buyer@example.com')
    expect(text).toContain('供应商确认 TDK 高容 MLCC 缺货，交期 16 周。')
  })

  it('详情接口失败时仍使用列表事件打开基础详情', async () => {
    api.getEvent.mockRejectedValue(new Error('detail failed'))
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()

    expect(api.getEvent).toHaveBeenCalledWith(1)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('TDK高容MLCC缺货涨价通知')
  })

  it('影响项目或复核来源加载失败时仍打开事件本体详情', async () => {
    api.getEventImpact.mockRejectedValue(new Error('impact failed'))
    api.getEventSourceSignal.mockRejectedValue(new Error('source failed'))
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('事件详情')
    expect(text).toContain('TDK代理商邮件')
    expect(text).toContain('来源链接：')
    expect(text).toContain('mail://tdk-notice-001')
    expect(text).toContain('风险等级：高')
    expect(text).toContain('触发条件：严重度 高，置信度 91%，交期影响 16 周，价格影响 20%')
    expect(text).toContain('暂无已记录影响项目')
    expect(text).toContain('暂无行情收件箱复核来源')
  })

  it('disables event from detail drawer and reloads list', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="events-disable"]').trigger('click')
    await flushPromises()

    expect(api.updateEventStatus).toHaveBeenCalledWith(1, { action: 'disable' })
    expect(api.listEvents.mock.calls.length).toBeGreaterThan(1)
  })

  it('enables inactive event from detail drawer and reloads list', async () => {
    api.listEvents.mockResolvedValue({ data: { total: 1, events: [inactiveEvent] } })
    api.getEvent.mockResolvedValue({ data: inactiveEvent })
    api.updateEventStatus.mockResolvedValue({ data: { event: { ...inactiveEvent, is_active: 1 }, message: '事件已启用' } })
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="events-enable"]').exists()).toBe(true)

    await wrapper.find('[data-testid="events-enable"]').trigger('click')
    await flushPromises()

    expect(api.updateEventStatus).toHaveBeenCalledWith(3, { action: 'enable' })
    expect(api.listEvents.mock.calls.length).toBeGreaterThan(1)
  })

  it('clears stale detail state immediately when opening another event', async () => {
    api.listEvents.mockResolvedValue({ data: { total: 2, events: [sampleEvent, secondEvent] } })
    const secondEventRequest = deferred()
    api.getEvent
      .mockResolvedValueOnce({ data: sampleEvent })
      .mockReturnValueOnce(secondEventRequest.promise)
    api.getEventImpact.mockResolvedValue({
      data: {
        event_id: 1,
        project_count: 1,
        item_count: 2,
        risk_counts: { red: 1, yellow: 1, green: 0, gray: 0 },
        projects: [{ project_id: 10, project_name: '真实项目A', affected_item_count: 2, highest_risk_level: 'red' }]
      }
    })
    api.getEventSourceSignal.mockResolvedValue({
      data: {
        event_id: 1,
        signal: {
          review_status: 'confirmed',
          reviewed_by: 'purchaser',
          review_notes: '电话复核属实',
          evidence_text: '供应商确认缺货涨价'
        },
        raw_notice: { source_name: '采购邮箱', title: 'TDK MLCC 缺货涨价邮件' }
      }
    })
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-detail"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('.detail-body').text()).toContain('TDK代理商邮件')
    expect(wrapper.find('.detail-body').text()).toContain('真实项目A')
    expect(wrapper.find('.detail-body').text()).toContain('电话复核属实')

    await wrapper.findAll('[data-testid="events-detail"]')[1].trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.detail-body').exists()).toBe(false)

    secondEventRequest.resolve({ data: secondEvent })
    await flushPromises()
    expect(wrapper.text()).toContain('Murata')
  })

  it('collects events and reloads list', async () => {
    const wrapper = mountMarketEvents()
    await flushPromises()

    await wrapper.find('[data-testid="events-collect"]').trigger('click')
    await flushPromises()

    expect(api.collectEvents).toHaveBeenCalled()
    expect(api.listEvents.mock.calls.length).toBeGreaterThan(1)
    expect(api.listEvents).toHaveBeenLastCalledWith({ active_status: 'active' })
  })
})
