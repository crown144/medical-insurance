<script setup lang="ts">
import type {
  ExtractedRule,
  RuleImportStatus,
  RuleImportTask,
} from '../../../api/model/ruleImportModel';

import { computed, onMounted, onUnmounted, ref } from 'vue';

import { Download, Refresh, UploadFilled } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  cancelRuleImportApi,
  confirmRuleImportApi,
  deleteRuleImportTaskApi,
  downloadRuleImportExampleApi,
  downloadRuleImportResultApi,
  getExtractedRulesApi,
  getRuleImportTaskApi,
  getRuleImportTasksApi,
  uploadRuleImportApi,
} from '../../../api/ruleImport';

const ALLOWED_EXTS = ['pdf', 'xlsx', 'xls'];
const MAX_FILE_SIZE = 50 * 1024 * 1024;
const TERMINAL: RuleImportStatus[] = ['success', 'failed', 'canceled'];

const STATUS_LABELS: Record<RuleImportStatus, string> = {
  pending: 'Pending',
  parsing: 'Parsing',
  extracting: 'Extracting',
  success: 'Success',
  failed: 'Failed',
  canceled: 'Canceled',
};

const RULE_TYPE_LABELS: Record<string, string> = {
  DRUG_RESTRICTION: 'Restricted Medication Use',
  FREQUENCY_LIMIT: 'Excessive Frequency Billing',
  DUPLICATE_CHARGE: 'Duplicate Charge',
  PRICE_LIMIT: 'Over-standard Charge',
  CONSUMABLE_RESTRICTION: 'Consumable Restriction',
  OVER_EXAMINATION: 'Overutilization',
  OTHER: 'Other',
};

const RULE_TYPE_OPTIONS = Object.entries(RULE_TYPE_LABELS).map(
  ([value, label]) => ({ value, label }),
);

const TERM_TRANSLATIONS: Record<string, string> = {
  艾普拉唑: 'Ilaprazole',
  醋酸钙: 'Calcium acetate tablets',
  胃肠减压: 'Gastrointestinal decompression',
  耳部特殊治疗: 'Special ear treatment',
  静脉注射: 'Intravenous injection',
  静脉采血: 'Venous blood collection',
  动脉加压注射: 'Arterial pressure injection',
  动脉采血: 'Arterial blood collection',
  机械辅助排痰: 'Mechanical assisted sputum clearance',
  血气分析: 'Blood gas analysis',
  '血清碳酸氢盐(HCO3)测定': 'Serum bicarbonate (HCO3) test',
  尿液分析: 'Urinalysis',
  糖化血红蛋白测定: 'Glycated Hemoglobin Assay',
  尿沉渣白细胞分类: 'Urinary sediment leukocyte classification',
  尿蛋白定量: 'Urine protein quantification',
  '急诊监护费': 'Emergency monitoring fee',
  '急诊诊查费': 'Emergency consultation fee',
};

const CONSTRAINT_TRANSLATIONS: Record<string, string> = {
  '使用艾普拉唑须有十二指肠溃疡、反流性食管炎诊断':
    'Use of ilaprazole requires a diagnosis of duodenal ulcer or reflux esophagitis',
  '使用醋酸钙须有高磷血症诊断':
    'Use of calcium acetate tablets requires a diagnosis of hyperphosphatemia',
  '插胃管加收10元':
    'An additional 10 yuan may be charged when a gastric tube is inserted',
  '原价79元，射频、激光、微波加收20元；等离子加收50元；冷冻减收55元':
    'The base price is 79 yuan; radiofrequency, laser, or microwave treatment may add 20 yuan; plasma treatment may add 50 yuan; cryotherapy should reduce the charge by 55 yuan',
  '“静脉注射”与“静脉采血”不能同时开':
    'Intravenous injection and venous blood collection cannot be ordered at the same time',
  '“动脉加压注射”与“动脉采血”不能同时开':
    'Arterial pressure injection and arterial blood collection cannot be ordered at the same time',
  '机械辅助排痰使用项目的数量总计超过上限数量，单日上限数量1，项目收费单位日':
    'The total quantity of mechanical assisted sputum clearance exceeds the allowed limit; the daily limit is 1 day',
  '使用项目的数量总计超过上限数量，单日上限数量1，项目收费单位日':
    'The total quantity of the service item exceeds the allowed limit; the daily limit is 1 day',
  '收取“血气分析”费用的同时收取“血清碳酸氢盐(HCO3)测定”费用':
    'Charging for blood gas analysis together with serum bicarbonate (HCO3) testing',
  '收取尿液分析费用时，同时收取尿沉渣白细胞分类费用或尿蛋白定量费用':
    'Charging for urinalysis together with urinary sediment leukocyte classification or urine protein quantification',
  '单日不得与急诊诊查费同时收费':
    'May not be charged together with emergency consultation fee on the same day',
  '急诊监护费单日不得与急诊诊查费同时收费':
    'Emergency monitoring fee may not be charged together with emergency consultation fee on the same day',
};

