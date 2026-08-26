<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  DocumentChecked,
  Download,
  Refresh,
  RefreshRight,
  Search,
  View,
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useUserStore } from '@vben/stores';

import { baseRequestClient } from '../../api/request';
import {
  downloadTaskResultCasesApi,
  getTaskResultListApi,
} from '../../api/result';
import { executeTaskApi } from '../../api/task';

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();
const canDownloadResultCases = computed(() =>
  userStore.userInfo?.roles?.includes('developer'),
);

const taskId = ref(String(route.query.taskId || ''));
const taskName = ref(String(route.query.taskName || ''));

const isLoading = ref(false);
const isDownloadingCases = ref(false);
const isRecalculating = ref(false);
const isAutoRefreshing = ref(false);
const taskStatus = ref('');
const taskReflection = ref('');
const interactionNote = ref('');
const lastSyncedAt = ref('');
const expandedPanels = ref(['reflection']);
const tableData = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
let refreshTimer: ReturnType<typeof window.setInterval> | null = null;

const filterForm = reactive({
  hosId: '',
  drugKey: '',
  dept: '',
  date: '',
});

const fetchTaskInfo = async () => {
  if (!taskId.value) return;
  try {
    const res = await baseRequestClient.get<any>(`/tasks/${taskId.value}/`);
    taskName.value = res.data.name;
    taskStatus.value = res.data.status || '';
    taskReflection.value = res.data.self_reflection || '';
    lastSyncedAt.value = new Date().toLocaleString();
  } catch (error) {
    console.error(error);
  }
};

// --- 核心修改在这里 ---
const fetchTableData = async () => {
  if (!taskId.value) return;
  isLoading.value = true;
  try {
    const params: any = {
      // 🔴 关键修改：后端要 'task_id'，前端就传 'task_id'
      task_id: taskId.value,

      page: currentPage.value,
      page_size: pageSize.value,
      hospitalization_id__icontains: filterForm.hosId || undefined,
    };

    const res = await getTaskResultListApi(params);
    const data = res.data;

    total.value = data.count || 0;

    tableData.value = (data.results || []).map((item: any) => {
      // 解析 JSON 字符串
      let detailObj: any = {};
      let parsedItemName = '';
      try {
        if (item.violation_item) {
          const validJson = item.violation_item
            .replaceAll("'", '"')
            .replaceAll('None', 'null');
          detailObj = JSON.parse(validJson);
          // 尝试从常见的字段中提取名称
          parsedItemName =
            detailObj.name ||
            detailObj.drug_name ||
            detailObj.item_name ||
            detailObj.xmname ||
            detailObj.xmmc ||
            detailObj['收费项目名称'] ||
            detailObj['收费项目代码'] ||
            '';
        }
      } catch {}

      // 确定最终显示的名称
      let finalItemName = parsedItemName;
      if (!finalItemName) {
        // 如果不是 JSON，直接显示文本
        if (
          item.violation_item &&
          !item.violation_item.trim().startsWith('{')
        ) {
          finalItemName = item.violation_item;
        } else {
          // 兜底：使用规则中的名称
          finalItemName = item.rule?.drug_name || '未知项目';
        }
      }

      return {
        id: item.id,
        hosNo: item.hospitalization_id,
        // 违规项目
        itemName: finalItemName,
        // 违规类型
        violationType: item.rule?.type || item.rule?.description || '通用规则',
        // 违规原因
        reason: item.reason,
        // 时间
        time: item.created_at
          ? new Date(item.created_at).toLocaleString()
          : '-',
        raw: item,
      };
    });
  } catch (error) {
    console.error('加载失败', error);
    ElMessage.error('获取违规数据失败');
  } finally {
    isLoading.value = false;
  }
};

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
  isAutoRefreshing.value = false;
};

const syncTaskState = async () => {
  await Promise.all([fetchTaskInfo(), fetchTableData()]);
  if (taskStatus.value !== 'running' && taskStatus.value !== 'pending') {
    stopAutoRefresh();
  }
};

const startAutoRefresh = () => {
  if (refreshTimer) return;
  isAutoRefreshing.value = true;
  refreshTimer = window.setInterval(syncTaskState, 3000);
};

const handleSearch = () => {
  currentPage.value = 1;
  fetchTableData();
};

const handleReset = () => {
  filterForm.hosId = '';
  filterForm.drugKey = '';
  filterForm.dept = '';
  filterForm.date = '';
  handleSearch();
};

const handlePageChange = (val: number) => {
  currentPage.value = val;
  fetchTableData();
};

