import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'analyze', component: () => import('../views/BomAnalyze.vue'), meta: { title: '上传分析' } },
  { path: '/projects', name: 'projects', component: () => import('../views/BomProjects.vue'), meta: { title: 'BOM项目' } },
  { path: '/projects/:id', name: 'project-detail', component: () => import('../views/BomProjectDetail.vue'), meta: { title: '项目详情' } },
  { path: '/dashboard', name: 'dashboard', component: () => import('../views/RiskDashboard.vue'), meta: { title: '风险仪表盘' } },
  { path: '/intelligence', name: 'intelligence', component: () => import('../views/IntelligenceCenter.vue'), meta: { title: '行情情报中心' } },
  { path: '/material-chain', name: 'material-chain', component: () => import('../views/MaterialChain.vue'), meta: { title: '上游材料链路' } },
  { path: '/preferred-library', name: 'preferred-library', component: () => import('../views/PreferredLibrary.vue'), meta: { title: '优选库治理' } },
  { path: '/materials', name: 'materials', component: () => import('../views/MaterialWatch.vue'), meta: { title: '原材料追踪' } },
  { path: '/data-sources', name: 'data-sources', component: () => import('../views/DataSourceStatus.vue'), meta: { title: '数据源状态' } },
  // 旧路由重定向
  { path: '/events', redirect: '/intelligence?tab=events' },
  { path: '/market-trends', redirect: '/intelligence?tab=trends' },
  { path: '/market-inbox', redirect: '/intelligence?tab=intake' },
  { path: '/watch', redirect: '/intelligence?tab=monitor' }
]

export default createRouter({ history: createWebHashHistory(), routes })
