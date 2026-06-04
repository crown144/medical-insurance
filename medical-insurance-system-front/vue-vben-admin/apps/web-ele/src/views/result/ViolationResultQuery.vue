<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Filter, Refresh, Search, View } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

// 引入 API
import { getTaskResultListApi } from '../../api/result';

const router = useRouter();

// 搜索表单
const searchForm = reactive({
  keyword: '', // 住院号
  dept: '', // 科室（目前后端暂不支持，先保留UI）
  ruleType: '', // 规则类型（目前后端支持 drug_name，type 暂时不支持过滤，先保留UI）
  ruleName: '', // 规则/药品名称
  taskId: '', // 任务号
  dateRange: [] as string[], // 出院时间范围
});

const isLoading = ref(false);
const tableData = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

// 获取全量违规数据
const fetchTableData = async () => {
  isLoading.value = true;
  try {
    const params: any = {
      page: currentPage.value,
      page_size: pageSize.value,
      // 灵活构造查询参数
      task: searchForm.taskId || undefined,
      hospitalization_id__icontains: searchForm.keyword || undefined,
      rule__drug_name__icontains: searchForm.ruleName || undefined,
      // 日期过滤：假设后端支持 year/month，或者 start/end
      // discharge_date__year: searchForm.dateRange?.[0]?.split('-')[0],
    };

    const res = await getTaskResultListApi(params);
    const data = res.data;
    console.log('API Response Results (First Item):', data.results?.[0]); // 🟢 Debug Log

    total.value = data.count || 0;

    tableData.value = (data.results || []).map((item: any) => {
      // 1. 解析任务ID (增强兼容性)
      const rawTask =
        item.task ||
        item.task_id ||
        item.taskId ||
        item.audit_task ||
        item.audit_task_id;
      // 🟢 修复：无论 rawTask 是对象还是数字，都统一转为字符串 ID
      const taskId =
        typeof rawTask === 'object' && rawTask !== null
          ? String(rawTask.id)
          : String(rawTask || '');

      // 2. 违规项目：优先使用规则定义的 drug_name
      // 用户明确要求：违规项目为...将medical_insurance.rules_rule表中对应drug_name字段作为违规项目
      const ruleDrugName = item.rule?.drugName || item.rule?.drug_name;

      let finalRuleName = ruleDrugName;

      // 如果规则中没有 drug_name，则尝试从 violation_item 解析 (兼容旧逻辑)
      if (!finalRuleName) {
        let parsedItemName = '';
        try {
          if (item.violation_item) {
            const validJson = item.violation_item
              .replaceAll("'", '"')
              .replaceAll('None', 'null');
            if (validJson.trim().startsWith('{')) {
              const detailObj = JSON.parse(validJson);
              parsedItemName =
                detailObj.name ||
                detailObj.drug_name ||
                detailObj.item_name ||
                detailObj.xmname ||
                detailObj.xmmc ||
                detailObj['收费项目名称'] ||
                detailObj['收费项目代码'] ||
                '';
            } else {
              parsedItemName = item.violation_item;
            }
          }
        } catch {
           if (item.violation_item && !item.violation_item.trim().startsWith('{')) {
             parsedItemName = item.violation_item;
           }
        }
        finalRuleName = parsedItemName || '未知项目';
      }

      return {
        id: item.id,
        // 🟢 修复：确保 taskId 不为 "undefined" 或 "null" 字符串
        taskId: taskId && taskId !== 'undefined' && taskId !== 'null' ? taskId : '#', // 关联任务ID
        hosNo: item.hospitalization_id,
        patientName: '未知', // 数据源暂无
        dept: '-', // 数据源暂无
        doctor: '-', // 数据源暂无
        // 违规信息
        ruleName: finalRuleName,
        ruleType: item.rule?.type || '通用规则',
        reason: item.reason,
        // 时间信息
        visitDate: '-', // 就诊时间暂无
        dischargeTime: item.discharge_date
          ? new Date(item.discharge_date).toLocaleDateString()
          : '-', // 出院时间
        createTime: item.created_at
          ? new Date(item.created_at).toLocaleString()
          : '-',
      };
    });
  } catch (error) {
    console.error(error);
    ElMessage.error('查询失败');
  } finally {
    isLoading.value = false;
  }
};

const handleSearch = () => {
  currentPage.value = 1;
  fetchTableData();
};

const handleReset = () => {
  searchForm.keyword = '';
  searchForm.dept = '';
  searchForm.ruleType = '';
  searchForm.ruleName = '';
  searchForm.taskId = '';
  searchForm.dateRange = [];
  handleSearch();
};

const handlePageChange = (val: number) => {
  currentPage.value = val;
  fetchTableData();
};

// 跳转详情（复用 AuditDetail）
const goToDetail = (row: any) => {
  router.push({
    name: 'ResultAuditViewDetail',
    query: {
      taskId: String(row.taskId), // 这里需要任务ID
      hospitalizationId: row.hosNo,
      resultId: row.id,
    },
  });
};

