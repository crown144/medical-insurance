import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const feijian: RouteRecordRaw = {
  path: '/feijian',
  name: 'FeiJian',
  component: BasicLayout,
  meta: {
    title: 'Inspection Comparison',
    icon: 'mdi:file-search-outline',
    order: 30,
    hideChildrenInMenu: true,
  },
  redirect: '/feijian/manage',
  children: [
    {
      path: 'manage',
      name: 'FeiJianManage',
      component: () => import('#/views/feijian/manage/index.vue'),
      meta: {
        title: 'Inspection Comparison',
        hideInMenu: true,
        keepAlive: false,
      },
    },
  ],
};

export default feijian;
