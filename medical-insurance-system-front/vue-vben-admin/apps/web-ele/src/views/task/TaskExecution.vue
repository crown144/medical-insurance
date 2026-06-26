<script setup lang="ts">
// 2. 导入类型 (Type) - 必须加 type 关键字！
import type { TaskItem } from '../../api/model/taskModel';

import { onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Delete, Download, Search, View } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  DEMO_MODE,
  DEMO_MODE_NOTICE_EN,
  DEMO_MODE_NOTICE_ZH,
} from '../../config/demo';

// 👇👇👇 重点修改这里 👇👇👇
// 1. 导入枚举 (Value)
import { TaskStatus } from '../../api/model/taskModel';
// 引入 API
import {
  deleteTaskApi,
  executeTaskApi,
  getDownloadUrl,
  getTaskListApi,
} from '../../api/task';
// Extended interface for frontend display
interface TaskItemDisplay extends TaskItem {
  taskName: string;
  progress: number;
  selectedSchemas: string[];
}

const router = useRouter();
const route = useRoute();

// --- State Variables ---
const searchForm = ref({
  id: '',
  search: '',
  status: '' as '' | TaskStatus,
});

const allTasks = ref<TaskItemDisplay[]>([]);
const totalTasks = ref(0);
const pageSize = ref(10);
const currentPage = ref(1);
const isLoading = ref(false);

const taskDetailVisible = ref(false);
const currentTaskDetail = ref<Partial<TaskItemDisplay>>({});
let pollingInterval: null | number = null;

const taskStatusOptions = [
  { value: 'pending', label: '待处理' },
  { value: 'running', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
];

// --- Helpers ---

function formatStatus(status?: string) {
  if (!status) return '未知';
  const map: Record<string, string> = {
    pending: '等待检测',
    running: '正在检测',
    completed: '检测完成',
    failed: '检测失败',
  };
  return map[status] || status;
}

function getStatusClass(status: string) {
  const map: Record<string, string> = {
    completed: 'status-completed',
    running: 'status-running',
    pending: 'status-pending',
    failed: 'status-failed',
  };
  return map[status] || '';
}

function getActionButtonText(status: string) {
  return status === 'completed' || status === 'failed' ? '结果' : '执行';
}

function calcProgress(status: string) {
  const map: Record<string, number> = {
    completed: 100,
    running: 60,
    failed: 25,
    pending: 0,
  };
  return map[status] || 0;
}

// --- API Interactions ---

// Load Tasks
const loadTasks = async () => {
  isLoading.value = true;
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      id: searchForm.value.id || undefined,
      search: searchForm.value.search || undefined,
      status: searchForm.value.status || undefined,
    };

    const res = await getTaskListApi(params);

    // Map backend data to frontend display format
    allTasks.value = res.results.map((task) => ({
      ...task,
      taskName: task.name,
      selectedSchemas: task.selectedSchemas || [],
      progress: calcProgress(task.status),
    }));
    totalTasks.value = res.count;

    // Polling logic
    if (allTasks.value.some((task) => task.status === TaskStatus.RUNNING)) {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    console.error('Failed to load tasks:', error);
  } finally {
    isLoading.value = false;
  }
};

const startPolling = () => {
  if (pollingInterval) return;
  pollingInterval = window.setInterval(loadTasks, 5000);
};

const stopPolling = () => {
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
};

// --- Actions ---

const handleSearch = () => {
  currentPage.value = 1;
  loadTasks();
};

// src/views/task/TaskExecution.vue

