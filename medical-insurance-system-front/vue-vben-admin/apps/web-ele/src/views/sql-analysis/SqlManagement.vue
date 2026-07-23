<script lang="ts" setup>
import type { SqlRule } from '#/api/sqlAnalysis';

import { onMounted, reactive, ref } from 'vue';

import { Delete, Edit, Plus, Search, View } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  createSqlRule,
  deleteSqlRule,
  getSqlRuleDetail,
  getSqlRules,
  updateSqlRule,
} from '#/api/sqlAnalysis';

import SqlRuleDialog from './components/SqlRuleDialog.vue';

const loading = ref(false);
const list = ref<SqlRule[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const dialogVisible = ref(false);
const dialogSaving = ref(false);
const dialogMode = ref<'create' | 'edit' | 'view'>('create');
const currentRule = ref<null | SqlRule>(null);

const searchForm = reactive({
  keyword: '',
  ruleType: '',
});

const fetchData = async () => {
  loading.value = true;
  try {
    const result = await getSqlRules({
      keyword: searchForm.keyword.trim() || undefined,
      page: currentPage.value,
      pageSize: pageSize.value,
      ruleType: searchForm.ruleType.trim() || undefined,
    });
    list.value = result?.items || [];
    total.value = result?.total || 0;
  } catch (error) {
    console.error(error);
    ElMessage.error('获取SQL规则列表失败');
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
  currentPage.value = 1;
  fetchData();
};

const openCreate = () => {
  dialogMode.value = 'create';
  currentRule.value = null;
  dialogVisible.value = true;
};

const openEdit = async (row: SqlRule) => {
  dialogMode.value = 'edit';
  currentRule.value = await getSqlRuleDetail(row.id);
  dialogVisible.value = true;
};

const openView = async (row: SqlRule) => {
  dialogMode.value = 'view';
  currentRule.value = await getSqlRuleDetail(row.id);
  dialogVisible.value = true;
};

const handleDelete = async (row: SqlRule) => {
  await ElMessageBox.confirm(`确定删除SQL规则【${row.ruleName}】吗？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  });
  await deleteSqlRule(row.id);
  ElMessage.success('删除成功');
  if (list.value.length === 1 && currentPage.value > 1) {
    currentPage.value -= 1;
  }
  fetchData();
};

const handleSubmit = async (payload: Partial<SqlRule>) => {
  dialogSaving.value = true;
  try {
    if (!payload.ruleName?.trim()) {
      ElMessage.warning('请填写医保规则名称');
      return;
    }
    if (!payload.ruleType?.trim()) {
      ElMessage.warning('请填写规则类型');
      return;
    }
    if (!payload.sqlContent?.trim()) {
      ElMessage.warning('请填写SQL内容');
      return;
    }

    if (dialogMode.value === 'create') {
      await createSqlRule(payload);
      ElMessage.success('新增成功');
    } else if (currentRule.value) {
      await updateSqlRule(currentRule.value.id, payload);
      ElMessage.success('更新成功');
    }
    dialogVisible.value = false;
    fetchData();
  } catch (error: any) {
    console.error(error);
    const message = error?.response?.data?.message || '保存失败';
    ElMessage.error(message);
  } finally {
    dialogSaving.value = false;
  }
};

onMounted(fetchData);
</script>

<template>
  <div class="page-card">
    <div class="header">
      <div class="title">
        <span class="bar"></span>
        <span>SQL管理</span>
      </div>
      <div class="header-actions">
        <el-button :icon="Plus" type="primary" @click="openCreate">新增SQL规则</el-button>
      </div>
    </div>

    <div class="search-panel">
      <el-input
        v-model="searchForm.keyword"
        clearable
        placeholder="请输入医保规则名称"
        style="width: 260px"
        @keyup.enter="handleSearch"
      />
      <el-input
        v-model="searchForm.ruleType"
        clearable
        placeholder="请输入规则类型"
        style="width: 200px"
        @keyup.enter="handleSearch"
      />
      <el-button :icon="Search" type="primary" @click="handleSearch">查询</el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <el-table v-loading="loading" :data="list" border>
      <el-table-column label="医保规则名称" min-width="220" prop="ruleName" />
      <el-table-column label="规则类型" min-width="160" prop="ruleType" />
      <el-table-column label="SQL状态" min-width="120" prop="sqlStatus">
        <template #default="{ row }">
          <el-tag :type="row.sqlStatus === '已配置' ? 'success' : 'info'">
            {{ row.sqlStatus }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" min-width="180" prop="updatedAt" />
      <el-table-column fixed="right" label="操作" min-width="220">
        <template #default="{ row }">
          <el-button :icon="View" link type="primary" @click="openView(row)">查看</el-button>
          <el-button :icon="Edit" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button :icon="Delete" link type="danger" @click="handleDelete(row)">删除</el-button>
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

    <SqlRuleDialog
      v-model="dialogVisible"
      :mode="dialogMode"
      :rule="currentRule"
      :saving="dialogSaving"
      @submit="handleSubmit"
    />
  </div>
</template>

<style scoped>
.page-card {
  padding: 20px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.header {
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
</style>

