<script setup lang="ts">
import type { RuleItem } from '../api/model/taskModel';

import { onMounted, ref, watch } from 'vue';

// Search 图标如果只在 template 字符串中使用，script 中可能也会报 unused，
// 建议在 template 中使用 :prefix-icon="Search" 绑定
import { Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus'; // 其他组件通常自动引入，只需引入 Message

import { getRuleListApi } from '../api/task';

// --- Props 定义 ---
// ✅ 修正：移除 "const props ="，直接调用 defineProps
defineProps<{
  modelValue: string[];
  pairs: string[];
}>();

// --- Emits 定义 ---
const emits = defineEmits(['update:modelValue', 'update:pairs']);

// --- 状态变量 ---
const loading = ref(false);
const tableData = ref<RuleItem[]>([]);
const searchQuery = ref('');
const selectedRows = ref<RuleItem[]>([]);

// --- 加载数据 ---
const loadRules = async () => {
  loading.value = true;
  try {
    const res = await getRuleListApi({
      search: searchQuery.value || undefined,
      type__in: '重复收费',
      paginate: 'false',
    });

    tableData.value = res || [];

    // Mock 数据 (调试用)
    if (tableData.value.length === 0 && !searchQuery.value) {
      tableData.value = [
        {
          id: 101,
          ruleId: 'XM-001',
          drugName: '阑尾切除术',
          description: '包含麻醉费',
          type: '重复收费',
        },
        {
          id: 102,
          ruleId: 'XM-002',
          drugName: '心脏支架',
          description: '包含导丝',
          type: '重复收费',
        },
      ];
    }
  } catch (error) {
    console.error(error);
    ElMessage.error('加载规则失败');
  } finally {
    loading.value = false;
  }
};

watch(searchQuery, () => {
  loadRules();
});

const handleSelectionChange = (rows: RuleItem[]) => {
  selectedRows.value = rows;
  const childCodes = rows.map((r) => r.ruleId);
  const rulePairs = rows.map((r) => `${r.drugName}/${r.ruleId}`);
  emits('update:modelValue', childCodes);
  emits('update:pairs', rulePairs);
};

onMounted(() => {
  loadRules();
});
</script>

<template>
  <div class="selector-container">
    <div class="selector-header">
      <h4>配置“重复收费”规则对</h4>
      <div class="header-tip">
        请勾选需要检测的父子项目关联规则。
        <span class="selected-count" v-if="selectedRows.length > 0">
          (已选 {{ selectedRows.length }} 条)
        </span>
      </div>
    </div>

    <div class="filter-bar">
      <el-input
        v-model="searchQuery"
        placeholder="搜索父项目或子项目..."
        :prefix-icon="Search"
        clearable
        class="search-input"
      />
    </div>

    <el-table
      :data="tableData"
      v-loading="loading"
      height="300"
      border
      stripe
      @selection-change="handleSelectionChange"
      class="rule-table"
    >
      <el-table-column type="selection" width="50" align="center" />

      <el-table-column prop="drugName" label="父项目 (收费项)" min-width="150">
        <template #default="{ row }">
          <span class="parent-item">{{ row.drugName }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="ruleId" label="子项目编码" width="120">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.ruleId }}</el-tag>
        </template>
      </el-table-column>

      <el-table-column
        prop="description"
        label="冲突描述 / 包含关系"
        min-width="200"
        show-overflow-tooltip
      />

      <template #empty>
        <el-empty description="暂无重复收费规则数据" :image-size="80" />
      </template>
    </el-table>
  </div>
</template>

<style scoped>
.selector-container {
}
.selector-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}
.selector-header h4 {
  margin: 0;
  font-size: 14px;
  color: #303133;
}
.header-tip {
  font-size: 12px;
  color: #909399;
}
.selected-count {
  color: #409eff;
  font-weight: 600;
}
.filter-bar {
  margin-bottom: 12px;
}
.search-input {
  width: 100%;
  max-width: 320px;
}
.parent-item {
  font-weight: 500;
  color: #303133;
}
</style>
