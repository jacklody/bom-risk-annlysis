import client from './client'

export function querySupply(mpn) {
  return client.get('/supply/query', { params: { mpn } })
}

export function refreshSupplyItem(itemId) {
  return client.post(`/supply/items/${itemId}/refresh`)
}

export function refreshSupplyProject(projectId, params = {}) {
  return client.post(`/supply/projects/${projectId}/refresh`, null, { params })
}

export function getSupplyProjectStatus(projectId) {
  return client.get(`/supply/projects/${projectId}/status`)
}

export function getSupplySourcesStatus(sampleMpn = 'STM32F103C8T6') {
  return client.get('/supply/sources/status', { params: { sample_mpn: sampleMpn } })
}
