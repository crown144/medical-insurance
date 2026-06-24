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
  redirect: '/rule/import/import',
  children: [
    // ========== 规则导入与校验 ==========
    {
      path: 'import',
      name: 'RuleImportAndValidate',
      component: ParentView,
      meta: {
        title: '规则导入与校验',
        icon: 'mdi:clipboard-check-outline',
      },
      redirect: '/rule/import/import',
      children: [
        {
          path: 'import',
          name: 'RuleImport',
          component: () => import('#/views/rule/flow/RuleImport.vue'),
          meta: { title: '规则导入', icon: 'mdi:tray-arrow-up' },
        },
        {
          path: 'batch-convert',
          name: 'RuleBatchConvert',
          component: () => import('#/views/rule/flow/RuleBatchConvert.vue'),
          meta: { title: '规则批量导入转换', icon: 'mdi:file-document-outline' },
        },
        {
          path: 'compile',
          name: 'RuleCompileGenerate',
          component: () => import('#/views/rule/flow/RuleCompileGenerate.vue'),
          meta: { title: '规则编译生成', icon: 'mdi:cog-outline' },
        },
        {
          path: 'simulate',
          name: 'RuleTestRun',
          component: () => import('#/views/rule/flow/RuleTestRun.vue'),
          meta: { title: '执行与校验', icon: 'mdi:play-circle-outline' },
        },
      ],
    },

    // ========== 规则库 ==========
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
