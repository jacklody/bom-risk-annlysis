import { mount, flushPromises } from '@vue/test-utils'
import ManualEventQuickAdd from '../ManualEventQuickAdd.vue'
import { addManualEvent } from '../../api/events'

vi.mock('../../api/events', () => ({
  addManualEvent: vi.fn()
}))

const globalStubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-alert': { props: ['title', 'description'], template: '<div>{{ title }} {{ description }}</div>' }
}

describe('ManualEventQuickAdd', () => {
  beforeEach(() => {
    addManualEvent.mockReset()
  })

  it('submits a manual price increase and emits backend review result', async () => {
    addManualEvent.mockResolvedValueOnce({
      data: {
        status: 'ok',
        review_recommendation: 'auto_confirm',
        confidence_reason: '人工确认且含涨价缺货事实'
      }
    })

    const wrapper = mount(ManualEventQuickAdd, {
      global: { stubs: globalStubs },
      props: {
        defaultItem: {
          raw_brand: 'TDK',
          v32_category: 'high_cap_mlcc',
          raw_part_number: 'C3216X5R1A226M'
        }
      }
    })

    await wrapper.find('[data-testid="manual-event-title"]').setValue('TDK高容MLCC缺货涨价通知')
    await wrapper.find('[data-testid="manual-event-increase"]').setValue('20')
    await wrapper.find('[data-testid="manual-event-submit"]').trigger('click')
    await flushPromises()

    expect(addManualEvent).toHaveBeenCalledWith(expect.objectContaining({
      title: 'TDK高容MLCC缺货涨价通知',
      brand: 'TDK',
      category: 'high_cap_mlcc',
      event_type: 'price_increase',
      increase_max_pct: 20,
      confirmed_by_user: true
    }))
    expect(wrapper.emitted('submitted')).toHaveLength(1)
    expect(wrapper.text()).toContain('auto_confirm')
  })
})
