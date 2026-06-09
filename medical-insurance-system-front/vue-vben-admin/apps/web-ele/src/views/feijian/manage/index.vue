<script setup lang="ts">
import type {
  AlignResultsResponse,
  AlignmentResult,
  ColumnMatch,
  FeiJianImportBatch,
  FeiJianRawRecord,
  FeiJianStats,
  PreviewRecord,
} from '../../../api/model/feijianModel';

import { computed, onMounted, reactive, ref } from 'vue';

import { DataAnalysis, Refresh, Search, Upload } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

import {
  alignFeiJianResultsApi,
  buildFeiJianAuditTaskApi,
  confirmFeiJianImportApi,
  getImportBatchesApi,
  getFeiJianStatsApi,
  getRawRecordsApi,
  previewFeiJianImportApi,
  uploadFeiJianFileApi,
} from '../../../api/feijian';

// ==================== 状态定义 ====================

const activeTab = ref('import');
const stats = ref<FeiJianStats>({
  totalImports: 0,
  totalRawRecords: 0,
  auditTaskCount: 0,
  alignmentRate: 0,
  diffCount: 0,
  unresolvedDiffCount: 0,
});

// ---- 导入 ----
const importBatches = ref<FeiJianImportBatch[]>([]);
const importBatchesLoading = ref(false);
const uploading = ref(false);
const analyzing = ref(false);

// 上传分析结果
const currentBatch = ref<FeiJianImportBatch | null>(null);
const analysisMappings = ref<ColumnMatch[]>([]);
const analysisColumns = ref<string[]>([]);
const analysisSamples = ref<Record<string, any>[]>([]);
const unmappedFields = ref<string[]>([]);
const unmappedColumns = ref<string[]>([]);
const showAnalysis = ref(false);

// 用户确认的列映射 {fieldKey: columnName}
const confirmedMapping = ref<Record<string, string>>({});

// 预览
const previewLoading = ref(false);
const previewRecords = ref<PreviewRecord[]>([]);
const showPreview = ref(false);

// 导入确认
const importing = ref(false);

// ---- 原始记录 ----
const rawRecords = ref<FeiJianRawRecord[]>([]);
const rawLoading = ref(false);
const rawTotal = ref(0);
const rawPage = ref(1);
const rawPageSize = ref(10);
const rawFilter = reactive({ batchId: '', keyword: '' });

// ---- 自动审查构建 ----
const auditBuildLoading = ref(false);
const auditBatchId = ref<number | null>(null);
const auditTaskName = ref('');
const auditExecuteNow = ref(true);
const auditSelectedSchemas = ref<string[]>([
  '超限定用药',
  '重复收费',
  '超标准收费',
]);
const auditBuildResult = ref<any | null>(null);
const auditSchemaOptions = [
  { label: '超限定用药', value: '超限定用药' },
  { label: '重复收费', value: '重复收费' },
  { label: '超标准收费', value: '超标准收费' },
];
const successfulBatches = computed(() =>
  importBatches.value.filter((batch) => batch.status === 'success'),
);
const selectedAuditBatch = computed(() =>
  successfulBatches.value.find((batch) => batch.id === auditBatchId.value),
);

// ---- 结果对齐 ----
const alignmentBatchId = ref<number | null>(null);
const alignmentTaskId = ref('');
const alignmentLoading = ref(false);
const alignmentResult = ref<AlignResultsResponse | null>(null);
const alignmentItems = ref<AlignmentResult[]>([]);
const alignmentPage = ref(1);
const alignmentPageSize = ref(10);
const alignmentTotal = ref(0);
const selectedAlignmentBatch = computed(() =>
  successfulBatches.value.find((batch) => batch.id === alignmentBatchId.value),
);

// ==================== 工具函数 ====================

function formatFileSize(bytes: number) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function getBatchStatusType(status: string) {
  const map: Record<string, string> = {
    uploading: 'info', analyzing: 'warning', mapping: 'warning',
    importing: 'warning', success: 'success', failed: 'danger',
  };
  return map[status] || 'info';
}

function getConfidenceColor(confidence: number) {
  if (confidence >= 0.8) return '#67c23a';
  if (confidence >= 0.5) return '#e6a23c';
  return '#f56c6c';
}

