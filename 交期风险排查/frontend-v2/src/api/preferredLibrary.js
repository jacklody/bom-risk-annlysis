import client from './client'

export function importPreferredLibrary(file) {
  const formData = new FormData()
  formData.append('file', file)
  return client.post('/preferred-library/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function getPreferredSummary() {
  return client.get('/preferred-library/summary')
}

export function listPreferredParts(params = {}) {
  return client.get('/preferred-library/parts', { params })
}

export function reviewBomSelection(projectId) {
  return client.post(`/preferred-library/review/${projectId}`)
}

export function getBomSelectionReview(projectId) {
  return client.get(`/preferred-library/review/${projectId}`)
}
