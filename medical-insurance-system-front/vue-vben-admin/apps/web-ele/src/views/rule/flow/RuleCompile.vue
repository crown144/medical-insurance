<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import type { RuleGenerateResult } from '#/api/rule';

import {
  Document,
  EditPen,
  FolderOpened,
  RefreshRight,
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  generateRuleApi,
  getSavedCompilation,
  requestRuleRevision,
  recompileRuleDraft,
  getRuleList,
  updateRule,
  validateRuleCodeApi,
} from '#/api/rule';
import {
  getRuleDescriptionEnglish,
  getRuleNameEnglish,
  getRuleTypeLabel,
} from '#/config/rule-type';

type RuleListItem = {
  id: number | string;
  ruleId: string;
  drugName: string;
  drugNameEnglish?: string;
  type: string;
  description: string;
  descriptionEnglish?: string;
  enabled: boolean;
  ruleCode: string;
  logicExpression?: string;
};

type EvidenceSource = {
  data_source?: string;
  field?: string;
  path: string;
};

const SOURCE_LABELS: Record<string, string> = {
  入院记录: 'Admission Record',
  首次病程记录: 'First Progress Note',
  诊断: 'Diagnosis Records',
  医保信息: 'Insurance Information',
  用药信息: 'Medication Records',
  收费报告: 'Charge Records',
};

const FIELD_LABELS: Record<string, string> = {
  现病史: 'History of Present Illness',
  既往史: 'Medical History',
  文档内容: 'Document Content',
  初步诊断: 'Initial Diagnosis',
  更正诊断: 'Revised Diagnosis',
  病例特点: 'Case Characteristics',
  诊断依据: 'Diagnostic Basis',
  诊断名称: 'Diagnosis Name',
  ICD编码: 'ICD Code',
  ICD10编码: 'ICD-10 Code',
  ICD10名称: 'ICD-10 Diagnosis Name',
  年龄: 'Age',
  药品名: 'Medication Name',
  药品通用名: 'Generic Drug Name',
  药品国家编码: 'National Medication Code',
  收费项目名称: 'Charge Item Name',
  收费日期: 'Charge Date',
  项目费用: 'Charge Amount',
};

const loading = ref(false);
const compiling = ref(false);
const saving = ref(false);
const testing = ref(false);
const compiledReady = ref(false);
const list = ref<RuleListItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const selectedRuleId = ref<number | string | null>(null);
const generatedCode = ref('');
const compilationResult = ref<RuleGenerateResult | null>(null);
const openOutputSections = ref<string[]>([]);
const sourceDialogVisible = ref(false);
const selectedBinding = ref<Record<string, any> | null>(null);

const modified = ref(false);
const revisionVisible = ref(false);
const revising = ref(false);
const revisionFeedback = ref('');
const revisionError = ref('');
const revisionProposal = ref<any>(null);
const workingDraft = ref<any>(null);
const previousCompilation = ref<RuleGenerateResult | null>(null);
let selectionEpoch = 0;
let revisionRequestId = 0;
const sessions = new Map<string, any>();
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
const draftFromResult = (result: RuleGenerateResult) => {
  const plan = result.compiled_plan;
  return plan ? { irr: result.irr, atomic_constraints: result.atomic_constraints,
    logic_tree: plan.logic, applicability_binding: plan.applicability,
    constraint_bindings: plan.constraints } : null;
};
const logicText = (node: any): string => typeof node === 'string' ? node :
  Object.entries(node || {}).map(([op, children]) => op === 'not'
    ? `NOT (${logicText((children as any[])[0])})`
    : `(${(children as any[]).map(logicText).join(` ${op.toUpperCase()} `)})`).join('');
