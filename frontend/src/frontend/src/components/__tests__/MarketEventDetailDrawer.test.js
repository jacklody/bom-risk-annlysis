import { mount } from '@vue/test-utils'
import MarketEventDetailDrawer from '../MarketEventDetailDrawer.vue'

const stubs = {
  'el-drawer': { props: ['modelValue', 'title'], template: '<section v-if="modelValue"><h2>{{ title }}</h2><slot /></section>' },
  'el-button': { props: ['loading'], emits: ['click'], template: '<button :disabled="loading" @click="$emit(\'click\')"><slot /></button>' }
}

const event = {
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
  created_at: '2026-06-27T10:00:00+00:00',
  is_active: 1
}

const impact = {
  project_count: 1,
  item_count: 2,
  risk_counts: { red: 1, yellow: 1, green: 0, gray: 0 },
  projects: [{ project_id: 10, project_name: '真实项目A', affected_item_count: 2, highest_risk_level: 'red' }]
}

const sourceSignal = {
  signal: { review_status: 'confirmed', reviewed_by: 'purchaser', review_notes: '电话复核属实', evidence_text: '供应商确认缺货涨价' },
  raw_notice: { source_type: 'email', source_name: '采购邮箱', sender: 'buyer@example.com', title: 'TDK MLCC 缺货涨价邮件', raw_text_excerpt: '供应商确认 TDK 高容 MLCC 缺货，交期 16 周。' }
}

describe('MarketEventDetailDrawer', () => {
  it('renders event source impact and audit context', () => {
    const wrapper = mount(MarketEventDetailDrawer, {
      props: { modelValue: true, event, impact, sourceSignal, operatingStatus: false },
      global: { stubs }
    })
    const text = wrapper.text()
    expect(text).toContain('事件详情')
    expect(text).toContain('风险等级：高')
    expect(text).toContain('触发条件：严重度 高，置信度 91%，交期影响 16 周，价格影响 20%')
    expect(text).toContain('mail://tdk-notice-001')
    expect(text).toContain('真实项目A')
    expect(text).toContain('电话复核属实')
  })

  it('emits status-change when clicking disable', async () => {
    const wrapper = mount(MarketEventDetailDrawer, {
      props: { modelValue: true, event, impact: null, sourceSignal: null, operatingStatus: false },
      global: { stubs }
    })
    await wrapper.find('[data-testid="events-disable"]').trigger('click')
    expect(wrapper.emitted('status-change')[0]).toEqual(['disable'])
  })
})
