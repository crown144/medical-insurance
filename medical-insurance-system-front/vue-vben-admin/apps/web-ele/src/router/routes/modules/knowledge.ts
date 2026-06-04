import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const ParentView = () => import('#/views/_shared/ParentView.vue');

const knowledge: RouteRecordRaw = {
  path: '/knowledge',
  name: 'KnowledgeCenter',
  component: BasicLayout,
  meta: {
    title: '医保知识库',
    icon: 'mdi:database-outline',
    order: 40,
  },
  redirect: '/knowledge/manage/item',
  children: [
    {
      path: 'manage',
      name: 'KnowledgeManage',
      component: ParentView,
      meta: { title: '知识库管理', icon: 'mdi:folder-cog-outline' },
      redirect: '/knowledge/manage/item',
      children: [
        {
          path: 'item',
          name: 'KnowledgeItem',
          component: () => import('#/views/knowledge/ItemKnowledge.vue'),
          meta: { title: '项目内涵知识库', icon: 'mdi:shape-outline' },
        },
        {
          path: 'drug',
          name: 'KnowledgeDrug',
          component: () => import('#/views/knowledge/DrugKnowledge.vue'),
          meta: { title: '医保药品知识库', icon: 'mdi:pill' },
        },
        {
          path: 'vector',
          name: 'KnowledgeVector',
          component: () => import('#/views/knowledge/VectorKnowledge.vue'),
          meta: { title: '医保知识向量库', icon: 'mdi:vector-arrange-above' },
        },
        {
          path: 'code',
          name: 'KnowledgeCodeTable',
          component: ParentView,
          meta: { title: '码表库', icon: 'mdi:code-tags' },
          redirect: '/knowledge/manage/code/operation',
          children: [
            {
              path: 'operation',
              name: 'OperationCode',
              component: () =>
                import('#/views/knowledge/code/OperationCode.vue'),
              meta: { title: '手术与操作编码库', icon: 'mdi:knife' },
            },
            {
              path: 'icd',
              name: 'ICDCode',
              component: () => import('#/views/knowledge/code/ICDCode.vue'),
              meta: { title: 'ICD编码库', icon: 'mdi:book-medical' },
            },
          ],
        },
      ],
    },
  ],
};

export default knowledge;
