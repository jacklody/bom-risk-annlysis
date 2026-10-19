import client from './client'
import { riskChainService } from './riskChainService'

/**
 * 旧接口：获取风险链路驾驶舱聚合数据
 * 兼容旧版 RiskChainDashboard 的数据结构
 * 新代码应直接使用 riskChainService.getDashboardData()
 */
export function getRiskChainDashboard() {
  return client.get('/risk-chain/dashboard')
}

/**
 * 新接口：通过 riskChainService 获取驾驶舱数据
 * 后续对接后端时，在此处切换到 client HTTP 调用
 */
export const riskChain = {
  getDashboardData: riskChainService.getDashboardData,
  getRiskSignals: riskChainService.getRiskSignals,
  getChainGraph: riskChainService.getChainGraph,
  getBomImpacts: riskChainService.getBomImpacts,
  switchDataSource: riskChainService.switchDataSource
}
