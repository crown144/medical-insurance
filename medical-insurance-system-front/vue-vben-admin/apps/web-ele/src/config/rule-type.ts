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

export const DEMO_RULE_IDS = [
  'R-0001',
  'R-0002',
  'R-20260704151155530323',
  'R-20260704151155864177',
  'R-20260704151200686615',
  'R-20260704151201033234',
  'R-20260704151207016105',
  'R-20260704151207710658',
  'R-20260709123055310514',
  'R-20260709124003677192',
] as const;

export const COMPILE_RULE_IDS = [
  'R-0001',
  'R-0002',
  'R-20260704151200686615',
  'R-20260704151201033234',
] as const;
export const COMPILE_RULE_NAMES = [
  '艾普拉唑',
  '醋酸钙',
  '静脉注射',
  '动脉加压注射',
] as const;

const DEMO_RULE_ID_SET = new Set<string>(DEMO_RULE_IDS);
const COMPILE_RULE_ID_SET = new Set<string>(COMPILE_RULE_IDS);
const COMPILE_RULE_NAME_SET = new Set<string>(COMPILE_RULE_NAMES);
const DEMO_RULE_DISPLAY_ID_MAP = new Map<string, string>(
  DEMO_RULE_IDS.map((ruleId, index) => [
    ruleId,
    `R-${String(index + 1).padStart(4, '0')}`,
  ]),
);

const RULE_NAME_LABEL_MAP: Record<string, string> = {
  'Ⅱ级护理': 'Level II nursing care',
  三人床: 'Three-person ward bed',
  '普通病房床位费(三人)': 'General ward bed fee (three-person room)',
  住院诊查费: 'Inpatient consultation fee',
  气管切开护理: 'Tracheostomy care',
  耳部特殊治疗: 'Special ear treatment',
  艾普拉唑: 'Ilaprazole',
  血气分析: 'Blood gas analysis',
  血清天门冬氨酸氨基转移酶测定: 'Serum aspartate aminotransferase test',
  葡萄糖测定: 'Glucose test',
  胃肠减压: 'Gastrointestinal decompression',
  连续性血液净化: 'Continuous blood purification',
  醋酸钙: 'Calcium acetate tablets',
  尿液分析: 'Urinalysis',
  糖化血红蛋白测定: 'Glycated hemoglobin test',
  机械辅助排痰: 'Mechanical assisted sputum clearance',
  动脉加压注射: 'Arterial pressure injection',
  动脉采血: 'Arterial blood collection',
  静脉注射: 'Intravenous injection',
  静脉采血: 'Venous blood collection',
};

const RULE_NAME_TERM_MAP: Record<string, string> = {
  一般专项护理: 'general specialized nursing care',
  三人床: 'three-person ward bed',
  中心静脉压测定: 'central venous pressure measurement',
  二级护理: 'level II nursing care',
  人工气腹术: 'artificial pneumoperitoneum',
  住院诊查费: 'inpatient consultation fee',
  冷热湿敷: 'hot and cold wet compress',
  动脉加压注射: 'arterial pressure injection',
  动脉置管护理: 'arterial catheter care',
  吸痰护理: 'sputum suction care',
  喉部特殊治疗: 'special laryngeal treatment',
  射频电疗: 'radiofrequency electrotherapy',
  床位费: 'bed fee',
  心电监测: 'ECG monitoring',
  气管切开护理: 'tracheostomy care',
  氧气吸入: 'oxygen inhalation',
  治疗: 'treatment',
  注射: 'injection',
  特殊: 'special',
  耳部: 'ear',
  胃肠: 'gastrointestinal',
  血氧饱和度监测: 'oxygen saturation monitoring',
  血液净化: 'blood purification',
  负压吸引: 'negative pressure suction',
  诊查费: 'consultation fee',
  连续性: 'continuous',
  雾化吸入: 'nebulized inhalation',
  静脉置管护理: 'venous catheter care',
  静脉注射: 'intravenous injection',
  静脉采血: 'venous blood collection',
};

