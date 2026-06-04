import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const result: RouteRecordRaw = {
  path: '/result',
  name: 'ResultCenter',
  component: BasicLayout,
  meta: {
    title: '结果中心',
    icon: 'mdi:file-document-outline',
    order: 30,
  },
  redirect: '/result/task-overview',
  children: [
    // 1. 总览仪表盘
    {
      path: 'task-overview',
      name: 'ResultTaskOverview',
      component: () => import('#/views/result/TaskResultOverview.vue'),
      meta: {
        title: '任务结果总览',
        icon: 'mdi:view-dashboard-variant-outline',
      },
    },

    // 2. 违规查询 (保留您的命名)
    {
      path: 'violation-query',
      name: 'ResultViolationQuery',
      component: () => import('#/views/result/ViolationResultQuery.vue'),
      meta: {
        title: '全量违规查询',
        icon: 'mdi:database-search-outline',
      },
    },

    // 3. 特定任务明细 (对应 SpecificTaskResult.vue)
    {
      path: 'task-items',
      name: 'ResultTaskItems', // 🚨 记住这个名字，跳转要用
      component: () => import('#/views/result/SpecificTaskResult.vue'),
      meta: {
        title: '任务明细清单',
        icon: 'mdi:format-list-bulleted-type',
        // hideInMenu: true, // 您注释掉了，说明想在菜单显示，没问题
        activeMenu: '/task/manage/execution', // 建议加上：让左侧菜单保持高亮在任务执行或结果中心
      },
    },

    // 4. 审计工作台 (对应 AuditDetail.vue / AuditViewDetail.vue)
    {
      path: 'audit-view',
      name: 'ResultAuditViewDetail',
      // 请确认您的文件名是 AuditViewDetail.vue 还是 AuditDetail.vue
      // 这里指向 result 目录下的文件
      component: () => import('#/views/result/AuditDetail.vue'),
      meta: {
        title: '结果审计详情',
        icon: 'mdi:file-eye-outline',
        hideInMenu: true, // 这个通常需要隐藏，因为必须带参数才能看
        activeMenu: '/task/manage/execution',
      },
    },
  ],
};

export default result;