const executeTask = async (task: TaskItemDisplay) => {
  if (task.status === 'running') return ElMessage.warning('任务正在运行中');

  // 🔴 修复这里：当状态是 完成/失败 时，点击按钮跳转到新的结果页
  if (task.status === 'completed' || task.status === 'failed') {
    router.push({
      // path: '/task/result-detail', // ❌ 旧地址 (导致 404)
      name: 'ResultTaskItems', // ✅ 新路由名称 (对应 SpecificTaskResult.vue)
      query: {
        taskId: String(task.id),
        taskName: task.name, // 顺便把名字传过去
      },
    });
    return;
  }

  // 下面是执行逻辑，保持不变
  try {
    await executeTaskApi(task.id);
    ElMessage.success(`任务 "${task.name}" 已开始执行`);
    loadTasks();
  } catch {
    // Error handled by global interceptor usually
  }
};
const deleteTask = async (task: TaskItemDisplay) => {
  try {
    await ElMessageBox.confirm(`确定要删除任务 “${task.name}” 吗？`, '警告', {
      type: 'warning',
    });
    await deleteTaskApi(task.id);
    ElMessage.success('任务删除成功');
    loadTasks();
  } catch (error) {
    if (error !== 'cancel') console.error(error);
  }
};

const viewTaskDetail = (task: TaskItemDisplay) => {
  // 不再弹窗，改为路由跳转
  router.push({
    name: 'ResultTaskItems', // 🔴 必须对应 result.ts 里配置的路由名称
    query: {
      taskId: String(task.id),
      taskName: task.name, // 顺便把任务名传过去显示在标题上
    },
  });
};

const downloadReport = (task: TaskItemDisplay) => {
  ElMessageBox.prompt('请输入报告期数（例如：3）', '生成报告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /^\d+$/,
    inputErrorMessage: '期数必须为数字',
  })
    .then(({ value }) => {
      const url = getDownloadUrl(task.id, value);
      window.open(url, '_blank');
      ElMessage.success('报告生成请求已发送，请等待下载...');
    })
    .catch(() => {
      ElMessage.info('已取消生成报告');
    });
};

const goToAddTask = () => {
  router.push('/task/add-new-task');
};

const handleVisibilityChange = () => {
  if (document.visibilityState === 'visible') {
    loadTasks();
  }
};

// --- Lifecycle & Watchers ---

watch(currentPage, loadTasks);

watch(
  () => route.query.refresh,
  () => {
    loadTasks();
  },
);

onMounted(() => {
  loadTasks();
  document.addEventListener('visibilitychange', handleVisibilityChange);
});