const POLICY_EXAMPLE = {
  key: 'policy-example',
  name: 'Policy_Example.pdf',
};

const activeTab = ref<'history' | 'upload'>('upload');

const fileInputRef = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const previewUrl = ref('');
const submitting = ref(false);

const currentTask = ref<null | RuleImportTask>(null);
const polling = ref(false);
let pollTimer: null | ReturnType<typeof setInterval> = null;

const rules = ref<ExtractedRule[]>([]);
const rulesLoading = ref(false);
const rulesTotal = ref(0);
const rulesPage = ref(1);
const rulesPageSize = ref(10);
const ruleTypeFilter = ref('');
const selectedRules = ref<ExtractedRule[]>([]);
const importing = ref(false);
const traceDialogVisible = ref(false);
const traceRule = ref<ExtractedRule | null>(null);

const historyList = ref<RuleImportTask[]>([]);
const historyLoading = ref(false);
const historyTotal = ref(0);
const historyPage = ref(1);
const historyPageSize = ref(10);

function formatFileSize(bytes: number) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

function getStatusType(status: string) {
  const map: Record<string, string> = {
    pending: 'info',
    parsing: 'warning',
    extracting: 'warning',
    success: 'success',
    failed: 'danger',
    canceled: 'info',
  };
  return map[status] || 'info';
}

function getStatusLabel(status: RuleImportStatus | string) {
  return STATUS_LABELS[status as RuleImportStatus] || status || '-';
}

function ruleTypeLabel(t: string) {
  return RULE_TYPE_LABELS[t] || t || 'Uncategorized';
}

function ruleTypeTagType(t: string): 'danger' | 'info' | 'primary' | 'success' | 'warning' {
  const typeMap: Record<string, 'danger' | 'info' | 'primary' | 'success' | 'warning'> = {
    CONSUMABLE_RESTRICTION: 'warning',
    DRUG_RESTRICTION: 'primary',
    DUPLICATE_CHARGE: 'danger',
    FREQUENCY_LIMIT: 'warning',
    OVER_EXAMINATION: 'success',
    PRICE_LIMIT: 'danger',
  };
  return typeMap[t] || 'info';
}

function translateExtractedText(value?: string) {
  const text = (value || '').trim();
  if (!text) return '-';
  if (!/[\u4E00-\u9FFF]/.test(text)) return text;
  if (CONSTRAINT_TRANSLATIONS[text]) return CONSTRAINT_TRANSLATIONS[text];
  if (TERM_TRANSLATIONS[text]) return TERM_TRANSLATIONS[text];
  let translated = text;
  Object.entries(TERM_TRANSLATIONS)
    .sort(([left], [right]) => right.length - left.length)
    .forEach(([cn, en]) => {
      translated = translated.split(cn).join(en);
    });
  return translated === text ? text : translated;
}

function targetObjectText(row: ExtractedRule) {
  // Keep identical policy objects visibly identical even when an extraction
  // response includes a different per-row LLM translation.
  return TERM_TRANSLATIONS[row.constrained_object] ||
    row.constrained_object_en ||
    translateExtractedText(row.constrained_object);
}

function constraintText(row: ExtractedRule) {
  return row.constraint_value_en || translateExtractedText(row.constraint_value);
}

