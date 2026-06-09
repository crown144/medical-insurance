import type { RouteRecordRaw } from 'vue-router';

import { $t } from '#/locales';

const routes: RouteRecordRaw[] = [
  {
    meta: {
      icon: 'lucide:search-check',
      order: 10,
      title: $t('page.feijian.title'),
    },
    name: 'FeiJian',
    path: '/feijian',
    children: [
      {
        name: 'FeiJianInspection',
        path: '/feijian/inspection',
        component: () => import('#/views/feijian/inspection/index.vue'),
        meta: {
          icon: 'lucide:clipboard-check',
          title: $t('page.feijian.inspection'),
        },
      },
    ],
  },
];

export default routes;