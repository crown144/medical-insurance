<script lang="ts" setup>
import type { SqlExecutionRecord, SqlRule } from '#/api/sqlAnalysis';

import { onMounted, reactive, ref } from 'vue';

import { Delete, Download, Refresh, VideoPlay, View } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  deleteSqlHistory,
  downloadSqlHistoryResult,
  executeSql,
  getSqlHistory,
  getSqlHistoryDetail,
  getSqlRules,
} from '#/api/sqlAnalysis';

import SqlResultDialog from './components/SqlResultDialog.vue';

const ruleOptions = ref<SqlRule[]>([]);
const historyList = ref<SqlExecutionRecord[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const executing = ref(false);
const loading = ref(false);
const latestRecord = ref<null | SqlExecutionRecord>(null);
const resultVisible = ref(false);
const currentResult = ref<null | SqlExecutionRecord>(null);

const form = reactive({
  sqlRuleId: undefined as number | undefined,
  startDate: '',
  endDate: '',
});

const fetchRuleOptions = async () => {
  const result = await getSqlRules({ page: 1, pageSize: 500 });
  ruleOptions.value = result?.items || [];
};

const fetchHistory = async () => {
  loading.value = true;
  try {
    const result = await getSqlHistory({
      page: currentPage.value,
      pageSize: pageSize.value,
      sqlRuleId: form.sqlRuleId,
    });
    historyList.value = result?.items || [];
    total.value = result?.total || 0;
  } catch (error) {
    console.error(error);
    ElMessage.error('获取执行历史失败');
  } finally {
    loading.value = false;
  }
};

const canDownload = (row: SqlExecutionRecord) =>
  row.executeStatus === 'success' &&
  !!row.resultJson?.columns?.length &&
  !!row.resultJson?.rows?.length;

const getDownloadTip = (row: SqlExecutionRecord) => {
  if (row.executeStatus !== 'success') {
    return '执行失败，暂无可下载数据';
  }
  if (!row.resultJson?.rows?.length) {
    return '查询结果为空，暂无可下载数据';
  }
  return '';
};

const parseFilename = (contentDisposition?: string) => {
  if (!contentDisposition) return '';
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }
  const plainMatch = contentDisposition.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] || '';
};

const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

const handleExecute = async () => {
  if (!form.sqlRuleId || !form.startDate || !form.endDate) {
    ElMessage.warning('请选择医保规则和时间范围');
    return;
  }
  executing.value = true;
  try {
    const result = await executeSql({
      sqlRuleId: form.sqlRuleId,
      startDate: form.startDate,
      endDate: form.endDate,
    });
    latestRecord.value = result;
    currentResult.value = result;
    resultVisible.value = true;
    ElMessage.success(result.executeStatus === 'success' ? '执行成功' : '执行完成');
    currentPage.value = 1;
    await fetchHistory();
  } catch (error: any) {
    console.error(error);
    const message = error?.response?.data?.message || '执行失败';
    ElMessage.error(message);
  } finally {
    executing.value = false;
  }
};

const handleView = async (row: SqlExecutionRecord) => {
  currentResult.value = await getSqlHistoryDetail(row.id);
  resultVisible.value = true;
};

const handleDownload = async (row: SqlExecutionRecord) => {
  if (!canDownload(row)) {
    ElMessage.warning(getDownloadTip(row) || '暂无可下载数据');
    return;
  }

  try {
    const response = await downloadSqlHistoryResult(row.id);
    const filename =
      parseFilename(response.headers?.['content-disposition']) ||
      `${row.ruleName}_${row.executeTime}.xlsx`;
    downloadBlob(response.data as Blob, filename);
    ElMessage.success('下载成功');
  } catch (error: any) {
    console.error(error);
    const message = error?.response?.data?.message || '下载失败';
    ElMessage.error(message);
  }
};

