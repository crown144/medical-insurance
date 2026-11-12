<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref, shallowRef, watch } from 'vue';
import { useRoute } from 'vue-router';

import {
  ArrowLeft,
  Document,
  Warning,
} from '@element-plus/icons-vue';
import axios from 'axios';
import { ElButton, ElEmpty, ElIcon } from 'element-plus';

import {
  getRuleDescriptionEnglish,
  getRuleNameEnglish,
  getRuleTypeLabel,
  getViolationReasonEnglish,
} from '../../config/rule-type';

const API_BASE_URL = '/api';
const PATIENT_CASE_API = '/api/cases/patient-case/';

interface Highlight {
  field_path: string;
  highlighted_text: string;
}
interface EvidenceEntry {
  source_path: string;
  text: string;
  comparisons?: [string, string | number][];
}
interface AtomicEvidence {
  normalized_constraint?: string;
  status?: string;
  reason?: string;
  searched_paths?: string[];
  checked_records?: EvidenceEntry[];
  evidence?: EvidenceEntry[];
}
interface AuditEvidence {
  applicability?: AtomicEvidence;
  atomic_results?: Record<string, AtomicEvidence>;
  failed_atomic_ids?: string[];
  insufficient_atomic_ids?: string[];
  insufficient_evidence?: boolean;
  selected_branch?: null | string;
  evaluation_trace?: { atomic_id: string; branch: string; status: string }[];
}
interface ViolationItem {
  id: number;
  hospitalization_id: string;
  reason: string;
  review_status?: string;
  rule: {
    description: string;
    descriptionEnglish?: string;
    drug_name?: string;
    drugName?: string;
    type?: string;
  };
  highlights: Highlight[];
  current_rule_conditions?: Record<string, string>;
  audit_evidence?: AuditEvidence | null;
}

const route = useRoute();

// --- 状态 ---
const isLoading = ref(true);
const error = ref('');
const taskId = ref<string>('');
const hospitalizationId = ref<string>('');
const allViolationsInCase = ref<ViolationItem[]>([]);
const selectedViolation = ref<null | ViolationItem>(null);

// 🟢 性能优化：存纯文本行，而非大对象
const jsonLines = shallowRef<string[]>([]);
const medicalRecordRaw = shallowRef<any>(null);
const recordVisible = ref(false);
const evidenceTarget = ref<{ line: number; text: string } | null>(null);
const recordLineByPath = new Map<string, number>();

const formatRecord = (value: unknown) => {
  const lines: string[] = [];
  recordLineByPath.clear();
  const visit = (item: any, path: string, depth: number, prefix = '', suffix = '') => {
    const indent = '  '.repeat(depth);
    recordLineByPath.set(path, lines.length);
    if (Array.isArray(item) && item.length) {
      lines.push(`${indent}${prefix}[`);
      item.forEach((child, index) => visit(child, `${path}[${index}]`, depth + 1, '', index < item.length - 1 ? ',' : ''));
      lines.push(`${indent}]${suffix}`);
    } else if (item && typeof item === 'object' && Object.keys(item).length) {
      lines.push(`${indent}${prefix}{`);
      const entries = Object.entries(item);
      entries.forEach(([key, child], index) => visit(child, `${path}.${key}`, depth + 1, `${JSON.stringify(key)}: `, index < entries.length - 1 ? ',' : ''));
      lines.push(`${indent}}${suffix}`);
    } else {
      lines.push(`${indent}${prefix}${JSON.stringify(item)}${suffix}`);
    }
  };
  visit(value, '$', 0);
  return lines;
};

const evidenceLocation = (entry: EvidenceEntry) => {
  const path = entry.source_path.startsWith('$') ? entry.source_path : `$.${entry.source_path}`;
  const line = recordLineByPath.get(path);
  if (line === undefined || !entry.text) return null;
  const escapedText = JSON.stringify(entry.text).slice(1, -1);
  return jsonLines.value[line]?.includes(escapedText) ? line : null;
};

const viewRecordLine = async (line: number, text: string) => {
  recordVisible.value = true;
  evidenceTarget.value = { line, text };
  await nextTick();
  // Wait for the newly visible record and its line wrapping to be laid out.
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
  const target = scrollerRef.value?.querySelector<HTMLElement>(`[data-record-line="${line}"]`);
  target?.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
};

