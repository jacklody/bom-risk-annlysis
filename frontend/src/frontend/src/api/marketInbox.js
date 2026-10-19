import client from './client'

export function submitMarketNotice(payload) {
  return client.post('/market-inbox/submit', payload)
}

export function listMarketNotices() {
  return client.get('/market-inbox/')
}

export function getMarketNotice(id) {
  return client.get(`/market-inbox/${id}`)
}

export function reviewSignal(signalId, payload) {
  return client.post(`/market-inbox/review/${signalId}`, payload)
}

export function listReviewQueue(status) {
  const params = status ? { status } : {}
  return client.get('/market-inbox/review-queue', { params })
}
