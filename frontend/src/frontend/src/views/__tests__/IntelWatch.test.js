import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import IntelWatch from '../IntelWatch.vue'

const { collectMediaSourceMock } = vi.hoisted(() => ({
  collectMediaSourceMock: vi.fn((sourceId) => Promise.resolve({
    data: sourceId
      ? { source_id: sourceId, articles_crawled: 2, signals_parsed: 2, events_created: 1 }
      : { articles_crawled: 4, signals_parsed: 3, events_created: 2, skipped_count: 2, skipped_sources: [{ source_id: 'xinshiyeye_wechat', source_status: 'waiting_for_manual_forward' }] }
  }))
}))

const { forwardArticleMock } = vi.hoisted(() => ({
  forwardArticleMock: vi.fn(() => Promise.resolve({
    data: { source_id: 'xinshiyeye_wechat', source_name: '芯师爷', signals_parsed: 1, events_created: 1 }
  }))
}))

vi.mock('../../api/intelWatch', () => ({
  submitWatch: vi.fn(() => Promise.resolve({ data: { id: 1, status: 'done' } })),
  getWatchHistory: vi.fn(() => Promise.resolve({
    data: { commands: [{ id: 1, raw_input: '关注 STM32 交期', status: 'done', research_summary: 'STM32全线紧缺', affected_project_count: 3, suggestion: '锁单并评估GD32替代', created_at: '2026-06-28T10:00:00' }] }
  }))
}))

vi.mock('../../api/events', () => ({
  listMediaSources: vi.fn(() => Promise.resolve({
    data: {
      total: 2,
      sources: [
        { source_id: 'lcsc_jlcsearch', name: '立创商城 / JLCSearch', crawler_strategy: 'api_json', channel_type: 'api_and_wechat', enabled: true, status: 'active', notes: 'API 用于库存/热词趋势' },
        { source_id: 'xinshiyeye_wechat', name: '芯师爷', crawler_strategy: 'manual_forward', channel_type: 'wechat_mp', enabled: true, status: 'waiting_for_manual_forward', notes: '每日芯闻/行情来源' },
        { source_id: 'semiinsights_wechat', name: '半导体行业观察', crawler_strategy: 'wechat_feed', channel_type: 'wechat_mp', enabled: true, status: 'waiting_for_configuration', notes: '需配置后接入' }
      ]
    }
  })),
  collectMediaSource: collectMediaSourceMock,
  listMediaSourceRuns: vi.fn(() => Promise.resolve({
    data: {
      total: 1,
      runs: [{ id: 1, source_id: 'lcsc_jlcsearch', status: 'success', articles_crawled: 2, signals_parsed: 2, events_created: 1, started_at: '2026-06-28T14:00:00', completed_at: '2026-06-28T14:01:00' }]
    }
  })),
  forwardArticle: forwardArticleMock
}))

vi.mock('axios', () => ({
  default: {
    get: vi.fn((url) => {
      if (url.includes('market-trends/summary')) return Promise.resolve({ data: { active_event_count: 22, high_severity_event_count: 8 } })
      if (url.includes('events')) return Promise.resolve({ data: { events: [{ id: 1, category: 'mcu', severity: 'critical' }] } })
      return Promise.resolve({ data: {} })
    })
  }
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn() }
}))

let currentRows = []
const stubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-input': {
    inheritAttrs: false,
    props: ['modelValue', 'placeholder', 'size', 'clearable', 'maxlength', 'showWordLimit', 'type', 'rows'],
    emits: ['update:modelValue'],
    template: '<textarea v-if="type === \'textarea\'" v-bind="$attrs" :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" /><input v-else v-bind="$attrs" :value="modelValue" :placeholder="placeholder" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  },
  'el-button': { props: ['loading', 'disabled'], emits: ['click'], template: '<button :disabled="loading || disabled" @click="$emit(\'click\')"><slot /></button>' },
  'el-tag': { props: ['type', 'effect'], template: '<span :data-type="type"><slot /></span>' },
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
  'el-table': { inheritAttrs: false, props: ['data', 'stripe', 'rowKey', 'maxHeight'], setup(props, { slots }) { return () => { currentRows = props.data || []; return slots.default?.() } } },
  'el-table-column': { inheritAttrs: false, props: ['prop', 'label'], setup(props, { slots }) { return () => currentRows.map(row => slots.default ? slots.default({ row }) : row[props.prop]) } }
}

