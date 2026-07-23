import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:database-zap',
      order: 11,
      title: $t('page.sqlAnalysis.title'),
    },
    name: 'SqlAnalysis',
    path: '/sql-analysis',
    children: [
      {
        name: 'SqlAnalysisManagement',
        path: '/sql-analysis/management',
        component: () => import('#/views/sql-analysis/management/index.vue'),
        meta: {
          icon: 'lucide:file-code-2',
          title: $t('page.sqlAnalysis.management'),
        },
      },
      {
        name: 'SqlAnalysisExecution',
        path: '/sql-analysis/execution',
        component: () => import('#/views/sql-analysis/execution/index.vue'),
        meta: {
          icon: 'lucide:play-circle',
          title: $t('page.sqlAnalysis.execution'),
        },
      },
    ],
  },
];

export default routes;
