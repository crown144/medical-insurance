<script lang="ts" setup>
import type { SqlExecutionRecord } from '#/api/core/sql-analysis';

import { computed, ref, watch } from 'vue';

import { Modal, Table, Tag } from 'ant-design-vue';
import dayjs from 'dayjs';

const props = defineProps<{
  open: boolean;
  record: null | SqlExecutionRecord;
}>();

const emit = defineEmits<{
  close: [];
}>();

const page = ref(1);
const pageSize = ref(10);

const tableColumns = computed(() =>
  (props.record?.resultJson?.columns || []).map((column) => ({
    dataIndex: column,
    key: column,
    title: column,
  })),
);

const total = computed(() => props.record?.resultJson?.rows?.length || 0);
const pagedRows = computed(() => {
  const rows = props.record?.resultJson?.rows || [];
  const start = (page.value - 1) * pageSize.value;
  return rows.slice(start, start + pageSize.value);
});

watch(
  () => props.open,
  (value) => {
    if (value) {
      page.value = 1;
      pageSize.value = 10;
    }
  },
);
</script>

<template>
  <Modal
    :footer="null"
    :open="open"
    :title="record ? `${record.ruleName} - 执行结果` : '执行结果'"
    width="1200px"
    @cancel="emit('close')"
  >
    <div v-if="record" class="space-y-4">
      <div class="grid grid-cols-2 gap-3 rounded-lg bg-slate-50 p-4 lg:grid-cols-4">
        <div>
          <div class="text-xs text-slate-500">执行状态</div>
          <Tag :color="record.executeStatus === 'success' ? 'success' : 'error'">
            {{ record.executeStatus === 'success' ? '成功' : '失败' }}
          </Tag>
        </div>
        <div>
          <div class="text-xs text-slate-500">执行时间</div>
          <div class="text-sm text-slate-700">
            {{ dayjs(record.executeTime).format('YYYY-MM-DD HH:mm:ss') }}
          </div>
        </div>
        <div>
          <div class="text-xs text-slate-500">返回记录数</div>
          <div class="text-sm text-slate-700">{{ record.rowCount }}</div>
        </div>
        <div>
          <div class="text-xs text-slate-500">执行耗时</div>
          <div class="text-sm text-slate-700">{{ record.duration }} ms</div>
        </div>
      </div>

      <div
        v-if="record.errorMessage"
        class="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600"
      >
        {{ record.errorMessage }}
      </div>

      <div class="rounded-lg border border-slate-200">
        <div class="border-b border-slate-200 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700">
          渲染后SQL
        </div>
        <pre class="max-h-56 overflow-auto whitespace-pre-wrap bg-slate-950 p-4 text-xs leading-6 text-slate-100">{{ record.resultJson?.renderedSql }}</pre>
      </div>

      <div class="rounded-lg border border-slate-200">
        <div class="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-2">
          <div class="text-sm font-medium text-slate-700">结果预览</div>
          <div v-if="record.resultJson?.truncated" class="text-xs text-amber-600">
            仅保存前 {{ record.resultJson?.previewRowLimit }} 行用于预览
          </div>
        </div>
        <Table
          :columns="tableColumns"
          :data-source="pagedRows"
          :pagination="{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (nextPage: number, nextPageSize: number) => {
              page = nextPage;
              pageSize = nextPageSize;
            },
          }"
          :row-key="(_, index) => index"
          :scroll="{ x: 'max-content' }"
          size="small"
        />
      </div>
    </div>
  </Modal>
</template>