function getMethodLabel(method: string) {
  const map: Record<string, string> = {
    'regex': '正则匹配',
    'regex+data': '正则+数据验证',
    'llm': 'LLM辅助',
  };
  return map[method] || method;
}

function getMatchStatusType(status: string) {
  const map: Record<string, string> = {
    matched: 'success',
    partial: 'warning',
    unmatched: 'danger',
    'system-only': 'info',
  };
  return map[status] || 'info';
}

// 目标字段标签映射
const fieldLabels: Record<string, string> = {
  hospitalization_no: '住院号',
  patient_name: '患者姓名',
  hospital_name: '医疗机构',
  admission_date: '入院日期',
  discharge_date: '出院日期',
  issue_category: '问题类别',
  issue_description: '问题描述',
  involved_amount: '涉及金额',
  audit_org: '飞检机构',
  audit_date: '飞检日期',
};

// ==================== 数据加载 ====================

async function loadStats() {
  try {
    const data = await getFeiJianStatsApi();
    if (data) stats.value = data;
  } catch {
    // 后端未就绪时用默认值
  }
}

async function loadImportBatches() {
  importBatchesLoading.value = true;
  try {
    const res = await getImportBatchesApi();
    importBatches.value = res.items;
    // 同时更新统计
    if (res.items.length > 0) {
      stats.value.totalImports = res.items.filter(
        (b) => b.status === 'success',
      ).length;
    }
  } catch {
    // 后端未就绪
  } finally {
    importBatchesLoading.value = false;
  }
}

async function loadRawRecords() {
  rawLoading.value = true;
  try {
    const params: any = { page: rawPage.value, page_size: rawPageSize.value };
    if (rawFilter.batchId) params.import_batch = rawFilter.batchId;
    if (rawFilter.keyword) params.hospitalization_no = rawFilter.keyword;
    const res = await getRawRecordsApi(params);
    rawRecords.value = res.items;
    rawTotal.value = res.total;
    stats.value.totalRawRecords = res.total;
  } catch {
    // 后端未就绪
  } finally {
    rawLoading.value = false;
  }
}

// ==================== 导入流程 ====================

/** 步骤1: 选择文件并上传分析 */
async function handleFileUpload(file: File) {
  showAnalysis.value = false;
  showPreview.value = false;
  uploading.value = true;
  analyzing.value = true;

  try {
    const result = await uploadFeiJianFileApi(file);
    currentBatch.value = result.batch;
    analysisMappings.value = result.analysis.mappings;
    analysisColumns.value = result.analysis.columns;
    analysisSamples.value = result.analysis.sample_rows;
    unmappedFields.value = result.analysis.unmapped_fields;
    unmappedColumns.value = result.analysis.unmapped_columns;

    // 构建确认映射
    confirmedMapping.value = {};
    for (const m of result.analysis.mappings) {
      confirmedMapping.value[m.field_key] = m.column_name;
    }

    showAnalysis.value = true;
    ElMessage.success('文件分析完成，请确认列映射');
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '上传失败';
    ElMessage.error(msg);
  } finally {
    uploading.value = false;
    analyzing.value = false;
  }
}

/** 步骤2: 用户修改映射 */
function updateMapping(fieldKey: string, columnName: string) {
  confirmedMapping.value[fieldKey] = columnName;
}

/** 步骤3: 预览 */
async function handlePreview() {
  if (!currentBatch.value) return;
  previewLoading.value = true;
  try {
    const result = await previewFeiJianImportApi({
      batch_id: currentBatch.value.id,
      column_mapping: confirmedMapping.value,
      limit: 10,
    });
    previewRecords.value = result.preview;
    showPreview.value = true;
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '预览失败';
    ElMessage.error(msg);
  } finally {
    previewLoading.value = false;
  }
}

/** 步骤4: 确认导入 */
async function handleConfirmImport() {
  if (!currentBatch.value) return;
  importing.value = true;
  try {
    const result = await confirmFeiJianImportApi({
      batch_id: currentBatch.value.id,
      column_mapping: confirmedMapping.value,
    });
    ElMessage.success(
      `导入完成：共 ${result.summary.total} 条，成功 ${result.summary.success} 条`,
    );
    showAnalysis.value = false;
    showPreview.value = false;
    currentBatch.value = null;
    await loadImportBatches();
    await loadRawRecords();
    await loadStats();
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '导入失败';
    ElMessage.error(msg);
  } finally {
    importing.value = false;
  }
}

