import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useMarketEventDetail } from '../useMarketEventDetail'
import * as api from '../../api/events'

vi.mock('../../api/events', () => ({
  getEvent: vi.fn(),
  getEventImpact: vi.fn(),
  getEventSourceSignal: vi.fn()
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn() }
}))

describe('useMarketEventDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads event, impact and source signal then opens detail drawer', async () => {
    api.getEvent.mockResolvedValue({ data: { id: 8, raw_title: 'TDK涨价事件' } })
    api.getEventImpact.mockResolvedValue({ data: { project_count: 1 } })
    api.getEventSourceSignal.mockResolvedValue({ data: { signal: { review_status: 'confirmed' } } })

    const detail = useMarketEventDetail()
    await detail.openEventDetail(8)

    expect(api.getEvent).toHaveBeenCalledWith(8)
    expect(api.getEventImpact).toHaveBeenCalledWith(8)
    expect(api.getEventSourceSignal).toHaveBeenCalledWith(8)
    expect(detail.detailVisible.value).toBe(true)
    expect(detail.selectedEvent.value.raw_title).toBe('TDK涨价事件')
    expect(detail.eventImpact.value.project_count).toBe(1)
    expect(detail.sourceSignal.value.signal.review_status).toBe('confirmed')
    expect(detail.detailLoading.value).toBe(false)
  })

  it('keeps event detail visible when impact and source signal loading fail', async () => {
    api.getEvent.mockResolvedValue({ data: { id: 9, raw_title: '自动打开事件' } })
    api.getEventImpact.mockRejectedValue(new Error('impact failed'))
    api.getEventSourceSignal.mockRejectedValue(new Error('source failed'))

    const detail = useMarketEventDetail()
    await detail.openEventDetail('9')

    expect(detail.detailVisible.value).toBe(true)
    expect(detail.selectedEvent.value.raw_title).toBe('自动打开事件')
    expect(detail.eventImpact.value).toBeNull()
    expect(detail.sourceSignal.value).toBeNull()
  })

  it('does not open drawer when event body loading fails', async () => {
    api.getEvent.mockRejectedValue(new Error('event failed'))

    const detail = useMarketEventDetail()
    await detail.openEventDetail(10)

    expect(detail.detailVisible.value).toBe(false)
    expect(detail.selectedEvent.value).toBeNull()
    expect(api.getEventImpact).not.toHaveBeenCalled()
    expect(api.getEventSourceSignal).not.toHaveBeenCalled()
  })
})
