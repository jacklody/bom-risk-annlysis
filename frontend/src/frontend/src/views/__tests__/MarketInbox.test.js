import { mount, flushPromises } from '@vue/test-utils'
import MarketInbox from '../MarketInbox.vue'
import * as api from '../../api/marketInbox'
import * as eventApi from '../../api/events'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }
}))

vi.mock('../../api/marketInbox', () => ({
  submitMarketNotice: vi.fn(),
  listReviewQueue: vi.fn(() => Promise.resolve({ data: { signals: [] } })),
  reviewSignal: vi.fn(() => Promise.resolve({}))
}))

vi.mock('../../api/events', () => ({
  getEvent: vi.fn(),
  getEventImpact: vi.fn(),
  getEventSourceSignal: vi.fn()
}))

const globalStubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-alert': { props: ['title', 'description'], template: '<div>{{ title }} {{ description }}</div>' },
  'el-tag': { props: ['type'], template: '<span><slot /></span>' },
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' },
  'el-button': { props: ['loading', 'size'], inheritAttrs: false, template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>' },
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
  'el-table': { props: ['data'], template: '<table><tbody><tr v-for="row in data" :key="row.id"><td>{{ row.brand }}</td><td>{{ row.category }}</td><td>{{ row.review_status }}</td><td>{{ row.raw_notice_title }}</td><td>{{ row.raw_notice_source_name }}</td><td>{{ row.raw_notice_excerpt }}</td></tr><slot /></tbody></table>' },
  'el-table-column': {
    template: '<td><slot :row="{ id: 1, brand: \'TDK\', category: \'high_cap_mlcc\', mpn: \'C3225X5R1A226M250AC\', event_type: \'price_increase\', confidence: 0.72, review_status: \'confirmed\', generated_event_id: 88, raw_notice_title: \'微信群MLCC涨价线索\', raw_notice_source_type: \'wechat\', raw_notice_source_name: \'采购微信群\', raw_notice_excerpt: \'微信群里转发：TDK MLCC 可能下月涨价，但暂未看到原厂正式通知。\' }" /></td>'
  }
}

