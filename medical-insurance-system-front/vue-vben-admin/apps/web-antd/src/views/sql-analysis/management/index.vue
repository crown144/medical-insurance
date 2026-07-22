<script lang="ts" setup>
import type { SqlRule } from '#/api/core/sql-analysis';

import { onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';
import {
  DeleteOutlined,
  EditOutlined,
  EyeOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue';
import {
  Button,
  Card,
  Form,
  FormItem,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  message,
} from 'ant-design-vue';
import dayjs from 'dayjs';

import {
  createSqlRuleApi,
  deleteSqlRuleApi,
  getSqlRulesApi,
  updateSqlRuleApi,
} from '#/api';

import SqlRuleModal from '../components/SqlRuleModal.vue';

defineOptions({ name: 'SqlAnalysisManagement' });

const loading = ref(false);
const modalOpen = ref(false);
const modalSubmitting = ref(false);
const modalMode = ref<'create' | 'edit' | 'view'>('create');
const currentRule = ref<null | SqlRule>(null);
const tableData = ref<SqlRule[]>([]);
const total = ref(0);

const searchForm = reactive({
  keyword: '',
  ruleType: '',
});

const pagination = reactive({
  current: 1,
  pageSize: 10,
});

const columns = [
  { dataIndex: 'ruleName', key: 'ruleName', title: '医保规则名称' },
  { dataIndex: 'ruleType', key: 'ruleType', title: '规则类型' },
  { dataIndex: 'sqlStatus', key: 'sqlStatus', title: 'SQL状态' },
  { dataIndex: 'updatedAt', key: 'updatedAt', title: '更新时间' },
  { key: 'action', title: '操作' },
];

async function loadData() {
  loading.value = true;
  try {
    const response = await getSqlRulesApi({
      keyword: searchForm.keyword || undefined,
      page: pagination.current,
      pageSize: pagination.pageSize,
      ruleType: searchForm.ruleType || undefined,
    });
    tableData.value = response.items;
    total.value = response.total;
  } finally {
    loading.value = false;
  }
}

function handleSearch() {
  pagination.current = 1;
  loadData();
}

function handleReset() {
  searchForm.keyword = '';
  searchForm.ruleType = '';
  pagination.current = 1;
  loadData();
}

function openCreateModal() {
  modalMode.value = 'create';
  currentRule.value = null;
  modalOpen.value = true;
}

function openEditModal(rule: SqlRule) {
  modalMode.value = 'edit';
  currentRule.value = rule;
  modalOpen.value = true;
}

function openViewModal(rule: SqlRule) {
  modalMode.value = 'view';
  currentRule.value = rule;
  modalOpen.value = true;
}

async function handleDelete(rule: SqlRule) {
  await deleteSqlRuleApi(rule.id);
  message.success('删除成功');
  if (tableData.value.length === 1 && pagination.current > 1) {
    pagination.current -= 1;
  }
  await loadData();
}

async function handleSubmit(payload: Partial<SqlRule>) {
  modalSubmitting.value = true;
  try {
    if (modalMode.value === 'create') {
      await createSqlRuleApi(payload);
      message.success('新增成功');
    } else if (currentRule.value) {
      await updateSqlRuleApi(currentRule.value.id, payload);
      message.success('更新成功');
    }
    modalOpen.value = false;
    await loadData();
  } finally {
    modalSubmitting.value = false;
  }
}

onMounted(loadData);
</script>

<template>
  <Page auto-content-height>
    <div class="space-y-4">
      <Card>
        <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <Form layout="inline">
            <FormItem label="规则名称">
              <Input v-model:value="searchForm.keyword" allow-clear placeholder="请输入医保规则名称" />
            </FormItem>
            <FormItem label="规则类型">
              <Input v-model:value="searchForm.ruleType" allow-clear placeholder="请输入规则类型" />
            </FormItem>
            <FormItem>
              <Space>
                <Button type="primary" @click="handleSearch">
                  <SearchOutlined />
                  查询
                </Button>
                <Button @click="handleReset">重置</Button>
              </Space>
            </FormItem>
          </Form>
          <Button type="primary" @click="openCreateModal">
            <PlusOutlined />
            新增SQL规则
          </Button>
        </div>
      </Card>

      <Card>
        <Table
          :columns="columns"
          :data-source="tableData"
          :loading="loading"
          :pagination="{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            onChange: (page: number, pageSize: number) => {
              pagination.current = page;
              pagination.pageSize = pageSize;
              loadData();
            },
          }"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'sqlStatus'">
              <Tag :color="record.sqlStatus === '已配置' ? 'success' : 'default'">
                {{ record.sqlStatus }}
              </Tag>
            </template>
            <template v-else-if="column.key === 'updatedAt'">
              {{ dayjs(record.updatedAt).format('YYYY-MM-DD HH:mm:ss') }}
            </template>
            <template v-else-if="column.key === 'action'">
              <Space>
                <Button size="small" type="link" @click="openViewModal(record)">
                  <EyeOutlined />
                  查看
                </Button>
                <Button size="small" type="link" @click="openEditModal(record)">
                  <EditOutlined />
                  编辑
                </Button>
                <Popconfirm title="确认删除该SQL规则？" @confirm="handleDelete(record)">
                  <Button danger size="small" type="link">
                    <DeleteOutlined />
                    删除
                  </Button>
                </Popconfirm>
              </Space>
            </template>
          </template>
        </Table>
      </Card>
    </div>

    <SqlRuleModal
      :mode="modalMode"
      :open="modalOpen"
      :rule="currentRule"
      :submitting="modalSubmitting"
      @close="modalOpen = false"
      @submit="handleSubmit"
    />
  </Page>
</template>

