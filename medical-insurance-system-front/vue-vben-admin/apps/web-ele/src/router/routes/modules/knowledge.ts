import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const ParentView = () => import('#/views/_shared/ParentView.vue');

const knowledge: RouteRecordRaw = {
  path: '/knowledge',
  name: 'KnowledgeCenter',
  component: BasicLayout,
  meta: {
    title: 'Medical Knowledge Base',
    icon: 'mdi:database-outline',
    order: 40,
    hideInMenu: true,
  },
  redirect: '/knowledge/manage/item',
  children: [
    {
      path: 'manage',
      name: 'KnowledgeManage',
      component: ParentView,
      meta: { title: 'Knowledge Base Management', icon: 'mdi:folder-cog-outline' },
      redirect: '/knowledge/manage/item',
      children: [
        {
          path: 'item',
          name: 'KnowledgeItem',
          component: () => import('#/views/knowledge/ItemKnowledge.vue'),
          meta: { title: 'Item Knowledge Base', icon: 'mdi:shape-outline' },
        },
        {
          path: 'drug',
          name: 'KnowledgeDrug',
          component: () => import('#/views/knowledge/DrugKnowledge.vue'),
          meta: { title: 'Drug Knowledge Base', icon: 'mdi:pill' },
        },
        {
          path: 'vector',
          name: 'KnowledgeVector',
          component: () => import('#/views/knowledge/VectorKnowledge.vue'),
          meta: { title: 'Knowledge Vector Store', icon: 'mdi:vector-arrange-above' },
        },
        {
          path: 'code',
          name: 'KnowledgeCodeTable',
          component: ParentView,
          meta: { title: 'Code Tables', icon: 'mdi:code-tags' },
          redirect: '/knowledge/manage/code/operation',
          children: [
            {
              path: 'operation',
              name: 'OperationCode',
              component: () =>
                import('#/views/knowledge/code/OperationCode.vue'),
              meta: { title: 'Procedure and Operation Codes', icon: 'mdi:knife' },
            },
            {
              path: 'icd',
              name: 'ICDCode',
              component: () => import('#/views/knowledge/code/ICDCode.vue'),
              meta: { title: 'ICD Code Library', icon: 'mdi:book-medical' },
            },
          ],
        },
      ],
    },
  ],
};

export default knowledge;