function isRunning(task: null | RuleImportTask) {
  return !!task && !TERMINAL.includes(task.status);
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  polling.value = false;
}

async function pollOnce() {
  if (!currentTask.value) return;
  try {
    const task = await getRuleImportTaskApi(currentTask.value.id);
    currentTask.value = task;
    if (TERMINAL.includes(task.status)) {
      stopPolling();
      if (task.status === 'success') {
        ElMessage.success(`Conversion completed. ${task.rule_count} rules extracted.`);
        rulesPage.value = 1;
        await loadRules();
      } else if (task.status === 'failed') {
        ElMessage.error(task.error_detail || 'Conversion failed. Please review the error details.');
      }
      await loadHistory();
    }
  } catch {
    // Ignore one failed poll cycle and continue polling next time.
  }
}

function startPolling() {
  stopPolling();
  polling.value = true;
  pollTimer = setInterval(pollOnce, 2000);
}

function triggerFileSelect() {
  fileInputRef.value?.click();
}

const isSelectedPdf = computed(() => selectedFile.value?.type === 'application/pdf' ||
  selectedFile.value?.name.toLowerCase().endsWith('.pdf'));

function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = '';
  }
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  const ext = file.name.includes('.')
    ? file.name.split('.').pop()!.toLowerCase()
    : '';
  if (!ALLOWED_EXTS.includes(ext)) {
    ElMessage.error(
      `Unsupported file type. Please upload a ${ALLOWED_EXTS.join(' / ')} file.`,
    );
    input.value = '';
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    ElMessage.error('File is too large. Maximum size is 50 MB.');
    input.value = '';
    return;
  }
  clearPreview();
  selectedFile.value = file;
  if (ext === 'pdf') previewUrl.value = URL.createObjectURL(file);
}

function validateForm(): boolean {
  if (!selectedFile.value) {
    ElMessage.warning('Please select a file to convert first.');
    return false;
  }
  return true;
}

async function handleSubmit() {
  if (!validateForm()) return;
  submitting.value = true;
  try {
    const res = await uploadRuleImportApi(selectedFile.value!);
    currentTask.value = res.task;
    rules.value = [];
    rulesTotal.value = 0;
    selectedRules.value = [];
    ElMessage.success(
      'Conversion task submitted and is now running in the background.',
    );
    startPolling();
    await loadHistory();
  } catch (error: any) {
    const msg =
      error?.response?.data?.error || error?.message || 'Submission failed';
    ElMessage.error(msg);
  } finally {
    submitting.value = false;
  }
}

