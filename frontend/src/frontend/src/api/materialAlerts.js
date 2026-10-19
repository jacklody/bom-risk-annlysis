import client from './client'

/** 获取原材料价格预警列表（支持多维度过滤 + 分页） */
export function getMaterialAlerts(params = {}) {
  return client.get('/material-alerts', { params })
}

/** 获取单材料历史价格趋势 */
export function getMaterialTrends(materialKey, days = 90) {
  return client.get(`/material-alerts/trends/${materialKey}`, { params: { days } })
}

/** 获取全品类原材料风险聚合摘要 */
export function getMaterialSummary(domain) {
  return client.get('/material-alerts/summary', { params: domain ? { domain } : {} })
}

/** 获取价格服务缓存/配额统计 */
export function getMaterialCacheStats() {
  return client.get('/material-alerts/cache-stats')
}
