import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const violation: RouteRecordRaw = {
  path: '/violation',
  name: 'Violation',
  component: BasicLayout,
  redirect: '/violation/list',
  meta: {
    title: '医保违规展示',
    icon: 'mdi:alert-circle-outline',
    orderNo: 30,
  },
  children: [
    {
      path: 'list',
      name: 'ViolationList',
      component: () => import('#/views/mi/Placeholder.vue'),
      meta: {
        title: '违规项目展示',
        icon: 'mdi:clipboard-text-search-outline',
      },
    },
    {
      path: 'review',
      name: 'ViolationReview',
      component: () => import('#/views/mi/Placeholder.vue'),
      meta: { title: '病历复核与高亮', icon: 'mdi:marker-check' },
    },
    {
      path: 'confirm',
      name: 'ViolationConfirm',
      component: () => import('#/views/mi/Placeholder.vue'),
      meta: { title: '违规信息确认', icon: 'mdi:check-decagram-outline' },
    },
  ],
};

export default violation;