const viewEvidenceInRecord = (entry: EvidenceEntry) => {
  const line = evidenceLocation(entry);
  if (line !== null) void viewRecordLine(line, entry.text);
};

const diagnosisRoot = (path: string) => {
  const root = path.replace(/^\$\./, '').split(/[.[]/)[0];
  return root === '诊断' || root === '诊断信息' ? root : null;
};

const isUnmatchedDiagnosis = (condition: AtomicEvidence) =>
  condition.status === 'unsatisfied' && Boolean(condition.checked_records?.length) &&
  condition.checked_records!.every((entry) => Boolean(diagnosisRoot(entry.source_path)));

const diagnosisLocation = (condition: AtomicEvidence) => {
  const root = condition.checked_records?.map((entry) => diagnosisRoot(entry.source_path))
    .find((item) => item && recordLineByPath.has(`$.${item}`));
  return root ? { line: recordLineByPath.get(`$.${root}`)!, text: root } : null;
};

const viewDiagnosisRecords = (condition: AtomicEvidence) => {
  const location = diagnosisLocation(condition);
  if (location) void viewRecordLine(location.line, location.text);
};

// --- 虚拟滚动配置 ---
const scrollerRef = ref<HTMLDivElement | null>(null);
const scrollTop = ref(0);
const viewportHeight = ref(600); // 容器高度，改为响应式
const defaultItemHeight = 24; // 默认单行高度
const buffer = 15; // 缓冲区
const containerWidth = ref(1000); // 容器宽度，默认给个安全值

// --- ResizeObserver 逻辑 ---
let resizeObserver: ResizeObserver | null = null;

watch(scrollerRef, (element) => {
  resizeObserver?.disconnect();
  if (element) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect) {
          // 减去 padding (24 * 2 = 48)
          containerWidth.value = Math.max(entry.contentRect.width - 48, 100);
          // 实时更新视口高度，解决底部留白问题
          viewportHeight.value = entry.contentRect.height;
        }
      }
    });
    resizeObserver.observe(element);
  }
}, { flush: 'post' });

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

