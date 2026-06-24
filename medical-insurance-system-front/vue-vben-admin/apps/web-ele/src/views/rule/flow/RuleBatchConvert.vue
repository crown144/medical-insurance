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

// ==================== 常量 ====================

const ALLOWED_EXTS = ['pdf', 'xlsx', 'xls'];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 与后端 RULE_IMPORT_MAX_FILE_SIZE 一致
const TERMINAL: RuleImportStatus[] = ['success', 'failed', 'canceled'];

// 规则类型枚举 -> 中文标签（与后端 importer.RULE_TYPE_MAP 对齐）
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

// ==================== 页面状态 ====================

const activeTab = ref<'history' | 'upload'>('upload');

// ---- 上传表单 ----
const fileInputRef = ref<HTMLInputElement | null>(null);
const selectedFile = ref<File | null>(null);
// 数量类参数留空 = 不限数量；LLM 分块行数由后端配置，前端不提供设置
const form = reactive({
  task_name: '',
  max_pdf_pages: undefined as number | undefined,
  max_rows_per_table: undefined as number | undefined,
  max_tables: undefined as number | undefined,
});
const submitting = ref(false);

// ---- 当前任务 / 轮询 ----
const currentTask = ref<null | RuleImportTask>(null);
const polling = ref(false);
let pollTimer: null | ReturnType<typeof setInterval> = null;

// ---- 抽取结果 ----
const rules = ref<ExtractedRule[]>([]);
const rulesLoading = ref(false);
const rulesTotal = ref(0);
const rulesPage = ref(1);
const rulesPageSize = ref(10);
const ruleTypeFilter = ref('');
const selectedRules = ref<ExtractedRule[]>([]);
const importing = ref(false);

// ---- 历史任务 ----
const historyList = ref<RuleImportTask[]>([]);
const historyLoading = ref(false);
const historyTotal = ref(0);
const historyPage = ref(1);
const historyPageSize = ref(10);

// ==================== 工具函数 ====================

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
  return RULE_TYPE_LABELS[t] || t || '未分类';
}

function isRunning(task: null | RuleImportTask) {
  return !!task && !TERMINAL.includes(task.status);
}

// ==================== 轮询 ====================

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
        ElMessage.success(`转换完成，共抽取 ${task.rule_count} 条规则`);
        rulesPage.value = 1;
        await loadRules();
      } else if (task.status === 'failed') {
        ElMessage.error('转换失败，请查看错误详情');
      }
      await loadHistory();
    }
  } catch {
    // 单次轮询失败忽略，下次继续
  }
}

function startPolling() {
  stopPolling();
  polling.value = true;
  pollTimer = setInterval(pollOnce, 2000);
}

// ==================== 上传与提交 ====================

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
    ElMessage.error(`不支持的文件类型，请上传 ${ALLOWED_EXTS.join(' / ')} 文件`);
    input.value = '';
    return;
  }
  if (file.size > MAX_FILE_SIZE) {
    ElMessage.error('文件过大，最大允许 50MB');
    input.value = '';
    return;
  }
  selectedFile.value = file;
  if (!form.task_name) form.task_name = file.name;
}

function validateForm(): boolean {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择要转换的文件');
    return false;
  }
  // 数量类参数可留空(不限)，若填写则需为正整数
  if (form.max_pdf_pages != null && form.max_pdf_pages < 1) {
    ElMessage.warning('PDF最大页数需大于 0，或留空表示不限');
    return false;
  }
  if (form.max_rows_per_table != null && form.max_rows_per_table < 1) {
    ElMessage.warning('每表最大行数需大于 0，或留空表示不限');
    return false;
  }
  if (form.max_tables != null && form.max_tables < 1) {
    ElMessage.warning('最大处理表数需大于 0，或留空表示不限');
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
    ElMessage.success('已提交转换任务，正在后台执行...');
    startPolling();
    await loadHistory();
  } catch (error: any) {
    const msg =
      error?.response?.data?.error || error?.message || '提交失败';
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

// ==================== 抽取结果 ====================

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
    const msg = error?.response?.data?.error || error?.message || '加载结果失败';
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
    ElMessage.warning('请先勾选要入库的规则，或选择“全部入库”');
    return;
  }
  importing.value = true;
  try {
    const payload = selectAll
      ? { select_all: true }
      : { rule_ids: selectedRules.value.map((r) => r.id) };
    const res = await confirmRuleImportApi(currentTask.value.id, payload);
    ElMessage.success(`入库完成：成功 ${res.imported} 条，跳过 ${res.skipped} 条`);
    currentTask.value = res.task;
    await loadRules();
    await loadHistory();
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '入库失败';
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
    a.download = `规则抽取_任务${taskId}.json`;
    document.body.append(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '下载失败';
    ElMessage.error(msg);
  }
}