const RULE_DESCRIPTION_LABEL_MAP: Record<string, string> = {
  '使用艾普拉唑须有十二指肠溃疡、反流性食管炎诊断':
    'Use of ilaprazole requires a diagnosis of duodenal ulcer or reflux esophagitis',
  '使用醋酸钙须有高磷血症诊断':
    'Use of calcium acetate tablets requires a diagnosis of hyperphosphatemia',
  '收取“血气分析”费用的同时收取“血清碳酸氢盐(HCO3)测定”费用':
    'Charging for blood gas analysis together with serum bicarbonate (HCO3) testing',
  '收取尿液分析费用时，同时收取尿沉渣白细胞分类费用或尿蛋白定量费用':
    'Charging for urinalysis together with urinary sediment leukocyte classification or urine protein quantification',
  '同一患者在90天内多次开展并收费':
    'The same patient is tested and charged multiple times within 90 days',
  '同一天用多种检测方法进行测定':
    'Multiple testing methods are used on the same day',
  '同一天用多种检测方法（干化学法和酶电极法）进行测定':
    'Multiple testing methods, including the dry chemistry method and the enzyme electrode method, are used on the same day',
  '对同一患者同日多次开展并纳入医保报销':
    'The same patient is tested multiple times on the same day and included in reimbursement',
  插胃管加收10元:
    'An additional 10 yuan may be charged when a gastric tube is inserted',
  '原价79元，射频、激光、微波加收20元；等离子加收50元；冷冻减收55元':
    'The base price is 79 yuan; radiofrequency, laser, or microwave treatment may add 20 yuan; plasma treatment may add 50 yuan; cryotherapy should reduce the charge by 55 yuan',
  '射频、激光、微波加收20元':
    'An additional 20 yuan may be charged for radiofrequency, laser, or microwave treatment',
  等离子加收50元:
    'An additional 50 yuan may be charged for plasma treatment',
  冷冻减收55元:
    'The charge should be reduced by 55 yuan for cryotherapy',
  '“静脉注射”与“静脉采血”不能同时开':
    'Intravenous injection and venous blood collection cannot be ordered at the same time',
  '“动脉加压注射”与“动脉采血”不能同时开':
    'Arterial pressure injection and arterial blood collection cannot be ordered at the same time',
  '机械辅助排痰使用项目的数量总计超过上限数量，单日上限数量1，项目收费单位日':
    'The total quantity of mechanical assisted sputum clearance exceeds the allowed limit; the daily limit is 1 day',
  '使用项目的数量总计超过上限数量，单日上限数量1，项目收费单位日':
    'The total quantity of the service item exceeds the allowed limit; the daily limit is 1 day',
};

const VIOLATION_REASON_LABEL_MAP: Record<string, string> = {
  '适应症不符：艾普拉唑限十二指肠溃疡或反流性食管炎，未发现相关诊断或病史支持':
    'Indication mismatch: ilaprazole is limited to duodenal ulcer or reflux esophagitis, and no supporting diagnosis or medical history was found',
  '适应症不符：醋酸钙限高磷血症患者使用，未发现相关诊断或病史支持':
    'Indication mismatch: calcium acetate tablets are limited to patients with hyperphosphatemia, and no supporting diagnosis or medical history was found',
  '“静脉注射”与“静脉采血”不能同时开':
    'Intravenous injection and venous blood collection cannot be ordered at the same time',
  '“动脉加压注射”与“动脉采血”不能同时开':
    'Arterial pressure injection and arterial blood collection cannot be ordered at the same time',
};

export function getRuleTypeLabel(value?: null | string) {
  if (!value) return '-';
  return RULE_TYPE_LABEL_MAP[value as keyof typeof RULE_TYPE_LABEL_MAP] || value;
}

export function isDemoRule(item: any) {
  const ruleId = item?.ruleId || item?.rule_id;
  return DEMO_RULE_ID_SET.has(String(ruleId || ''));
}

export function getDisplayRuleId(value?: null | string) {
  const ruleId = String(value || '');
  return DEMO_RULE_DISPLAY_ID_MAP.get(ruleId) || ruleId || '-';
}

export function filterDemoRules<T>(items: T[]) {
  return items.filter((item) => isDemoRule(item));
}

export function isCompileRule(item: any) {
  const ruleId = item?.ruleId || item?.rule_id;
  const ruleName = item?.drugName || item?.drug_name;
  return (
    COMPILE_RULE_ID_SET.has(String(ruleId || '')) ||
    COMPILE_RULE_NAME_SET.has(String(ruleName || ''))
  );
}

export function filterCompileRules<T>(items: T[]) {
  const seenNames = new Set<string>();
  return items
    .filter((item: any) => isCompileRule(item))
    .filter((item: any) => {
      const ruleName = String(item?.drugName || item?.drug_name || '');
      const dedupeKey = COMPILE_RULE_NAME_SET.has(ruleName)
        ? ruleName
        : String(item?.ruleId || item?.rule_id || '');
      if (seenNames.has(dedupeKey)) return false;
      seenNames.add(dedupeKey);
      return true;
    })
    .sort((left: any, right: any) => {
      const leftName = String(left?.drugName || left?.drug_name || '');
      const rightName = String(right?.drugName || right?.drug_name || '');
      const leftIndex = COMPILE_RULE_NAMES.indexOf(leftName as any);
      const rightIndex = COMPILE_RULE_NAMES.indexOf(rightName as any);
      return (leftIndex < 0 ? 999 : leftIndex) - (rightIndex < 0 ? 999 : rightIndex);
    });
}

export function isDemoRuleType(item: any, type: string) {
  return isDemoRule(item) && item?.type === type;
}

function hasChinese(value: string) {
  return /[\u4E00-\u9FFF]/.test(value);
}

function formatBilingual(value?: null | string, english?: string) {
  const text = (value || '').trim();
  if (!text) return '-';
  if (!hasChinese(text) || !english) return text;
  return `${text}（${english}）`;
}

