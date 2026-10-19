import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import RiskDetailTable from '../RiskDetailTable.vue'
import * as supplyApi from '../../api/supply'
import { ElMessage } from 'element-plus'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), warning: vi.fn(), error: vi.fn() }
}))

vi.mock('../../api/supply', () => ({
  refreshSupplyItem: vi.fn()
}))

function mountTable(items) {
  return mount(RiskDetailTable, {
    props: { items },
    global: {
      stubs: {
        V32EvidencePanel: true,
        ElTable: { template: '<div><slot /></div>' },
        ElTableColumn: { template: '<div><slot :row="mockRow" /></div>', data: () => ({ mockRow: items[0] }) },
        ElTag: { template: '<span><slot /></span>' },
        ElButton: { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        ElPopover: { template: '<div><slot name="reference" /><slot /></div>' }
      }
    }
  })
}

describe('RiskDetailTable supply data', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows supply fields and refreshes one row', async () => {
    supplyApi.refreshSupplyItem.mockResolvedValue({
      data: {
        updated: true,
        item: {
          id: 10,
          total_stock: 120,
          supplier_count: 1,
          lead_time_days: 14,
          unit_price: 12.34,
          lifecycle_status: 'Unknown',
          supply_risk_reason: 'LCSC 有库存，供应风险低'
        }
      }
    })
    const wrapper = mountTable([{
      id: 10,
      row_number: 1,
      raw_part_number: 'STM32F103C8T6',
      raw_brand: 'ST',
      raw_category: 'MCU',
      risk_level: 'yellow',
      total_stock: 7,
      supplier_count: 1,
      lead_time_days: 30,
      unit_price: 8.8,
      lifecycle_status: 'Active',
      production_risk_level: 'yellow',
      eol_status: 'none'
    }])

    expect(wrapper.text()).toContain('库存')
    expect(wrapper.text()).toContain('7')
    await wrapper.find('[data-testid="refresh-supply-item"]').trigger('click')
    await flushPromises()

    expect(supplyApi.refreshSupplyItem).toHaveBeenCalledWith(10)
    expect(wrapper.emitted('supply-refreshed')).toBeTruthy()
  })

  it('刷新供应数据失败时展示失败原因且不触发行数据覆盖', async () => {
    supplyApi.refreshSupplyItem.mockResolvedValue({
      data: {
        updated: false,
        failure_reason: 'LCSC 暂未命中该型号',
        result: { error_reason: '兜底错误' },
        item: {
          id: 10,
          total_stock: null,
          supplier_count: 0,
          lead_time_days: null,
          unit_price: null,
          lifecycle_status: 'Unknown'
        }
      }
    })
    const wrapper = mountTable([{
      id: 10,
      row_number: 1,
      raw_part_number: 'STM32F103C8T6',
      raw_brand: 'ST',
      raw_category: 'MCU',
      risk_level: 'yellow',
      total_stock: 7,
      supplier_count: 1,
      lead_time_days: 30,
      unit_price: 8.8,
      lifecycle_status: 'Active',
      production_risk_level: 'yellow',
      eol_status: 'none'
    }])

    await wrapper.find('[data-testid="refresh-supply-item"]').trigger('click')
    await flushPromises()

    expect(ElMessage.warning).toHaveBeenCalledWith('LCSC 暂未命中该型号')
    expect(wrapper.emitted('supply-refreshed')).toBeFalsy()
  })

  it('关联事件可点击并向上打开事件源头详情', async () => {
    const wrapper = mountTable([{
      id: 10,
      row_number: 1,
      raw_part_number: 'STM32F103C8T6',
      raw_brand: 'ST',
      raw_category: 'MCU',
      risk_level: 'red',
      matched_events: [{
        id: 9,
        brand: 'ST',
        category: 'MCU',
        event_type: 'lead_time',
        severity: 'high',
        source_name: '采购邮箱',
        raw_title: 'ST MCU 交期延长'
      }]
    }])

    await wrapper.find('[data-testid="open-matched-event-9"]').trigger('click')

    expect(wrapper.emitted('open-event-detail')?.[0]).toEqual([9])
    expect(wrapper.text()).toContain('触发源头')
  })
})
