import { mount } from '@vue/test-utils'
import V32EvidencePanel from '../V32EvidencePanel.vue'

const globalStubs = {
  'el-empty': { props: ['description'], template: '<div>{{ description }}</div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-alert': { props: ['title'], template: '<div>{{ title }}</div>' },
  'el-timeline': { template: '<div><slot /></div>' },
  'el-timeline-item': { props: ['timestamp'], template: '<div><slot /></div>' }
}

describe('V32EvidencePanel', () => {
  it('renders v3.2 risk summary, action suggestion and evidence nodes', () => {
    const wrapper = mount(V32EvidencePanel, {
      global: { stubs: globalStubs },
      props: {
        item: {
          v32_category_display: '高容MLCC',
          v32_primary_track: 'demand_supply',
          v32_risk_level: 'orange',
          v32_risk_score: 72,
          v32_evidence_summary: '高容MLCC当前为orange风险，主导轨道为demand_supply。',
          v32_action_suggestion: '建议锁定库存并确认替代料。',
          v32_evidence_chain: [
            { type: 'category', title: '品类识别', detail: '识别为高容MLCC' },
            { type: 'market_event', title: '市场事件', detail: 'TDK缺货涨价通知' }
          ]
        }
      }
    })

    expect(wrapper.text()).toContain('高容MLCC')
    expect(wrapper.text()).toContain('需求/供应轨')
    expect(wrapper.text()).toContain('72')
    expect(wrapper.text()).toContain('建议锁定库存并确认替代料')
    expect(wrapper.text()).toContain('品类识别')
    expect(wrapper.text()).toContain('TDK缺货涨价通知')
  })

  it('renders empty-state text when no v3.2 evidence exists', () => {
    const wrapper = mount(V32EvidencePanel, {
      global: { stubs: globalStubs },
      props: { item: {} }
    })
    expect(wrapper.text()).toContain('暂无 v3.2 依据链数据')
  })
})