// ==================== 历史任务 ====================

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
    const msg = error?.response?.data?.error || error?.message || '加载历史失败';
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
    await ElMessageBox.confirm(`确认取消任务「${task.task_name}」吗？`, '提示', {
      type: 'warning',
    });
  } catch {
    return;
  }
  try {
    await cancelRuleImportApi(task.id);
    ElMessage.success('任务已取消');
    if (currentTask.value?.id === task.id) {
      stopPolling();
      await pollOnce();
    }
    await loadHistory();
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '取消失败';
    ElMessage.error(msg);
  }
}

// ==================== 计算属性 ====================

const canImport = computed(
  () => currentTask.value?.status === 'success' && rulesTotal.value > 0,
);

// ==================== 生命周期 ====================

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
      <!-- 标题 -->
      <div class="page-title">
        <div class="title-bar"></div>
        <div>
          <div class="title-main">规则批量导入转换</div>
          <div class="title-sub">
            上传药品 / 收费目录文件（PDF / Excel），由算法自动抽取医保审核规则，确认后写入规则库
          </div>
        </div>
      </div>

      <el-tabs v-model="activeTab" type="border-card" class="main-tabs">
        <!-- ==================== Tab 1: 上传转换 ==================== -->
        <el-tab-pane label="上传转换" name="upload">
          <!-- 上传表单 -->
          <div class="upload-panel">
            <div class="upload-box" @click="triggerFileSelect">
              <el-icon class="upload-icon"><UploadFilled /></el-icon>
              <div v-if="selectedFile" class="upload-file">
                {{ selectedFile.name }}（{{ formatFileSize(selectedFile.size) }}）
              </div>
              <div v-else class="upload-hint">
                点击选择文件，支持 .pdf / .xlsx / .xls，最大 50MB
              </div>
              <input
                ref="fileInputRef"
                type="file"
                accept=".pdf,.xlsx,.xls"
                style="display: none"
                @change="onFileChange"
              />
            </div>

            <el-form label-width="120px" class="param-form">
              <div class="form-grid">
                <el-form-item label="任务名称">
                  <el-input
                    v-model="form.task_name"
                    placeholder="留空则使用文件名"
                    maxlength="255"
                  />
                </el-form-item>
                <el-form-item label="PDF最大页数">
                  <el-input-number
                    v-model="form.max_pdf_pages"
                    :min="1"
                    placeholder="留空=不限"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="每表最大行数">
                  <el-input-number
                    v-model="form.max_rows_per_table"
                    :min="1"
                    placeholder="留空=不限"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item label="最大处理表数">
                  <el-input-number
                    v-model="form.max_tables"
                    :min="1"
                    placeholder="留空=不限"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </div>
              <div class="form-actions">
                <el-button @click="resetUpload">重置</el-button>
                <el-button
                  type="primary"
                  :loading="submitting"
                  :disabled="polling"
                  @click="handleSubmit"
                >
                  {{ submitting ? '提交中...' : '开始转换' }}
                </el-button>
              </div>
            </el-form>
          </div>

          <!-- 当前任务状态 -->
          <div v-if="currentTask" class="task-status-panel">
            <div class="list-title">当前任务</div>
            <div class="status-row">
              <span class="status-name">{{ currentTask.task_name }}</span>
              <el-tag :type="getStatusType(currentTask.status)" size="small">
                {{ currentTask.status_label }}
              </el-tag>
              <span v-if="polling" class="muted">（执行中，自动刷新…）</span>
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
              <span>解析表数：{{ currentTask.table_count }}</span>
              <span>抽取规则：{{ currentTask.rule_count }}</span>
              <span>已入库：{{ currentTask.imported_count }}</span>
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

          <!-- 抽取结果 -->
          <div v-if="currentTask && currentTask.status === 'success'" class="result-panel">
            <div class="result-header">
              <div class="list-title">抽取规则结果</div>
              <div class="result-actions">
                <el-select
                  v-model="ruleTypeFilter"
                  placeholder="全部类型"
                  clearable
                  size="small"
                  style="width: 150px"
                  @change="() => { rulesPage = 1; loadRules(); }"
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
                  下载JSON
                </el-button>
                <el-button
                  size="small"
                  :loading="importing"
                  :disabled="!canImport || selectedRules.length === 0"
                  @click="handleConfirmImport(false)"
                >
                  入库选中（{{ selectedRules.length }}）
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :loading="importing"
                  :disabled="!canImport"
                  @click="handleConfirmImport(true)"
                >
                  全部入库
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
                <el-table-column prop="seq" label="序号" width="64" align="center" />
                <el-table-column label="规则类型" width="120">
                  <template #default="{ row }">
                    <el-tag size="small">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="constrained_object"
                  label="约束对象"
                  min-width="160"
                  show-overflow-tooltip
                />
                <el-table-column
                  prop="constraint_value"
                  label="限制内容"
                  min-width="260"
                  show-overflow-tooltip
                />
                <el-table-column label="来源" width="160" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.source?.file_name || '-' }}
                    <span v-if="row.source?.page">（第{{ row.source.page }}页）</span>
                  </template>
                </el-table-column>
                <el-table-column label="入库" width="80" align="center">
                  <template #default="{ row }">
                    <el-tag
                      :type="row.is_imported ? 'success' : 'info'"
                      size="small"
                    >
                      {{ row.is_imported ? '已入库' : '未入库' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <template #empty>
                  <el-empty description="暂无抽取规则" />
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

          <!-- 初始空状态 -->
          <el-empty
            v-if="!currentTask"
            description="请上传文件并开始转换"
            class="mt-3"
          />
        </el-tab-pane>

        <!-- ==================== Tab 2: 转换历史 ==================== -->
        <el-tab-pane label="转换历史" name="history">
          <div class="tab-header">
            <div class="tab-desc">查看历史转换任务，可回看结果、下载或取消执行中的任务</div>
            <el-button :icon="Refresh" size="small" @click="loadHistory">刷新</el-button>
          </div>

          <div class="table-card">
            <el-table
              :data="historyList"
              v-loading="historyLoading"
              border
              style="width: 100%"
            >
              <el-table-column prop="id" label="ID" width="64" align="center" />
              <el-table-column prop="task_name" label="任务名称" min-width="180" show-overflow-tooltip />
              <el-table-column prop="file_name" label="文件" min-width="160" show-overflow-tooltip />
              <el-table-column label="状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="getStatusType(row.status)" size="small">
                    {{ row.status_label }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="进度" width="80" align="center">
                <template #default="{ row }">{{ row.progress }}%</template>
              </el-table-column>
              <el-table-column prop="rule_count" label="规则数" width="80" align="center" />
              <el-table-column prop="imported_count" label="已入库" width="80" align="center" />
              <el-table-column prop="created_at" label="创建时间" width="170">
                <template #default="{ row }">
                  {{ new Date(row.created_at).toLocaleString() }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="180" fixed="right" align="center">
                <template #default="{ row }">
                  <el-button type="primary" link @click="viewHistoryTask(row)">
                    查看
                  </el-button>
                  <el-button
                    v-if="row.status === 'success'"
                    type="primary"
                    link
                    @click="handleDownload(row.id)"
                  >
                    下载
                  </el-button>
                  <el-button
                    v-if="!['success', 'failed', 'canceled'].includes(row.status)"
                    type="danger"
                    link
                    @click="handleCancel(row)"
                  >
                    取消
                  </el-button>
                </template>
              </el-table-column>
              <template #empty>
                <el-empty description="暂无转换任务" />
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

/* 上传区 */
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

/* 任务状态 */
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

/* 结果区 */
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

/* tab header */
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