// 跳转任务列表
const goToTask = (taskId: string) => {
  if (!taskId || taskId === '#') return;
  router.push({
    name: 'ResultTaskItems', // 修正路由名称
    query: { taskId },
  });
};

onMounted(() => {
  fetchTableData();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">全量违规查询</div>
          <div class="title-sub">Full Violation Search & Analysis</div>
        </div>
      </div>

      <div class="query-card">
        <el-form :model="searchForm" label-position="top" class="search-form">
          <el-row :gutter="20">
            <el-col :span="6">
              <el-form-item label="综合搜索 (住院号)">
                <el-input
                  v-model="searchForm.keyword"
                  placeholder="输入住院号"
                  clearable
                  prefix-icon="Search"
                  @keyup.enter="handleSearch"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="任务号 (Task ID)">
                <el-input
                  v-model="searchForm.taskId"
                  placeholder="例如：10096"
                  clearable
                  @keyup.enter="handleSearch"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6">
              <el-form-item label="具体规则/药品名称">
                <el-input
                  v-model="searchForm.ruleName"
                  placeholder="例如：葡萄糖测定"
                  clearable
                  @keyup.enter="handleSearch"
                />
              </el-form-item>
            </el-col>
            <el-col :span="6" class="btn-col">
              <div class="search-btns">
                <el-button
                  type="primary"
                  :icon="Search"
                  @click="handleSearch"
                  :loading="isLoading"
                >
                  查询结果
                </el-button>
                <el-button :icon="Refresh" @click="handleReset">重置</el-button>
              </div>
            </el-col>
          </el-row>
        </el-form>
      </div>

      <div class="table-container">
        <div class="table-header">
          <div class="left-tip">
            <el-icon><Filter /></el-icon>
            共检索到
            <span class="highlight-num">{{ total }}</span>
            条疑似违规记录
          </div>
        </div>

        <el-table
          :data="tableData"
          v-loading="isLoading"
          border
          stripe
          style="width: 100%"
          class="custom-table"
        >
          <el-table-column prop="hosNo" label="住院号" width="160" fixed />

          <el-table-column label="来源任务" width="120" align="center">
            <template #default="{ row }">
              <el-link
                v-if="row.taskId && row.taskId !== '#'"
                type="primary"
                :underline="false"
                class="task-link"
                @click="goToTask(row.taskId)"
              >
                #{{ row.taskId }}
              </el-link>
              <span v-else class="text-gray-400">-</span>
            </template>
          </el-table-column>

          <el-table-column
            label="违规项目"
            min-width="200"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span class="font-bold text-gray-700">{{ row.ruleName }}</span>
            </template>
          </el-table-column>

          <el-table-column label="违规类型" width="160">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">
                {{ row.ruleType }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column
            prop="reason"
            label="违规原因"
            min-width="250"
            show-overflow-tooltip
          />

          <el-table-column
            prop="dischargeTime"
            label="出院时间"
            width="140"
            align="center"
          />

          <el-table-column
            prop="createTime"
            label="检测时间"
            width="180"
            align="center"
            class-name="text-gray-500 text-xs"
          />

          <el-table-column
            label="操作"
            width="100"
            fixed="right"
            align="center"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                :icon="View"
                @click="goToDetail(row)"
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
            background
            layout="total, sizes, prev, pager, next, jumper"
            :total="total"
            :page-sizes="[10, 20, 50]"
            @size-change="handlePageChange"
            @current-change="handlePageChange"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 复用您的 CSS，稍作微调以适配新列 */
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
}
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.page-title {
  display: flex;
  gap: 12px;
  padding-bottom: 20px;
  border-bottom: 1px solid #eef2f7;
  margin-bottom: 20px;
}
.title-bar {
  width: 4px;
  height: 24px;
  background: #409eff;
  border-radius: 2px;
  margin-top: 4px;
}
.title-main {
  font-size: 20px;
  font-weight: 600;
  color: #1f2d3d;
}
.title-sub {
  margin-top: 2px;
  font-size: 13px;
  color: #909399;
}
.query-card {
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #eef2f7;
}
.btn-col {
  display: flex;
  align-items: flex-end;
} /* 按钮对齐 */
.search-btns {
  display: flex;
  gap: 10px;
  margin-bottom: 18px;
} /* 按钮间距 */
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.highlight-num {
  color: #409eff;
  font-weight: 700;
  font-size: 15px;
  margin: 0 2px;
}
.custom-table {
  border-radius: 4px;
  overflow: hidden;
}
.task-link {
  font-family: monospace;
  font-size: 13px;
}
.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.font-bold {
  font-weight: 700;
}
.text-gray-700 {
  color: #374151;
}
:deep(.el-form-item__label) {
  padding-bottom: 4px;
  font-weight: 500;
}
</style>
