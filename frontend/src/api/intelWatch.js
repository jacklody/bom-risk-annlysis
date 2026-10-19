import client from './client'

export function submitWatch(rawInput) {
  return client.post('/intel/watch', { raw_input: rawInput })
}

export function getWatch(cmdId) {
  return client.get(`/intel/watch/${cmdId}`)
}

export function getWatchHistory() {
  return client.get('/intel/watch/history')
}
