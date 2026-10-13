import type { RouteRecordRaw } from 'vue-router';

import { preferences } from '@vben/preferences';

const BasicLayout = () => import('#/layouts/basic.vue');

const fallbackNotFoundRoute: RouteRecordRaw = {
  component: () => import('#/views/_core/fallback/not-found.vue'),
  meta: {
    hideInBreadcrumb: true,
    hideInMenu: true,
    hideInTab: true,
    title: '404',
  },
  name: 'FallbackNotFound',
  path: '/:path(.*)*',
};

const coreRoutes: RouteRecordRaw[] = [
  {
    component: BasicLayout,
    meta: {
      hideInBreadcrumb: true,
      title: 'Root',
    },
    name: 'Root',
    path: '/',
    redirect: preferences.app.defaultHomePath,
    children: [],
  },
  {
    // Old login/register bookmarks now enter the application directly.
    name: 'RemovedAuthenticationPages',
    path: '/auth/:pathMatch(.*)*',
    redirect: preferences.app.defaultHomePath,
    meta: {
      hideInMenu: true,
      hideInTab: true,
      title: 'Authentication removed',
    },
  },
];

export { coreRoutes, fallbackNotFoundRoute };
