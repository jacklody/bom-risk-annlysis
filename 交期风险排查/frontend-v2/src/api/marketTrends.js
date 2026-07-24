import client from './client'

export function getTrendSummary() {
  return client.get('/market-trends/summary')
}

export function getTrendTimeline(params = {}) {
  return client.get('/market-trends/timeline', { params })
}

export function getTrendValidation() {
  return client.get('/market-trends/validation')
}

export function getTrendActions() {
  return client.get('/market-trends/actions')
}

export function createPredictionValidationRecord(eventId, payload) {
  return client.post(`/market-trends/validation/${eventId}/records`, payload)
}
