<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Refresh, Search, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

import { baseRequestClient } from '../../api/request';
import { getTaskResultListApi } from '../../api/result';

const route = useRoute();
const router = useRouter();

const taskId = ref(String(route.query.taskId || ''));
const taskName = ref(String(route.query.taskName || ''));

const isLoading = ref(false);
const tableData = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

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

onMounted(() => {
  if (taskId.value) {
    fetchTaskInfo();
    fetchTableData();
  }
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
            <el-col :span="6">
              <el-button
                type="primary"
                :icon="Search"
                @click="handleSearch"
                :loading="isLoading"
              >
                查询
              </el-button>
              <el-button :icon="Refresh" @click="handleReset">重置</el-button>
            </el-col>
          </el-row>
        </el-form>
      </div>

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
  padding-bottom: 10px;
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
