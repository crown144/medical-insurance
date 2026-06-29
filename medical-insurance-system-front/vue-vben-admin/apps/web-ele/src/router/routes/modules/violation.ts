import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const violation: RouteRecordRaw = {
  path: '/violation',
  name: 'Violation',
  component: BasicLayout,
  redirect: '/violation/list',
  meta: {
    title: 'Violation Review',
    icon: 'mdi:alert-circle-outline',
    orderNo: 30,
  },
  children: [
    {
      path: 'list',
      name: 'ViolationList',
      component: () => import('#/views/mi/Placeholder.vue'),
      meta: {
        title: 'Violation Items',
        icon: 'mdi:clipboard-text-search-outline',
      },
    },
    {
      path: 'review',
      name: 'ViolationReview',
      component: () => import('#/views/mi/Placeholder.vue'),
      meta: { title: 'Chart Review and Highlighting', icon: 'mdi:marker-check' },
    },
    {
      path: 'confirm',
      name: 'ViolationConfirm',
      component: () => import('#/views/mi/Placeholder.vue'),
      meta: { title: 'Violation Confirmation', icon: 'mdi:check-decagram-outline' },
    },
  ],
};

export default violation;
