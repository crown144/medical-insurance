<script setup lang="ts">
import type {
  ExtractedRule,
  RuleImportStatus,
  RuleImportTask,
} from '../../../api/model/ruleImportModel';

import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';

import { Download, Refresh, UploadFilled } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  cancelRuleImportApi,
  confirmRuleImportApi,
  downloadRuleImportResultApi,
  getExtractedRulesApi,
  getRuleImportTaskApi,
  getRuleImportTasksApi,
  uploadRuleImportApi,
} from '../../../api/ruleImport';

const ALLOWED_EXTS = ['pdf', 'xlsx', 'xls'];
const MAX_FILE_SIZE = 50 * 1024 * 1024;
const TERMINAL: RuleImportStatus[] = ['success', 'failed', 'canceled'];

const RULE_TYPE_LABELS: Record<string, string> = {
  DRUG_RESTRICTION: '超限定用药',
  FREQUENCY_LIMIT: '超频次收费',
  DUPLICATE_CHARGE: '重复收费',
  PRICE_LIMIT: '超标准收费',
  CONSUMABLE_RESTRICTION: '耗材超限定',
  OVER_EXAMINATION: '过度医疗',
  OTHER: '其他',
};

const RULE_TYPE_OPTIONS = Object.entries(RULE_TYPE_LABELS).map(
  ([value, label]) => ({ value, label }),
);

const activeTab = ref<'history' | 'upload'>('upload');

const fileInputRef = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
const form = reactive({
  task_name: '',
  max_pdf_pages: undefined as number | undefined,
  max_rows_per_table: undefined as number | undefined,
  max_tables: undefined as number | undefined,
});
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

function ruleTypeLabel(t: string) {
  return RULE_TYPE_LABELS[t] || t || 'Uncategorized';
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
        ElMessage.error('Conversion failed. Please review the error details.');
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
  selectedFile.value = file;
  if (!form.task_name) form.task_name = file.name;
}

function validateForm(): boolean {
  if (!selectedFile.value) {
    ElMessage.warning('Please select a file to convert first.');
    return false;
  }
  if (form.max_pdf_pages != null && form.max_pdf_pages < 1) {
    ElMessage.warning(
      'Maximum PDF pages must be greater than 0, or left blank for no limit.',
    );
    return false;
  }
  if (form.max_rows_per_table != null && form.max_rows_per_table < 1) {
    ElMessage.warning(
      'Maximum rows per table must be greater than 0, or left blank for no limit.',
    );
    return false;
  }
  if (form.max_tables != null && form.max_tables < 1) {
    ElMessage.warning(
      'Maximum number of tables must be greater than 0, or left blank for no limit.',
    );
    return false;
  }
  return true;
}

async function handleSubmit() {
  if (!validateForm()) return;
  submitting.value = true;
  try {
    const res = await uploadRuleImportApi(selectedFile.value!, {
      task_name: form.task_name.trim() || undefined,
      max_pdf_pages: form.max_pdf_pages ?? undefined,
      max_rows_per_table: form.max_rows_per_table ?? undefined,
      max_tables: form.max_tables ?? undefined,
    });
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
  selectedFile.value = null;
  currentTask.value = null;
  rules.value = [];
  rulesTotal.value = 0;
  selectedRules.value = [];
  form.task_name = '';
  form.max_pdf_pages = undefined;
  form.max_rows_per_table = undefined;
  form.max_tables = undefined;
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
    ElMessage.success(
      `Import completed: ${res.imported} imported, ${res.skipped} skipped.`,
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
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rule-extraction-task-${taskId}.json`;
    document.body.append(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || 'Download failed';
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

const canImport = computed(
  () => currentTask.value?.status === 'success' && rulesTotal.value > 0,
);

onMounted(() => {
  loadHistory();
});

onUnmounted(() => {
  stopPolling();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div>
          <div class="title-main">Rule Discovery</div>
          <div class="title-sub">
            Upload drug or billing catalog files (PDF or Excel). The system
            automatically extracts audit rules for review before writing them
            into the rule library.
          </div>
        </div>
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

            <el-form label-width="150px" class="param-form">
              <div class="form-grid">
                <el-form-item label="Task Name">
                  <el-input
                    v-model="form.task_name"
                    placeholder="Leave blank to use the file name"
                    maxlength="255"
                  />
                </el-form-item>
                <el-form-item label="Max PDF Pages">
                  <el-input-number
                    v-model="form.max_pdf_pages"
                    :min="1"
                    placeholder="Blank = no limit"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="Max Rows per Table">
                  <el-input-number
                    v-model="form.max_rows_per_table"
                    :min="1"
                    placeholder="Blank = no limit"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="Max Tables to Process">
                  <el-input-number
                    v-model="form.max_tables"
                    :min="1"
                    placeholder="Blank = no limit"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
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
            </el-form>
          </div>

          <div v-if="currentTask" class="task-status-panel">
            <div class="list-title">Current Task</div>
            <div class="status-row">
              <span class="status-name">{{ currentTask.task_name }}</span>
              <el-tag :type="getStatusType(currentTask.status)" size="small">
                {{ currentTask.status_label }}
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

            <div class="table-card">
              <el-table
                :data="rules"
                v-loading="rulesLoading"
                border
                size="small"
                style="width: 100%"
                @selection-change="onSelectionChange"
              >
                <el-table-column type="selection" width="44" />
                <el-table-column prop="seq" label="No." width="64" align="center" />
                <el-table-column label="Rule Type" width="120">
                  <template #default="{ row }">
                    <el-tag size="small">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="constrained_object"
                  label="Target Object"
                  min-width="160"
                  show-overflow-tooltip
                />
                <el-table-column
                  prop="constraint_value"
                  label="Constraint"
                  min-width="260"
                  show-overflow-tooltip
                />
                <el-table-column label="Source" width="160" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.source?.file_name || '-' }}
                    <span v-if="row.source?.page">(Page {{ row.source.page }})</span>
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
                    {{ row.status_label }}
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
                width="180"
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
    </div>
  </div>
</template>

<style scoped>
.page-wrap {
  box-sizing: border-box;
  min-height: calc(100vh - 36px);
  padding: 18px;
  background: #f5f7fb;
}
.content-card {
  padding: 18px 18px 16px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgb(16 24 40 / 6%);
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
  background: #409eff;
  border-radius: 3px;
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
.main-tabs :deep(.el-tabs__content) {
  padding: 18px 16px 0;
}

.upload-panel {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.upload-box {
  display: flex;
  flex: 0 0 280px;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  justify-content: center;
  height: 160px;
  cursor: pointer;
  background: #fafcff;
  border: 1px dashed #c0ccda;
  border-radius: 8px;
  transition: border-color 0.2s;
}
.upload-box:hover {
  border-color: #409eff;
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
.param-form {
  flex: 1;
  min-width: 0;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 24px;
}
.form-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 8px;
}

.task-status-panel {
  padding: 14px 16px;
  margin-top: 18px;
  background: #f7f9fc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
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
  margin-bottom: 10px;
}
.result-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.list-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}
.table-card {
  padding: 6px;
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
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
</style>