const goToAuditDetail = (row: any) => {
  router.push({
    name: 'ResultAuditViewDetail',
    query: {
      taskId: taskId.value,
      hospitalizationId: row.hosNo,
      resultId: row.id,
    },
  });
};

const downloadResultCases = async () => {
  if (!taskId.value) return;
  isDownloadingCases.value = true;
  try {
    const blob = await downloadTaskResultCasesApi(taskId.value);
    const extension = blob.type.includes('zip') ? 'zip' : 'json';
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `任务病历_任务${taskId.value}.${extension}`;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error: any) {
    const data = error?.response?.data;
    if (data instanceof Blob) {
      try {
        const payload = JSON.parse(await data.text());
        ElMessage.error(payload.error || '任务病历下载失败');
        return;
      } catch {}
    }
    ElMessage.error('任务病历下载失败');
  } finally {
    isDownloadingCases.value = false;
  }
};

const requestModelRecalculation = async () => {
  if (!taskId.value || isRecalculating.value) return;
  try {
    await ElMessageBox.confirm(
      '系统将按当前任务配置重新读取病历并执行规则。当前违规明细会被新计算结果替换。',
      '确认重新计算当前指标',
      {
        confirmButtonText: '重新计算',
        cancelButtonText: '取消',
        type: 'warning',
      },
    );
    isRecalculating.value = true;
    await executeTaskApi(Number(taskId.value));
    ElMessage.success('已重新发起计算，正在跳转至任务执行页。');
    await router.push({
      name: 'ExecuteRun',
      query: { taskId: taskId.value },
    });
  } catch (error) {
    if (error !== 'cancel') console.error('重新计算任务失败', error);
  } finally {
    isRecalculating.value = false;
  }
};

onMounted(() => {
  if (taskId.value) {
    fetchTaskInfo();
    fetchTableData();
    startAutoRefresh();
  }
});

