import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const ParentView = () => import('#/views/_shared/ParentView.vue');

const task: RouteRecordRaw = {
  path: '/task',
  name: 'ExecuteCenter',
  component: BasicLayout,
  meta: {
    title: 'Task Execution',
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
        title: 'Task Management',
        icon: 'mdi:format-list-bulleted',
      },
      redirect: '/task/manage/execution',
      children: [
        {
          path: 'execution',
          name: 'ExecuteRun',
          component: () => import('#/views/task/TaskExecution.vue'),
          meta: {
            title: 'Task Execution',
            icon: 'mdi:play-circle-outline',
            keepAlive: false, //
          },
        },
        {
          path: 'new',
          name: 'ExecuteNewTask',
          component: () => import('#/views/task/TaskExecutionAddNewTask.vue'),
          meta: {
            title: 'New Task',
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
        title: 'Legacy Task List Redirect', //
        hideInMenu: true,
      },
    },
    {
      path: 'add-new-task',
      name: 'TaskAddLegacy',
      redirect: '/task/manage/new',
      meta: {
        title: 'Legacy New Task Redirect', //
        hideInMenu: true,
      },
    },
  ],
};

export default task;
