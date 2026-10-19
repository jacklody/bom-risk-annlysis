import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'risk-chain-dashboard',
    component: () => import('../views/RiskChainDashboard.vue')
  },
  {
    path: '/analyze',
    name: 'analyze',
    component: () => import('../views/BomAnalyze.vue')
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/RiskDashboard.vue')
  },
  {
    path: '/projects',
    name: 'projects',
    component: () => import('../views/BomProjects.vue')
  },
  {
    path: '/projects/:id',
    name: 'project-detail',
    component: () => import('../views/BomProjectDetail.vue')
  },
  {
    path: '/events',
    name: 'events',
    component: () => import('../views/MarketEvents.vue')
  },
  {
    path: '/market-trends',
    name: 'market-trends',
    component: () => import('../views/MarketTrends.vue')
  },
  {
    path: '/market-inbox',
    name: 'market-inbox',
    component: () => import('../views/MarketInbox.vue')
  },
  {
    path: '/preferred-library',
    name: 'preferred-library',
    component: () => import('../views/PreferredLibrary.vue')
  },
  {
    path: '/watch',
    name: 'watch',
    component: () => import('../views/IntelWatch.vue')
  },
  {
    path: '/materials',
    name: 'materials',
    component: () => import('../views/MaterialWatch.vue')
  },
  {
    path: '/delivery-risk',
    name: 'delivery-risk',
    component: () => import('../views/DeliveryRisk.vue')
  },
  {
    path: '/project-review',
    name: 'project-review',
    component: () => import('../views/ProjectReview.vue')
  },
]

export default createRouter({
  history: createWebHashHistory(),
  routes
})