onUnmounted(() => {
  stopAutoRefresh();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">违规明细列表</div>
          <div class="title-sub">
            任务 #{{ taskId }} · {{ taskName }}
            <span class="ml-2 text-gray-400"
              >(共发现 {{ total }} 条违规线索)</span
            >
          </div>
        </div>
      </div>

      <div class="query-card">
        <el-form :inline="true" :model="filterForm" class="filter-form">
          <el-row :gutter="16" style="width: 100%">
            <el-col :span="6">
              <el-form-item label="住院号" style="width: 100%; margin-right: 0">
                <el-input
                  v-model="filterForm.hosId"
                  placeholder="输入住院号"
                  style="width: 100%"
                  clearable
                  @keyup.enter="handleSearch"
                />
              </el-form-item>
            </el-col>
            <el-col :span="18">
              <div class="action-group">
                <el-button
                  type="primary"
                  :icon="Search"
                  @click="handleSearch"
                  :loading="isLoading"
                >
                  查询
                </el-button>
                <el-button :icon="Refresh" @click="handleReset">重置</el-button>
                <el-button
                  v-if="canDownloadResultCases"
                  class="secondary-action"
                  :icon="Download"
                  :loading="isDownloadingCases"
                  @click="downloadResultCases"
                >
                  下载病历
                </el-button>
                <el-tooltip content="按当前任务配置重新读取病历并执行规则" placement="top">
                  <el-button
                    class="recalculate-action"
                    :icon="RefreshRight"
                    :loading="isRecalculating"
                    :disabled="!taskId"
                    @click="requestModelRecalculation"
                  >
                    重新计算
                  </el-button>
                </el-tooltip>
              </div>
            </el-col>
          </el-row>
        </el-form>
      </div>

      <div class="interaction-card">
        <div class="interaction-header">
          <div>
            <div class="interaction-title">模型互动区</div>
            <div class="interaction-sub">
              支持当前任务重新计算与结果自动刷新
              <span v-if="lastSyncedAt">，最近同步：{{ lastSyncedAt }}</span>
            </div>
          </div>
          <el-tag :type="taskStatus === 'completed' ? 'success' : 'warning'" effect="plain">
            {{ taskStatus || '未同步' }}
          </el-tag>
        </div>
        <el-input
          v-model="interactionNote"
          type="textarea"
          :rows="2"
          placeholder="可输入本次重算说明"
        />
        <div class="interaction-actions">
          <el-button
            class="secondary-action"
            :loading="isLoading"
            @click="syncTaskState"
          >
            刷新结果
          </el-button>
          <el-button
            class="recalculate-action"
            :loading="isRecalculating"
            :disabled="!taskId"
            @click="requestModelRecalculation"
          >
            重新计算当前指标
          </el-button>
          <span v-if="isAutoRefreshing" class="interaction-hint">自动刷新中</span>
        </div>
      </div>

      <el-collapse v-model="expandedPanels" class="reflection-panel">
        <el-collapse-item name="reflection">
          <template #title>
            <div class="reflection-title">
              <el-icon><DocumentChecked /></el-icon>
              <span>模型计算自检</span>
              <span class="reflection-caption">仅辅助核验，不改变违规判定</span>
            </div>
          </template>
          <div v-if="taskReflection" class="reflection-content">
            {{ taskReflection }}
          </div>
          <div v-else class="reflection-empty">
            {{ taskStatus === 'completed' ? '该任务尚未生成模型自检结果。请点击“重新计算”后查看。' : '任务完成后将自动生成模型自检结果。' }}
          </div>
        </el-collapse-item>
      </el-collapse>

      <div class="table-card">
        <el-table
          :data="tableData"
          v-loading="isLoading"
          border
          stripe
          style="width: 100%"
        >
          <el-table-column type="index" width="50" align="center" label="#" />
          <el-table-column prop="hosNo" label="住院号" width="180" />
          <el-table-column
            prop="itemName"
            label="违规项目/药品"
            width="220"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span class="font-bold text-gray-700">{{ row.itemName }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="violationType" label="违规类型" width="160">
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="
                  row.violationType.includes('重复') ? 'warning' : 'danger'
                "
                effect="plain"
              >
                {{ row.violationType }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="reason"
            label="违规原因说明"
            min-width="300"
            show-overflow-tooltip
          />
          <el-table-column
            label="操作"
            width="100"
            align="center"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                :icon="View"
                @click="goToAuditDetail(row)"
              >
                详情
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pagination-bar">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            background
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handlePageChange"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
}
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 24px;
}
.page-title {
  display: flex;
  gap: 10px;
  padding-bottom: 14px;
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
}
.title-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}
.query-card {
  padding-bottom: 14px;
}
.interaction-card {
  background: #f7f9ff;
  border: 1px solid #e4e9ff;
  border-radius: 12px;
  margin-bottom: 12px;
  padding: 16px;
}
.interaction-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
}
.interaction-title {
  color: #1f2d3d;
  font-size: 15px;
  font-weight: 600;
}
.interaction-sub {
  color: #6b7280;
  font-size: 12px;
  margin-top: 4px;
}
.interaction-actions {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 12px;
}
.interaction-hint {
  color: #409eff;
  font-size: 12px;
}
.action-group {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 32px;
}
.action-group :deep(.el-button + .el-button) {
  margin-left: 0;
}
.secondary-action {
  border-color: #b7ebd0;
  color: #1c9c5a;
}
.secondary-action:hover {
  background: #effbf4;
  border-color: #6bd49b;
  color: #158448;
}
.recalculate-action {
  background: #fffaf0;
  border-color: #f3d39a;
  color: #b97810;
}
.recalculate-action:hover {
  background: #fff3dc;
  border-color: #e8b75f;
  color: #935b05;
}
.reflection-panel {
  border-bottom: 0;
  border-top: 0;
  margin-bottom: 12px;
}
.reflection-panel :deep(.el-collapse-item__header) {
  background: #f7faff;
  border: 1px solid #e1ebfa;
  border-radius: 8px;
  color: #29476f;
  font-size: 14px;
  height: 42px;
  padding: 0 14px;
}
.reflection-panel :deep(.el-collapse-item__wrap) {
  border-bottom: 0;
}
.reflection-panel :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}
.reflection-title {
  align-items: center;
  display: flex;
  font-weight: 600;
  gap: 8px;
}
.reflection-caption {
  color: #8492a6;
  font-size: 12px;
  font-weight: 400;
}
.reflection-content,
.reflection-empty {
  border: 1px solid #e7edf7;
  border-radius: 0 0 8px 8px;
  border-top: 0;
  color: #43556e;
  line-height: 1.8;
  padding: 12px 16px;
  white-space: pre-wrap;
}
.reflection-empty {
  color: #8a94a6;
}
.table-card {
  border-top: 1px solid #eef2f7;
  padding-top: 10px;
}
.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.text-gray-700 {
  color: #374151;
}
.text-gray-400 {
  color: #9ca3af;
}
.font-bold {
  font-weight: 700;
}
:deep(.el-form-item) {
  margin-bottom: 0;
}
</style>
