import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import RiskDashboard from '../RiskDashboard.vue'
import * as dashboardApi from '../../api/dashboard'
import * as eventApi from '../../api/events'

vi.mock('../../api/dashboard', () => ({
  getDashboardSummary: vi.fn(),
  getDashboardNotificationPreview: vi.fn(),
  dispatchDashboardNotification: vi.fn(),
  getDashboardNotificationHistory: vi.fn(),
  getDashboardNotificationChannels: vi.fn()
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
  'el-card': { template: '<section><slot name="header" /><slot /></section>' },
  'el-button': { emits: ['click'], template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>' },
  'el-table': { props: ['data'], template: '<div><slot /><div v-for="row in data" :key="row.id || row.project_id || row.category || row.source">{{ row.project_name || row.title || row.category || row.source }}</div></div>' },
  'el-table-column': { template: '<div />' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
  'el-progress': { template: '<div />' },
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' }
}

const notificationPreview = {
  channel: 'manual',
  ready: true,
  subject: 'BOM风险变化提醒：新增红色风险1项，黄色风险2项',
  body: '方案B演示项目新增红色风险1项、黄色风险2项',
  actions: [{ label: '查看风险仪表盘', target_route: '/dashboard' }]
}

const notificationHistory = {
  records: [{
    id: 101,
    channel: 'manual',
    status: 'prepared',
    idempotency_key: 'daily-risk-20260630',
    subject: 'BOM风险变化提醒：新增红色风险1项，黄色风险2项',
    delivered: false,
    failure_reason: null,
    retry_count: 0,
    delivered_at: null,
    created_at: '2026-06-30T09:00:00+00:00'
  }]
}

const notificationChannels = {
  channels: [
    { channel: 'manual', label: '人工通知', enabled: true, configured: true, external_delivery: false, status: 'available' },
    { channel: 'mock', label: '测试通道', enabled: true, configured: true, external_delivery: true, status: 'available' },
    { channel: 'email', label: '邮件', enabled: false, configured: false, external_delivery: true, status: 'not_configured' }
  ]
}

const notificationChannelsWithEmail = {
  channels: [
    { channel: 'manual', label: '人工通知', enabled: true, configured: true, external_delivery: false, status: 'available' },
    { channel: 'mock', label: '测试通道', enabled: true, configured: true, external_delivery: true, status: 'available' },
    { channel: 'email', label: '邮件', enabled: true, configured: true, external_delivery: true, status: 'available' }
  ]
}

const summaryPayload = {
  overview: {
    project_count: 2,
    high_risk_project_count: 1,
    red_item_count: 3,
    active_event_count_30d: 4,
    pending_action_count: 5
  },
  project_risks: [{ project_id: 7, project_name: '方案B演示项目', risk_counts: { red: 1, yellow: 1, green: 2, gray: 0 }, risk_rate: 50, last_analysis_at: '2026-06-29T10:00:00' }],
  category_risks: [{ category: 'MCU', red: 1, yellow: 1, green: 0, gray: 0, total: 2, event_count: 1, related_event_ids: [9], target_query: { event_ids: '9', category: 'MCU' } }],
  recent_events: [{ id: 9, title: 'ST MCU 交期延长', source_name: '采购邮箱', severity: 'high', confidence: 0.86, impact_item_count: 2 }],
  trend_actions: [{ id: 'review_event:9', title: '建议复核高风险事件', priority: 'high', project_count: 1, item_count: 2, target_route: '/events', target_query: { event_ids: '9' } }],
  risk_changes: {
    window_days: 7,
    new_red_item_count: 1,
    new_yellow_item_count: 2,
    changed_project_count: 1,
    recent_event_count_7d: 1,
    notification_ready: true,
    notification_summary: '方案B演示项目新增红色风险1项、黄色风险2项；近7天新增活跃事件1条',
    projects: [{ project_id: 7, project_name: '方案B演示项目', new_red_count: 1, new_yellow_count: 2, target_route: '/projects/7' }],
    events: [{ id: 9, title: 'ST MCU 交期延长', target_route: '/events', target_query: { event_ids: '9' } }]
  },
  supply_sources: [{ source: 'lcsc', configured: true, status: 'active', error_reason: '' }],
  generated_at: '2026-06-29T10:00:00'
}

describe('RiskDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    push.mockReset()
    dashboardApi.getDashboardNotificationHistory.mockResolvedValue({ data: notificationHistory })
    dashboardApi.getDashboardNotificationChannels.mockResolvedValue({ data: notificationChannels })
  })

  it('展示仪表盘指标、项目风险、品类风险、事件、行动和供应源状态', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: summaryPayload })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: notificationPreview })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('风险仪表盘')
    expect(wrapper.text()).toContain('项目总数')
    expect(wrapper.text()).toContain('2')
    expect(wrapper.text()).toContain('方案B演示项目')
    expect(wrapper.text()).toContain('MCU')
    expect(wrapper.text()).toContain('ST MCU 交期延长')
    expect(wrapper.text()).toContain('建议复核高风险事件')
    expect(wrapper.text()).toContain('风险变化摘要')
    expect(wrapper.text()).toContain('通知预览')
    expect(wrapper.text()).toContain('新增红色风险')
    expect(wrapper.text()).toContain('方案B演示项目新增红色风险1项、黄色风险2项')
    expect(wrapper.text()).toContain('BOM风险变化提醒：新增红色风险1项，黄色风险2项')
    expect(wrapper.text()).toContain('通知执行历史')
    expect(wrapper.text()).toContain('daily-risk-20260630')
    expect(wrapper.text()).toContain('lcsc')
    expect(wrapper.text()).toContain('统计口径')
  })

  it('点击项目、事件和行动时带上下文跳转', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: summaryPayload })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: notificationPreview })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.vm.openProject(summaryPayload.project_risks[0])
    expect(push).toHaveBeenCalledWith('/projects/7')

    await wrapper.vm.goEventLibrary(summaryPayload.recent_events[0])
    expect(push).toHaveBeenCalledWith({ path: '/events', query: { eventId: 9, event_ids: '9' } })

    await wrapper.vm.openCategoryEvents(summaryPayload.category_risks[0])
    expect(push).toHaveBeenCalledWith({ path: '/events', query: { eventId: 9, event_ids: '9', category: 'MCU' } })

    await wrapper.vm.openAction(summaryPayload.trend_actions[0])
    expect(push).toHaveBeenCalledWith({ path: '/events', query: { eventId: 9, event_ids: '9' } })
  })

  it('仪表盘事件风险数据可当前页打开事件源头并展示触发原则', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: summaryPayload })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: notificationPreview })
    eventApi.getEvent.mockResolvedValue({
      data: {
        id: 9,
        raw_title: 'ST MCU 交期延长源头',
        severity: 'high',
        confidence: 0.86,
        estimated_lead_time_impact_weeks: 12,
        estimated_price_impact_pct: 8,
        source_name: '采购邮箱',
        source_url: 'mail://st-mcu-001'
      }
    })
    eventApi.getEventImpact.mockResolvedValue({ data: { project_count: 1, item_count: 2, projects: [] } })
    eventApi.getEventSourceSignal.mockResolvedValue({ data: null })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.vm.openEvent(summaryPayload.recent_events[0])
    await flushPromises()

    expect(eventApi.getEvent).toHaveBeenCalledWith(9)
    expect(wrapper.text()).toContain('事件详情')
    expect(wrapper.text()).toContain('ST MCU 交期延长源头')
    expect(wrapper.text()).toContain('影响触发原则')
    expect(wrapper.text()).toContain('命中原则')
    expect(wrapper.text()).toContain('mail://st-mcu-001')
  })

  it('接口为空时显示空态', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: { ...summaryPayload, project_risks: [], category_risks: [], recent_events: [], trend_actions: [], supply_sources: [] } })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: { ...notificationPreview, ready: false, subject: 'BOM风险变化提醒：暂无新增红黄风险' } })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('暂无项目风险数据')
    expect(wrapper.text()).toContain('暂无近期活跃事件')
  })

  it('点击准备通知时调用手动通知准备接口', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: summaryPayload })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: notificationPreview })
    dashboardApi.dispatchDashboardNotification.mockResolvedValue({ data: { status: 'prepared', message: '通知内容已准备完成，请在正式通知通道接入后发送。' } })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    await wrapper.find('[data-testid="prepare-notification"]').trigger('click')

    expect(dashboardApi.dispatchDashboardNotification).toHaveBeenCalledWith({ channel: 'manual' })
  })

  it('展示通知通道状态并支持发送测试通知', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: summaryPayload })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: notificationPreview })
    dashboardApi.dispatchDashboardNotification.mockResolvedValue({
      data: {
        status: 'sent',
        message: '测试通知已发送，未触达外部系统。',
        preview: notificationPreview
      }
    })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(dashboardApi.getDashboardNotificationChannels).toHaveBeenCalled()
    expect(wrapper.text()).toContain('通知通道')
    expect(wrapper.text()).toContain('测试通道')
    expect(wrapper.text()).toContain('未配置')

    await wrapper.find('[data-testid="send-test-notification"]').trigger('click')

    expect(dashboardApi.dispatchDashboardNotification).toHaveBeenCalledWith({ channel: 'mock' })
  })

  it('邮件通道已配置时支持发送邮件通知', async () => {
    dashboardApi.getDashboardSummary.mockResolvedValue({ data: summaryPayload })
    dashboardApi.getDashboardNotificationPreview.mockResolvedValue({ data: notificationPreview })
    dashboardApi.getDashboardNotificationChannels.mockResolvedValue({ data: notificationChannelsWithEmail })
    dashboardApi.dispatchDashboardNotification.mockResolvedValue({
      data: {
        status: 'sent',
        message: '邮件通知已发送。',
        preview: notificationPreview
      }
    })

    const wrapper = mount(RiskDashboard, { global: { stubs, directives: { loading: {} } } })
    await flushPromises()

    expect(wrapper.text()).toContain('发送邮件通知')

    await wrapper.find('[data-testid="send-email-notification"]').trigger('click')

    expect(dashboardApi.dispatchDashboardNotification).toHaveBeenCalledWith({ channel: 'email' })
  })
})