const rememberSession = () => {
  if (selectedRuleId.value !== null) sessions.set(String(selectedRuleId.value), clone({
    result: compilationResult.value, code: generatedCode.value, draft: workingDraft.value,
    previous: previousCompilation.value, modified: modified.value, ready: compiledReady.value,
  }));
};
const loadSaved = async (rule: RuleListItem, epoch: number) => {
  if (!hasCode(rule.ruleCode)) return;
  try {
    const result = await getSavedCompilation(rule.id);
    if (epoch !== selectionEpoch || !result) return;
    compilationResult.value = result; generatedCode.value = result.generated_code;
    workingDraft.value = draftFromResult(result); previousCompilation.value = clone(result);
    compiledReady.value = true;
  } catch {
    if (epoch === selectionEpoch) ElMessage.warning('The saved compilation could not be loaded. You can compile the rule again.');
  }
};
const openRevision = () => {
  revisionRequestId++;
  revisionFeedback.value = ''; revisionError.value = ''; revisionProposal.value = null; revisionVisible.value = true;
};
const submitRevision = async () => {
  const rule = selectedRule.value;
  if (!rule || !workingDraft.value || !revisionFeedback.value.trim()) return;
  const epoch = selectionEpoch;
  const requestId = ++revisionRequestId;
  revising.value = true; revisionError.value = ''; revisionProposal.value = null;
  try {
    const proposal = await requestRuleRevision(rule.id, clone(workingDraft.value), revisionFeedback.value.trim());
    if (epoch === selectionEpoch && requestId === revisionRequestId && revisionVisible.value) revisionProposal.value = proposal;
  } catch (error: any) {
    if (epoch === selectionEpoch && requestId === revisionRequestId) {
      revisionError.value = error?.response?.data?.error || error?.response?.data?.message ||
        error?.message || 'Revision request failed. Your draft was preserved.';
    }
  } finally { if (epoch === selectionEpoch) revising.value = false; }
};
const applyRevision = () => {
  if (!revisionProposal.value?.changes?.length || !compilationResult.value) return;
  const draft = clone(revisionProposal.value.draft);
  workingDraft.value = draft;
  compilationResult.value = { ...compilationResult.value, ...draft,
    logical_expression: logicText(draft.logic_tree),
    execution_bindings: [{ ...draft.applicability_binding, atomic_constraint_id: 'Applicability', role: 'applicability' },
      ...draft.constraint_bindings.map((item: any) => ({ ...item, role: 'condition' }))] };
  modified.value = true; compiledReady.value = false; revisionVisible.value = false;
  selectionEpoch++;
  rememberSession();
};
const discardChanges = () => {
  if (!previousCompilation.value) return;
  const result = clone(previousCompilation.value);
  compilationResult.value = result; generatedCode.value = result.generated_code;
  workingDraft.value = draftFromResult(result); modified.value = false; compiledReady.value = true;
  selectionEpoch++; rememberSession();
};
const revisionSectionLabel = (key: string) => ({ atomic_constraints: 'Atomic Constraints', logic_tree: 'Decision Logic',
  applicability_binding: 'Applicability Binding', constraint_bindings: 'Execution Bindings' }[key] || key);

const searchForm = reactive({
  keyword: '',
});

const hasCode = (value?: null | string) => Boolean((value || '').trim());

const formatAuditFunction = (value?: string) => {
  const name = String(value || '').trim();
  return name ? (name.endsWith('()') ? name : `${name}()`) : '—';
};

const selectedRule = computed(() => {
  return list.value.find((item) => item.id === selectedRuleId.value) || null;
});

const canCompile = computed(() => {
  return Boolean(selectedRule.value && selectedRule.value.description.trim());
});

const canSave = computed(() => {
  return Boolean(
    selectedRule.value &&
      compiledReady.value &&
      generatedCode.value.trim() &&
      !saving.value && !compiling.value && !modified.value,
  );
});

const resetCompileState = () => {
  selectionEpoch++;
  modified.value = false; revisionVisible.value = false; revising.value = false;
  revisionProposal.value = null; workingDraft.value = null; previousCompilation.value = null;
  compiling.value = false;
  generatedCode.value = '';
  compilationResult.value = null;
  openOutputSections.value = [];
  sourceDialogVisible.value = false;
  selectedBinding.value = null;
  compiledReady.value = false;
};

const displayIrr = computed(() => {
  if (!selectedRule.value) return null;
  return {
    ruleCategory: getRuleTypeLabel(selectedRule.value.type) || 'Translation unavailable',
    constraintObject:
      getRuleNameEnglish(selectedRule.value.drugName) ||
      selectedRule.value.drugNameEnglish ||
      'Translation unavailable',
    constraintCondition:
      selectedRule.value.descriptionEnglish ||
      getRuleDescriptionEnglish(selectedRule.value.description) ||
      'Translation unavailable',
  };
});

const constraintBindings = computed(() => {
  const atomicConstraints = compilationResult.value?.atomic_constraints || [];
  const bindings = compilationResult.value?.execution_bindings || [];
  const applicability = compilationResult.value?.applicability_binding;
  const bindingByAtomicId = new Map(
    bindings.map((binding) => [binding.atomic_constraint_id, binding]),
  );
  const rows: Array<Record<string, any>> = atomicConstraints.map((constraint) => ({
    ...constraint,
    ...(bindingByAtomicId.get(constraint.id) || {}),
  }));
  if (applicability) {
    rows.unshift({
      id: 'Applies when',
      normalized_constraint: `The current item matches ${displayIrr.value?.constraintObject || 'the constraint object'}.`,
      ...applicability,
    });
  }
  return rows;
});

const evidenceSources = (row: Record<string, any>): EvidenceSource[] => {
  if (!Array.isArray(row.evidence_sources)) return [];
  return row.evidence_sources.filter(
    (source: any): source is EvidenceSource =>
      source && typeof source.path === 'string' && Boolean(source.path.trim()),
  );
};