function translateRuleDescription(value: string) {
  if (RULE_DESCRIPTION_LABEL_MAP[value]) return RULE_DESCRIPTION_LABEL_MAP[value];
  return '';
}

function translateRuleName(value: string) {
  if (RULE_NAME_LABEL_MAP[value]) return RULE_NAME_LABEL_MAP[value];

  const matchedKey = Object.keys(RULE_NAME_LABEL_MAP).find((key) =>
    value.includes(key),
  );
  if (matchedKey) return RULE_NAME_LABEL_MAP[matchedKey];

  const matchedTerms = Object.entries(RULE_NAME_TERM_MAP)
    .filter(([term]) => value.includes(term))
    .sort(([a], [b]) => b.length - a.length)
    .map(([, english]) => english);

  return Array.from(new Set(matchedTerms)).join(' / ');
}

function translateViolationReason(value: string) {
  if (VIOLATION_REASON_LABEL_MAP[value]) return VIOLATION_REASON_LABEL_MAP[value];
  if (RULE_DESCRIPTION_LABEL_MAP[value]) return RULE_DESCRIPTION_LABEL_MAP[value];

  if (value.includes('适应症不符') && value.includes('未发现相关诊断或病史支持')) {
    const itemName = Object.keys(RULE_NAME_LABEL_MAP).find((name) =>
      value.includes(name),
    );
    const englishName = itemName ? RULE_NAME_LABEL_MAP[itemName] : 'the item';
    return `Indication mismatch: ${englishName} lacks supporting diagnosis or medical history`;
  }

  const sameSecondConflictMatch = value.match(
    /^(.+?)与(.+?)在同一秒内同时开具，冲突时间点[:：](.+)$/,
  );
  if (sameSecondConflictMatch) {
    const firstItem = sameSecondConflictMatch[1] || '';
    const secondItem = sameSecondConflictMatch[2] || '';
    const conflictDetails = sameSecondConflictMatch[3] || '';
    const firstName = translateRuleName(firstItem.trim()) || firstItem.trim();
    const secondName = translateRuleName(secondItem.trim()) || secondItem.trim();
    const translatedDetails = conflictDetails
      .replace(/；/g, '; ')
      .replace(/，/g, ', ')
      .replace(/项/g, ' item(s)')
      .replace(/静脉注射/g, 'intravenous injection')
      .replace(/静脉采血/g, 'venous blood collection')
      .replace(/动脉加压注射/g, 'arterial pressure injection')
      .replace(/动脉采血/g, 'arterial blood collection');

    return `${firstName} and ${secondName} were ordered in the same second. Conflict time point(s): ${translatedDetails}`;
  }

  const frequencyMatch = value.match(
    /^(.+?)项目单日上限为(.+?)，发现超限记录[:：](.+?)(。|$)/,
  );
  if (frequencyMatch) {
    const itemName = frequencyMatch[1] || '';
    const limit = frequencyMatch[2] || '';
    const englishName = translateRuleName(itemName.trim()) || itemName.trim();
    return `${englishName} exceeds the daily limit of ${limit}`;
  }

  const durationMatch = value.match(/^(.+?)单日使用时长超限[:：]/);
  if (durationMatch) {
    const itemName = durationMatch[1] || '';
    const englishName =
      translateRuleName(itemName.trim()) || itemName.trim();
    return `${englishName} exceeds the allowed daily usage duration`;
  }

  const duplicateMatch = value.match(/^收费项目["“](.+?)["”].*重复收费/);
  if (duplicateMatch) {
    const itemName = duplicateMatch[1] || '';
    const englishName =
      translateRuleName(itemName.trim()) || itemName.trim();
    return `${englishName} has duplicate billing`;
  }

  const overPriceMatch = value.match(/价格超标[:：]标准价(.+?)[,，]实际价(.+?)(。|$)/);
  if (overPriceMatch) {
    return `Price exceeds the standard: standard price ${overPriceMatch[1]}, actual price ${overPriceMatch[2]}`;
  }

  return '';
}

export function getBilingualRuleTypeLabel(value?: null | string) {
  return formatBilingual(value, getRuleTypeLabel(value));
}

export function getBilingualRuleName(value?: null | string) {
  const text = (value || '').trim();
  return formatBilingual(text, translateRuleName(text));
}

export function getRuleNameEnglish(value?: null | string) {
  return translateRuleName((value || '').trim());
}

export function getBilingualRuleDescription(value?: null | string) {
  const text = (value || '').trim();
  return formatBilingual(text, translateRuleDescription(text));
}

export function getRuleDescriptionEnglish(value?: null | string) {
  return translateRuleDescription((value || '').trim());
}

export function getViolationReasonEnglish(value?: null | string) {
  return translateViolationReason((value || '').trim());
}

export function formatRuleTypeList(values?: null | string[]) {
  if (!values?.length) return [];
  return values.map((value) => getRuleTypeLabel(value));
}
