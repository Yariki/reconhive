import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/search' },
  { path: '/search', name: 'search', component: () => import('../views/SearchView.vue') },
  { path: '/hosts', name: 'hosts', component: () => import('../views/HostsView.vue') },
  { path: '/hosts/:id', name: 'host', component: () => import('../views/HostDetailView.vue') },
  { path: '/jobs', name: 'jobs', component: () => import('../views/JobsView.vue') },
  { path: '/engagements', name: 'engagements', component: () => import('../views/EngagementsView.vue') },
  { path: '/audit', name: 'audit', component: () => import('../views/AuditView.vue') },
]

export default createRouter({ history: createWebHistory(), routes })