/** 重置导入流程 */
async function handleBuildAuditTask() {
  if (!auditBatchId.value) {
    ElMessage.warning('请选择导入批次');
    return;
  }
  if (auditSelectedSchemas.value.length === 0) {
    ElMessage.warning('请选择审查方案');
    return;
  }

  auditBuildLoading.value = true;
  try {
    const result = await buildFeiJianAuditTaskApi(auditBatchId.value, {
      execute: auditExecuteNow.value,
      name: auditTaskName.value.trim() || undefined,
      selectedSchemas: auditSelectedSchemas.value,
    });
    auditBuildResult.value = result;
    ElMessage.success(
      `已创建审查任务：${result.task.name}，共 ${result.hospitalization_count} 个住院号`,
    );
    await loadImportBatches();
    await loadRawRecords();
    await loadStats();
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '创建审查任务失败';
    ElMessage.error(msg);
  } finally {
    auditBuildLoading.value = false;
  }
}

async function handleAlignResults(resetPage = false) {
  if (!alignmentBatchId.value) {
    ElMessage.warning('请选择导入批次');
    return;
  }
  if (resetPage) {
    alignmentPage.value = 1;
  }

  const taskIdText = alignmentTaskId.value.trim();
  const taskId = taskIdText ? Number(taskIdText) : undefined;
  if (taskIdText && Number.isNaN(taskId)) {
    ElMessage.warning('任务ID必须是数字');
    return;
  }

  alignmentLoading.value = true;
  try {
    const result = await alignFeiJianResultsApi(alignmentBatchId.value, {
      page: alignmentPage.value,
      page_size: alignmentPageSize.value,
      task_id: taskId,
    });
    alignmentResult.value = result;
    alignmentItems.value = result.items;
    alignmentTotal.value = result.pagination.total;
    stats.value.alignmentRate = result.summary.alignmentRate;
    stats.value.diffCount = result.summary.diffCount;
    stats.value.unresolvedDiffCount = result.summary.unresolvedDiffCount;
    ElMessage.success(`对齐完成：对齐率 ${result.summary.alignmentRate}%`);
  } catch (error: any) {
    const msg = error?.response?.data?.error || error?.message || '结果对齐失败';
    ElMessage.error(msg);
  } finally {
    alignmentLoading.value = false;
  }
}

function resetImport() {
  showAnalysis.value = false;
  showPreview.value = false;
  currentBatch.value = null;
  analysisMappings.value = [];
  previewRecords.value = [];
  confirmedMapping.value = {};
}