onUnmounted(() => {
  document.removeEventListener('visibilitychange', handleVisibilityChange);
  stopPolling();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">任务计算</div>
          <div class="title-sub">医保病例检测任务管理与执行</div>
        </div>
      </div>

      <el-alert
        v-if="DEMO_MODE"
        type="info"
        show-icon
        :closable="false"
        class="demo-alert"
      >
        <template #title>
          <div>{{ DEMO_MODE_NOTICE_EN }}</div>
          <div>{{ DEMO_MODE_NOTICE_ZH }}</div>
        </template>
      </el-alert>

      <div class="query-card">
        <div class="query-row">
          <div class="query-left">
            <div class="query-item">
              <div class="query-label">任务ID</div>
              <el-input
                v-model="searchForm.id"
                placeholder="输入任务ID"
                clearable
              />
            </div>

            <div class="query-item">
              <div class="query-label">任务名称</div>
              <el-input
                v-model="searchForm.search"
                placeholder="输入任务名称"
                clearable
              />
            </div>

            <div class="query-item">
              <div class="query-label">任务状态</div>
              <el-select
                v-model="searchForm.status"
                placeholder="请选择状态"
                clearable
                style="width: 180px"
              >
                <el-option
                  v-for="option in taskStatusOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </div>

            <div class="query-actions">
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="resetSearch">重置</el-button>
            </div>
          </div>

          <div class="query-right">
            <el-button type="success" class="create-btn" @click="goToAddTask">
              + 创建计算任务
            </el-button>
          </div>
        </div>
      </div>

      <div class="list-title">任务列表</div>

      <div class="table-card">
        <el-table
          :data="allTasks"
          v-loading="isLoading"
          border
          style="width: 100%"
          class="task-table"
        >
          <el-table-column
            prop="id"
            label="任务ID"
            width="100"
            align="center"
          />
          <el-table-column prop="name" label="任务名称" min-width="220" />

          <el-table-column label="审查范围" width="140" align="center">
            <template #default="{ row }">
              共 {{ row.hospitalization_ids?.length || 0 }} 例
            </template>
          </el-table-column>

          <el-table-column label="检测方案" min-width="220">
            <template #default="{ row }">
              <el-tag
                v-for="s in row.selectedSchemas"
                :key="s"
                class="scheme-tag"
              >
                {{ s }}
              </el-tag>
              <span v-if="!row.selectedSchemas?.length" class="muted">无</span>
            </template>
          </el-table-column>

          <el-table-column
            prop="status"
            label="任务状态"
            width="140"
            align="center"
          >
            <template #default="{ row }">
              <span class="status-pill" :class="getStatusClass(row.status)">
                <span v-if="row.status === 'running'" class="dot"></span>
                {{ formatStatus(row.status) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="进度" width="180" align="center">
            <template #default="{ row }">
              <el-progress
                :percentage="calcProgress(row.status)"
                :status="
                  row.status === 'completed'
                    ? 'success'
                    : row.status === 'failed'
                      ? 'exception'
                      : undefined
                "
                :indeterminate="row.status === 'running'"
                :stroke-width="10"
              />
            </template>
          </el-table-column>

          <el-table-column label="操作" width="260" align="center">
            <template #default="{ row }">
              <div class="op-cell">
                <div class="op-line">
                  <el-button
                    link
                    type="primary"
                    :icon="Search"
                    class="op-btn"
                    @click="executeTask(row)"
                    :disabled="row.status === 'running'"
                  >
                    {{ getActionButtonText(row.status) }}
                  </el-button>

                  <span class="op-sep">|</span>

                  <el-button
                    link
                    type="primary"
                    :icon="View"
                    class="op-btn"
                    @click="viewTaskDetail(row)"
                  >
                    详情
                  </el-button>

                  <template
                    v-if="row.status === 'completed' || row.status === 'failed'"
                  >
                    <span class="op-sep">|</span>
                    <el-button
                      link
                      type="primary"
                      :icon="Download"
                      class="op-btn"
                      @click="downloadReport(row)"
                    >
                      下载报告
                    </el-button>
                  </template>
                </div>

                <div class="op-line op-line--second">
                  <el-button
                    link
                    type="danger"
                    :icon="Delete"
                    class="op-btn op-btn--danger"
                    @click="deleteTask(row)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <el-empty description="暂无数据" />
          </template>
        </el-table>

        <div class="pager">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="totalTasks"
            layout="total, prev, pager, next, jumper"
            background
          />
        </div>
      </div>
    </div>

    <el-dialog
      v-model="taskDetailVisible"
      title="任务详情"
      width="700px"
      destroy-on-close
    >
      <div v-if="currentTaskDetail.id" class="task-detail-container">
        <div class="detail-header">
          <div class="header-icon">
            <el-icon
              :size="40"
              :color="
                currentTaskDetail.status === 'completed' ? '#67c23a' : '#409eff'
              "
            >
              <component
                :is="
                  currentTaskDetail.status === 'completed'
                    ? 'CircleCheckFilled'
                    : 'InfoFilled'
                "
              />
            </el-icon>
          </div>
          <div class="header-info">
            <div class="header-title">{{ currentTaskDetail.name }}</div>
            <div class="header-id">任务ID: {{ currentTaskDetail.id }}</div>
          </div>
          <div class="header-status">
            <el-tag
              :type="getStatusClass(currentTaskDetail.status as string)"
              effect="dark"
              size="large"
            >
              {{ formatStatus(currentTaskDetail.status) }}
            </el-tag>
          </div>
        </div>

        <el-divider content-position="left">基础信息</el-divider>

        <el-descriptions :column="2" border>
          <el-descriptions-item label="检测方案">
            <el-tag
              v-for="s in currentTaskDetail.selectedSchemas"
              :key="s"
              class="mr-2"
              size="small"
            >
              {{ s }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="任务摘要">
            {{ currentTaskDetail.summary || '无' }}
          </el-descriptions-item>
          <el-descriptions-item label="住院号列表" :span="2">
            <div class="id-list">
              <el-tag
                v-for="id in currentTaskDetail.hospitalization_ids"
                :key="id"
                type="info"
                size="small"
                class="id-tag"
              >
                {{ id }}
              </el-tag>
            </div>
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">执行时间</el-divider>

        <div class="time-timeline">
          <el-steps
            :active="currentTaskDetail.status === 'completed' ? 3 : 2"
            align-center
            finish-status="success"
          >
            <el-step
              title="创建"
              :description="
                currentTaskDetail.created_at
                  ? new Date(currentTaskDetail.created_at).toLocaleString()
                  : ''
              "
            />
            <el-step
              title="开始"
              :description="
                currentTaskDetail.started_at
                  ? new Date(currentTaskDetail.started_at).toLocaleString()
                  : '等待中'
              "
            />
            <el-step
              title="结束"
              :description="
                currentTaskDetail.completed_at
                  ? new Date(currentTaskDetail.completed_at).toLocaleString()
                  : '计算中'
              "
            />
          </el-steps>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 外层：浅灰背景 + 统一留白 */
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
  box-sizing: border-box;
}

/* 内层：白色卡片 */
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 18px 16px;
  box-shadow: 0 2px 10px rgba(16, 24, 40, 0.06);
}

/* 标题：左侧蓝色竖线 */
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

/* 查询区 */
.query-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px 14px 12px;
  margin-bottom: 14px;
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
.query-right {
  display: flex;
  align-items: flex-end;
}
.create-btn {
  padding: 10px 14px;
  border-radius: 6px;
  font-weight: 600;
}

/* 列表标题 */
.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #344054;
  margin: 10px 0 10px;
}

/* 表格卡片 */
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
  height: 56px;
}

/* Tag & Status styles */
.scheme-tag {
  margin-right: 6px;
  margin-bottom: 4px;
  border-radius: 14px;
  padding: 0 10px;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid transparent;
}
.status-completed {
  background: #ecfdf3;
  border-color: #abefc6;
  color: #067647;
}
.status-running {
  background: #fff7ed;
  border-color: #fed7aa;
  color: #9a3412;
}
.status-pending {
  background: #f2f4f7;
  border-color: #e4e7ec;
  color: #667085;
}
.status-failed {
  background: #fef3f2;
  border-color: #fecdca;
  color: #b42318;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1.2s infinite ease-in-out;
}
@keyframes pulse {
  0% {
    opacity: 0.35;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.1);
  }
  100% {
    opacity: 0.35;
    transform: scale(0.9);
  }
}

/* Operation buttons */
.op-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  line-height: 1;
}
.op-line {
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.op-line--second {
  margin-top: 2px;
}
.op-sep {
  margin: 0 10px;
  color: #d0d5dd;
  user-select: none;
}
.op-btn {
  padding: 0 !important;
  font-size: 13px;
  font-weight: 500;
}
.op-btn :deep(.el-icon) {
  font-size: 14px;
  margin-right: 4px;
}
.op-btn--danger {
  font-weight: 600;
}
.muted {
  color: #98a2b3;
}

/* Pagination */
.pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 12px;
  background: #fff;
  border-top: 1px solid #eef2f7;
}

/* Modal Styles */
.task-detail-container {
  padding: 0 10px;
}
.detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  padding: 16px;
  background-color: #f8f9fa;
  border-radius: 8px;
}
.header-icon {
  margin-right: 16px;
}
.header-info {
  flex: 1;
}
.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}
.header-id {
  font-size: 13px;
  color: #909399;
}
.id-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.id-tag {
  font-family: monospace;
}
.time-timeline {
  margin-top: 24px;
  padding: 0 20px;
}
.mr-2 {
  margin-right: 8px;
}
</style>
