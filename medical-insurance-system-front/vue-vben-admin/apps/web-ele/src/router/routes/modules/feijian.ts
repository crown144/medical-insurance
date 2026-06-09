import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const feijian: RouteRecordRaw = {
  path: '/feijian',
  name: 'FeiJian',
  component: BasicLayout,
  meta: {
    title: '飞检结果管理',
    icon: 'mdi:file-search-outline',
    order: 30,
  },
  redirect: '/feijian/manage',
  children: [
    {
      path: 'manage',
      name: 'FeiJianManage',
      component: () => import('#/views/feijian/manage/index.vue'),
      meta: {
        title: '飞检结果处理',
        icon: 'mdi:clipboard-check-outline',
        keepAlive: false,
      },
    },
  ],
};

export default feijian;