/** 文件上传触发 */
const fileInputRef = ref<HTMLInputElement | null>(null);
function triggerFileInput() {
  fileInputRef.value?.click();
}
function onFileInputChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) {
    handleFileUpload(file);
  }
  input.value = '';
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadStats();
  loadImportBatches();
  loadRawRecords();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <!-- 页面标题 -->
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">飞检结果管理</div>
          <div class="title-sub">飞检结果导入 → 自动审查构建 → 结果对齐 → 差异分析 → 结果管理</div>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-value" style="color: #1677ff">{{ stats.totalImports }}</div>
          <div class="stat-label">导入批次</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #722ed1">{{ stats.totalRawRecords }}</div>
          <div class="stat-label">原始记录</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #52c41a">{{ stats.auditTaskCount }}</div>
          <div class="stat-label">审查任务</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #1677ff">{{ stats.alignmentRate }}%</div>
          <div class="stat-label">对齐率</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #faad14">{{ stats.diffCount }}</div>
          <div class="stat-label">差异总数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #ff4d4f">{{ stats.unresolvedDiffCount }}</div>
          <div class="stat-label">待解决差异</div>
        </div>
      </div>

      <!-- Tab 切换 -->
      <el-tabs v-model="activeTab" type="border-card" class="main-tabs" @tab-change="(tab: string) => { if (tab === 'records') loadRawRecords(); if (tab === 'import') loadImportBatches(); }">

        <!-- ==================== Tab 1: 飞检结果导入 ==================== -->
        <el-tab-pane label="飞检结果导入" name="import">
          <div class="tab-header">
            <span class="tab-desc">从飞检结果文件中提取住院号及问题信息，自动解析列结构并导入</span>
            <div class="tab-actions">
              <el-button type="primary" :icon="Upload" :loading="uploading" @click="triggerFileInput">
                {{ uploading ? '分析中...' : '上传飞检文件' }}
              </el-button>
              <input ref="fileInputRef" type="file" accept=".xlsx,.xls,.csv" style="display: none" @change="onFileInputChange" />
            </div>
          </div>

          <!-- 分析结果：列映射确认 -->
          <div v-if="showAnalysis && currentBatch" class="analysis-panel">
            <el-alert
              :title="`文件「${currentBatch.file_name}」分析完成，请确认列映射后点击导入`"
              type="success"
              :closable="false"
              show-icon
              class="mb-3"
            />

            <div class="analysis-grid">
              <!-- 左：列映射 -->
              <div class="analysis-left">
                <div class="list-title">列映射确认</div>
                <div class="table-card">
                  <table class="mapping-table">
                    <thead>
                      <tr>
                        <th>目标字段</th>
                        <th>匹配到的列</th>
                        <th>置信度</th>
                        <th>方法</th>
                        <th>手动调整</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="m in analysisMappings" :key="m.field_key">
                        <td class="field-label-cell">
                          <span class="required-mark">*</span>
                          {{ m.field_label }}
                        </td>
                        <td>
                          <el-tag size="small" type="success">{{ m.column_name }}</el-tag>
                        </td>
                        <td>
                          <span :style="{ color: getConfidenceColor(m.confidence), fontWeight: 'bold' }">
                            {{ (m.confidence * 100).toFixed(0) }}%
                          </span>
                        </td>
                        <td>
                          <el-tag size="small" type="info">{{ getMethodLabel(m.method) }}</el-tag>
                        </td>
                        <td>
                          <el-select
                            :model-value="confirmedMapping[m.field_key]"
                            size="small"
                            style="width: 150px"
                            @change="(val: string) => updateMapping(m.field_key, val)"
                          >
                            <el-option
                              v-for="col in analysisColumns"
                              :key="col"
                              :label="col"
                              :value="col"
                            />
                          </el-select>
                        </td>
                      </tr>
                      <!-- 未匹配的字段 -->
                      <tr v-for="field in unmappedFields" :key="field" class="unmapped-row">
                        <td class="field-label-cell">
                          <span class="required-mark">*</span>
                          {{ fieldLabels[field] || field }}
                        </td>
                        <td colspan="3">
                          <el-tag size="small" type="danger">未匹配</el-tag>
                        </td>
                        <td>
                          <el-select
                            :model-value="confirmedMapping[field] || ''"
                            size="small"
                            placeholder="手动选择"
                            clearable
                            style="width: 150px"
                            @change="(val: string) => updateMapping(field, val)"
                          >
                            <el-option
                              v-for="col in unmappedColumns"
                              :key="col"
                              :label="col"
                              :value="col"
                            />
                          </el-select>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <!-- 右：样本数据 -->
              <div class="analysis-right">
                <div class="list-title">样本数据预览（前5行）</div>
                <div class="sample-table-wrap">
                  <table class="sample-table">
                    <thead>
                      <tr>
                        <th v-for="col in analysisColumns.slice(0, 6)" :key="col">{{ col }}</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, i) in analysisSamples" :key="i">
                        <td v-for="col in analysisColumns.slice(0, 6)" :key="col">
                          {{ row[col] ?? '' }}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div v-if="unmappedColumns.length" class="mt-3">
                  <span class="muted">未识别列：</span>
                  <el-tag v-for="col in unmappedColumns" :key="col" size="small" class="mr-1" type="info">{{ col }}</el-tag>
                </div>
              </div>
            </div>

            <!-- 预览 -->
            <div v-if="showPreview" class="mt-3">
              <div class="list-title">导入预览</div>
              <div class="table-card">
                <el-table :data="previewRecords" border size="small" style="width: 100%">
                  <el-table-column prop="row_index" label="行号" width="70" align="center" />
                  <el-table-column prop="hospitalization_no" label="住院号" width="150" />
                  <el-table-column prop="patient_name" label="患者" width="80" />
                  <el-table-column prop="hospital_name" label="医疗机构" min-width="140" />
                  <el-table-column prop="issue_category" label="问题类别" width="100" />
                  <el-table-column prop="issue_description" label="问题描述" min-width="160" show-overflow-tooltip />
                  <el-table-column label="涉及金额" width="110" align="center">
                    <template #default="{ row }">{{ row.involved_amount?.toLocaleString() }}</template>
                  </el-table-column>
                </el-table>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="mt-3 flex justify-end gap-3">
              <el-button @click="resetImport">取消</el-button>
              <el-button :loading="previewLoading" @click="handlePreview">预览导入</el-button>
              <el-button type="primary" :loading="importing" @click="handleConfirmImport">
                确认导入
              </el-button>
            </div>
          </div>

          <!-- 导入批次列表 -->
          <div class="list-title" style="margin-top: 16px">导入批次记录</div>
          <div class="table-card">
            <el-table :data="importBatches" v-loading="importBatchesLoading" border style="width: 100%" class="task-table">
              <el-table-column prop="file_name" label="文件名" min-width="280" />
              <el-table-column label="文件大小" width="110" align="center">
                <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
              </el-table-column>
              <el-table-column label="记录数" width="90" align="center">
                <template #default="{ row }">{{ row.record_count || row.success_count || '-' }}</template>
              </el-table-column>
              <el-table-column label="状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="getBatchStatusType(row.status)" size="small">{{ row.status_label }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="导入时间" width="180" align="center" />
              <el-table-column label="操作" width="140" align="center">
                <template #default="{ row }">
                  <el-button link type="primary" :icon="Search" @click="rawFilter.batchId = String(row.id); activeTab = 'records';">查看记录</el-button>
                </template>
              </el-table-column>
              <template #empty><el-empty description="暂无导入记录" /></template>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- ==================== Tab 2: 原始记录查看 ==================== -->
        <el-tab-pane label="原始记录" name="records">
          <div class="tab-header">
            <span class="tab-desc">查看已导入的飞检原始记录</span>
          </div>

          <div class="query-card">
            <div class="query-row">
              <div class="query-left">
                <div class="query-item">
                  <div class="query-label">住院号</div>
                  <el-input v-model="rawFilter.keyword" placeholder="输入住院号" clearable style="width: 180px" @keyup.enter="loadRawRecords" />
                </div>
                <div class="query-item">
                  <div class="query-label">批次</div>
                  <el-select v-model="rawFilter.batchId" placeholder="全部" clearable style="width: 200px" @change="loadRawRecords">
                    <el-option v-for="b in importBatches" :key="b.id" :label="b.file_name" :value="String(b.id)" />
                  </el-select>
                </div>
                <div class="query-actions">
                  <el-button type="primary" :icon="Search" @click="loadRawRecords">查询</el-button>
                  <el-button :icon="Refresh" @click="rawFilter.keyword = ''; rawFilter.batchId = ''; loadRawRecords();">重置</el-button>
                </div>
              </div>
            </div>
          </div>

          <div class="list-title">原始记录列表</div>
          <div class="table-card">
            <el-table :data="rawRecords" v-loading="rawLoading" border style="width: 100%" class="task-table">
              <el-table-column prop="hospitalization_no" label="住院号" width="150" align="center" />
              <el-table-column prop="patient_name" label="患者" width="80" align="center" />
              <el-table-column prop="hospital_name" label="医疗机构" min-width="160" />
              <el-table-column prop="issue_category" label="问题类别" width="110" align="center" />
              <el-table-column prop="issue_description" label="问题描述" min-width="200" show-overflow-tooltip />
              <el-table-column label="涉及金额" width="110" align="center">
                <template #default="{ row }">{{ row.involved_amount?.toLocaleString() }}</template>
              </el-table-column>
              <el-table-column prop="audit_org" label="飞检机构" width="150" align="center" />
              <el-table-column prop="audit_date" label="飞检日期" width="110" align="center" />
              <el-table-column prop="import_file_name" label="来源文件" min-width="180" show-overflow-tooltip />
              <template #empty><el-empty description="暂无数据" /></template>
            </el-table>
            <div class="pager">
              <el-pagination
                v-model:current-page="rawPage"
                :page-size="rawPageSize"
                :total="rawTotal"
                :page-sizes="[10, 20, 50]"
                layout="total, sizes, prev, pager, next"
                background
                small
                @size-change="(v: number) => { rawPageSize = v; loadRawRecords(); }"
                @current-change="() => loadRawRecords()"
              />
            </div>
          </div>
        </el-tab-pane>

        <!-- ==================== Tab 3: 自动审查构建 ==================== -->
        <el-tab-pane label="自动审查构建" name="audit">
          <div class="tab-header">
            <span class="tab-desc">根据已导入飞检批次中的住院号创建审查任务，并可立即加入计算队列</span>
          </div>
          <div class="audit-build-panel">
            <div class="query-card">
              <div class="query-row">
                <div class="query-left">
                  <div class="query-item">
                    <div class="query-label">导入批次</div>
                    <el-select
                      v-model="auditBatchId"
                      placeholder="选择已导入成功的批次"
                      filterable
                      style="width: 320px"
                    >
                      <el-option
                        v-for="batch in successfulBatches"
                        :key="batch.id"
                        :label="`${batch.file_name}（${batch.success_count || batch.record_count}条）`"
                        :value="batch.id"
                      />
                    </el-select>
                  </div>
                  <div class="query-item">
                    <div class="query-label">任务名称</div>
                    <el-input
                      v-model="auditTaskName"
                      clearable
                      placeholder="不填则自动生成"
                      style="width: 260px"
                    />
                  </div>
                  <div class="query-item">
                    <div class="query-label">审查方案</div>
                    <el-select
                      v-model="auditSelectedSchemas"
                      multiple
                      collapse-tags
                      collapse-tags-tooltip
                      style="width: 300px"
                    >
                      <el-option
                        v-for="item in auditSchemaOptions"
                        :key="item.value"
                        :label="item.label"
                        :value="item.value"
                      />
                    </el-select>
                  </div>
                  <div class="query-item">
                    <div class="query-label">执行方式</div>
                    <el-switch
                      v-model="auditExecuteNow"
                      active-text="立即执行"
                      inactive-text="仅创建"
                    />
                  </div>
                  <div class="query-actions">
                    <el-button
                      type="primary"
                      :icon="DataAnalysis"
                      :loading="auditBuildLoading"
                      @click="handleBuildAuditTask"
                    >
                      构建审查任务
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="selectedAuditBatch" class="audit-build-summary">
              <div class="summary-item">
                <span class="muted">当前批次</span>
                <strong>{{ selectedAuditBatch.file_name }}</strong>
              </div>
              <div class="summary-item">
                <span class="muted">导入记录</span>
                <strong>{{ selectedAuditBatch.success_count || selectedAuditBatch.record_count }}</strong>
              </div>
              <div class="summary-item">
                <span class="muted">状态</span>
                <el-tag :type="getBatchStatusType(selectedAuditBatch.status)" size="small">
                  {{ selectedAuditBatch.status_label }}
                </el-tag>
              </div>
            </div>

            <el-alert
              v-if="auditBuildResult"
              type="success"
              show-icon
              :closable="false"
              class="mt-3"
            >
              <template #title>
                已创建任务 {{ auditBuildResult.task.name }}，共
                {{ auditBuildResult.hospitalization_count }} 个住院号，任务ID：
                {{ auditBuildResult.task.id }}
              </template>
            </el-alert>
          </div>
        </el-tab-pane>

        <!-- ==================== Tab 4: 结果对齐 ==================== -->
        <el-tab-pane label="结果对齐" name="alignment">
          <div class="tab-header">
            <span class="tab-desc">按住院号、问题类型归一、文本相似度与金额接近度匹配飞检和系统审查结果</span>
          </div>
          <div class="alignment-panel">
            <div class="query-card">
              <div class="query-row">
                <div class="query-left">
                  <div class="query-item">
                    <div class="query-label">导入批次</div>
                    <el-select
                      v-model="alignmentBatchId"
                      filterable
                      placeholder="选择需要对齐的批次"
                      style="width: 320px"
                    >
                      <el-option
                        v-for="batch in successfulBatches"
                        :key="batch.id"
                        :label="`${batch.file_name}（${batch.success_count || batch.record_count}条）`"
                        :value="batch.id"
                      />
                    </el-select>
                  </div>
                  <div class="query-item">
                    <div class="query-label">审查任务ID</div>
                    <el-input
                      v-model="alignmentTaskId"
                      clearable
                      placeholder="不填则自动使用批次关联任务"
                      style="width: 240px"
                    />
                  </div>
                  <div class="query-actions">
                    <el-button
                      type="primary"
                      :icon="DataAnalysis"
                      :loading="alignmentLoading"
                      @click="handleAlignResults(true)"
                    >
                      开始对齐
                    </el-button>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="selectedAlignmentBatch" class="audit-build-summary">
              <div class="summary-item">
                <span class="muted">当前批次</span>
                <strong>{{ selectedAlignmentBatch.file_name }}</strong>
              </div>
              <div class="summary-item">
                <span class="muted">导入记录</span>
                <strong>{{ selectedAlignmentBatch.success_count || selectedAlignmentBatch.record_count }}</strong>
              </div>
              <div class="summary-item">
                <span class="muted">任务ID</span>
                <strong>{{ alignmentResult?.task_id || alignmentTaskId || '自动推断' }}</strong>
              </div>
            </div>

            <div v-if="alignmentResult" class="alignment-summary">
              <div class="alignment-stat">
                <span>总数</span>
                <strong>{{ alignmentResult.summary.total }}</strong>
              </div>
              <div class="alignment-stat success">
                <span>完全匹配</span>
                <strong>{{ alignmentResult.summary.matched }}</strong>
              </div>
              <div class="alignment-stat warning">
                <span>部分匹配</span>
                <strong>{{ alignmentResult.summary.partial }}</strong>
              </div>
              <div class="alignment-stat danger">
                <span>仅飞检发现</span>
                <strong>{{ alignmentResult.summary.unmatched }}</strong>
              </div>
              <div class="alignment-stat info">
                <span>系统额外发现</span>
                <strong>{{ alignmentResult.summary.systemOnly }}</strong>
              </div>
              <div class="alignment-stat primary">
                <span>对齐率</span>
                <strong>{{ alignmentResult.summary.alignmentRate }}%</strong>
              </div>
            </div>

            <div class="table-card mt-3">
              <el-table
                :data="alignmentItems"
                v-loading="alignmentLoading"
                border
                class="task-table"
                style="width: 100%"
              >
                <el-table-column prop="hospitalizationNo" label="住院号" width="150" align="center" />
                <el-table-column prop="patientName" label="患者" width="90" align="center" />
                <el-table-column label="飞检问题" min-width="220" show-overflow-tooltip>
                  <template #default="{ row }">
                    <div class="issue-main">{{ row.feijianIssue || '-' }}</div>
                    <div class="muted">{{ row.feijianCategory || '-' }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="系统问题" min-width="220" show-overflow-tooltip>
                  <template #default="{ row }">
                    <div class="issue-main">{{ row.systemIssue || '-' }}</div>
                    <div class="muted">{{ row.systemCategory || '-' }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="金额" width="140" align="center">
                  <template #default="{ row }">
                    <div>{{ row.feijianAmount?.toLocaleString() || 0 }}</div>
                    <div class="muted">{{ row.systemAmount?.toLocaleString() || 0 }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="匹配状态" width="120" align="center">
                  <template #default="{ row }">
                    <el-tag :type="getMatchStatusType(row.matchStatus)" size="small">
                      {{ row.matchStatusLabel }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="分数" width="90" align="center">
                  <template #default="{ row }">
                    {{ Math.round((row.matchScore || 0) * 100) }}%
                  </template>
                </el-table-column>
                <el-table-column label="依据" min-width="180" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.matchReasons?.join('、') || '-' }}
                  </template>
                </el-table-column>
                <template #empty>
                  <el-empty description="请选择批次并执行对齐" />
                </template>
              </el-table>
              <div class="pager">
                <el-pagination
                  v-model:current-page="alignmentPage"
                  v-model:page-size="alignmentPageSize"
                  :total="alignmentTotal"
                  :page-sizes="[10, 20, 50, 100]"
                  layout="total, sizes, prev, pager, next"
                  background
                  small
                  @size-change="() => handleAlignResults(true)"
                  @current-change="() => handleAlignResults()"
                />
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- ==================== Tab 5: 差异分析 ==================== -->
        <el-tab-pane label="差异分析" name="diff">
          <div class="tab-header">
            <span class="tab-desc">自动识别飞检与系统审查之间的差异问题（需后端实现差异分析接口）</span>
          </div>
          <el-empty description="差异分析功能待后端实现" />
        </el-tab-pane>

        <!-- ==================== Tab 6: 结果管理 ==================== -->
        <el-tab-pane label="结果管理" name="manage">
          <div class="tab-header">
            <span class="tab-desc">对飞检问题进行统一归档与追踪（需后端实现管理接口）</span>
          </div>
          <el-empty description="结果管理功能待后端实现" />
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<style scoped>
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
  box-sizing: border-box;
}
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 18px 16px;
  box-shadow: 0 2px 10px rgba(16, 24, 40, 0.06);
}

