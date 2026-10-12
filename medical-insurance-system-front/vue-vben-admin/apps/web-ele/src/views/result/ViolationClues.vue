<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { Download, Refresh, Search, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

import { getViolationCluesApi } from '#/api/result';

const loading = ref(false);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(200);
const selectedClue = ref<Record<string, any> | null>(null);
const dialogVisible = ref(false);
const clues = ref<Record<string, any>[]>([]);
const selectedRows = ref<Record<string, any>[]>([]);
const tableRef = ref();
const form = reactive({
  taskId: '',
  hospitalizationId: '',
  ruleKeyword: '',
});

const rows = computed(() =>
  clues.value.map((clue) => {
    const evidence = clue.clueEvidence?.[0] || {};
    return { ...clue, ...evidence };
  }),
);

async function loadClues() {
  loading.value = true;
  selectedRows.value = [];
  try {
    const response = await getViolationCluesApi({
      page: currentPage.value,
      page_size: pageSize.value,
      task_id: form.taskId || undefined,
      hospitalization_id: form.hospitalizationId || undefined,
      rule_keyword: form.ruleKeyword || undefined,
    });
    const payload = response.data || response;
    clues.value = payload.results || [];
    total.value = payload.count || 0;
  } catch (error: any) {
    ElMessage.error(error?.detail || 'Failed to load violation clues');
  } finally {
    loading.value = false;
  }
}

function search() {
  currentPage.value = 1;
  loadClues();
}

function reset() {
  form.taskId = '';
  form.hospitalizationId = '';
  form.ruleKeyword = '';
  search();
}

function handlePageSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  loadClues();
}

function showJson(row: Record<string, any>) {
  selectedClue.value = clues.value.find(
    (item) => item.externalClueId === row.externalClueId,
  ) || null;
  dialogVisible.value = true;
}

function buildRequestBody(selectedClues: Record<string, any>[]) {
  return {
    data: selectedClues.map(({ _internalResultId, ...clue }) => clue),
  };
}

