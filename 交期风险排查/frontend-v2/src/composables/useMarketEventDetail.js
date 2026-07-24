import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getEvent, getEventImpact, getEventSourceSignal } from '../api/events'

export function useMarketEventDetail() {
  const detailVisible = ref(false)
  const selectedEvent = ref(null)
  const eventImpact = ref(null)
  const sourceSignal = ref(null)
  const detailLoading = ref(false)

  function resetDetail() {
    selectedEvent.value = null
    eventImpact.value = null
    sourceSignal.value = null
  }

  function closeEventDetail() {
    detailVisible.value = false
  }

  async function openEventDetail(eventOrId) {
    resetDetail()
    detailLoading.value = true
    const eventId = typeof eventOrId === 'object' ? eventOrId?.id : eventOrId
    const fallbackEvent = typeof eventOrId === 'object' ? eventOrId : null
    try {
      const { data: eventData } = await getEvent(eventId)
      selectedEvent.value = eventData
      detailVisible.value = true
    } catch (error) {
      if (!fallbackEvent) {
        ElMessage.error(error?.response?.data?.detail || '事件详情加载失败')
        detailLoading.value = false
        return
      }
      selectedEvent.value = fallbackEvent
      detailVisible.value = true
      ElMessage.warning('事件详情接口暂不可用，已展示列表中的基础事件信息')
    }

    try {
      const { data: impactData } = await getEventImpact(eventId)
      eventImpact.value = impactData
    } catch {
      eventImpact.value = null
    }

    try {
      const { data: sourceData } = await getEventSourceSignal(eventId)
      sourceSignal.value = sourceData
    } catch {
      sourceSignal.value = null
    } finally {
      detailLoading.value = false
    }
  }

  return {
    detailVisible,
    selectedEvent,
    eventImpact,
    sourceSignal,
    detailLoading,
    openEventDetail,
    closeEventDetail
  }
}