/* 标题 */
.page-title {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0 14px;
  border-bottom: 1px solid #eef2f7;
  margin-bottom: 14px;
}
.title-bar {
  width: 4px;
  height: 18px;
  background: #409eff;
  border-radius: 3px;
  margin-top: 3px;
}
.title-main {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
  line-height: 1.2;
}
.title-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 100px;
  background: #f7f9fc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 12px 14px;
  text-align: center;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  margin-top: 4px;
  font-size: 12px;
  color: #667085;
}

/* Tabs */
.main-tabs {
  box-shadow: none;
}
.main-tabs :deep(.el-tabs__content) {
  padding: 16px 0 0;
}

/* Tab header */
.tab-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}
.tab-desc {
  font-size: 13px;
  color: #8a94a6;
}
.tab-actions {
  display: flex;
  gap: 8px;
}

/* 查询区 */
.query-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px 14px 12px;
  margin-bottom: 12px;
}
.query-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.query-left {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px 16px;
}
.query-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.query-label {
  font-size: 12px;
  color: #667085;
}
.query-actions {
  display: flex;
  gap: 10px;
  padding-bottom: 2px;
}

/* 列表标题 */
.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #344054;
  margin: 0 0 10px;
}

/* 表格 */
.table-card {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.task-table :deep(.el-table__header th) {
  background: #f7f9fc !important;
  color: #475467;
  font-weight: 600;
  height: 46px;
}
.task-table :deep(.el-table__row td) {
  height: 50px;
}

/* 分页 */
.pager {
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
}

/* 分析面板 */
.analysis-panel {
  background: #f7f9fc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}
.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.analysis-left, .analysis-right {
  min-width: 0;
}

/* 映射表 */
.mapping-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.mapping-table th {
  background: #f7f9fc;
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  color: #475467;
  border-bottom: 2px solid #eef2f7;
}
.mapping-table td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: middle;
}
.mapping-table .unmapped-row {
  background: #fef0f0;
}
.field-label-cell {
  font-weight: 500;
  color: #303133;
}
.required-mark {
  color: #f56c6c;
  margin-right: 2px;
}

/* 样本表 */
.sample-table-wrap {
  overflow-x: auto;
  border: 1px solid #eef2f7;
  border-radius: 6px;
}
.sample-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.sample-table th {
  background: #f7f9fc;
  padding: 6px 8px;
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
  border-bottom: 1px solid #eef2f7;
}
.sample-table td {
  padding: 6px 8px;
  border-bottom: 1px solid #f5f5f5;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-build-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.audit-build-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 14px;
  background: #f7f9fc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
}

.summary-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 180px;
}

