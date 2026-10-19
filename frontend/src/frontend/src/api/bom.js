import client from './client'

export function uploadBom(file, projectName = '') {
  const formData = new FormData()
  formData.append('file', file)
  if (projectName) formData.append('project_name', projectName)
  return client.post('/bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function uploadBomBatch(files) {
  const formData = new FormData()
  files.forEach(file => formData.append('files', file))
  return client.post('/bom/upload-batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function analyzeBom(uploadId) {
  return client.post(`/risk/analyze/${uploadId}`)
}

export function analyzeAll() {
  return client.post('/risk/analyze-all')
}

export function listBomProjects() {
  return client.get('/bom/projects')
}

export function getBomProject(projectId) {
  return client.get(`/bom/projects/${projectId}`)
}

export function getProjectRiskReport(projectId) {
  return client.get(`/risk/report/${projectId}`)
}

export function getProjectRiskReportHtmlUrl(projectId) {
  return `/api/risk/report/${projectId}/export.html`
}

export function getProjectRiskReportXlsxUrl(projectId) {
  return `/api/risk/report/${projectId}/export.xlsx`
}
