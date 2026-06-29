import type { RouteRecordRaw } from 'vue-router';

import { BasicLayout } from '#/layouts';

const ParentView = () => import('#/views/_shared/ParentView.vue');

const legacyRuleCenter: RouteRecordRaw = {
  path: '/rule',
  name: 'RuleCenter',
  component: BasicLayout,
  meta: {
    title: '',
    // icon: 'mdi:script-text-outline',
    hideInMenu: true,
  },
  redirect: '/rule/import/batch-convert',
  children: [
    {
      path: 'import',
      name: 'RuleImportAndValidate',
      component: ParentView,
      meta: {
        title: '',
        // icon: 'mdi:clipboard-check-outline',
        hideInMenu: true,
      },
      redirect: '/rule/import/batch-convert',
      children: [
        {
          path: 'batch-convert',
          name: 'RuleBatchConvert',
          component: () => import('#/views/rule/flow/RuleBatchConvert.vue'),
          meta: {
            title: 'Rule Discovery',
            icon: 'mdi:file-document-outline',
            hideInMenu: true,
          },
        },
        {
          path: 'compile',
          name: 'RuleCompile',
          component: () => import('#/views/rule/flow/RuleCompile.vue'),
          meta: {
            title: 'Rule Compilation',
            icon: 'mdi:cog-outline',
            hideInMenu: true,
          },
        },
      ],
    },
    // {
    //   path: 'library',
    //   name: 'RuleLibraryLegacy',
    //   component: ParentView,
    //   meta: {
    //     title: '规则库',
    //     icon: 'ant-design:unordered-list-outlined',
    //     hideInMenu: true,
    //   },
    //   redirect: '/rule/library/all-rules',
    //   children: [
    //     {
    //       path: 'all-rules',
    //       name: 'AllRulesLegacy',
    //       redirect: '/rule-library/all-rules',
    //       meta: { title: '全部规则', hideInMenu: true },
    //     },
    //     {
    //       path: 'limited-drug',
    //       name: 'RuleLimitedDrugLegacy',
    //       redirect: '/rule-library/limited-drug',
    //       meta: { title: '超限定用药规则', hideInMenu: true },
    //     },
    //     {
    //       path: 'over-standard-fee',
    //       name: 'RuleOverStandardFeeLegacy',
    //       redirect: '/rule-library/over-standard-fee',
    //       meta: { title: '超标准收费规则', hideInMenu: true },
    //     },
    //     {
    //       path: 'duplicate-charge',
    //       name: 'RuleDuplicateChargeLegacy',
    //       redirect: '/rule-library/duplicate-charge',
    //       meta: { title: '重复收费规则', hideInMenu: true },
    //     },
    //     {
    //       path: 'over-medical',
    //       name: 'RuleOverMedicalLegacy',
    //       redirect: '/rule-library/over-medical',
    //       meta: { title: '过度医疗规则', hideInMenu: true },
    //     },
    //     {
    //       path: 'fake-fee',
    //       name: 'RuleFakeFeeLegacy',
    //       redirect: '/rule-library/fake-fee',
    //       meta: { title: '超频次收费规则', hideInMenu: true },
    //     },
    //   ],
    // },
  ],
};

const ruleDiscovery: RouteRecordRaw = {
  path: '/rule-discovery',
  name: 'RuleDiscoveryMenu',
  component: BasicLayout,
  meta: {
    title: 'Rule Discovery',
    icon: 'mdi:file-document-outline',
    order: 10,
  },
  redirect: '/rule/import/batch-convert',
  children: [
    {
      path: 'entry',
      name: 'RuleDiscoveryEntry',
      redirect: '/rule/import/batch-convert',
      meta: {
        title: 'Rule Discovery',
        hideInMenu: true,
      },
    },
  ],
};

const ruleCompilation: RouteRecordRaw = {
  path: '/rule-compilation',
  name: 'RuleCompilationMenu',
  component: BasicLayout,
  meta: {
    title: 'Rule Compilation',
    icon: 'mdi:cog-outline',
    order: 11,
  },
  redirect: '/rule/import/compile',
  children: [
    {
      path: 'entry',
      name: 'RuleCompilationEntry',
      redirect: '/rule/import/compile',
      meta: {
        title: 'Rule Compilation',
        hideInMenu: true,
      },
    },
  ],
};

const ruleLibrary: RouteRecordRaw = {
  path: '/rule-library',
  name: 'RuleLibrary',
  component: BasicLayout,
  meta: {
    title: 'Rule Library',
    icon: 'ant-design:unordered-list-outlined',
    order: 12,
  },
  redirect: '/rule-library/all-rules',
  children: [
    {
      path: 'all-rules',
      name: 'AllRules',
      component: () => import('#/views/rule/AllRules.vue'),
      meta: { title: 'All Rules', icon: 'mdi:format-list-bulleted' },
    },
    {
      path: 'limited-drug',
      name: 'RuleLimitedDrug',
      component: () => import('#/views/rule/RuleDetail.vue'),
      props: { ruleType: '超限定用药' },
      meta: { title: 'Restricted Medication Rules', icon: 'mdi:pill' , hideInMenu: true },
    },
    {
      path: 'over-standard-fee',
      name: 'RuleOverStandardFee',
      component: () => import('#/views/rule/RuleDetail.vue'),
      props: { ruleType: '超标准收费' },
      meta: { title: 'Over-standard Charge Rules', icon: 'mdi:cash-multiple', hideInMenu: true },
    },
    {
      path: 'duplicate-charge',
      name: 'RuleDuplicateCharge',
      component: () => import('#/views/rule/RuleDetail.vue'),
      props: { ruleType: '重复收费' },
      meta: { title: 'Duplicate Charge Rules', icon: 'mdi:repeat', hideInMenu: true },
    },
    {
      path: 'over-medical',
      name: 'RuleOverMedical',
      component: () => import('#/views/rule/RuleDetail.vue'),
      props: { ruleType: '过度医疗' as any },
      meta: { title: 'Overutilization Rules', icon: 'mdi:stethoscope', hideInMenu: true },
    },
    {
      path: 'fake-fee',
      name: 'RuleFakeFee',
      component: () => import('#/views/rule/RuleDetail.vue'),
      props: { ruleType: '超频次收费' as any },
      meta: { title: 'Excessive Frequency Rules', icon: 'mdi:alert-circle-outline', hideInMenu: true },
    },
  ],
};

const routes: RouteRecordRaw[] = [
  legacyRuleCenter,
  ruleDiscovery,
  ruleCompilation,
  ruleLibrary,
];

export default routes;
