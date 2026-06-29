<script setup lang="ts">
// 引入类型
import type { TaskItem } from '../../api/model/taskModel';

import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Document, Refresh, Search, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

// 引入 API
import { getDownloadUrl, getTaskListApi } from '../../api/task';
import { formatRuleTypeList } from '../../config/rule-type';

const router = useRouter();

// 搜索表单
const searchForm = reactive({
  taskId: '',
  taskName: '',
  status: '', // 可以筛选状态
  dateRange: [] as string[],
});

// 列表数据
const isLoading = ref(false);
const taskList = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

// 获取任务列表
const fetchTaskList = async () => {
  isLoading.value = true;
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      id: searchForm.taskId || undefined,
      search: searchForm.taskName || undefined,
      status: searchForm.status || undefined, // 如果只看完成的，可以写死 'completed'
    };

    const res = await getTaskListApi(params);

    taskList.value = res.results.map((item: TaskItem) => ({
      id: item.id,
      name: item.name,
      // 范围：后端暂时没返回具体的病例数，先用 hospitalization_ids 长度代替
      scope: `${item.hospitalization_ids?.length || 0} cases`,
      // 方案
      scheme: formatRuleTypeList(item.selectedSchemas).join(', ') || 'Default Scheme',
      status: item.status,
      // 违规数：如果后端任务列表没返回这个字段，需要后端补上，或者前端单独查
      // 暂时用 item.violation_count (假设后端有) 或者 '-'
      violationCount: (item as any).violation_count ?? '-',
      // 完成时间
      finishTime: item.completed_at
        ? new Date(item.completed_at).toLocaleString()
        : '-',
    }));

    total.value = res.count;
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to load the task list.');
  } finally {
    isLoading.value = false;
  }
};

const handleSearch = () => {
  currentPage.value = 1;
  fetchTaskList();
};

const handleReset = () => {
  searchForm.taskId = '';
  searchForm.taskName = '';
  searchForm.status = '';
  searchForm.dateRange = [];
  handleSearch();
};

const handlePageChange = (val: number) => {
  currentPage.value = val;
  fetchTaskList();
};

// 跳转结果详情
const handleViewResult = (row: any) => {
  router.push({
    name: 'ResultTaskItems', // 对应路由配置
    query: { taskId: String(row.id), taskName: row.name },
  });
};

// 下载报告
const handleDownload = (row: any) => {
  // 简单演示下载逻辑，实际可能需要弹窗选期数
  const url = getDownloadUrl(row.id, 1);
  window.open(url, '_blank');
};

const formatStatus = (status: string) => {
  const map: Record<string, string> = {
    completed: 'Completed',
    failed: 'Failed',
    running: 'Running',
    pending: 'Pending',
  };
  return map[status] || status;
};

onMounted(() => {
  fetchTaskList();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">Task Results Overview</div>
          <div class="title-sub">Task Results Overview</div>
        </div>
      </div>

      <div class="query-card">
        <el-form :inline="true" :model="searchForm" class="demo-form-inline">
          <el-form-item label="Task ID">
            <el-input
              v-model="searchForm.taskId"
              placeholder="Enter ID"
              style="width: 140px"
              clearable
              @keyup.enter="handleSearch"
            />
          </el-form-item>
          <el-form-item label="Task Name">
            <el-input
              v-model="searchForm.taskName"
              placeholder="Enter task name"
              style="width: 180px"
              clearable
              @keyup.enter="handleSearch"
            />
          </el-form-item>
          <el-form-item label="Status">
            <el-select
              v-model="searchForm.status"
              placeholder="All"
              style="width: 120px"
              clearable
              @change="handleSearch"
            >
              <el-option label="Completed" value="completed" />
              <el-option label="Failed" value="failed" />
              <el-option label="Running" value="running" />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              :icon="Search"
              @click="handleSearch"
              :loading="isLoading"
            >
              Search
            </el-button>
            <el-button :icon="Refresh" @click="handleReset">Reset</el-button>
          </el-form-item>
        </el-form>
      </div>

      <div class="table-card">
        <el-table
          :data="taskList"
          v-loading="isLoading"
          border
          stripe
          style="width: 100%"
        >
          <el-table-column
            prop="id"
            label="Task ID"
            width="100"
            align="center"
          />
          <el-table-column prop="name" label="Task Name" min-width="220">
            <template #default="{ row }">
              <span class="font-bold text-gray-700">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="scope"
            label="Case Scope"
            width="140"
            align="center"
          />
          <el-table-column label="Detection Schemes" width="200" align="center">
            <template #default="{ row }">
              <el-tag effect="plain" type="info" size="small">
                {{ row.scheme }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="Violations Found" width="140" align="center">
            <template #default="{ row }">
              <span v-if="row.status === 'completed'" class="violation-count">
                {{
                  row.violationCount !== '-' ? `${row.violationCount} items` : '-'
                }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>

          <el-table-column label="Status" width="120" align="center">
            <template #default="{ row }">
              <el-tag
                :type="
                  row.status === 'completed'
                    ? 'success'
                    : row.status === 'failed'
                      ? 'danger'
                      : 'warning'
                "
                effect="dark"
              >
                {{ formatStatus(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="finishTime"
            label="Completed At"
            width="180"
            align="center"
          />

          <el-table-column
            label="Actions"
            width="200"
            fixed="right"
            align="center"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                :icon="View"
                @click="handleViewResult(row)"
                :disabled="row.status !== 'completed'"
              >
                View Details
              </el-button>
              <span class="sep">|</span>
              <el-button
                type="primary"
                link
                :icon="Document"
                @click="handleDownload(row)"
                :disabled="row.status !== 'completed'"
              >
                Download
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
/* 保持统一的 CSS 风格 */
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
}
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 24px;
  box-shadow: 0 2px 10px rgba(16, 24, 40, 0.06);
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
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 18px 18px 0 18px;
  margin-bottom: 14px;
}
.table-card {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  overflow: hidden;
}
.violation-count {
  color: #f56c6c;
  font-weight: 700;
}
.sep {
  margin: 0 8px;
  color: #e5e7eb;
}
.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  padding: 10px;
}
.text-gray-700 {
  color: #374151;
}
.font-bold {
  font-weight: 700;
}
</style>