describe('IntelWatch', () => {
  it('renders watch input, submits command, and shows history', async () => {
    const wrapper = mount(IntelWatch, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('情报监控')
    expect(wrapper.text()).toContain('提交关注指令')

    // should show history row
    expect(wrapper.text()).toContain('关注 STM32 交期')
    expect(wrapper.text()).toContain('已完成')
    expect(wrapper.text()).toContain('3 个项目')
  })

  it('renders media source status and triggers single-source collection', async () => {
    const wrapper = mount(IntelWatch, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('媒体源接入状态')
    expect(wrapper.text()).toContain('立创商城 / JLCSearch')
    expect(wrapper.text()).toContain('芯师爷')
    expect(wrapper.text()).toContain('api_json')
    expect(wrapper.text()).toContain('manual_forward')
    expect(wrapper.text()).toContain('可采集')
    expect(wrapper.text()).toContain('需手动转发')
    expect(wrapper.text()).toContain('待配置')

    const collectButton = wrapper.find('[data-testid="collect-source-lcsc_jlcsearch"]')
    expect(collectButton.exists()).toBe(true)
    await collectButton.trigger('click')
    await flushPromises()

    expect(collectMediaSourceMock).toHaveBeenCalledWith('lcsc_jlcsearch')
    expect(wrapper.text()).toContain('新增事件 1')
  })

  it('triggers all-source media collection and shows skipped source summary', async () => {
    const wrapper = mount(IntelWatch, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    const collectAllButton = wrapper.find('[data-testid="collect-all-media-sources"]')
    expect(collectAllButton.exists()).toBe(true)
    await collectAllButton.trigger('click')
    await flushPromises()

    expect(collectMediaSourceMock).toHaveBeenCalledWith()
    expect(wrapper.text()).toContain('跳过来源 2')
  })

  it('shows media source run history and allows pasting article from wechat source', async () => {
    const wrapper = mount(IntelWatch, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    // run history should be visible
    expect(wrapper.text()).toContain('采集运行记录')
    expect(wrapper.text()).toContain('success')
    expect(wrapper.text()).toContain('2')

    // manual paste section should be visible
    expect(wrapper.text()).toContain('手动转发文章')

    // select a manual_forward source
    const sourceSelect = wrapper.find('[data-testid="paste-source-select"]')
    expect(sourceSelect.exists()).toBe(true)

    // paste text and submit
    const pasteInput = wrapper.find('[data-testid="paste-text-input"]')
    expect(pasteInput.exists()).toBe(true)
  })

  it('opens detail drawers for media source, collection run, and watch command', async () => {
    const wrapper = mount(IntelWatch, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.find('[data-testid="open-source-detail-lcsc_jlcsearch"]').trigger('click')
    expect(wrapper.text()).toContain('媒体源详情')
    expect(wrapper.text()).toContain('立创商城 / JLCSearch')
    expect(wrapper.text()).toContain('API 用于库存/热词趋势')

    await wrapper.find('[data-testid="open-run-detail-1"]').trigger('click')
    expect(wrapper.text()).toContain('采集运行详情')
    expect(wrapper.text()).toContain('source_id：lcsc_jlcsearch')
    expect(wrapper.text()).toContain('events_created：1')

    await wrapper.find('[data-testid="open-watch-detail-1"]').trigger('click')
    expect(wrapper.text()).toContain('关注指令详情')
    expect(wrapper.text()).toContain('STM32全线紧缺')
    expect(wrapper.text()).toContain('锁单并评估GD32替代')
  })
})
