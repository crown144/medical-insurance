import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const ParentView = () => import('#/views/_shared/ParentView.vue');

const rule: RouteRecordRaw = {
  path: '/rule',
  name: 'RuleCenter',
  component: BasicLayout,
  meta: {
    title: '规则中心',
    icon: 'mdi:script-text-outline',
    order: 10,
  },
  redirect: '/rule/import/batch-convert',
  children: [
    {
      path: 'import',
      name: 'RuleImportAndValidate',
      component: ParentView,
      meta: {
        title: '规则导入与编译',
        icon: 'mdi:clipboard-check-outline',
      },
      redirect: '/rule/import/batch-convert',
      children: [
        {
          path: 'batch-convert',
          name: 'RuleBatchConvert',
          component: () => import('#/views/rule/flow/RuleBatchConvert.vue'),
          meta: {
            title: '规则批量导入转换',
            icon: 'mdi:file-document-outline',
          },
        },
        {
          path: 'compile',
          name: 'RuleCompile',
          component: () => import('#/views/rule/flow/RuleCompile.vue'),
          meta: { title: '规则编译', icon: 'mdi:cog-outline' },
        },
      ],
    },
    {
      path: 'library',
      name: 'RuleLibrary',
      component: ParentView,
      meta: {
        title: '规则库',
        icon: 'ant-design:unordered-list-outlined',
      },
      redirect: '/rule/library/limited-drug',
      children: [
        {
          path: 'all-rules',
          name: 'AllRules',
          component: () => import('#/views/rule/AllRules.vue'),
          meta: { title: '全部规则', icon: 'mdi:format-list-bulleted' },
        },
        {
          path: 'limited-drug',
          name: 'RuleLimitedDrug',
          component: () => import('#/views/rule/RuleDetail.vue'),
          props: { ruleType: '超限定用药' },
          meta: { title: '超限定用药规则', icon: 'mdi:pill' },
        },
        {
          path: 'over-standard-fee',
          name: 'RuleOverStandardFee',
          component: () => import('#/views/rule/RuleDetail.vue'),
          props: { ruleType: '超标准收费' },
          meta: { title: '超标准收费规则', icon: 'mdi:cash-multiple' },
        },
        {
          path: 'duplicate-charge',
          name: 'RuleDuplicateCharge',
          component: () => import('#/views/rule/RuleDetail.vue'),
          props: { ruleType: '重复收费' },
          meta: { title: '重复收费规则', icon: 'mdi:repeat' },
        },
        {
          path: 'over-medical',
          name: 'RuleOverMedical',
          component: () => import('#/views/rule/RuleDetail.vue'),
          props: { ruleType: '过度医疗' as any },
          meta: { title: '过度医疗规则', icon: 'mdi:stethoscope' },
        },
        {
          path: 'fake-fee',
          name: 'RuleFakeFee',
          component: () => import('#/views/rule/RuleDetail.vue'),
          props: { ruleType: '虚记费用' as any },
          meta: { title: '虚记费用规则', icon: 'mdi:alert-circle-outline' },
        },
      ],
    },
  ],
};

export default rule;