// --- 1. 加载数据 ---
const loadPageData = async () => {
  taskId.value = String(route.query.taskId || '');
  hospitalizationId.value = String(route.query.hospitalizationId || '');

  if (!taskId.value || !hospitalizationId.value) {
    error.value = 'Missing required parameters.';
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  try {
    // 1.1 并发获取违规列表
    const fetchViolations = async () => {
      let all: ViolationItem[] = [];
      let next = `${API_BASE_URL}/results/`;
      let page = 1;
      while (next) {
        const params =
          page === 1
            ? {
                task_id: taskId.value,
                hospitalization_id: hospitalizationId.value,
              }
            : {};
        const res = await axios.get(next, page === 1 ? { params } : {});
        if (res.data?.results) {
          all = all.concat(res.data.results);
          next = res.data.next;
        } else break;
        page++;
      }
      return all;
    };

    // 1.2 获取病历全文
    const fetchRecord = () =>
      axios.get(PATIENT_CASE_API, {
        params: {
          hospitalization_id: hospitalizationId.value,
          task_id: taskId.value,
        },
      });

    const [resViolations, resRecord] = await Promise.allSettled([
      fetchViolations(),
      fetchRecord(),
    ]);

    allViolationsInCase.value =
      resViolations.status === 'fulfilled' ? resViolations.value : [];

    if (resRecord.status === 'fulfilled' && resRecord.value.data) {
      const raw = resRecord.value.data;
      medicalRecordRaw.value = Object.freeze(raw);
      // 格式化 JSON，2空格缩进
      jsonLines.value = formatRecord(raw);
    } else {
      jsonLines.value = [
        `// No medical record data is available or loading failed.`,
        `// Please check the backend service.`,
      ];
    }
  } catch (error_: any) {
    error.value = error_.message;
  } finally {
    isLoading.value = false;
  }
};

// --- 2. 核心：虚拟滚动与智能高亮 ---

const escapeHtml = (unsafe: string) => {
  return unsafe
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
};

// 简单的行高估算（为了支持长文本折行）
// 动态计算每行能容纳的字符数
const getLineHeight = (line: string) => {
  const base = defaultItemHeight;
  // 假设字体大小 14px，按最宽字符（中文）估算以确保安全
  // 如果全是英文，虽然会高估行数导致留白，但绝不会重叠
  const charsPerLine = Math.floor(containerWidth.value / 14);

  if (line.length > charsPerLine) {
    return base * Math.ceil(line.length / charsPerLine);
  }
  return base;
};

// 计算累加高度（用于撑开滚动条）
const linePositions = computed(() => {
  const positions: number[] = [0];
  let current = 0;
  for (let i = 0; i < jsonLines.value.length; i++) {
    const h = getLineHeight(jsonLines.value[i] || '');
    current += h;
    positions.push(current);
  }
  return positions;
});

const totalHeight = computed(
  () => linePositions.value[linePositions.value.length - 1],
);

const visibleData = computed(() => {
  const scroll = scrollTop.value;
  // 二分查找当前可视的起始行（因为行高不固定）
  let startIdx = 0;
  let high = linePositions.value.length - 1;
  let low = 0;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if ((linePositions.value[mid] ?? 0) < scroll) {
      startIdx = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  const start = Math.min(0, startIdx);
  // 向下预加载
  // 🟢 修复空白关键点：
  // 之前根据 getLineHeight（高估值）累加来判断是否填满视口，导致实际渲染行数不足。
  // 现在改用 defaultItemHeight（最小行高）来计算需要的行数，确保宁多勿少，填满视口。
  const itemsNeeded =
    Math.ceil(viewportHeight.value / defaultItemHeight) + buffer * 2;
  const end = Math.min(start + Math.max(itemsNeeded, jsonLines.value.length), jsonLines.value.length);

  const lines = jsonLines.value.slice(start, end);

  const highlightSet = new Set(
    evidenceTarget.value ? [JSON.stringify(evidenceTarget.value.text).slice(1, -1)] : [],
  );
  return {
    startOffset: linePositions.value[start],
    items: lines.map((line, index) => {
      const realIndex = start + index;
      // 1. 先转义 HTML，防止 XSS，同时为了匹配 &quot;
      let html = escapeHtml(line);

      if (highlightSet.size > 0 && evidenceTarget.value?.line === realIndex) {
        highlightSet.forEach((val) => {
          // 🟢 智能匹配修正：
          // 1. 转义 keyword，使其能匹配到 &quot; 等转义后的字符
          const safeVal = escapeHtml(val);

          // 2. 构造正则：如果是纯数字，要求两边不能是数字（防止匹配到 "123" 里的 "1"）
          let regex: RegExp;
          if (/^\d+(\.\d+)?$/.test(val)) {
            // 数字边界匹配：前面不能是数字，后面也不能是数字
            regex = new RegExp(String.raw`(?<!\d)(${safeVal})(?!\d)`, 'g');
          } else {
            // 普通文本，直接全局匹配
            // 这里的 split/join 替换比正则快且安全
            // 但为了不破坏已有的 <mark> 标签，我们得小心。
            // 简单起见，我们假设高亮词不重叠。
            regex = new RegExp(
              safeVal.replaceAll(/[.*+?^${}()|[\]\\]/g, String.raw`\$&`),
              'g',
            );
          }

          // 🟢 修复 bug：使用回调函数避免 $1 被错误解析
          html = html.replace(regex, (match) => `<mark class="hl">${match}</mark>`);
        });
      }

      return {
        index: realIndex,
        content: html,
      };
    }),
  };
});

const onScroll = (e: Event) => {
  scrollTop.value = (e.target as HTMLElement).scrollTop;
};

// --- 交互 ---
const selectViolation = (v: ViolationItem) => {
  selectedViolation.value = v;
  recordVisible.value = false;
  evidenceTarget.value = null;
};

watch(
  () => [route.query.taskId, route.query.hospitalizationId],
  ([t, h]) => {
    if (t && h) {
      selectedViolation.value = null;
      allViolationsInCase.value = [];
      jsonLines.value = [];
      loadPageData();
    }
  },
  { immediate: true },
);

watch(allViolationsInCase, (newVal) => {
  if (newVal.length > 0 && !selectedViolation.value) {
    selectViolation(newVal[0]!);
  }
});

const goBack = () => window.history.back();

const formatRuleType = (t?: string) => getRuleTypeLabel(t) || t || 'Rule';

const getViolationName = (v: ViolationItem) => {
  // 1. 尝试从 violation_item (这里假设后端API如果包含了它，需要添加到 ViolationItem 接口定义) 获取
  // 注意：我们需要先在 ViolationItem 接口中添加 violation_item 字段
  const rawItem = (v as any).violation_item;

  let parsedName = '';
  if (rawItem) {
    try {
       // 如果是 JSON 字符串
       if (rawItem.trim().startsWith('{')) {
          const validJson = rawItem.replaceAll("'", '"').replaceAll('None', 'null');
          const obj = JSON.parse(validJson);
          parsedName = obj.name || obj.drug_name || obj.item_name || obj.xmname || obj.xmmc || obj['收费项目名称'] || obj['收费项目代码'];
       } else {
          parsedName = rawItem;
       }
    } catch {}
  }

  const rawName = parsedName || v.rule?.drug_name || v.rule?.drugName || 'Unknown Item';
  const translated = getRuleNameEnglish(rawName);
  return translated || (/[\u3400-\u9fff]/.test(rawName) ? 'Item name unavailable in English' : rawName);
};

const getViolationReason = (v: ViolationItem) => {
  return getViolationReasonEnglish(v.reason) || v.reason || '-';
};

const getRuleDescription = (v: ViolationItem) => {
  const english = v.rule?.descriptionEnglish || getRuleDescriptionEnglish(v.rule?.description);
  if (english) return english;
  const original = v.rule?.description || '';
  return /[\u3400-\u9fff]/.test(original) ? 'English translation unavailable' : original || '-';
};

const checkedEvidence = computed(() => {
  const evidence = selectedViolation.value?.audit_evidence;
  const branch = evidence?.selected_branch;
  const branchIds = branch ? (evidence?.evaluation_trace || [])
    .filter((entry) => entry.branch === branch || branch.startsWith(`${entry.branch}.`))
    .map((entry) => entry.atomic_id) : [];
  const ids = [...new Set([...branchIds, ...(evidence?.failed_atomic_ids || []), ...(evidence?.insufficient_atomic_ids || [])])];
  return ids.flatMap((id) => {
    const item = evidence?.atomic_results?.[id];
    return item ? [{ id, ...item }] : [];
  });
});

const decisionStatus = (v: ViolationItem) => {
  if (v.review_status === 'needs_review' || v.audit_evidence?.insufficient_evidence) return 'Needs review';
  if (v.review_status === 'compliant') return 'Compliant';
  if (v.review_status === 'not_applicable') return 'Not applicable';
  return 'Violation'; // This endpoint returns persisted violation results.
};
const relevantIds = computed(() => new Set([
  ...(selectedViolation.value?.audit_evidence?.failed_atomic_ids || []),
  ...(selectedViolation.value?.audit_evidence?.insufficient_atomic_ids || []),
]));
const decisionConditions = computed(() => checkedEvidence.value.filter((item) => relevantIds.value.has(item.id)));
const supportingConditions = computed(() => checkedEvidence.value.filter((item) => !relevantIds.value.has(item.id)));
const englishText = (text?: string) => !text ? '' : /[\u3400-\u9fff]/.test(text) ? 'English description unavailable' : text;
const conditionHeading = (condition: AtomicEvidence) => {
  if (condition.status === 'insufficient_evidence') return 'Insufficient evidence';
  if (isUnmatchedDiagnosis(condition)) return 'Required diagnosis not found';
  return condition.status === 'unsatisfied' ? 'Condition not satisfied' : 'Condition checked';
};
const shortReason = (v: ViolationItem) => {
  const evidence = v.audit_evidence;
  if (decisionStatus(v) === 'Needs review') return 'Insufficient evidence; manual review needed.';
  const id = evidence?.failed_atomic_ids?.[0];
  const item = id ? evidence?.atomic_results?.[id] : undefined;
  if (item && isUnmatchedDiagnosis(item)) return 'A required diagnosis was not found.';
  if (item?.normalized_constraint) return `${englishText(item.normalized_constraint)} — not satisfied.`;
  const reason = getViolationReason(v);
  return englishText(reason.replace(/\bA\d+:\s*/g, '')) || 'See finding details.';
};
const comparisonText = (entry: EvidenceEntry) => entry.comparisons?.length
  ? ` (${entry.comparisons.map(([operator, value]) => `${operator} ${value}`).join(', ')})` : '';
const statusText = (condition: AtomicEvidence) => condition.status === 'satisfied' ? 'Satisfied' :
  condition.status === 'unsatisfied' ? 'Not satisfied' : condition.status === 'insufficient_evidence' ? 'Insufficient evidence' : 'Checked';

const legacyEvidence = computed<EvidenceEntry[]>(() =>
  (selectedViolation.value?.highlights || []).map((item) => ({
    source_path: item.field_path,
    text: item.highlighted_text,
  })),
);

// The original values remain available in the medical record. Do not invent
// a translation when no verified display term is available.
const evidenceDisplayText = (text: string) => {
  const clinicalTerms: Record<string, string> = {
    '非酒精性脂肪性肝病': 'Non-alcoholic fatty liver disease',
    '肝功能异常': 'Abnormal liver function',
  };
  const translated = clinicalTerms[text] || getRuleNameEnglish(text);
  if (translated && !/[\u3400-\u9fff]/.test(translated)) return translated;
  return /[\u3400-\u9fff]/.test(text) ? 'English translation unavailable' : text;
};

const sourceDisplayName = (path: string) => {
  const root = path.replace(/^\$\./, '').split(/[.[]/)[0];
  const labels: Record<string, string> = {
    诊断: 'Diagnosis Records',
    诊断信息: 'Diagnosis Records',
    用药信息: 'Medication Records',
    医保信息: 'Insurance Information',
    入院记录: 'Admission Record',
    首次病程记录: 'First Progress Note',
    收费报告: 'Charge Records',
  };
  return labels[root || ''] || 'Medical Record';
};
</script>

<template>
  <div class="page-wrap">
    <div class="page-header-card">
      <div class="title-row">
        <div class="title-left">
          <div class="title-bar"></div>
          <div class="title-text">
            <h1 class="page-title">Audit Result Detail</h1>
            <div class="sub-info">
              <span class="sub-item">Task: {{ taskId }}</span>
              <span class="dot">•</span>
              <span class="sub-item">Hospitalization ID: {{ hospitalizationId }}</span>
            </div>
          </div>
        </div>
        <div class="header-actions">
          <ElButton @click="goBack" class="back-btn">
            <ElIcon class="el-icon--left"><ArrowLeft /></ElIcon>Back to List
          </ElButton>
        </div>
      </div>

      <!-- <div class="patient-bar">
        <div class="pitem">
          <div class="k">
            <ElIcon><User /></ElIcon> 患者信息
          </div>
          <div class="v user-name">
            {{ patientSummary.name }}
            <span class="sub-v"
              >({{ patientSummary.sex }}/{{ patientSummary.age }})</span
            >
          </div>
        </div>
        <div class="pitem">
          <div class="k">科室</div>
          <div class="v">{{ patientSummary.dept }}</div>
        </div>
        <div class="pitem">
          <div class="k">费用总额</div>
          <div class="v fee">¥ {{ patientSummary.total }}</div>
        </div>
      </div> -->
    </div>

    <div class="page-body" v-loading="isLoading">
      <div v-if="error" class="error-container">
        <ElIcon><Warning /></ElIcon> {{ error }}
      </div>

      <div v-else class="grid-layout">
        <div class="panel list-panel">
          <div class="panel-header">
            <div class="panel-title">
              <ElIcon class="mr-1"><Warning /></ElIcon> Violation Items
            </div>
            <div class="panel-badge">{{ allViolationsInCase.length }}</div>
          </div>
          <div class="list-content">
            <button
              v-for="v in allViolationsInCase" :key="v.id" type="button"
              class="violation-card" :class="{ active: selectedViolation?.id === v.id }"
              :aria-pressed="selectedViolation?.id === v.id" @click="selectViolation(v)"
            >
              <span class="rule-title">{{ getViolationName(v) }}</span>
              <span class="list-category">{{ formatRuleType(v.rule?.type) }}</span>
              <span class="list-reason">{{ shortReason(v) }}</span>
            </button>
            <ElEmpty
              v-if="allViolationsInCase.length === 0"
              description="No violation data available."
            />
          </div>
        </div>

        <div class="panel preview-panel">
          <div class="panel-header">
            <div class="panel-title"><ElIcon class="mr-1"><Document /></ElIcon> Finding Details</div>
            <ElButton v-if="recordVisible" link type="primary" @click="recordVisible = false">Back to Finding Details</ElButton>
          </div>

          <div v-if="!selectedViolation" class="evidence-empty">
            <ElEmpty description="Select a violation to view its evidence." />
          </div>
          <div v-else-if="!recordVisible" class="evidence-content">
            <div class="finding-header">
              <h2>{{ getViolationName(selectedViolation) }}</h2>
              <span class="status-label" :class="decisionStatus(selectedViolation) === 'Needs review' ? 'status-review' : decisionStatus(selectedViolation) === 'Violation' ? 'status-violation' : 'status-neutral'">{{ decisionStatus(selectedViolation) }}</span>
            </div>

            <section class="decision-section">
              <h3>Decision</h3>
              <template v-if="decisionConditions.length">
                <div v-for="condition in decisionConditions" :key="condition.id" class="decision-item" :class="{ 'decision-item--review': condition.status === 'insufficient_evidence' }">
                  <div class="decision-heading">{{ conditionHeading(condition) }} <span>· {{ condition.id }}</span></div>
                  <div class="condition-description">{{ englishText(condition.normalized_constraint) || 'Condition description unavailable' }}</div>
                  <p class="decision-reason">{{ isUnmatchedDiagnosis(condition) ? 'No matching diagnosis was found in the diagnosis records checked.' : condition.status === 'insufficient_evidence' ? 'Insufficient evidence to determine whether this condition is satisfied.' : englishText(condition.reason) || 'No detailed reason was saved.' }}</p>
                  <div v-if="condition.searched_paths?.length" class="evidence-muted">Sources checked: {{ [...new Set(condition.searched_paths.map(sourceDisplayName))].join(', ') }}</div>
                  <ElButton v-if="isUnmatchedDiagnosis(condition) && diagnosisLocation(condition)" link type="primary" @click="viewDiagnosisRecords(condition)">View diagnosis records</ElButton>
                  <template v-if="!isUnmatchedDiagnosis(condition)">
                    <div v-for="(entry, index) in (condition.evidence?.length ? condition.evidence : condition.checked_records || [])" :key="index" class="evidence-excerpt">
                      <span class="evidence-record__source">{{ sourceDisplayName(entry.source_path) }} · {{ condition.evidence?.length ? 'Original evidence' : 'Original record checked' }}</span>
                      <div class="original-text">{{ entry.text }}</div>
                      <ElButton v-if="evidenceLocation(entry) !== null" link type="primary" @click="viewEvidenceInRecord(entry)">View in medical record</ElButton>
                    </div>
                  </template>
                </div>
              </template>
              <p v-else class="decision-reason">{{ englishText(getViolationReason(selectedViolation)) || 'No detailed reason was saved.' }}</p>
            </section>

            <section v-if="selectedViolation.audit_evidence" class="support-section">
              <h3>Supporting checks</h3>
              <div v-for="(entry, index) in selectedViolation.audit_evidence.applicability?.evidence || []" :key="`app-${index}`" class="support-row">
                <span class="support-check">✓ <span>Applicability matched</span></span>
                <span>{{ evidenceDisplayText(entry.text) }}<span v-if="evidenceDisplayText(entry.text) !== entry.text" class="original-inline"> · Original evidence: {{ entry.text }}</span></span>
                <ElButton v-if="evidenceLocation(entry) !== null" link type="primary" @click="viewEvidenceInRecord(entry)">View in medical record</ElButton>
              </div>
              <div v-for="condition in supportingConditions" :key="condition.id" class="support-row">
                <span class="support-check" :class="{ 'support-check--muted': condition.status !== 'satisfied' }">{{ condition.status === 'satisfied' ? '✓' : '•' }} <span>{{ englishText(condition.normalized_constraint) || 'Condition' }} · {{ statusText(condition) }}</span></span>
                <span v-for="(entry, index) in condition.evidence || []" :key="index" class="support-value">{{ evidenceDisplayText(entry.text) }}{{ comparisonText(entry) }} <ElButton v-if="evidenceLocation(entry) !== null" link type="primary" @click="viewEvidenceInRecord(entry)">View in medical record</ElButton></span>
              </div>
              <div v-if="!selectedViolation.audit_evidence.applicability?.evidence?.length && !supportingConditions.length" class="evidence-muted">No supporting checks were saved.</div>
            </section>
            <section v-else class="support-section">
              <h3>Saved evidence</h3>
              <p class="evidence-muted">This historical result does not include condition-level evidence.</p>
              <div v-for="(entry, index) in legacyEvidence" :key="index" class="evidence-excerpt">
                <span class="evidence-record__source">{{ sourceDisplayName(entry.source_path) }} · Original evidence</span>
                <div class="original-text">{{ entry.text }}</div>
                <ElButton v-if="evidenceLocation(entry) !== null" link type="primary" @click="viewEvidenceInRecord(entry)">View in medical record</ElButton>
              </div>
              <p v-if="!legacyEvidence.length" class="evidence-muted">No evidence excerpts were saved.</p>
            </section>
            <details class="policy-details"><summary>View full policy rule</summary><p>{{ getRuleDescription(selectedViolation) === 'English translation unavailable' ? selectedViolation.rule?.description : getRuleDescription(selectedViolation) }}</p></details>
          </div>

          <div v-show="recordVisible" class="virtual-scroller" ref="scrollerRef" @scroll="onScroll">
            <div class="phantom" :style="{ height: `${totalHeight}px` }"></div>
            <div class="render-area" :style="{ transform: `translateY(${visibleData.startOffset}px)` }">
              <div v-for="line in visibleData.items" :key="line.index" :data-record-line="line.index" class="line-item" v-html="line.content"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.grid-layout { grid-template-columns: minmax(0, 3fr) minmax(0, 7fr) !important; }
.panel, .evidence-content { min-width: 0; }
.violation-card { display: flex; flex-direction: column; width: 100%; text-align: left; border-left: 4px solid transparent; }
.violation-card.active { border-left-color: #409eff; }
.violation-card:focus-visible { outline: 3px solid #409eff; outline-offset: 2px; }
.list-category { margin-top: 5px; color: #667b95; font-size: 12px; }
.list-reason { margin-top: 8px; color: #465468; font-size: 13px; line-height: 1.4; overflow-wrap: anywhere; }
.finding-header { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.finding-header h2 { margin: 0; flex: 1; min-width: 0; font-size: 19px; line-height: 1.35; color: #263445; overflow-wrap: anywhere; }
.status-label { padding: 3px 9px; border-radius: 4px; font-weight: 600; font-size: 12px; }
.status-violation { background: #fef0f0; color: #b83232; }
.status-review { background: #fdf4df; color: #976400; }
.status-neutral { background: #eef4f7; color: #465c6b; }
.decision-section, .support-section { margin-top: 18px; }
.decision-section h3, .support-section h3 { margin: 0 0 9px; font-size: 14px; color: #344457; }
.decision-item { padding: 11px 14px; margin: 8px 0; border-left: 3px solid #e36868; background: #fff8f7; overflow-wrap: anywhere; }
.decision-item--review { border-left-color: #d6a13c; background: #fffbf0; }
.decision-item--review .decision-heading { color: #89600c; }
.decision-heading { font-weight: 700; color: #8d3030; }
.decision-heading span { color: #71839a; font-size: 12px; font-weight: 500; }
.condition-description, .decision-reason { margin: 5px 0; color: #354458; line-height: 1.45; overflow-wrap: anywhere; }
.support-row { display: flex; gap: 8px 16px; flex-wrap: wrap; align-items: baseline; border-top: 1px solid #edf0f4; padding: 8px 0; color: #38495c; font-size: 13px; overflow-wrap: anywhere; }
.support-check { color: #258452; }.support-check span { color: #354458; }.support-check--muted { color: #738195; }
.support-value { overflow-wrap: anywhere; }
.original-inline { color: #657487; }
.evidence-excerpt { margin-top: 8px; color: #354458; }.original-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.policy-details { border-top: 1px solid #e9edf2; margin-top: 18px; padding-top: 14px; color: #354458; overflow-wrap: anywhere; }
.policy-details summary { color: #1675d1; cursor: pointer; }
.policy-details p { line-height: 1.5; }
@media (max-width: 800px) { .grid-layout { grid-template-columns: minmax(0, 1fr) !important; height: auto !important; } .list-content { max-height: 320px; } }

.evidence-content {
  flex: 1;
  overflow: auto;
  padding: 20px 24px;
}
.evidence-section + .evidence-section {
  margin-top: 24px;
}
.evidence-section__title {
  font-size: 15px;
  font-weight: 700;
  color: #263d59;
}
.evidence-section__subtitle,
.evidence-muted {
  margin: 6px 0 10px;
  font-size: 12px;
  line-height: 1.6;
  color: #71839a;
}
.evidence-record {
  margin-top: 10px;
  padding: 12px 14px;
  border: 1px solid #e5edf7;
  border-radius: 8px;
  background: #f8fbff;
}
.evidence-record__source {
  margin-bottom: 5px;
  font-size: 12px;
  font-weight: 600;
  color: #6683a7;
}
.evidence-record__text {
  color: #354b65;
  line-height: 1.6;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.condition-evidence {
  margin-top: 12px;
}
.condition-evidence__heading {
  color: #354b65;
  font-weight: 600;
  line-height: 1.5;
}
.condition-evidence__reason {
  margin-top: 5px;
  color: #ad6b19;
  line-height: 1.5;
}
.evidence-notice {
  padding: 11px 14px;
  margin-bottom: 20px;
  border: 1px solid #f2dfb7;
  border-radius: 8px;
  background: #fffaf0;
  color: #8b6b34;
  font-size: 12px;
  line-height: 1.6;
}
/* 布局与配色 */
.page-wrap {
  background: #f5f7fb;
  padding: 20px;
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei',
    sans-serif;
}
.page-header-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  padding: 20px 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.title-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-bar {
  width: 4px;
  height: 24px;
  background: #409eff;
  border-radius: 2px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.sub-info {
  margin-left: 12px;
  font-size: 13px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f4f4f5;
  padding: 4px 10px;
  border-radius: 4px;
}
.sub-item {
  font-family: monospace;
}
.dot {
  color: #dcdfe6;
}

.patient-bar {
  background: #fcfcfc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px 20px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.pitem {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.k {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}
.v {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub-v {
  font-size: 13px;
  color: #909399;
  font-weight: normal;
  margin-left: 4px;
}
.v.fee {
  color: #f56c6c;
  font-family: monospace;
  font-size: 16px;
}

.page-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.grid-layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  height: 100%;
  min-height: 600px;
}

.panel {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
.panel-header {
  height: 50px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  display: flex;
  align-items: center;
}
.mr-1 {
  margin-right: 6px;
  font-size: 16px;
  color: #909399;
}
.panel-badge {
  background: #f56c6c;
  color: #fff;
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  margin-left: 8px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f5f7fa;
}
.violation-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}
.violation-card:hover {
  border-color: #c6e2ff;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.violation-card.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 0 0 1px #409eff;
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
  gap: 8px;
}
.rule-title {
  flex: 1;
  min-width: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
  word-break: normal;
  overflow-wrap: anywhere;
}
.card-header-row .tags {
  flex-shrink: 0;
}
.checked-conditions {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #e8eef6;
  font-size: 12px;
  line-height: 1.5;
  color: #52677f;
}
.checked-conditions__label {
  margin-bottom: 3px;
  font-weight: 600;
  color: #70839b;
}
.desc-text {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
  line-height: 1.5;
}
.reason-box {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  background: #fdf6ec;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #faecd8;
}
.active .reason-box {
  background: #fff;
  border-color: #d9ecff;
}
.reason-title {
  font-weight: 700;
  color: #e6a23c;
  margin-bottom: 4px;
}
.card-footer {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
.evidence-link {
  font-size: 12px;
  color: #409eff;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 2px;
}

/* 虚拟滚动优化版 */
.virtual-scroller {
  flex: 1;
  min-height: 0;
  max-height: min(70vh, 720px);
  overflow-y: auto;
  position: relative;
  background: #fff;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 14px;
  /* 允许长文本换行，解决横向滚动问题 */
  white-space: pre-wrap;
  word-break: break-all;
  color: #606266;
}
.phantom {
  display: none;
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  z-index: -1;
}
.render-area {
  position: relative;
  left: 0;
  right: 0;
  top: 0;
  padding: 0 24px; /* 左右留白 */
}
.line-item {
  /* 行高需与计算逻辑一致 */
  line-height: 24px;
}

/* 高亮样式 */
.render-area :deep(mark.hl) {
  background-color: #ffeb3b; /* 亮黄色 */
  color: #000;
  border-radius: 2px;
  padding: 0 1px;
  box-shadow: 0 0 2px rgba(0, 0, 0, 0.2);
  font-weight: bold;
}

.back-btn {
  font-weight: 500;
}
.error-container {
  padding: 40px;
  text-align: center;
  color: #909399;
}
</style>