const atomicEvidenceSources = (id: string): EvidenceSource[] => {
  const binding = workingDraft.value?.constraint_bindings?.find(
    (item: Record<string, any>) => item.atomic_constraint_id === id,
  );
  return binding ? evidenceSources(binding) : [];
};

const physicalSource = (source: EvidenceSource) =>
  source.data_source || source.path.split('.').slice(0, -1).join('.');

const physicalField = (source: EvidenceSource) =>
  source.field || source.path.split('.').at(-1) || '';

const sourceLabel = (value: string) =>
  SOURCE_LABELS[value] || (/^[\x00-\x7F]+$/.test(value) && value ? value : 'Untranslated source');

const fieldLabel = (value: string) =>
  FIELD_LABELS[value] || (/^[\x00-\x7F]+$/.test(value) ? value : 'Original field');

const sourceNames = (row: Record<string, any>) => {
  const groups = [...new Set(evidenceSources(row).map(physicalSource).filter(Boolean))];
  if (!groups.length) return [sourceLabel(row.data_source || '')];
  return groups.map(sourceLabel);
};

const englishSourcePath = (source: EvidenceSource) =>
  `${sourceLabel(physicalSource(source))} · ${fieldLabel(physicalField(source))}`;

const sourceGroups = computed(() => {
  const groups = new Map<string, EvidenceSource[]>();
  for (const source of selectedBinding.value ? evidenceSources(selectedBinding.value) : []) {
    const name = physicalSource(source);
    groups.set(name, [...(groups.get(name) || []), source]);
  }
  return [...groups].map(([name, sources]) => ({ name, sources }));
});

const openSourceDialog = (row: Record<string, any>) => {
  selectedBinding.value = row;
  sourceDialogVisible.value = true;
};

const getErrorMessage = (error: any, fallback: string) => {
  const data = error?.response?.data;
  if (typeof data === 'string') {
    if (data.includes('504 Gateway Time-out')) {
      return 'Rule compilation timed out. Please try again later or shorten the rule description.';
    }
    return data.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() || fallback;
  }
  return (
    data?.message ||
    data?.detail ||
    data?.error ||
    data?.result?.error ||
    error?.message ||
    fallback
  );
};

const normalizeList = (rawList: any[]) => {
  return rawList.map((item) => ({
    id: item.id,
    ruleId: item.ruleId || item.rule_id || `R-${item.id}`,
    drugName: item.drugName || item.drug_name || '',
    drugNameEnglish: item.drugNameEnglish || item.drug_name_english || '',
    type: item.type || '',
    description: item.description || '',
    descriptionEnglish: item.descriptionEnglish || item.description_english || '',
    enabled: Boolean(item.enabled),
    ruleCode: item.rule_code || item.ruleCode || '',
    logicExpression: item.logicExpression || item.logic_expression || '',
  })) as RuleListItem[];
};

const matchesKeyword = (item: RuleListItem, keyword: string) => {
  if (!keyword) return true;
  const text = [
    item.ruleId,
    item.drugName,
    item.drugNameEnglish,
    getRuleNameEnglish(item.drugName),
    item.type,
    getRuleTypeLabel(item.type),
    item.description,
    item.descriptionEnglish,
    getRuleDescriptionEnglish(item.description),
    item.ruleCode,
  ].join(' ');
  return text.toLowerCase().includes(keyword.toLowerCase());
};

const ruleNameDisplay = (item: RuleListItem) =>
  getRuleNameEnglish(item.drugName) || item.drugNameEnglish || 'Translation unavailable';