function downloadRequestBody(selectedClues: Record<string, any>[]) {
  if (selectedClues.length === 0) {
    ElMessage.warning('Select violation clues to download first.');
    return;
  }
  const blob = new Blob([JSON.stringify(buildRequestBody(selectedClues), null, 2)], {
    type: 'application/json',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `violation_clues_${selectedClues.length}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function handleSelectionChange(rows: Record<string, any>[]) {
  selectedRows.value = rows;
}

function selectCurrentPage() {
  tableRef.value?.toggleAllSelection();
}

function clearSelection() {
  tableRef.value?.clearSelection();
  selectedRows.value = [];
}

function downloadSelectedRequestBody() {
  const selectedClues = selectedRows.value
    .map((row) => clues.value.find((item) => item.externalClueId === row.externalClueId))
    .filter((item): item is Record<string, any> => Boolean(item));
  downloadRequestBody(selectedClues);
}

function printRequestBody(row: Record<string, any>) {
  const clue = clues.value.find((item) => item.externalClueId === row.externalClueId);
  if (!clue) return;
  const requestBody = buildRequestBody([clue]);
  console.group('Violation clue request body (preview only)');
  console.log(JSON.stringify(requestBody, null, 2));
  console.groupEnd();
  ElMessage.success('Request body printed to the browser console. No POST request was sent.');
}

onMounted(loadClues);
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div>
          <div class="title-main">Violation Clues</div>
          <div class="title-sub">Developer access: structured clue preview</div>
        </div>
      </div>

      <el-alert
        title="Select clues to download a JSON request body. This page previews requests without sending them."
        type="info"
        :closable="false"
        class="mb-4"
      />

      <el-form :inline="true" :model="form" class="query-card">
        <el-form-item label="Task ID">
          <el-input v-model="form.taskId" clearable placeholder="Task ID" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="Admission ID">
          <el-input v-model="form.hospitalizationId" clearable placeholder="Admission ID" @keyup.enter="search" />
        </el-form-item>
        <el-form-item label="Rule">
          <el-input
            v-model="form.ruleKeyword"
            clearable
            placeholder="Rule code or name"
            @keyup.enter="search"
          />
        </el-form-item>
        <el-form-item>
          <el-button :icon="Search" type="primary" :loading="loading" @click="search">Search</el-button>
          <el-button :icon="Refresh" @click="reset">Reset</el-button>
        </el-form-item>
      </el-form>

      <div class="batch-actions">
        <el-button :icon="Download" type="success" :disabled="selectedRows.length === 0" @click="downloadSelectedRequestBody">
          Download Selected ({{ selectedRows.length }})
        </el-button>
        <el-button @click="selectCurrentPage">Select Page</el-button>
        <el-button :disabled="selectedRows.length === 0" @click="clearSelection">Clear Selection</el-button>
      </div>

      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="rows"
        border
        stripe
        row-key="externalClueId"
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="52" />
        <el-table-column prop="externalClueId" label="externalClueId" min-width="310" show-overflow-tooltip />
        <el-table-column prop="sourceSystem" label="sourceSystem" min-width="180" />
        <el-table-column prop="clueType" label="clueType" width="120" />
        <el-table-column prop="ruleCode" label="ruleCode" min-width="150" show-overflow-tooltip />
        <el-table-column prop="ruleName" label="ruleName" min-width="160" show-overflow-tooltip />
        <el-table-column prop="evidenceVersion" label="evidenceVersion" min-width="130" />
        <el-table-column prop="orgCode" label="orgCode" min-width="120" />
        <el-table-column prop="orgName" label="orgName" min-width="140" show-overflow-tooltip />
        <el-table-column prop="evidenceType" label="evidenceType" width="120" />
        <el-table-column prop="evidenceCount" label="evidenceCount" width="130" align="center" />
        <el-table-column prop="itemId" label="itemId" min-width="300" show-overflow-tooltip />
        <el-table-column prop="hospitalizationId" label="hospitalizationId" min-width="170" />
        <el-table-column prop="dischargeDate" label="dischargeDate" min-width="180" />
        <el-table-column prop="violationItemName" label="violationItemName" min-width="180" show-overflow-tooltip />
        <el-table-column prop="violationItemCode" label="violationItemCode" min-width="180" show-overflow-tooltip />
        <el-table-column prop="cluePrompt" label="cluePrompt" min-width="260" show-overflow-tooltip />
        <el-table-column label="Actions" width="140" fixed="right">
          <template #default="{ row }">
            <el-button :icon="View" link type="primary" @click="showJson(row)">JSON</el-button>
            <el-button link type="warning" @click="printRequestBody(row)">Print Request</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :page-sizes="[10, 50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @current-change="loadClues"
          @size-change="handlePageSizeChange"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="Structured Violation Clue JSON" width="860px">
      <pre class="json-preview">{{ JSON.stringify(selectedClue, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-wrap { min-height: calc(100vh - 36px); padding: 18px; background: #f5f7fb; }
.content-card { padding: 18px; background: #fff; border-radius: 10px; box-shadow: 0 2px 10px #1018280f; }
.page-title { display: flex; gap: 10px; padding: 6px 0 14px; margin-bottom: 14px; border-bottom: 1px solid #eef2f7; }
.title-bar { width: 4px; height: 38px; border-radius: 3px; background: #409eff; }
.title-main { color: #1f2d3d; font-size: 18px; font-weight: 600; }
.title-sub { margin-top: 4px; color: #8a94a6; font-size: 13px; }
.query-card { padding: 14px 14px 0; margin-bottom: 14px; border: 1px solid #eef2f7; border-radius: 8px; }
.batch-actions { display: flex; gap: 10px; align-items: center; padding: 0 0 14px; }
.pager { display: flex; justify-content: flex-end; padding-top: 14px; }
.json-preview { max-height: 60vh; padding: 14px; overflow: auto; border-radius: 6px; background: #0f172a; color: #e2e8f0; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
</style>
