export const RULE_TYPE_LABEL_MAP = {
  超限定用药: 'Restricted Medication Use',
  超标准收费: 'Over-standard Charge',
  重复收费: 'Duplicate Charge',
  超频次收费: 'Excessive Frequency Billing',
  过度医疗: 'Overutilization',
  其他: 'Other',
} as const;

export const RULE_TYPE_OPTIONS = Object.entries(RULE_TYPE_LABEL_MAP).map(
  ([value, label]) => ({
    value,
    label,
  }),
);

export function getRuleTypeLabel(value?: null | string) {
  if (!value) return '-';
  return RULE_TYPE_LABEL_MAP[value as keyof typeof RULE_TYPE_LABEL_MAP] || value;
}

export function formatRuleTypeList(values?: null | string[]) {
  if (!values?.length) return [];
  return values.map((value) => getRuleTypeLabel(value));
}
