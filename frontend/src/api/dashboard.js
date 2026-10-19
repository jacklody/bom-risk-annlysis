import client from './client'

export function getDashboardSummary() {
  return client.get('/dashboard/summary')
}

export function getDashboardNotificationPreview(channel = 'manual') {
  return client.get('/dashboard/notification/preview', { params: { channel } })
}

export function dispatchDashboardNotification(payload = { channel: 'manual' }) {
  return client.post('/dashboard/notification/dispatch', payload)
}

export function getDashboardNotificationHistory(limit = 20) {
  return client.get('/dashboard/notification/history', { params: { limit } })
}

export function getDashboardNotificationChannels() {
  return client.get('/dashboard/notification/channels')
}
