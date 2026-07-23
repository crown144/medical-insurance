import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const sqlAnalysis: RouteRecordRaw = {
  path: '/sql-analysis',
  name: 'SqlAnalysisCenter',
  component: BasicLayout,
  meta: {
    title: 'SQL分析',
    icon: 'mdi:database-search-outline',
    order: 35,
  },
  redirect: '/sql-analysis/management',
  children: [
    {
      path: 'management',
      name: 'SqlAnalysisManagement',
      component: () => import('#/views/sql-analysis/SqlManagement.vue'),
      meta: {
        title: 'SQL管理',
        icon: 'mdi:code-tags',
      },
    },
    {
      path: 'execution',
      name: 'SqlAnalysisExecution',
      component: () => import('#/views/sql-analysis/SqlExecution.vue'),
      meta: {
        title: 'SQL执行',
        icon: 'mdi:play-circle-outline',
      },
    },
    {
      path: 'results',
      name: 'SqlAnalysisResults',
      component: () => import('#/views/sql-analysis/SqlResultCenter.vue'),
      meta: {
        title: '执行结果',
        icon: 'mdi:file-chart-outline',
      },
    },
    {
      path: 'results/:id',
      name: 'SqlAnalysisResultDetail',
      component: () => import('#/views/sql-analysis/SqlResultDetail.vue'),
      meta: {
        title: '规则执行详情',
        hideInMenu: true,
        activeMenu: '/sql-analysis/results',
      },
    },
  ],
};

export default sqlAnalysis;