function resetUpload() {
  stopPolling();
  clearPreview();
  selectedFile.value = null;
  currentTask.value = null;
  rules.value = [];
  rulesTotal.value = 0;
  selectedRules.value = [];
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function loadRules() {
  if (!currentTask.value) return;
  rulesLoading.value = true;
  try {
    const params: Record<string, any> = {
      page: rulesPage.value,
      page_size: rulesPageSize.value,
    };
    if (ruleTypeFilter.value) params.rule_type = ruleTypeFilter.value;
    const res = await getExtractedRulesApi(currentTask.value.id, params);
    rules.value = res.results;
    rulesTotal.value = res.count;
  } catch (error: any) {
    const msg =
      error?.response?.data?.error ||
      error?.message ||
      'Failed to load extraction results';
    ElMessage.error(msg);
  } finally {
    rulesLoading.value = false;
  }
}

function onSelectionChange(rows: ExtractedRule[]) {
  selectedRules.value = rows;
}

function openTrace(row: ExtractedRule) {
  traceRule.value = row;
  traceDialogVisible.value = true;
}

function traceEntries(row: ExtractedRule): Array<[string, any]> {
  const evidence = row.evidence || {};
  const itemName = String(evidence['药品分类'] || '');
  const rowNumber = String(evidence['药品分类代码'] || '');
  const quantity = String(evidence['药品名称'] || '');

  // The frequency-policy PDF uses a different table schema. Its first page
  // is extracted with generic drug-list headers, which shifts these values.
  // Re-label only this well-identified layout; the stored source values stay
  // untouched and all other policy rows keep their original headers.
  if (
    row.rule_type === 'FREQUENCY_LIMIT' &&
    itemName === row.constrained_object &&
    /^\d+$/.test(rowNumber) &&
    /^\d+$/.test(quantity) &&
    evidence['剂型']
  ) {
    const correctedEntries: Array<[string, any]> = [
      ['序号', rowNumber],
      ['医疗服务项目名称', itemName],
      ['限定支付数量', quantity],
      ['检查逻辑', evidence['剂型']],
      ['备注', evidence['备注']],
    ];
    return correctedEntries.filter(([, value]) => value !== undefined && value !== '');
  }
  return Object.entries(evidence);
}

async function handleConfirmImport(selectAll: boolean) {
  if (!currentTask.value) return;
  if (!selectAll && selectedRules.value.length === 0) {
    ElMessage.warning(
      'Please select the rules to import, or choose "Import All".',
    );
    return;
  }
  importing.value = true;
  try {
    const payload = selectAll
      ? { select_all: true }
      : { rule_ids: selectedRules.value.map((r) => r.id) };
    const res = await confirmRuleImportApi(currentTask.value.id, payload);
    const duplicateCount = res.duplicate_rule_ids?.length || 0;
    ElMessage.success(
      duplicateCount
        ? `Import completed: ${res.imported} imported; ${duplicateCount} duplicate rule${duplicateCount === 1 ? '' : 's'} skipped.`
        : `Import completed: ${res.imported} imported, ${res.skipped} skipped.`,
    );
    currentTask.value = res.task;
    await loadRules();
    await loadHistory();
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || 'Import failed';
    ElMessage.error(msg);
  } finally {
    importing.value = false;
  }
}

async function handleDownload(taskId: number) {
  try {
    const blob = await downloadRuleImportResultApi(taskId);
    saveBlob(blob, `rule-extraction-task-${taskId}.json`);
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || 'Download failed';
    ElMessage.error(msg);
  }
}

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

async function handleDownloadExample() {
  try {
    const blob = await downloadRuleImportExampleApi(POLICY_EXAMPLE.key);
    saveBlob(blob, POLICY_EXAMPLE.name);
  } catch (error: any) {
    const msg =
      error?.response?.data?.error ||
      error?.message ||
      'Example file download failed';
    ElMessage.error(msg);
  }
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    const res = await getRuleImportTasksApi({
      page: historyPage.value,
      page_size: historyPageSize.value,
    });
    historyList.value = res.results;
    historyTotal.value = res.count;
  } catch (error: any) {
    const msg =
      error?.response?.data?.error || error?.message || 'Failed to load history';
    ElMessage.error(msg);
  } finally {
    historyLoading.value = false;
  }
}

async function viewHistoryTask(task: RuleImportTask) {
  stopPolling();
  currentTask.value = task;
  selectedRules.value = [];
  rulesPage.value = 1;
  ruleTypeFilter.value = '';
  activeTab.value = 'upload';
  if (isRunning(task)) {
    startPolling();
  } else if (task.status === 'success') {
    await loadRules();
  } else {
    rules.value = [];
    rulesTotal.value = 0;
  }
}

async function handleCancel(task: RuleImportTask) {
  try {
    await ElMessageBox.confirm(
      `Cancel task "${task.task_name}"?`,
      'Confirmation',
      { type: 'warning' },
    );
  } catch {
    return;
  }
  try {
    await cancelRuleImportApi(task.id);
    ElMessage.success('Task canceled.');
    if (currentTask.value?.id === task.id) {
      stopPolling();
      await pollOnce();
    }
    await loadHistory();
  } catch (error: any) {
    const msg =
      error?.response?.data?.error ||
      error?.message ||
      'Cancellation failed';
    ElMessage.error(msg);
  }
}

async function handleDelete(task: RuleImportTask) {
  try {
    await ElMessageBox.confirm(
      `Delete task "${task.task_name || task.file_name}" and its extracted records? This action cannot be undone.`,
      'Delete Conversion History',
      {
        confirmButtonText: 'Delete',
        confirmButtonClass: 'el-button--danger',
        type: 'warning',
      },
    );
  } catch {
    return;
  }

  try {
    await deleteRuleImportTaskApi(task.id);
    if (currentTask.value?.id === task.id) {
      resetUpload();
    }
    if (historyList.value.length === 1 && historyPage.value > 1) {
      historyPage.value -= 1;
    }
    await loadHistory();
    ElMessage.success('Conversion history deleted.');
  } catch (error: any) {
    const msg =
      error?.response?.data?.error || error?.message || 'Deletion failed';
    ElMessage.error(msg);
  }
}