.alignment-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alignment-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(120px, 1fr));
  gap: 10px;
}

.alignment-stat {
  padding: 12px;
  background: #f7f9fc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  text-align: center;
}

.alignment-stat span {
  display: block;
  font-size: 12px;
  color: #667085;
}

.alignment-stat strong {
  display: block;
  margin-top: 4px;
  font-size: 20px;
  color: #344054;
}

.alignment-stat.success strong { color: #67c23a; }
.alignment-stat.warning strong { color: #e6a23c; }
.alignment-stat.danger strong { color: #f56c6c; }
.alignment-stat.info strong { color: #909399; }
.alignment-stat.primary strong { color: #1677ff; }

.issue-main {
  color: #303133;
  font-weight: 500;
}

/* 辅助 */
.op-sep {
  color: #dcdfe6;
  margin: 0 2px;
}
.muted {
  color: #8a94a6;
  font-size: 12px;
}
.mr-1 { margin-right: 4px; }
.mt-3 { margin-top: 12px; }
.mb-3 { margin-bottom: 12px; }
.flex { display: flex; }
.justify-end { justify-content: flex-end; }
.gap-3 { gap: 12px; }

@media (max-width: 900px) {
  .analysis-grid {
    grid-template-columns: 1fr;
  }

  .alignment-summary {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }
}
</style>

