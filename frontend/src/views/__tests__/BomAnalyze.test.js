import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import BomAnalyze from '../BomAnalyze.vue'
import * as bomApi from '../../api/bom'
import * as supplyApi from '../../api/supply'

vi.mock('../../api/bom', () => ({
  uploadBom: vi.fn(),
  uploadBomBatch: vi.fn(),
  analyzeBom: vi.fn(),
  analyzeAll: vi.fn()
}))

vi.mock('../../api/supply', () => ({
  refreshSupplyProject: vi.fn(),
  getSupplySourcesStatus: vi.fn()
}))

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push })
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() }
}))

const stubs = {
  BomUploader: {
    emits: ['upload'],
    template: '<button data-testid="upload-one" @click="$emit(\'upload\', { name: \'bom.xlsx\' }, \'demo\')">upload</button>'
  },
  ProgressSteps: true,
  RiskSummary: true,
  ManualEventQuickAdd: true,
  RiskDetailTable: {
    props: ['items'],
    emits: ['supply-refreshed'],
    template: '<div data-testid="risk-detail">{{ items.map(i => i.total_stock).join(\',\') }}</div>'
  },
  'el-alert': { props: ['title'], template: '<div>{{ title }}<slot /></div>' },
  'el-button': { props: ['loading'], emits: ['click'], template: '<button v-bind="$attrs" :disabled="loading" @click="$emit(\'click\')"><slot /></button>' },
  'el-divider': true,
  'el-tag': { template: '<span><slot /></span>' },
  'el-result': true,
  'el-icon': true,
  'el-table': { template: '<div><slot /></div>' },
  'el-table-column': true,
  Loading: true,
  Download: true
}

function mountPage() {
  return mount(BomAnalyze, { global: { stubs } })
}

describe('BomAnalyze supply refresh', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    push.mockReset()
  })

  it('renders supply source configuration and health summary after analysis', async () => {
    bomApi.uploadBom.mockResolvedValue({ data: { upload_id: 77 } })
    bomApi.analyzeBom.mockResolvedValue({
      data: {
        upload_id: 77,
        total_items: 1,
        summary: { red: 0, yellow: 1, green: 0, gray: 0 },
        items: [{ id: 10, row_number: 1, raw_part_number: 'STM32F103C8T6', risk_level: 'yellow', total_stock: 7 }]
      }
    })
    supplyApi.getSupplySourcesStatus.mockResolvedValue({
      data: {
        sample_mpn: 'STM32F103C8T6',
        summary: { total_sources: 4, active_sources: 1, not_configured_sources: 2, degraded_sources: 1 },
        sources: [
          { source: 'lcsc', configured: true, status: 'active', match_status: 'hit', total_stock: 88 },
          { source: 'mouser', configured: false, status: 'not_configured' },
          { source: 'digikey', configured: false, status: 'not_configured' },
          { source: 'guanxintai', configured: true, status: 'degraded', error_reason: 'timeout' }
        ]
      }
    })

    const wrapper = mountPage()
    await wrapper.find('[data-testid="upload-one"]').trigger('click')
    await flushPromises()
    await new Promise(resolve => setTimeout(resolve, 900))
    await flushPromises()

    expect(supplyApi.getSupplySourcesStatus).toHaveBeenCalledWith('STM32F103C8T6')
    expect(wrapper.text()).toContain('供应源状态')
    expect(wrapper.text()).toContain('活跃 1')
    expect(wrapper.text()).toContain('未配置 2')
    expect(wrapper.text()).toContain('异常 1')
    expect(wrapper.text()).toContain('lcsc')
    expect(wrapper.text()).toContain('guanxintai')
    expect(wrapper.text()).toContain('timeout')
  })


  it('refreshes project supply data and updates current table rows', async () => {
    bomApi.uploadBom.mockResolvedValue({ data: { upload_id: 77 } })
    bomApi.analyzeBom.mockResolvedValue({
      data: {
        upload_id: 77,
        total_items: 1,
        summary: { red: 0, yellow: 1, green: 0, gray: 0 },
        items: [{ id: 10, row_number: 1, raw_part_number: 'STM32F103C8T6', risk_level: 'yellow', total_stock: 7 }]
      }
    })
    supplyApi.getSupplySourcesStatus.mockResolvedValue({
      data: {
        sample_mpn: 'STM32F103C8T6',
        summary: { total_sources: 4, active_sources: 1, not_configured_sources: 2, degraded_sources: 1 },
        sources: []
      }
    })
    supplyApi.refreshSupplyProject.mockResolvedValue({
      data: {
        processed_count: 1,
        updated_count: 1,
        failed_count: 0,
        items: [{ updated: true, item: { id: 10, total_stock: 120, supplier_count: 1, lifecycle_status: 'Unknown' } }]
      }
    })

    const wrapper = mountPage()
    await wrapper.find('[data-testid="upload-one"]').trigger('click')
    await flushPromises()
    await new Promise(resolve => setTimeout(resolve, 600))
    await flushPromises()

    expect(wrapper.text()).toContain('分析完成')
    expect(wrapper.text()).toContain('7')

    await wrapper.find('[data-testid="refresh-supply-project"]').trigger('click')
    await flushPromises()

    expect(supplyApi.refreshSupplyProject).toHaveBeenCalledWith(77, { limit: 50, concurrency: 3 })
    expect(wrapper.text()).toContain('供应数据刷新：处理 1 条，更新 1 条，失败 0 条')
    expect(wrapper.text()).toContain('120')
  })
})
