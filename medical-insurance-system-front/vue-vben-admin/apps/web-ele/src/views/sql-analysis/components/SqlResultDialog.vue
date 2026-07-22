<script lang="ts" setup>
import type { SqlExecutionRecord } from '#/api/sqlAnalysis';

import { computed, ref, watch } from 'vue';

const props = defineProps<{
  modelValue: boolean;
  record: null | SqlExecutionRecord;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const currentPage = ref(1);
const pageSize = ref(10);

const tableColumns = computed(() =>
  (props.record?.resultJson?.columns || []).map((column) => ({
    label: column,
    prop: column,
  })),
);

const pagedRows = computed(() => {
  const rows = props.record?.resultJson?.rows || [];
  const start = (currentPage.value - 1) * pageSize.value;
  return rows.slice(start, start + pageSize.value);
});

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      currentPage.value = 1;
      pageSize.value = 10;
    }
  },
);
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="record ? `${record.ruleName} - 执行结果` : '执行结果'"
    top="4vh"
    width="1200px"
    @close="emit('update:modelValue', false)"
  >
    <div v-if="record" class="result-wrap">
      <div class="summary-grid">
        <div class="summary-item">
          <span class="summary-label">执行状态</span>
          <el-tag :type="record.executeStatus === 'success' ? 'success' : 'danger'">
            {{ record.executeStatus === 'success' ? '成功' : '失败' }}
          </el-tag>
        </div>
        <div class="summary-item">
          <span class="summary-label">执行时间</span>
          <span>{{ record.executeTime }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">执行耗时</span>
          <span>{{ record.duration }} ms</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">返回记录数</span>
          <span>{{ record.rowCount }}</span>
        </div>
      </div>

      <el-alert
        v-if="record.errorMessage"
        :closable="false"
        :title="record.errorMessage"
        show-icon
        type="error"
      />

      <section class="panel">
        <div class="panel__title">渲染后SQL</div>
        <pre class="panel__code">{{ record.resultJson?.renderedSql }}</pre>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div class="panel__title panel__title--plain">结果预览</div>
          <div v-if="record.resultJson?.truncated" class="panel__hint">
            仅保存前 {{ record.resultJson?.previewRowLimit }} 行用于预览
          </div>
        </div>
        <el-table :data="pagedRows" border max-height="420">
          <el-table-column
            v-for="column in tableColumns"
            :key="column.prop"
            :label="column.label"
            :min-width="180"
            :prop="column.prop"
            show-overflow-tooltip
          />
        </el-table>
        <div class="pager-wrap">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50]"
            :total="record.resultJson?.rows?.length || 0"
            background
            layout="total, sizes, prev, pager, next"
          />
        </div>
      </section>
    </div>
  </el-dialog>
</template>

<style scoped>
.result-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background: #f8fafc;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  color: #334155;
}

.summary-label {
  font-size: 12px;
  color: #64748b;
}

.panel {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}

.panel__title {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #334155;
}

.panel__title--plain {
  padding: 0;
}

.panel__hint {
  font-size: 12px;
  color: #d97706;
}

.panel__code {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  padding: 16px;
  background: #020617;
  color: #e2e8f0;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  padding: 16px;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

