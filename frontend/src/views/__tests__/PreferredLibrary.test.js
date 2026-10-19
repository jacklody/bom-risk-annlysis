import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import PreferredLibrary from '../PreferredLibrary.vue'

vi.mock('../../api/preferredLibrary', () => ({
  getPreferredSummary: vi.fn(() => Promise.resolve({ data: { total_parts: 2 } })),
  reviewBomSelection: vi.fn(() => Promise.resolve({
    data: {
      summary: {
        total_items: 2, preferred_hit_count: 1, non_preferred_count: 1,
        new_part_count: 1, red_count: 1, yellow_count: 0, alternative_count: 1
      },
      items: [
        {
          id: 1, bom_part_number: '0603B104K500CT', bom_brand: 'FH',
          bom_total_stock: 6235051, bom_lead_time_days: null, bom_unit_price: 0.0018,
          bom_lifecycle_status: 'Unknown',
          pref_mpn: 'CL10B104KB8NNNC', pref_brand: 'SAMSUNG',
          pref_preferred_level: 'strong_recommended', pref_cost: 0.0025,
          match_status: 'not_found', selection_risk_level: 'red',
          selection_reason: '未命中优选库', selection_action: '从替代建议中选择',
          recommended_alternatives: [{ brand: 'SAMSUNG', mpn: 'CL10B104KB8NNNC' }]
        }
      ]
    }
  }))
}))

vi.mock('../../api/bom', () => ({
  listBomProjects: vi.fn(() => Promise.resolve({
    data: { projects: [{ id: 301, project_name: '测试项目', filename: 'test.xlsx', status: 'active', total_items: 2 }] }
  }))
}))

const globalStubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-tag': { props: ['type'], template: '<span :data-type=\"type\"><slot /></span>' },
  'el-button': { props: ['loading', 'disabled'], template: '<button :disabled=\"loading || disabled\" @click=\"$emit(\'click\')\"><slot /></button>' },
  'el-upload': { template: '<div><slot /></div>' },
  'el-select': {
    props: ['modelValue'], emits: ['update:modelValue'],
    template: '<select :value=\"modelValue\" @change=\"$emit(\'update:modelValue\', Number($event.target.value))\"><slot /></select>'
  },
  'el-option': { props: ['label', 'value'], template: '<option :value=\"value\">{{ label }}</option>' },
  'el-table': { props: ['data'], template: '<table><tbody><tr v-for=\"row in data\" :key=\"row.id\"><td>{{ row.bom_part_number }}</td><td>{{ row.pref_mpn }}</td><td>{{ row.match_status }}</td></tr></tbody></table>' },
  'el-table-column': { template: '<td><slot /></td>' },
}

describe('PreferredLibrary', () => {
  it('shows diff comparison table with bom vs preferred side-by-side', async () => {
    const wrapper = mount(PreferredLibrary, { global: { stubs: globalStubs } })
    await flushPromises()

    expect(wrapper.get('[data-testid="preferred-library-page"]').text()).toContain('差异对比')

    const select = wrapper.get('[data-testid="bom-project-select"]')
    await select.setValue(301)
    await flushPromises()

    await wrapper.get('[data-testid="run-selection-review"]').trigger('click')
    await flushPromises()

    const result = wrapper.get('[data-testid="selection-review-result"]')
    expect(result.text()).toContain('0603B104K500CT')
    expect(result.text()).toContain('CL10B104KB8NNNC')
    expect(result.text()).toContain('not_found')
    expect(result.text()).toContain('差异明细')
  })
})
