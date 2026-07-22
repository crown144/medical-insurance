<script lang="ts" setup>
import type { SqlExecutionRecord, SqlRule } from '#/api/core/sql-analysis';

import { onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';
import {
  DeleteOutlined,
  EyeOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons-vue';
import {
  Button,
  Card,
  DatePicker,
  Form,
  FormItem,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  message,
} from 'ant-design-vue';
import dayjs from 'dayjs';

import {
  deleteSqlHistoryApi,
  executeSqlApi,
  getSqlHistoryApi,
  getSqlHistoryDetailApi,
  getSqlRulesApi,
} from '#/api';

import SqlResultModal from '../components/SqlResultModal.vue';

defineOptions({ name: 'SqlAnalysisExecution' });

const rules = ref<SqlRule[]>([]);
const historyData = ref<SqlExecutionRecord[]>([]);
const historyTotal = ref(0);
const executing = ref(false);
const historyLoading = ref(false);
const latestExecution = ref<null | SqlExecutionRecord>(null);
const resultModalOpen = ref(false);
const currentResult = ref<null | SqlExecutionRecord>(null);

const executeForm = reactive({
  sqlRuleId: undefined as number | undefined,
  startDate: null as null | string,
  endDate: null as null | string,
});

const historyPagination = reactive({
  current: 1,
  pageSize: 10,
});

const historyColumns = [
  { dataIndex: 'id', key: 'id', title: '任务ID' },
  { dataIndex: 'ruleName', key: 'ruleName', title: '医保规则' },
  { key: 'dateRange', title: '时间范围' },
  { dataIndex: 'executeTime', key: 'executeTime', title: '执行时间' },
  { dataIndex: 'executeStatus', key: 'executeStatus', title: '状态' },
  { dataIndex: 'duration', key: 'duration', title: '耗时' },
  { dataIndex: 'rowCount', key: 'rowCount', title: '返回记录数' },
  { key: 'action', title: '操作' },
];

async function loadRules() {
  const response = await getSqlRulesApi({ page: 1, pageSize: 200 });
  rules.value = response.items;
}

async function loadHistory() {
  historyLoading.value = true;
  try {
    const response = await getSqlHistoryApi({
      page: historyPagination.current,
      pageSize: historyPagination.pageSize,
      sqlRuleId: executeForm.sqlRuleId,
    });
    historyData.value = response.items;
    historyTotal.value = response.total;
  } finally {
    historyLoading.value = false;
  }
}

async function handleExecute() {
  if (!executeForm.sqlRuleId || !executeForm.startDate || !executeForm.endDate) {
    message.warning('请选择医保规则和时间范围');
    return;
  }
  executing.value = true;
  try {
    const execution = await executeSqlApi({
      sqlRuleId: executeForm.sqlRuleId,
      startDate: executeForm.startDate,
      endDate: executeForm.endDate,
    });
    latestExecution.value = execution;
    currentResult.value = execution;
    resultModalOpen.value = true;
    message.success(execution.executeStatus === 'success' ? '执行成功' : '执行完成');
    historyPagination.current = 1;
    await loadHistory();
  } finally {
    executing.value = false;
  }
}

async function handleViewResult(record: SqlExecutionRecord) {
  currentResult.value = await getSqlHistoryDetailApi(record.id);
  resultModalOpen.value = true;
}

async function handleDelete(record: SqlExecutionRecord) {
  await deleteSqlHistoryApi(record.id);
  message.success('删除成功');
  if (historyData.value.length === 1 && historyPagination.current > 1) {
    historyPagination.current -= 1;
  }
  await loadHistory();
}

onMounted(async () => {
  await loadRules();
  await loadHistory();
});
</script>

<template>
  <Page auto-content-height>
    <div class="space-y-4">
      <Card title="SQL执行">
        <Form layout="inline">
          <FormItem label="医保规则">
            <Select
              v-model:value="executeForm.sqlRuleId"
              :options="rules.map((item) => ({ label: item.ruleName, value: item.id }))"
              allow-clear
              placeholder="请选择医保规则"
              style="width: 260px"
            />
          </FormItem>
          <FormItem label="开始日期">
            <DatePicker
              :value="executeForm.startDate ? dayjs(executeForm.startDate) : null"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @update:value="(value) => (executeForm.startDate = value || null)"
            />
          </FormItem>
          <FormItem label="结束日期">
            <DatePicker
              :value="executeForm.endDate ? dayjs(executeForm.endDate) : null"
              format="YYYY-MM-DD"
              value-format="YYYY-MM-DD"
              @update:value="(value) => (executeForm.endDate = value || null)"
            />
          </FormItem>
          <FormItem>
            <Space>
              <Button :loading="executing" type="primary" @click="handleExecute">
                <PlayCircleOutlined />
                执行SQL
              </Button>
              <Button @click="loadHistory">刷新历史</Button>
            </Space>
          </FormItem>
        </Form>
      </Card>

      <Card v-if="latestExecution" title="最近一次执行">
        <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div>
            <div class="text-xs text-slate-500">执行状态</div>
            <Tag :color="latestExecution.executeStatus === 'success' ? 'success' : 'error'">
              {{ latestExecution.executeStatus === 'success' ? '成功' : '失败' }}
            </Tag>
          </div>
          <div>
            <div class="text-xs text-slate-500">执行时间</div>
            <div>{{ dayjs(latestExecution.executeTime).format('YYYY-MM-DD HH:mm:ss') }}</div>
          </div>
          <div>
            <div class="text-xs text-slate-500">执行耗时</div>
            <div>{{ latestExecution.duration }} ms</div>
          </div>
          <div>
            <div class="text-xs text-slate-500">返回记录数</div>
            <div>{{ latestExecution.rowCount }}</div>
          </div>
        </div>
      </Card>

      <Card title="历史执行记录">
        <Table
          :columns="historyColumns"
          :data-source="historyData"
          :loading="historyLoading"
          :pagination="{
            current: historyPagination.current,
            pageSize: historyPagination.pageSize,
            total: historyTotal,
            showSizeChanger: true,
            onChange: (page: number, pageSize: number) => {
              historyPagination.current = page;
              historyPagination.pageSize = pageSize;
              loadHistory();
            },
          }"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'dateRange'">
              {{ record.startDate }} ~ {{ record.endDate }}
            </template>
            <template v-else-if="column.key === 'executeTime'">
              {{ dayjs(record.executeTime).format('YYYY-MM-DD HH:mm:ss') }}
            </template>
            <template v-else-if="column.key === 'executeStatus'">
              <Tag :color="record.executeStatus === 'success' ? 'success' : 'error'">
                {{ record.executeStatus === 'success' ? '成功' : '失败' }}
              </Tag>
            </template>
            <template v-else-if="column.key === 'duration'">
              {{ record.duration }} ms
            </template>
            <template v-else-if="column.key === 'action'">
              <Space>
                <Button size="small" type="link" @click="handleViewResult(record)">
                  <EyeOutlined />
                  查看结果
                </Button>
                <Popconfirm title="确认删除该执行记录？" @confirm="handleDelete(record)">
                  <Button danger size="small" type="link">
                    <DeleteOutlined />
                    删除记录
                  </Button>
                </Popconfirm>
              </Space>
            </template>
          </template>
        </Table>
      </Card>
    </div>

    <SqlResultModal
      :open="resultModalOpen"
      :record="currentResult"
      @close="resultModalOpen = false"
    />
  </Page>
</template>
