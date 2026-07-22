<script lang="ts" setup>
import type { SqlExecutionRecord, SqlRuleResultDetail } from '#/api/sqlAnalysis';

import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { ArrowLeft, Download, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

import {
  downloadSqlHistoryResult,
  getSqlHistoryDetail,
  getSqlResultRuleDetail,
} from '#/api/sqlAnalysis';

import SqlResultDialog from './components/SqlResultDialog.vue';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const detail = ref<null | SqlRuleResultDetail>(null);
const executions = ref<SqlExecutionRecord[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const resultVisible = ref(false);
const currentResult = ref<null | SqlExecutionRecord>(null);
const showSql = ref(false);

const ruleId = computed(() => Number(route.params.id));

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

const fetchData = async () => {
  if (!ruleId.value) return;
  loading.value = true;
  try {
    const result = await getSqlResultRuleDetail(ruleId.value, {
      page: currentPage.value,
      pageSize: pageSize.value,
    });
    detail.value = result?.rule || null;
    executions.value = result?.executions?.items || [];
    total.value = result?.executions?.total || 0;
  } catch (error) {
    console.error(error);
    ElMessage.error('获取规则执行详情失败');
  } finally {
    loading.value = false;
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

onMounted(fetchData);
</script>

<template>
  <div class="result-detail">
    <section class="panel">
      <div class="title-row">
        <div class="title">
          <span class="bar"></span>
          <span>规则执行详情</span>
        </div>
        <el-button :icon="ArrowLeft" plain @click="router.push({ name: 'SqlAnalysisResults' })">
          返回执行结果
        </el-button>
      </div>

      <div v-if="detail" class="detail-grid">
        <div class="detail-item">
          <span class="detail-label">规则名称</span>
          <span class="detail-value">{{ detail.ruleName }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">规则类型</span>
          <span class="detail-value">{{ detail.ruleType }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">创建时间</span>
          <span class="detail-value">{{ detail.createdAt }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">最近执行时间</span>
          <span class="detail-value">{{ detail.recentExecuteTime || '-' }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">累计执行次数</span>
          <span class="detail-value">{{ detail.executionCount }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">累计违规数量</span>
          <span class="detail-value highlight">{{ detail.totalViolationCount }}</span>
        </div>
      </div>

      <div v-if="detail" class="sql-block">
        <div class="sql-block__header">
          <span>SQL内容</span>
          <el-button link type="primary" @click="showSql = !showSql">
            {{ showSql ? '收起' : '展开' }}
          </el-button>
        </div>
        <pre v-if="showSql" class="sql-block__code">{{ detail.sqlContent }}</pre>
      </div>
    </section>

    <section class="panel">
      <div class="sub-title">历史执行记录</div>
      <el-table v-loading="loading" :data="executions" border>
        <el-table-column label="执行时间" min-width="180" prop="executeTime" />
        <el-table-column label="查询范围" min-width="220">
          <template #default="{ row }">
            {{ row.startDate }} ~ {{ row.endDate }}
          </template>
        </el-table-column>
        <el-table-column label="命中违规数量" min-width="130" prop="rowCount" />
        <el-table-column label="执行耗时" min-width="120">
          <template #default="{ row }">{{ (row.duration / 1000).toFixed(2) }}s</template>
        </el-table-column>
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="row.executeStatus === 'success' ? 'success' : 'danger'">
              {{ row.executeStatus === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" min-width="220">
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
          @change="fetchData"
        />
      </div>
    </section>

    <SqlResultDialog v-model="resultVisible" :record="currentResult" />
  </div>
</template>

<style scoped>
.result-detail {
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
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

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8fafc;
}

.detail-label {
  font-size: 12px;
  color: #64748b;
}

.detail-value {
  font-size: 15px;
  color: #0f172a;
  word-break: break-word;
}

.detail-value.highlight {
  color: #b91c1c;
  font-weight: 700;
}

.sql-block {
  margin-top: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.sql-block__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  color: #334155;
}

.sql-block__code {
  margin: 0;
  max-height: 260px;
  overflow: auto;
  padding: 16px;
  background: #020617;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.sub-title {
  margin-bottom: 16px;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}

@media (max-width: 960px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