const handleDelete = async (row: SqlExecutionRecord) => {
  await ElMessageBox.confirm(`确定删除执行记录【${row.id}】吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  });
  await deleteSqlHistory(row.id);
  ElMessage.success('删除成功');
  if (historyList.value.length === 1 && currentPage.value > 1) {
    currentPage.value -= 1;
  }
  await fetchHistory();
};

onMounted(async () => {
  await fetchRuleOptions();
  await fetchHistory();
});
</script>

<template>
  <div class="execution-page">
    <section class="panel">
      <div class="title-row">
        <div class="title">
          <span class="bar"></span>
          <span>任务执行</span>
        </div>
      </div>

      <div class="execute-form">
        <el-select
          v-model="form.sqlRuleId"
          clearable
          filterable
          placeholder="请选择医保规则"
          style="width: 280px"
        >
          <el-option
            v-for="item in ruleOptions"
            :key="item.id"
            :label="item.ruleName"
            :value="item.id"
          />
        </el-select>
        <el-date-picker
          v-model="form.startDate"
          placeholder="开始日期"
          style="width: 180px"
          type="date"
          value-format="YYYY-MM-DD"
        />
        <el-date-picker
          v-model="form.endDate"
          placeholder="结束日期"
          style="width: 180px"
          type="date"
          value-format="YYYY-MM-DD"
        />
        <el-button :icon="VideoPlay" :loading="executing" type="primary" @click="handleExecute">
          执行SQL
        </el-button>
        <el-button :icon="Refresh" @click="fetchHistory">刷新历史</el-button>
      </div>
    </section>

    <section v-if="latestRecord" class="panel">
      <div class="summary-grid">
        <div class="summary-item">
          <span class="summary-label">执行状态</span>
          <el-tag :type="latestRecord.executeStatus === 'success' ? 'success' : 'danger'">
            {{ latestRecord.executeStatus === 'success' ? '成功' : '失败' }}
          </el-tag>
        </div>
        <div class="summary-item">
          <span class="summary-label">执行时间</span>
          <span>{{ latestRecord.executeTime }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">执行耗时</span>
          <span>{{ latestRecord.duration }} ms</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">返回记录数</span>
          <span>{{ latestRecord.rowCount }}</span>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="sub-title">历史执行记录</div>
      <el-table v-loading="loading" :data="historyList" border>
        <el-table-column label="任务ID" min-width="90" prop="id" />
        <el-table-column label="医保规则" min-width="220" prop="ruleName" />
        <el-table-column label="时间范围" min-width="220">
          <template #default="{ row }">
            {{ row.startDate }} ~ {{ row.endDate }}
          </template>
        </el-table-column>
        <el-table-column label="执行时间" min-width="180" prop="executeTime" />
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="row.executeStatus === 'success' ? 'success' : 'danger'">
              {{ row.executeStatus === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="耗时" min-width="110">
          <template #default="{ row }">{{ row.duration }} ms</template>
        </el-table-column>
        <el-table-column label="返回记录数" min-width="120" prop="rowCount" />
        <el-table-column fixed="right" label="操作" min-width="300">
          <template #default="{ row }">
            <el-button :icon="View" link type="primary" @click="handleView(row)">
              查看结果
            </el-button>
            <el-tooltip
              :content="getDownloadTip(row)"
              :disabled="canDownload(row)"
              placement="top"
            >
              <span>
                <el-button
                  :icon="Download"
                  :disabled="!canDownload(row)"
                  link
                  type="primary"
                  @click="handleDownload(row)"
                >
                  下载结果
                </el-button>
              </span>
            </el-tooltip>
            <el-button :icon="Delete" link type="danger" @click="handleDelete(row)">
              删除记录
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          background
          layout="total, sizes, prev, pager, next"
          @change="fetchHistory"
        />
      </div>
    </section>

    <SqlResultDialog v-model="resultVisible" :record="currentResult" />
  </div>
</template>

<style scoped>
.execution-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  padding: 20px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.title-row {
  margin-bottom: 16px;
}

.title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
  color: #0f172a;
}

.bar {
  width: 6px;
  height: 20px;
  border-radius: 999px;
  background: linear-gradient(180deg, #2563eb 0%, #0ea5e9 100%);
}

.sub-title {
  margin-bottom: 16px;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.execute-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8fafc;
  color: #334155;
}

.summary-label {
  font-size: 12px;
  color: #64748b;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