const fetchData = async () => {
  rememberSession();
  loading.value = true;
  try {
    const res = await getRuleList({
      compile: true,
      paginate: false,
      ordering: 'id',
    });
    const rawList = res?.results || (Array.isArray(res) ? res : []);
    const keyword = searchForm.keyword.trim();
    const demoList = normalizeList(rawList).filter((item) =>
      matchesKeyword(item, keyword),
    );
    total.value = demoList.length;
    const start = (currentPage.value - 1) * pageSize.value;
    list.value = demoList.slice(start, start + pageSize.value);

    if (list.value.length === 0) {
      selectedRuleId.value = null;
      resetCompileState();
      return;
    }

    const stillSelected = list.value.find((item) => item.id === selectedRuleId.value);
    selectedRuleId.value = stillSelected?.id ?? list.value[0]!.id;
    resetCompileState();
    const current = selectedRule.value;
    const session = current && sessions.get(String(current.id));
    if (session) {
      compilationResult.value = session.result; generatedCode.value = session.code;
      workingDraft.value = session.draft; previousCompilation.value = session.previous;
      modified.value = session.modified; compiledReady.value = session.ready;
    } else if (current) await loadSaved(current, selectionEpoch);
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to load the rule list');
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  currentPage.value = 1;
  fetchData();
};

const handleReset = () => {
  searchForm.keyword = '';
  currentPage.value = 1;
  fetchData();
};

const handleSelectRule = (rule: RuleListItem) => {
  rememberSession();
  selectedRuleId.value = rule.id;
  resetCompileState();
  const session = sessions.get(String(rule.id));
  if (session) {
    compilationResult.value = session.result; generatedCode.value = session.code;
    workingDraft.value = session.draft; previousCompilation.value = session.previous;
    modified.value = session.modified; compiledReady.value = session.ready;
  } else void loadSaved(rule, selectionEpoch);
};

const handleCompile = async () => {
  if (!selectedRule.value) {
    ElMessage.warning('Please select a rule first');
    return;
  }
  if (!selectedRule.value.description.trim()) {
    ElMessage.warning('The selected rule has no description and cannot be compiled');
    return;
  }

  const ruleId = selectedRule.value.id;
  const epoch = ++selectionEpoch;
  compiling.value = true;
  try {
    const result = modified.value && workingDraft.value
      ? await recompileRuleDraft(ruleId, clone(workingDraft.value)) : await generateRuleApi(ruleId);
    if (epoch !== selectionEpoch) return;
    openOutputSections.value = [];
    const nextCode = result?.generated_code || '';
    if (!nextCode.trim()) {
      const validationError = result?.validation?.errors?.join('; ');
      ElMessage.error(validationError || 'The compilation result is empty');
      return;
    }
    compilationResult.value = result;
    generatedCode.value = nextCode;
    workingDraft.value = draftFromResult(result); previousCompilation.value = clone(result);
    modified.value = false; compiledReady.value = true; rememberSession();
    ElMessage.success('Rule compiled successfully');
  } catch (error) {
    console.error(error);
    if (epoch === selectionEpoch) ElMessage.error((error as any)?.response?.data?.error || getErrorMessage(error, 'Rule compilation failed. Your draft was preserved.'));
  } finally {
    if (epoch === selectionEpoch) compiling.value = false;
  }
};

const handleValidate = async () => {
  if (!generatedCode.value.trim()) {
    ElMessage.warning('Please generate code before validation');
    return;
  }

  testing.value = true;
  try {
    const validation = await validateRuleCodeApi(generatedCode.value);
    const valid = Boolean(validation?.valid);
    const message = valid
      ? 'The generated program is valid.'
      : validation?.errors?.join('\n') || 'Program validation failed.';
    await ElMessageBox.alert(message, 'Program Validation', {
      confirmButtonText: 'OK',
      type: valid ? 'success' : 'error',
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Program validation failed'));
  } finally {
    testing.value = false;
  }
};

const handleSave = async () => {
  if (!selectedRule.value) {
    ElMessage.warning('Please select a rule first');
    return;
  }
  if (modified.value || !compiledReady.value || !generatedCode.value.trim()) {
    ElMessage.warning('Please complete compilation first');
    return;
  }

  const rule = selectedRule.value;
  const code = generatedCode.value;
  saving.value = true;
  try {
    await updateRule(
      rule.id,
      {
        drug_name: selectedRule.value.drugName,
        ruleId: selectedRule.value.ruleId,
        type: selectedRule.value.type,
        description: selectedRule.value.description,
        logicExpression:
          compilationResult.value?.logical_expression ||
          selectedRule.value.logicExpression ||
          '',
        enabled: true,
        rule_code: generatedCode.value,
      },
      { compileScope: true },
    );
    ElMessage.success('Rule library updated');
    rule.ruleCode = code;
    rule.enabled = true;
  } catch (error: any) {
    console.error(error);
    const message =
      error?.response?.data?.enabled?.[0] ||
      error?.response?.data?.enabled ||
      error?.response?.data?.detail ||
      'Failed to update the rule library';
    ElMessage.error(message);
  } finally {
    saving.value = false;
  }
};

onMounted(fetchData);
</script>

<template>
  <div class="compile-page">
    <div class="page-title">
      <div class="title-bar"></div>
      <div>
        <div class="title-main">Rule Compilation</div>
        <div class="title-sub">
          Decompose an existing rule, bind the decomposed constraints to the
          corresponding EMR data sources, audit functions, and parameters, and
          compile a Python program.
        </div>
      </div>
    </div>

    <div class="compile-layout">
      <el-card class="left-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>Rule Library</span>
            <el-button link type="primary" :icon="RefreshRight" @click="fetchData">Refresh</el-button>
          </div>
        </template>

        <div class="search-bar">
          <el-input
            v-model="searchForm.keyword"
            clearable
            placeholder="Search by rule name, code, or description"
            @clear="handleReset"
            @keyup.enter="handleSearch"
          />
          <div class="search-actions">
            <el-button type="primary" @click="handleSearch">Search</el-button>
            <el-button @click="handleReset">Reset</el-button>
          </div>
        </div>

        <div v-loading="loading" class="rule-list">
          <div
            v-for="item in list"
            :key="item.id"
            class="rule-item"
            :class="{ active: item.id === selectedRuleId }"
            @click="handleSelectRule(item)"
          >
            <div class="rule-item__top">
              <span class="rule-name">{{ ruleNameDisplay(item) }}</span>
            </div>
            <div class="rule-item__meta">
              <span>{{ getRuleTypeLabel(item.type) || 'Translation unavailable' }}</span>
            </div>
          </div>
          <el-empty
            v-if="!loading && list.length === 0"
            description="No rules available"
          />
        </div>

        <div class="pager">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            small
            background
            @current-change="fetchData"
            @size-change="fetchData"
          />
        </div>
      </el-card>

      <el-card class="right-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>Compilation Workspace</span>
            <el-tag :type="selectedRule ? 'primary' : 'info'">
              {{
                selectedRule
                  ? hasCode(selectedRule.ruleCode)
                    ? 'Compiled'
                    : 'Not Compiled'
                  : 'No Rule Selected'
              }}
            </el-tag>
          </div>
        </template>

        <template v-if="selectedRule">
          <section class="pipeline-section">
            <div class="section-heading">
              <div class="section-title">Intermediate Rule Representation</div>
              <span class="section-hint">IRR</span>
            </div>
            <div class="irr-summary">
              <div class="irr-field">
                <span class="label">Rule Category</span>
                <el-tag size="small" type="primary" effect="light">
                  {{ displayIrr?.ruleCategory }}
                </el-tag>
              </div>
              <div class="irr-field">
                <span class="label">Constraint Object</span>
                <strong>{{ displayIrr?.constraintObject }}</strong>
              </div>
              <div class="irr-field irr-field--condition">
                <span class="label">Constraint Condition</span>
                <div class="description-box">{{ displayIrr?.constraintCondition }}</div>
              </div>
            </div>
          </section>

          <div v-if="modified" class="revision-status">Modified · Recompile required <el-button link type="primary" @click="discardChanges">Discard changes</el-button></div>
          <div class="toolbar">
            <el-button
              type="primary"
              :disabled="!canCompile"
              :loading="compiling"
              @click="handleCompile"
            >
              {{ modified ? 'Recompile' : 'Compile Rule' }}
            </el-button>
            <el-button
              class="revision-entry-button"
              type="primary"
              plain
              :icon="EditPen"
              :disabled="!workingDraft || compiling || saving || revising"
              @click="openRevision"
            >
              Request Revision
            </el-button>
            <el-button
              :disabled="!generatedCode.trim() || modified || compiling"
              :loading="testing"
              @click="handleValidate"
            >
              Validate Program
            </el-button>
            <el-button
              type="primary"
              plain
              :disabled="!canSave"
              :loading="saving"
              @click="handleSave"
            >
              Save
            </el-button>
          </div>

          <section class="pipeline-section">
            <div class="section-heading">
              <div class="section-title">Constraint-to-EMR Bindings</div>
              <span class="section-hint">ATOMIC CONDITION → EMR → AUDIT FUNCTION</span>
            </div>
            <el-table
              v-if="constraintBindings.length"
              :data="constraintBindings"
              class="binding-table combined-binding-table"
              size="small"
            >
              <el-table-column prop="id" label="Atomic ID" width="105">
                <template #default="scope">
                  <el-tag size="small" effect="plain">{{ scope.row.id }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="normalized_constraint"
                label="Normalized Constraint"
                min-width="260"
                show-overflow-tooltip
              />
              <el-table-column label="EMR Data Source" min-width="190">
                <template #default="scope">
                  <div class="binding-sources">
                    <span v-for="(name, index) in sourceNames(scope.row)" :key="`${name}-${index}`" class="binding-cell">
                      <el-icon class="binding-cell__icon binding-cell__icon--source"><FolderOpened /></el-icon>
                      <span>{{ name }}</span>
                    </span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="EMR Field" min-width="210">
                <template #default="scope">
                  <span class="binding-cell">
                    <el-icon class="binding-cell__icon binding-cell__icon--field"><Document /></el-icon>
                    <template v-if="evidenceSources(scope.row).length > 1">
                      <span>Multiple Fields ({{ evidenceSources(scope.row).length }})</span>
                      <el-button link type="primary" @click="openSourceDialog(scope.row)">View</el-button>
                    </template>
                    <span v-else>{{ scope.row.field || (evidenceSources(scope.row).length ? fieldLabel(physicalField(evidenceSources(scope.row)[0]!)) : '—') }}</span>
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="Audit Function" min-width="200" show-overflow-tooltip>
                <template #default="scope">
                  <span class="function-chip">
                    <span class="function-chip__symbol">ƒ</span>
                    <code>{{ formatAuditFunction(scope.row.audit_function) }}</code>
                  </span>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else :image-size="54" description="Compile to view constraint-to-EMR bindings" />
            <div class="decision-logic">
              <div class="decision-logic__title">Decision Logic</div>
              <div
                class="expression-box"
                :class="{ 'expression-box--empty': !compilationResult?.logical_expression }"
              >
                <span class="expression-glyph">ƒ</span>
                <code>{{ compilationResult?.logical_expression || 'Compile to view the logical expression' }}</code>
              </div>
            </div>
          </section>

          <el-dialog v-model="revisionVisible" title="Request revision" width="min(1000px, 94vw)" :close-on-click-modal="false">
            <p class="revision-help">Describe what should change. Suggestions are checked against the EMR schema and audit function catalog. Your draft changes only after you apply a revision.</p>
            <div class="revision-context"><strong>Current rule condition</strong><p>{{ displayIrr?.constraintCondition }}</p>
              <strong>Applies when</strong>
              <p>The current item matches {{ displayIrr?.constraintObject }}.</p>
              <template v-if="workingDraft?.applicability_binding">
                <div v-for="source in evidenceSources(workingDraft.applicability_binding)" :key="source.path">Evidence source: {{ englishSourcePath(source) }}</div>
                <div v-if="!evidenceSources(workingDraft.applicability_binding).length">Evidence source: unavailable</div>
              </template>
              <strong>Current atomic constraints</strong>
              <div v-for="atom in compilationResult?.atomic_constraints || []" :key="atom.id" class="revision-atom">
                <div>{{ atom.id }} · {{ atom.normalized_constraint }}</div>
                <template v-if="atomicEvidenceSources(atom.id).length">
                  <div v-for="source in atomicEvidenceSources(atom.id)" :key="source.path" class="revision-atom__source">Evidence source: {{ englishSourcePath(source) }}</div>
                </template>
                <div v-else class="revision-atom__source">Evidence source: unavailable</div>
              </div>
              <strong>Current decision logic</strong><p>{{ compilationResult?.logical_expression }}</p>
            </div>
            <label for="revision-feedback">Revision feedback</label>
            <el-input id="revision-feedback" v-model="revisionFeedback" @input="revisionProposal = null" type="textarea" :rows="4" maxlength="8000" placeholder="Describe changes to Applies when, conditions, logic, or evidence sources. For example: Match the medication name instead of the generic drug name." :disabled="revising" />
            <el-button class="revision-submit" type="primary" :loading="revising" :disabled="!revisionFeedback.trim() || compiling" @click="submitRevision">Request suggestion</el-button>
            <el-alert v-if="revisionError" class="revision-error" type="error" :closable="false" show-icon title="Revision could not be applied" :description="revisionError" />
            <div v-if="revisionProposal" class="revision-preview">
              <h3>Proposed changes</h3>
              <p v-if="revisionProposal.summary">{{ revisionProposal.summary }}</p>
              <p v-if="!revisionProposal.changes.length">No validated changes were proposed. Refine the feedback and try again.</p>
              <div v-if="revisionProposal.operations?.length" class="revision-operations">
                <el-tag v-for="operation in revisionProposal.operations" :key="`${operation.operation}-${operation.target}`" size="small" effect="plain">
                  {{ operation.operation.replaceAll('_', ' ') }} · {{ operation.target }}
                </el-tag>
              </div>
              <section v-for="change in revisionProposal.changes" :key="change.section"><h4>{{ revisionSectionLabel(change.section) }}</h4>
                <div class="revision-diff"><div><strong>Before</strong><pre>{{ JSON.stringify(change.before, null, 2) }}</pre></div><div><strong>After</strong><pre>{{ JSON.stringify(change.after, null, 2) }}</pre></div></div>
              </section>
            </div>
            <template #footer><el-button @click="revisionVisible = false">Cancel</el-button><el-button type="primary" :disabled="!revisionProposal?.changes?.length || revising" @click="applyRevision">Apply revision</el-button></template>
          </el-dialog>

          <el-dialog
            v-model="sourceDialogVisible"
            title="EMR Evidence Sources"
            width="min(720px, 92vw)"
            destroy-on-close
          >
            <template v-if="selectedBinding">
              <div class="source-dialog-summary">
                <el-tag size="small" effect="plain">{{ selectedBinding.id }}</el-tag>
                <span v-if="selectedBinding.logical_label">{{ fieldLabel(selectedBinding.logical_label) }}</span>
                <span class="source-dialog-count">{{ evidenceSources(selectedBinding).length }} fields</span>
              </div>
              <div class="source-dialog-description">Fields used by this binding, grouped by data source. Names are displayed in English.</div>
              <div v-for="group in sourceGroups" :key="group.name" class="source-group">
                <div class="source-group__heading">
                  <el-icon><FolderOpened /></el-icon>
                  <span>{{ sourceLabel(group.name) }}</span>
                </div>
                <div v-for="(source, index) in group.sources" :key="`${source.path}-${index}`" class="source-field">
                  <span class="source-field__name">{{ fieldLabel(physicalField(source)) }}</span>
                  <span class="source-field__path">{{ englishSourcePath(source) }}</span>
                </div>
              </div>
            </template>
          </el-dialog>

          <section class="pipeline-section generated-program-section">
            <div class="section-heading">
              <div class="section-title">
                {{ modified ? 'Previous compilation · Executable Logic Preview' : 'Executable Logic Preview' }}
              </div>
              <span class="section-hint">READABLE PYTHON</span>
            </div>
            <div class="preview-note">A readable explanation generated from the execution plan. Conceptual helpers are not standalone executable code.</div>
            <div class="code-box">
              <pre>{{ compilationResult?.readable_python || (generatedCode ? 'A readable preview is not available for this program.' : 'Select a rule and click "Compile Rule" to generate a preview') }}</pre>
            </div>
            <el-collapse v-if="compilationResult?.compiled_plan" v-model="openOutputSections" class="plan-collapse">
              <el-collapse-item title="Execution Plan" name="plan">
                <div class="plan-box"><pre>{{ JSON.stringify(compilationResult.compiled_plan, null, 2) }}</pre></div>
              </el-collapse-item>
            </el-collapse>
          </section>
        </template>
        <el-empty
          v-else
          description="Please select a rule from the left panel first"
        />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.revision-status { padding: 8px 12px; background: #fff8e7; color: #8b6417; border-radius: 6px; }
.revision-context { margin: 14px 0; padding: 12px; background: #f5f7fb; color: #344456; line-height: 1.6; }
.revision-atom { margin: 6px 0; }
.revision-atom__source { padding-left: 1em; color: #64758a; font-size: 0.95em; }
.revision-context strong { display: block; margin-top: 6px; }.revision-context p { margin: 4px 0; }
.revision-error { margin-top: 12px; }
.revision-help { color: #64758a; line-height: 1.5; }.revision-submit { margin-top: 12px; }
.revision-operations { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.revision-diff { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
.revision-diff pre { padding: 10px; max-height: 300px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; background: #f5f7fb; font-size: 12px; }
@media(max-width: 700px) { .revision-diff { grid-template-columns: 1fr; } }

.compile-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 120px);
  padding: 18px;
  background: #f5f7fb;
}

.page-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 6px 0 14px;
}

.title-bar {
  width: 4px;
  height: 18px;
  margin-top: 3px;
  background: #409eff;
  border-radius: 3px;
}

.title-main {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}

.title-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}

.compile-layout {
  display: grid;
  grid-template-columns: minmax(280px, 25%) minmax(0, 75%);
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  border-radius: 10px;
}

.left-panel :deep(.el-card__body),
.right-panel :deep(.el-card__body) {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.search-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.search-actions {
  display: flex;
  gap: 8px;
}

.rule-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow-y: auto;
}

.rule-item {
  padding: 12px;
  cursor: pointer;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.rule-item:hover,
.rule-item.active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgb(64 158 255 / 18%);
}

.rule-item__top {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  justify-content: space-between;
}

.rule-name {
  font-weight: 600;
  color: #1f2937;
}

.rule-item__meta {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}

.rule-item__meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pager {
  display: flex;
  justify-content: flex-end;
}

.pipeline-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 13px 14px;
  background: #fff;
  border: 1px solid #e5ebf3;
  border-radius: 9px;
  box-shadow: 0 3px 10px rgb(45 76 112 / 4%);
}

.section-heading {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  min-height: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 700;
  color: #263d59;
}

.section-hint {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.055em;
  color: #8b9bb1;
}

.irr-summary {
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(200px, 1fr) minmax(280px, 2.2fr);
  gap: 12px;
  align-items: stretch;
}

.irr-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 10px 12px;
  background: #f8faff;
  border: 1px solid #edf2f8;
  border-radius: 7px;
}

.irr-field strong {
  overflow-wrap: anywhere;
  color: #263d59;
  line-height: 1.35;
}

.label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #73849a;
}

.description-box {
  width: 100%;
  line-height: 1.5;
  color: #40546d;
  white-space: pre-wrap;
}

.toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.revision-entry-button {
  font-weight: 650;
}

.binding-table {
  border: 1px solid #e5ebf3;
  border-radius: 7px;
  overflow: hidden;
}

.binding-table :deep(th.el-table__cell) {
  height: 38px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.015em;
  color: #4a607d;
  background: #f3f7fc;
}

.binding-table :deep(td.el-table__cell) {
  padding-top: 8px;
  padding-bottom: 8px;
  color: #40546d;
}

.binding-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #f7faff;
}

.binding-cell {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  min-width: 0;
  color: #40546d;
}

.binding-sources {
  display: flex;
  flex-direction: column;
  gap: 5px;
  align-items: flex-start;
}

.binding-cell__icon {
  flex: 0 0 auto;
  font-size: 15px;
}

.binding-cell__icon--source {
  color: #5b8dd6;
}

.binding-cell__icon--field {
  color: #7a8eaa;
}

.source-dialog-summary {
  display: flex;
  gap: 10px;
  align-items: center;
  font-weight: 600;
  color: #263d59;
}

.source-dialog-count {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
  color: #788ba4;
}

.source-dialog-description {
  margin: 9px 0 16px;
  font-size: 12px;
  color: #71839a;
}

.source-group {
  overflow: hidden;
  margin-top: 12px;
  border: 1px solid #e5ebf3;
  border-radius: 8px;
}

.source-group__heading {
  display: flex;
  gap: 7px;
  align-items: center;
  padding: 9px 12px;
  font-weight: 700;
  color: #37577e;
  background: #f3f7fc;
}

.source-field {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) minmax(0, 1.5fr);
  gap: 12px;
  padding: 9px 12px;
  border-top: 1px solid #edf1f6;
}

.source-field__name {
  color: #40546d;
}

.source-field__path {
  color: #7689a2;
  overflow-wrap: anywhere;
}

.function-chip {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  max-width: 100%;
  padding: 4px 7px;
  color: #7a4c0f;
  background: #fff8eb;
  border: 1px solid #f4ddb1;
  border-radius: 5px;
}

.function-chip code {
  overflow: hidden;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.function-chip__symbol {
  font-weight: 800;
  line-height: 1;
}

.decision-logic {
  display: flex;
  gap: 10px;
  align-items: center;
  padding-top: 8px;
  margin-top: 0;
  border-top: 1px dashed #dce5f0;
}

.decision-logic__title {
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 700;
  color: #526a88;
}

.decision-logic .expression-box {
  min-height: 38px;
  padding: 6px 10px;
}

.decision-logic .expression-glyph {
  flex-basis: 22px;
  width: 22px;
  height: 22px;
  font-size: 15px;
}

.decision-logic .expression-box code {
  font-size: 12px;
  line-height: 1.35;
}

.expression-box {
  display: flex;
  flex: 1;
  gap: 10px;
  align-items: center;
  min-height: 76px;
  padding: 12px 14px;
  color: #234a77;
  font-family:
    'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  background: linear-gradient(135deg, #f3f8ff, #f9fbff);
  border: 1px solid #dce9f8;
  border-radius: 7px;
}

.expression-box code {
  overflow-wrap: anywhere;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.65;
}

.expression-box--empty {
  color: #8495aa;
}

.expression-glyph {
  display: grid;
  flex: 0 0 28px;
  width: 28px;
  height: 28px;
  place-items: center;
  color: #3b82d0;
  font-size: 19px;
  font-weight: 700;
  background: #e5f0ff;
  border-radius: 7px;
}

.generated-program-section {
  flex: 1;
}

.preview-note {
  font-size: 12px;
  line-height: 1.5;
  color: #71839a;
}

.plan-collapse {
  margin-top: 2px;
}

.plan-collapse :deep(.el-collapse-item__header) {
  font-weight: 600;
  color: #405976;
}

.plan-box {
  max-height: 400px;
  overflow: auto;
  background: #f8fafc;
  border: 1px solid #e5ebf3;
  border-radius: 8px;
}

.plan-box pre {
  margin: 0;
  padding: 14px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.code-box {
  flex: 1;
  min-height: 320px;
  overflow: auto;
  background: #f3f8ff;
  border: 1px solid #cfe0f5;
  border-radius: 10px;
}

.code-box pre {
  margin: 0;
  padding: 16px;
  color: #24364a;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  font-family:
    'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
}

@media (width <= 1024px) {
  .compile-layout {
    grid-template-columns: 1fr;
  }

  .code-box {
    min-height: 240px;
  }

  .irr-summary {
    grid-template-columns: 1fr;
  }

  .decision-logic {
    align-items: flex-start;
    flex-direction: column;
  }

  .decision-logic .expression-box {
    width: 100%;
  }
}
</style>
