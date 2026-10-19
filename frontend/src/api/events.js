import client from './client'

export function listEvents(params = {}) {
  return client.get('/events/', { params })
}

export function getEvent(eventId) {
  return client.get(`/events/${eventId}`)
}

export function collectEvents() {
  return client.post('/events/collect')
}

export function listMediaSources(params = {}) {
  return client.get('/events/media-sources', { params })
}

export function collectMediaSource(sourceId) {
  const config = sourceId ? { params: { source_id: sourceId } } : undefined
  return client.post('/events/collect-media', null, config)
}

export function listMediaSourceRuns(params = {}) {
  return client.get('/events/media-source-runs', { params })
}

export function forwardArticle(payload) {
  return client.post('/events/forward-article', payload)
}

export function addManualEvent(payload) {
  return client.post('/events/manual', payload)
}

export function updateEventStatus(eventId, payload) {
  return client.patch(`/events/${eventId}/status`, payload)
}

export function getEventImpact(eventId) {
  return client.get(`/events/${eventId}/impact`)
}

export function getEventSourceSignal(eventId) {
  return client.get(`/events/${eventId}/source-signal`)
}
