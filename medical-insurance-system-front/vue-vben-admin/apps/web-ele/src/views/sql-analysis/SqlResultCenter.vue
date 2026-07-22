<script lang="ts" setup>
import type { SqlRuleResultStats, SqlRuleResultSummary } from '#/api/sqlAnalysis';

import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { ArrowRight, Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

import { getSqlResultRules } from '#/api/sqlAnalysis';

const router = useRouter();
const loading = ref(false);
const rules = ref<SqlRuleResultSummary[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const stats = ref<SqlRuleResultStats>({
  totalRules: 0,
  executedRules: 0,
  totalExecutions: 0,
  totalViolations: 0,
});

const searchForm = reactive({
  keyword: '',
  ruleType: '',
  ordering: '-recentExecuteTime',
});

const sortOptions = [
  { label: '最近执行时间倒序', value: '-recentExecuteTime' },
  { label: '最近执行时间正序', value: 'recentExecuteTime' },
  { label: '累计执行次数倒序', value: '-executionCount' },
  { label: '累计违规数量倒序', value: '-totalViolationCount' },
  { label: '规则名称正序', value: 'ruleName' },
];

const statusText = computed(() => (status: SqlRuleResultSummary['status']) => {
  if (status === 'success') return '成功';
  if (status === 'failed') return '失败';
  return '未执行';
});

const statusTagType = computed(() => (status: SqlRuleResultSummary['status']) => {
  if (status === 'success') return 'success';
  if (status === 'failed') return 'danger';
  return 'info';
});

const fetchData = async () => {
  loading.value = true;
  try {
    const result = await getSqlResultRules({
      keyword: searchForm.keyword.trim() || undefined,
      ordering: searchForm.ordering,
      page: currentPage.value,
      pageSize: pageSize.value,
      ruleType: searchForm.ruleType.trim() || undefined,
    });
    rules.value = result?.items || [];
    total.value = result?.total || 0;
    stats.value = result?.stats || stats.value;
  } catch (error) {
    console.error(error);
    ElMessage.error('获取执行结果汇总失败');
  } finally {
    loading.value = false;
  }
};

const handleSearch = () => {
  currentPage.value = 1;
  fetchData();
};

const handleReset = () => {
  searchForm.keyword = '';
  searchForm.ruleType = '';
  searchForm.ordering = '-recentExecuteTime';
  currentPage.value = 1;
  fetchData();
};

const goDetail = (row: SqlRuleResultSummary) => {
  router.push({ name: 'SqlAnalysisResultDetail', params: { id: row.id } });
};

onMounted(fetchData);
</script>

<template>
  <div class="result-center">
    <section class="panel">
      <div class="title-row">
        <div class="title">
          <span class="bar"></span>
          <span>执行结果</span>
        </div>
      </div>

      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-label">SQL规则数量</div>
          <div class="stat-value">{{ stats.totalRules }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">已执行规则数量</div>
          <div class="stat-value">{{ stats.executedRules }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">累计执行次数</div>
          <div class="stat-value">{{ stats.totalExecutions }}</div>
        </div>
        <div class="stat-card accent">
          <div class="stat-label">累计违规数量</div>
          <div class="stat-value">{{ stats.totalViolations }}</div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="search-panel">
        <el-input
          v-model="searchForm.keyword"
          clearable
          placeholder="按规则名称搜索"
          style="width: 240px"
          @keyup.enter="handleSearch"
        />
        <el-input
          v-model="searchForm.ruleType"
          clearable
          placeholder="按规则类型筛选"
          style="width: 180px"
          @keyup.enter="handleSearch"
        />
        <el-select v-model="searchForm.ordering" style="width: 220px">
          <el-option
            v-for="option in sortOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button :icon="Search" type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <el-table v-loading="loading" :data="rules" border>
        <el-table-column label="规则名称" min-width="220" prop="ruleName" />
        <el-table-column label="规则类型" min-width="140" prop="ruleType" />
        <el-table-column label="最近执行时间" min-width="180" prop="recentExecuteTime">
          <template #default="{ row }">
            {{ row.recentExecuteTime || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="累计执行次数" min-width="120" prop="executionCount" sortable />
        <el-table-column label="累计违规数量" min-width="140" prop="totalViolationCount" sortable />
        <el-table-column label="最近一次违规数量" min-width="150" prop="latestViolationCount" />
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column fixed="right" label="操作" min-width="120">
          <template #default="{ row }">
            <el-button :icon="ArrowRight" link type="primary" @click="goDetail(row)">
              查看详情
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
          @change="fetchData"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.result-center {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  padding: 18px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f8fafc 0%, #eef6ff 100%);
  border: 1px solid #e2e8f0;
}

.stat-card.accent {
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
}

.stat-label {
  font-size: 13px;
  color: #64748b;
}

.stat-value {
  margin-top: 10px;
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.search-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 18px;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}

@media (max-width: 960px) {
  .stats-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