const canImport = computed(
  () => currentTask.value?.status === 'success' && rulesTotal.value > 0,
);

onMounted(() => {
  loadHistory();
});

onUnmounted(() => {
  stopPolling();
  clearPreview();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-copy">
          <div class="title-main">Rule Discovery</div>
          <div class="title-sub">
            Upload drug or billing catalog files (PDF or Excel). The system
            automatically extracts audit rules for review before writing them
            into the rule library.
          </div>
        </div>
        <el-button :icon="Download" @click="handleDownloadExample">
          Download Policy Example
        </el-button>
      </div>

      <el-tabs v-model="activeTab" type="border-card" class="main-tabs">
        <el-tab-pane label="Upload & Convert" name="upload">
          <div class="upload-panel">
            <div class="upload-box" @click="triggerFileSelect">
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div v-if="selectedFile" class="upload-file">
                {{ selectedFile.name }} ({{ formatFileSize(selectedFile.size) }})
              </div>
              <div v-else class="upload-hint">
                Click to select a file. Supported formats: .pdf / .xlsx / .xls,
                up to 50 MB.
              </div>
              <input
                ref="fileInputRef"
                type="file"
                accept=".pdf,.xlsx,.xls"
                style="display: none"
                @change="onFileChange"
              />
            </div>
            <div v-if="selectedFile" class="upload-preview">
              <div class="upload-preview__header">
                <span>Document Preview</span>
                <el-tag size="small" type="info">{{ isSelectedPdf ? 'PDF' : 'Spreadsheet' }}</el-tag>
              </div>
              <iframe
                v-if="isSelectedPdf && previewUrl"
                class="upload-preview__frame"
                :src="previewUrl"
                :title="`Preview of ${selectedFile.name}`"
              />
              <div v-else class="upload-preview__summary">
                <div class="upload-preview__filetype">{{ selectedFile.name.split('.').pop()?.toUpperCase() }}</div>
                <div>{{ selectedFile.name }}</div>
                <span>Spreadsheet preview is not available. The file is ready to convert.</span>
              </div>
            </div>
            <div class="form-actions">
              <el-button @click="resetUpload">Reset</el-button>
              <el-button
                type="primary"
                :loading="submitting"
                :disabled="polling"
                @click="handleSubmit"
              >
                {{ submitting ? 'Submitting...' : 'Start Conversion' }}
              </el-button>
            </div>
          </div>

          <div v-if="currentTask" class="task-status-panel">
            <div class="list-title">Current Task</div>
            <div class="status-row">
              <span class="status-name">{{ currentTask.task_name }}</span>
              <el-tag :type="getStatusType(currentTask.status)" size="small">
                {{ getStatusLabel(currentTask.status) }}
              </el-tag>
              <span v-if="polling" class="muted">(running, auto-refreshing...)</span>
            </div>
            <el-progress
              :percentage="currentTask.progress"
              :status="
                currentTask.status === 'failed'
                  ? 'exception'
                  : currentTask.status === 'success'
                    ? 'success'
                    : undefined
              "
              class="mt-2"
            />
            <div class="status-meta">
              <span>Parsed Tables: {{ currentTask.table_count }}</span>
              <span>Extracted Rules: {{ currentTask.rule_count }}</span>
              <span>Imported: {{ currentTask.imported_count }}</span>
            </div>
            <el-alert
              v-if="currentTask.status === 'failed' && currentTask.error_detail"
              type="error"
              :title="currentTask.error_detail"
              :closable="false"
              show-icon
              class="mt-2"
            />
          </div>

          <div
            v-if="currentTask && currentTask.status === 'success'"
            class="result-panel"
          >
            <div class="result-header">
              <div class="list-title">Extracted Rules</div>
              <div class="result-actions">
                <el-select
                  v-model="ruleTypeFilter"
                  placeholder="All Types"
                  clearable
                  size="small"
                  style="width: 150px"
                  @change="
                    () => {
                      rulesPage = 1;
                      loadRules();
                    }
                  "
                >
                  <el-option
                    v-for="opt in RULE_TYPE_OPTIONS"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
                <el-button
                  size="small"
                  :icon="Download"
                  @click="handleDownload(currentTask.id)"
                >
                  Download JSON
                </el-button>
                <el-button
                  size="small"
                  :loading="importing"
                  :disabled="!canImport || selectedRules.length === 0"
                  @click="handleConfirmImport(false)"
                >
                  Import Selected ({{ selectedRules.length }})
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :loading="importing"
                  :disabled="!canImport"
                  @click="handleConfirmImport(true)"
                >
                  Import All
                </el-button>
              </div>
            </div>

            <div class="table-card extracted-rules-table">
              <el-table
                :data="rules"
                v-loading="rulesLoading"
                border
                size="small"
                style="width: 100%"
                @selection-change="onSelectionChange"
              >
                <el-table-column type="selection" width="44" />
                <el-table-column prop="seq" label="No." width="68" align="center" />
                <el-table-column label="Rule Category" width="120">
                  <template #default="{ row }">
                    <el-tag size="small" effect="light" :type="ruleTypeTagType(row.rule_type)" :class="{ 'rule-tag--duplicate': row.rule_type === 'DUPLICATE_CHARGE' }">
                      {{ ruleTypeLabel(row.rule_type) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  label="Constraint Object"
                  min-width="160"
                  show-overflow-tooltip
                >
                  <template #default="{ row }">
                    <span class="object-name">{{ targetObjectText(row) }}</span>
                  </template>
                </el-table-column>
                <el-table-column
                  label="Constraint Condition"
                  min-width="260"
                  show-overflow-tooltip
                >
                  <template #default="{ row }">
                    <span class="condition-text">{{ constraintText(row) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="Trace" width="88" align="center">
                  <template #default="{ row }">
                    <el-button link type="primary" @click="openTrace(row)">View</el-button>
                  </template>
                </el-table-column>
                <el-table-column label="Imported" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag
                      :type="row.is_imported ? 'success' : 'info'"
                      size="small"
                    >
                      {{ row.is_imported ? 'Yes' : 'No' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <template #empty>
                  <el-empty description="No extracted rules yet" />
                </template>
              </el-table>
              <div class="pager">
                <el-pagination
                  v-model:current-page="rulesPage"
                  v-model:page-size="rulesPageSize"
                  :total="rulesTotal"
                  :page-sizes="[10, 20, 50, 100]"
                  layout="total, sizes, prev, pager, next"
                  background
                  small
                  @size-change="loadRules"
                  @current-change="loadRules"
                />
              </div>
            </div>
          </div>

          <el-empty
            v-if="!currentTask"
            description="Upload a file and start the conversion process"
            class="mt-3"
          />
        </el-tab-pane>

        <el-tab-pane label="Conversion History" name="history">
          <div class="tab-header">
            <div class="tab-desc">
              Review previous conversion tasks, revisit results, download outputs,
              or cancel running jobs.
            </div>
            <el-button :icon="Refresh" size="small" @click="loadHistory">
              Refresh
            </el-button>
          </div>

          <div class="table-card">
            <el-table
              :data="historyList"
              v-loading="historyLoading"
              border
              style="width: 100%"
            >
              <el-table-column prop="id" label="ID" width="64" align="center" />
              <el-table-column
                prop="task_name"
                label="Task Name"
                min-width="180"
                show-overflow-tooltip
              />
              <el-table-column
                prop="file_name"
                label="File"
                min-width="160"
                show-overflow-tooltip
              />
              <el-table-column label="Status" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)" size="small">
                    {{ getStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="Progress" width="80" align="center">
                <template #default="{ row }">{{ row.progress }}%</template>
              </el-table-column>
              <el-table-column
                prop="rule_count"
                label="Rules"
                width="80"
                align="center"
              />
              <el-table-column
                prop="imported_count"
                label="Imported"
                width="80"
                align="center"
              />
              <el-table-column prop="created_at" label="Created At" width="170">
                <template #default="{ row }">
                  {{ new Date(row.created_at).toLocaleString() }}
                </template>
              </el-table-column>
              <el-table-column
                label="Actions"
                width="230"
                fixed="right"
                align="center"
              >
                <template #default="{ row }">
                  <el-button type="primary" link @click="viewHistoryTask(row)">
                    View
                  </el-button>
                  <el-button
                    v-if="row.status === 'success'"
                    type="primary"
                    link
                    @click="handleDownload(row.id)"
                  >
                    Download
                  </el-button>
                  <el-button
                    v-if="!['success', 'failed', 'canceled'].includes(row.status)"
                    type="danger"
                    link
                    @click="handleCancel(row)"
                  >
                    Cancel
                  </el-button>
                  <el-button
                    v-else
                    type="danger"
                    link
                    @click="handleDelete(row)"
                  >
                    Delete
                  </el-button>
                </template>
              </el-table-column>
              <template #empty>
                <el-empty description="No conversion tasks yet" />
              </template>
            </el-table>
            <div class="pager">
              <el-pagination
                v-model:current-page="historyPage"
                v-model:page-size="historyPageSize"
                :total="historyTotal"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next"
                background
                small
                @size-change="loadHistory"
                @current-change="loadHistory"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <el-dialog v-model="traceDialogVisible" title="Policy Record" width="720px">
        <template v-if="traceRule">
          <div class="trace-location">
            {{ traceRule.source?.file_name || 'Original policy file' }}
            <span v-if="traceRule.source?.page"> · Page {{ traceRule.source.page }}</span>
          </div>
          <div class="trace-caption">Original policy record</div>
          <el-descriptions :column="1" border class="trace-record">
            <el-descriptions-item
              v-for="([key, value], index) in traceEntries(traceRule)"
              :key="`${key}-${index}`"
              :label="key"
            >
              {{ value || '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <el-empty
            v-if="traceEntries(traceRule).length === 0"
            description="No original row data is available for this rule."
          />
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<style scoped>
.rule-tag--duplicate {
  --el-tag-bg-color: #f3efff;
  --el-tag-border-color: #d9cbfa;
  --el-tag-text-color: #7551b8;
}

.page-wrap {
  box-sizing: border-box;
  min-height: calc(100vh - 36px);
  padding: 18px;
  background: linear-gradient(135deg, #f4f7fc 0%, #f8fbff 52%, #f3f7fd 100%);
}
.content-card {
  padding: 20px 20px 18px;
  background: #fff;
  border: 1px solid #e7edf7;
  border-radius: 14px;
  box-shadow: 0 12px 32px rgb(35 70 120 / 8%);
}
.page-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 6px 0 14px;
  margin-bottom: 14px;
  border-bottom: 1px solid #eef2f7;
}
.title-bar {
  width: 4px;
  height: 18px;
  margin-top: 3px;
  background: linear-gradient(180deg, #4f8df7, #285bbf);
  border-radius: 3px;
}
.title-copy {
  flex: 1;
  min-width: 0;
}
.title-main {
  font-size: 18px;
  font-weight: 600;
  line-height: 1.2;
  color: #1f2d3d;
}
.title-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}
.main-tabs {
  box-shadow: none;
}
.main-tabs :deep(.el-tabs__header) {
  margin: 0;
  background: #f8faff;
}
.main-tabs :deep(.el-tabs__item) {
  font-weight: 600;
}
.main-tabs :deep(.el-tabs__content) {
  padding: 20px 18px 2px;
}

.upload-panel {
  display: flex;
  gap: 24px;
  align-items: stretch;
  flex-wrap: wrap;
  padding: 22px;
  background: linear-gradient(115deg, #f8fbff, #fff);
  border: 1px solid #e6edf8;
  border-radius: 12px;
}
.upload-box {
  display: flex;
  flex: 0 0 310px;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  justify-content: center;
  height: 260px;
  cursor: pointer;
  background: #fff;
  border: 1.5px dashed #9bbcf2;
  border-radius: 12px;
  transition: all 0.2s ease;
}
.upload-box:hover {
  border-color: #409eff;
  box-shadow: 0 8px 20px rgb(64 158 255 / 12%);
  transform: translateY(-1px);
}
.upload-preview {
  display: flex;
  flex: 1 1 420px;
  flex-direction: column;
  min-width: 0;
  height: 260px;
  overflow: hidden;
  background: #fff;
  border: 1px solid #dbe6f5;
  border-radius: 12px;
  box-shadow: 0 4px 14px rgb(45 75 120 / 7%);
}
.upload-preview__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 34px;
  padding: 0 10px 0 12px;
  font-size: 12px;
  font-weight: 700;
  color: #405976;
  background: #f7faff;
  border-bottom: 1px solid #e7eef8;
}
.upload-preview__frame {
  width: 100%;
  flex: 1;
  border: 0;
  background: #f2f5f9;
}
.upload-preview__summary {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 7px;
  justify-content: center;
  padding: 14px;
  overflow: hidden;
  font-size: 12px;
  color: #5e718b;
  word-break: break-word;
}
.upload-preview__summary span {
  line-height: 1.45;
  color: #8a9ab0;
}
.upload-preview__filetype {
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #5782c7;
}
.upload-icon {
  font-size: 40px;
  color: #c0ccda;
}
.upload-file {
  padding: 0 12px;
  font-size: 13px;
  color: #409eff;
  text-align: center;
  word-break: break-all;
}
.upload-hint {
  padding: 0 12px;
  font-size: 13px;
  color: #8a94a6;
  text-align: center;
}
.form-actions {
  flex-basis: 100%;
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: -4px;
}

.task-status-panel {
  padding: 14px 16px;
  margin-top: 18px;
  background: #f7faff;
  border: 1px solid #dfeafa;
  border-radius: 10px;
}
.status-row {
  display: flex;
  gap: 10px;
  align-items: center;
}
.status-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.status-meta {
  display: flex;
  gap: 20px;
  margin-top: 8px;
  font-size: 13px;
  color: #667085;
}

.result-panel {
  margin-top: 18px;
}
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 22px 2px 12px;
}
.result-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.list-title {
  margin-bottom: 0;
  font-size: 16px;
  font-weight: 700;
  color: #203759;
}
.table-card {
  padding: 8px;
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 10px;
  overflow: hidden;
}
.extracted-rules-table :deep(.el-table__header th.el-table__cell) {
  height: 48px;
  font-size: 12px;
  font-weight: 750;
  letter-spacing: 0.02em;
  color: #294664;
  background: #eaf1fb;
}
.extracted-rules-table :deep(.el-table__row td.el-table__cell) {
  padding-top: 12px;
  padding-bottom: 12px;
}
.extracted-rules-table :deep(.el-table__row:hover > td.el-table__cell) {
  background: #f5f9ff;
}
.object-name {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  font-weight: 650;
  color: #263d59;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.condition-text {
  line-height: 1.55;
  color: #465b76;
}
.trace-location {
  margin-bottom: 14px;
  font-size: 13px;
  color: #697b96;
}
.trace-caption {
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #294664;
}
.trace-record :deep(.el-descriptions__label) {
  width: 160px;
  font-weight: 650;
  color: #405976;
  background: #f6f9fe;
}
.trace-record :deep(.el-descriptions__content) {
  line-height: 1.6;
  color: #354b65;
  white-space: pre-wrap;
}
.pager {
  display: flex;
  justify-content: flex-end;
  padding: 10px 4px 2px;
}

.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.tab-desc {
  font-size: 13px;
  color: #8a94a6;
}
.muted {
  font-size: 12px;
  color: #909399;
}
.mt-2 {
  margin-top: 8px;
}
.mt-3 {
  margin-top: 16px;
}

@media (max-width: 880px) {
  .upload-panel {
    flex-direction: column;
  }
  .upload-box {
    flex-basis: auto;
    width: 100%;
  }
  .upload-preview {
    flex-basis: auto;
    width: 100%;
    height: 240px;
  }
  .result-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
  .result-actions {
    flex-wrap: wrap;
  }
}
</style>