describe('MarketInbox', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.listReviewQueue.mockResolvedValue({ data: { signals: [] } })
  })

  it('submits raw notice text and renders extracted scan result', async () => {
    api.submitMarketNotice.mockResolvedValueOnce({
      data: {
        notice: { id: 1, parse_status: 'parsed', title: 'TDK高容MLCC缺货涨价通知' },
        signals: [{ id: 1, brand: 'TDK', category: 'high_cap_mlcc', review_status: 'auto_confirmed', confidence: 0.93 }],
        events_created: 1,
        events_skipped: 0,
        scan_summary: { projects_scanned: 2, affected_projects: 1, top_impacted_items: [{ mpn: 'C3225X5R1A226M250AC', project_name: '控制板A', risk_level: 'red' }] }
      }
    })

    const wrapper = mount(MarketInbox, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.find('[data-testid="market-notice-title"]').setValue('TDK高容MLCC缺货涨价通知')
    await wrapper.find('[data-testid="market-notice-raw-text"]').setValue('TDK 高容MLCC 缺货，涨价 10%-20%，交期 16 周')
    await wrapper.find('[data-testid="market-notice-submit"]').trigger('click')
    await flushPromises()

    expect(api.submitMarketNotice).toHaveBeenCalledWith(expect.objectContaining({
      title: 'TDK高容MLCC缺货涨价通知',
      raw_text: 'TDK 高容MLCC 缺货，涨价 10%-20%，交期 16 周',
      auto_scan: true
    }))
    expect(wrapper.find('[data-testid="market-inbox-result"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('TDK')
    expect(wrapper.text()).toContain('high_cap_mlcc')
    expect(wrapper.text()).toContain('受影响项目 1 个')
  })

  it('submits reviewer and notes when confirming a review signal', async () => {
    api.listReviewQueue.mockResolvedValue({
      data: {
        signals: [{
          id: 1,
          brand: 'TDK',
          category: 'high_cap_mlcc',
          review_status: 'need_review',
          raw_notice_title: '微信群MLCC涨价线索'
        }]
      }
    })

    const wrapper = mount(MarketInbox, { global: { stubs: globalStubs } })
    await flushPromises()
    await wrapper.find('[data-testid="reviewer-input"]').setValue('采购张三')
    await wrapper.find('[data-testid="review-notes-input"]').setValue('已与代理商电话确认涨价')
    await wrapper.find('[data-testid="review-confirm"]').trigger('click')
    await flushPromises()

    expect(api.reviewSignal).toHaveBeenCalledWith(1, {
      action: 'confirm',
      notes: '已与代理商电话确认涨价',
      reviewer: '采购张三'
    })
  })

  it('shows review queue status summary counts', async () => {
    api.listReviewQueue.mockResolvedValue({
      data: {
        summary: { need_review: 2, observation: 1, confirmed: 4, rejected: 3, queue_total: 3 },
        signals: []
      }
    })

    const wrapper = mount(MarketInbox, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.text()).toContain('待处理 3')
    expect(wrapper.text()).toContain('待复核 2')
    expect(wrapper.text()).toContain('观察中 1')
    expect(wrapper.text()).toContain('已确认 4')
    expect(wrapper.text()).toContain('已驳回 3')
  })

  it('shows review queue with need_review signals and raw notice context', async () => {
    api.listReviewQueue.mockResolvedValue({
      data: {
        signals: [{
          id: 1,
          brand: 'TDK',
          category: 'high_cap_mlcc',
          mpn: 'C3225X5R1A226M250AC',
          event_type: 'price_increase',
          confidence: 0.72,
          review_status: 'need_review',
          raw_notice_title: '微信群MLCC涨价线索',
          raw_notice_source_type: 'wechat',
          raw_notice_source_name: '采购微信群',
          raw_notice_excerpt: '微信群里转发：TDK MLCC 可能下月涨价，但暂未看到原厂正式通知。'
        }]
      }
    })

    const wrapper = mount(MarketInbox, { global: { stubs: globalStubs } })
    await flushPromises()
    expect(wrapper.text()).toContain('待复核队列')
    expect(wrapper.text()).toContain('need_review')
    expect(wrapper.text()).toContain('high_cap_mlcc')
    expect(wrapper.text()).toContain('微信群MLCC涨价线索')
    expect(wrapper.text()).toContain('采购微信群')
    expect(wrapper.text()).toContain('暂未看到原厂正式通知')
  })

  it('opens signal trace drawer and can open generated market event in current page', async () => {
    api.listReviewQueue.mockResolvedValue({
      data: {
        signals: [{
          id: 1,
          brand: 'TDK',
          category: 'high_cap_mlcc',
          mpn: 'C3225X5R1A226M250AC',
          event_type: 'price_increase',
          confidence: 0.72,
          review_status: 'confirmed',
          generated_event_id: 88,
          raw_notice_title: '微信群MLCC涨价线索',
          raw_notice_source_type: 'wechat',
          raw_notice_source_name: '采购微信群',
          raw_notice_excerpt: '微信群里转发：TDK MLCC 可能下月涨价，但暂未看到原厂正式通知。'
        }]
      }
    })

    eventApi.getEvent.mockResolvedValue({ data: { id: 88, raw_title: '已生成TDK市场事件', severity: 'high', confidence: 0.91 } })
    eventApi.getEventImpact.mockResolvedValue({ data: { project_count: 1, item_count: 2, projects: [] } })
    eventApi.getEventSourceSignal.mockResolvedValue({ data: null })

    const wrapper = mount(MarketInbox, { global: { stubs: globalStubs } })
    await flushPromises()

    await wrapper.find('[data-testid="open-signal-trace"]').trigger('click')

    expect(wrapper.text()).toContain('信号溯源详情')
    expect(wrapper.text()).toContain('信号 #1')
    expect(wrapper.text()).toContain('原始通知：微信群MLCC涨价线索')
    expect(wrapper.text()).toContain('采购微信群')

    await wrapper.find('[data-testid="open-generated-event"]').trigger('click')
    await flushPromises()

    expect(eventApi.getEvent).toHaveBeenCalledWith(88)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('已生成TDK市场事件')
  })

  it('can still navigate to generated market event library from trace drawer', async () => {
    api.listReviewQueue.mockResolvedValue({
      data: {
        signals: [{
          id: 1,
          brand: 'TDK',
          category: 'high_cap_mlcc',
          generated_event_id: 88,
          raw_notice_title: '微信群MLCC涨价线索',
          raw_notice_source_name: '采购微信群',
          raw_notice_excerpt: '微信群里转发：TDK MLCC 可能下月涨价。'
        }]
      }
    })

    const wrapper = mount(MarketInbox, { global: { stubs: globalStubs } })
    await flushPromises()

    await wrapper.find('[data-testid="open-signal-trace"]').trigger('click')
    await wrapper.find('[data-testid="go-generated-event"]').trigger('click')

    expect(push).toHaveBeenCalledWith({ path: '/events', query: { eventId: 88 } })
  })
})
