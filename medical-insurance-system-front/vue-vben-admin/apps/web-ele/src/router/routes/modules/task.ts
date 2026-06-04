import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const ParentView = () => import('#/views/_shared/ParentView.vue');

const task: RouteRecordRaw = {
  path: '/task',
  name: 'ExecuteCenter',
  component: BasicLayout,
  meta: {
    title: '医保执行任务',
    icon: 'mdi:clipboard-text-outline',
    order: 20,
  },
  redirect: '/task/manage/execution',
  children: [
    // ===== 计算任务管理 =====
    {
      path: 'manage',
      name: 'ExecuteManage',
      component: ParentView,
      meta: {
        title: '计算任务管理',
        icon: 'mdi:format-list-bulleted',
      },
      redirect: '/task/manage/execution',
      children: [
        {
          path: 'execution',
          name: 'ExecuteRun',
          component: () => import('#/views/task/TaskExecution.vue'),
          meta: {
            title: '医保任务执行',
            icon: 'mdi:play-circle-outline',
            keepAlive: false, //
          },
        },
        {
          path: 'new',
          name: 'ExecuteNewTask',
          component: () => import('#/views/task/TaskExecutionAddNewTask.vue'),
          meta: {
            title: '新建计算任务',
            icon: 'mdi:plus-box-outline',
          },
        },
      ],
    },

    // ===== 旧URL兼容 (已补全 title) =====
    {
      path: 'execution',
      name: 'TaskExecutionLegacy',
      redirect: '/task/manage/execution',
      meta: {
        title: '旧版列表跳转', //
        hideInMenu: true,
      },
    },
    {
      path: 'add-new-task',
      name: 'TaskAddLegacy',
      redirect: '/task/manage/new',
      meta: {
        title: '旧版新建跳转', //
        hideInMenu: true,
      },
    },
  ],
};

export default task;
