<script lang="ts" setup>
import type { FeiJianQueryParams, FeiJianRecord, FeiJianStats } from '#/api/core/feijian';

import { onMounted, reactive, ref } from 'vue';

import { Page } from '@vben/common-ui';
import {
  ArrowUpOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  FileSearchOutlined,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons-vue';
import { $t } from '#/locales';
import {
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Form,
  FormItem,
  Input,
  message,
  Modal,
  Popconfirm,
  Row,
  Select,
  SelectOption,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
} from 'ant-design-vue';
import dayjs, { type Dayjs } from 'dayjs';

import InspectionDetail from './InspectionDetail.vue';
import InspectionForm from './InspectionForm.vue';
import { mockRecords, mockStats } from './mock';

defineOptions({ name: 'FeiJianInspection' });

// ==================== 状态定义 ====================

const { RangePicker } = DatePicker;

const loading = ref(false);
const statsLoading = ref(true);
const stats = ref<FeiJianStats>({
  total: 0,
  inProgress: 0,
  completed: 0,
  withIssues: 0,
  totalViolationAmount: 0,
});

const queryParams = reactive<FeiJianQueryParams>({
  page: 1,
  pageSize: 10,
});

const tableData = ref<FeiJianRecord[]>([]);
const total = ref(0);

// Modal/Drawer 状态
const modalVisible = ref(false);
const modalTitle = ref('');
const editingRecord = ref<FeiJianRecord | null>(null);
const detailVisible = ref(false);
const detailRecord = ref<FeiJianRecord | null>(null);

// 搜索表单
const searchForm = reactive({
  inspectionNo: '',
  hospitalName: '',
  hospitalType: undefined as string | undefined,
  inspectionType: undefined as string | undefined,
  status: undefined as string | undefined,
  result: undefined as string | undefined,
  dateRange: undefined as [Dayjs, Dayjs] | undefined,
});

// ==================== 枚举选项 ====================

const hospitalTypeOptions = [
  { value: 'general', label: $t('page.feijian.hospitalType.general') },
  { value: 'specialist', label: $t('page.feijian.hospitalType.specialist') },
  { value: 'community', label: $t('page.feijian.hospitalType.community') },
  { value: 'private', label: $t('page.feijian.hospitalType.private') },
];

const inspectionTypeOptions = [
  { value: 'routine', label: $t('page.feijian.type.routine') },
  { value: 'special', label: $t('page.feijian.type.special') },
  { value: 'unannounced', label: $t('page.feijian.type.unannounced') },
  { value: 'follow-up', label: $t('page.feijian.type.follow-up') },
];

const statusOptions = [
  { value: 'draft', label: $t('page.feijian.status.draft') },
  { value: 'pending', label: $t('page.feijian.status.pending') },
  { value: 'in-progress', label: $t('page.feijian.status.in-progress') },
  { value: 'completed', label: $t('page.feijian.status.completed') },
  { value: 'cancelled', label: $t('page.feijian.status.cancelled') },
];

const resultOptions = [
  { value: 'none', label: $t('page.feijian.result.none') },
  { value: 'compliant', label: $t('page.feijian.result.compliant') },
  { value: 'minor-issue', label: $t('page.feijian.result.minor-issue') },
  { value: 'major-issue', label: $t('page.feijian.result.major-issue') },
  { value: 'violation', label: $t('page.feijian.result.violation') },
];

// ==================== 状态标签颜色 ====================

function getStatusColor(status: string) {
  const map: Record<string, string> = {
    'draft': 'default',
    'pending': 'blue',
    'in-progress': 'processing',
    'completed': 'success',
    'cancelled': 'warning',
  };
  return map[status] || 'default';
}

function getResultColor(result: string) {
  const map: Record<string, string> = {
    'none': 'default',
    'compliant': 'success',
    'minor-issue': 'warning',
    'major-issue': 'orange',
    'violation': 'red',
  };
  return map[result] || 'default';
}

// ==================== 数据加载 ====================

async function loadStats() {
  statsLoading.value = true;
  // 模拟后端接口延迟
  await new Promise((resolve) => setTimeout(resolve, 300));
  stats.value = mockStats;
  statsLoading.value = false;
}

async function loadData() {
  loading.value = true;
  // 模拟后端接口延迟
  await new Promise((resolve) => setTimeout(resolve, 500));

  let filtered = [...mockRecords];

  // 搜索过滤
  if (searchForm.inspectionNo) {
    filtered = filtered.filter((r) =>
      r.inspectionNo.includes(searchForm.inspectionNo),
    );
  }
  if (searchForm.hospitalName) {
    filtered = filtered.filter((r) =>
      r.hospital.name.includes(searchForm.hospitalName),
    );
  }
  if (searchForm.hospitalType) {
    filtered = filtered.filter(
      (r) => r.hospital.type === searchForm.hospitalType,
    );
  }
  if (searchForm.inspectionType) {
    filtered = filtered.filter(
      (r) => r.inspectionType === searchForm.inspectionType,
    );
  }
  if (searchForm.status) {
    filtered = filtered.filter((r) => r.status === searchForm.status);
  }
  if (searchForm.result) {
    filtered = filtered.filter((r) => r.result === searchForm.result);
  }
  if (searchForm.dateRange && searchForm.dateRange.length === 2) {
    const [start, end] = searchForm.dateRange;
    filtered = filtered.filter((r) => {
      const date = dayjs(r.inspectionDate);
      return date.isAfter(start.startOf('day')) && date.isBefore(end.endOf('day'));
    });
  }

  total.value = filtered.length;
  const start = (queryParams.page - 1) * queryParams.pageSize;
  tableData.value = filtered.slice(start, start + queryParams.pageSize);
  loading.value = false;
}

// ==================== 事件处理 ====================

function handleSearch() {
  queryParams.page = 1;
  loadData();
}

function handleReset() {
  searchForm.inspectionNo = '';
  searchForm.hospitalName = '';
  searchForm.hospitalType = undefined;
  searchForm.inspectionType = undefined;
  searchForm.status = undefined;
  searchForm.result = undefined;
  searchForm.dateRange = undefined;
  queryParams.page = 1;
  loadData();
}

function handlePageChange(page: number, pageSize: number) {
  queryParams.page = page;
  queryParams.pageSize = pageSize;
  loadData();
}

function handleAdd() {
  editingRecord.value = null;
  modalTitle.value = $t('page.feijian.modal.add');
  modalVisible.value = true;
}

function handleEdit(record: FeiJianRecord) {
  editingRecord.value = { ...record };
  modalTitle.value = $t('page.feijian.modal.edit');
  modalVisible.value = true;
}

function handleDetail(record: FeiJianRecord) {
  detailRecord.value = record;
  detailVisible.value = true;
}

function handleDelete(record: FeiJianRecord) {
  const index = mockRecords.findIndex((r) => r.id === record.id);
  if (index > -1) {
    mockRecords.splice(index, 1);
  }
  message.success($t('page.feijian.deleteSuccess'));
  loadStats();
  loadData();
}

function handleModalSubmit(record: FeiJianRecord) {
  if (editingRecord.value) {
    // 编辑
    const index = mockRecords.findIndex((r) => r.id === record.id);
    if (index > -1) {
      mockRecords[index] = record;
    }
    message.success($t('page.feijian.updateSuccess'));
  } else {
    // 新增
    mockRecords.unshift(record);
    message.success($t('page.feijian.createSuccess'));
  }
  modalVisible.value = false;
  loadStats();
  loadData();
}

function handleExport() {
  message.info('导出功能需后端配合实现');
}

// ==================== 表格列定义 ====================

const columns = [
  {
    title: $t('page.feijian.table.inspectionNo'),
    dataIndex: 'inspectionNo',
    key: 'inspectionNo',
    width: 160,
  },
  {
    title: $t('page.feijian.table.hospitalName'),
    dataIndex: ['hospital', 'name'],
    key: 'hospitalName',
    width: 200,
    ellipsis: true,
  },
  {
    title: $t('page.feijian.table.hospitalType'),
    dataIndex: ['hospital', 'typeLabel'],
    key: 'hospitalType',
    width: 120,
  },
  {
    title: $t('page.feijian.table.inspectionType'),
    dataIndex: 'inspectionTypeLabel',
    key: 'inspectionType',
    width: 110,
  },
  {
    title: $t('page.feijian.table.inspectionDate'),
    dataIndex: 'inspectionDate',
    key: 'inspectionDate',
    width: 120,
  },
  {
    title: $t('page.feijian.table.teamLeader'),
    dataIndex: 'teamLeader',
    key: 'teamLeader',
    width: 100,
  },
  {
    title: $t('page.feijian.table.result'),
    dataIndex: 'result',
    key: 'result',
    width: 100,
  },
  {
    title: $t('page.feijian.table.status'),
    dataIndex: 'status',
    key: 'status',
    width: 90,
  },
  {
    title: $t('page.feijian.table.action'),
    key: 'action',
    width: 200,
    fixed: 'right' as const,
  },
];

// ==================== 生命周期 ====================

onMounted(() => {
  loadStats();
  loadData();
});
</script>

<template>
  <Page
    :description="'飞行检查任务管理，支持检查任务的创建、跟踪、结果记录与统计导出'"
    :title="$t('page.feijian.inspection')"
  >
    <!-- 统计卡片 -->
    <Spin :spinning="statsLoading">
      <Row :gutter="16" class="mb-4">
        <Col :lg="4" :md="8" :sm="12" :xs="24">
          <Card class="mb-4" size="small">
            <Statistic
              :title="$t('page.feijian.stats.total')"
              :value="stats.total"
              :value-style="{ color: '#1677ff' }"
            >
              <template #prefix>
                <FileSearchOutlined />
              </template>
            </Statistic>
          </Card>
        </Col>
        <Col :lg="4" :md="8" :sm="12" :xs="24">
          <Card class="mb-4" size="small">
            <Statistic
              :title="$t('page.feijian.stats.inProgress')"
              :value="stats.inProgress"
              :value-style="{ color: '#faad14' }"
            >
              <template #prefix>
                <ExclamationCircleOutlined />
              </template>
            </Statistic>
          </Card>
        </Col>
        <Col :lg="4" :md="8" :sm="12" :xs="24">
          <Card class="mb-4" size="small">
            <Statistic
              :title="$t('page.feijian.stats.completed')"
              :value="stats.completed"
              :value-style="{ color: '#52c41a' }"
            >
              <template #prefix>
                <CheckCircleOutlined />
              </template>
            </Statistic>
          </Card>
        </Col>
        <Col :lg="4" :md="8" :sm="12" :xs="24">
          <Card class="mb-4" size="small">
            <Statistic
              :title="$t('page.feijian.stats.withIssues')"
              :value="stats.withIssues"
              :value-style="{ color: '#ff4d4f' }"
            >
              <template #prefix>
                <ArrowUpOutlined />
              </template>
            </Statistic>
          </Card>
        </Col>
        <Col :lg="8" :md="16" :sm="24" :xs="24">
          <Card class="mb-4" size="small">
            <Statistic
              :title="$t('page.feijian.stats.totalViolationAmount')"
              :value="stats.totalViolationAmount"
              :precision="2"
              :value-style="{ color: '#ff4d4f' }"
            >
              <template #prefix>
                <ArrowUpOutlined />
              </template>
              <template #suffix>万元</template>
            </Statistic>
          </Card>
        </Col>
      </Row>
    </Spin>

    <!-- 搜索区域 -->
    <Card class="mb-4" size="small">
      <Form layout="inline" :model="searchForm">
        <Row :gutter="[16, 16]" style="width: 100%">
          <Col :lg="6" :md="8" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.inspectionNo')" name="inspectionNo">
              <Input
                v-model:value="searchForm.inspectionNo"
                :placeholder="$t('page.feijian.search.inspectionNo')"
                allow-clear
                @pressEnter="handleSearch"
              />
            </FormItem>
          </Col>
          <Col :lg="6" :md="8" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.hospitalName')" name="hospitalName">
              <Input
                v-model:value="searchForm.hospitalName"
                :placeholder="$t('page.feijian.search.hospitalName')"
                allow-clear
                @pressEnter="handleSearch"
              />
            </FormItem>
          </Col>
          <Col :lg="6" :md="8" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.hospitalType')" name="hospitalType">
              <Select
                v-model:value="searchForm.hospitalType"
                :placeholder="$t('page.feijian.search.hospitalType')"
                allow-clear
              >
                <SelectOption
                  v-for="opt in hospitalTypeOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
          <Col :lg="6" :md="8" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.inspectionType')" name="inspectionType">
              <Select
                v-model:value="searchForm.inspectionType"
                :placeholder="$t('page.feijian.search.inspectionType')"
                allow-clear
              >
                <SelectOption
                  v-for="opt in inspectionTypeOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
          <Col :lg="6" :md="8" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.status')" name="status">
              <Select
                v-model:value="searchForm.status"
                :placeholder="$t('page.feijian.search.status')"
                allow-clear
              >
                <SelectOption
                  v-for="opt in statusOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
          <Col :lg="6" :md="8" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.result')" name="result">
              <Select
                v-model:value="searchForm.result"
                :placeholder="$t('page.feijian.search.result')"
                allow-clear
              >
                <SelectOption
                  v-for="opt in resultOptions"
                  :key="opt.value"
                  :value="opt.value"
                >
                  {{ opt.label }}
                </SelectOption>
              </Select>
            </FormItem>
          </Col>
          <Col :lg="8" :md="10" :sm="12" :xs="24">
            <FormItem :label="$t('page.feijian.search.dateRange')" name="dateRange">
              <RangePicker
                v-model:value="searchForm.dateRange"
                style="width: 100%"
              />
            </FormItem>
          </Col>
          <Col :lg="4" :md="6" :sm="12" :xs="24">
            <FormItem>
              <Space>
                <Button type="primary" @click="handleSearch">
                  <template #icon><SearchOutlined /></template>
                  {{ $t('page.feijian.search.search') }}
                </Button>
                <Button @click="handleReset">
                  {{ $t('page.feijian.search.reset') }}
                </Button>
              </Space>
            </FormItem>
          </Col>
        </Row>
      </Form>
    </Card>

    <!-- 操作栏 + 表格 -->
    <Card size="small">
      <div class="mb-4 flex items-center justify-between">
        <Space>
          <Button type="primary" @click="handleAdd">
            <template #icon><PlusOutlined /></template>
            {{ $t('page.feijian.modal.add') }}
          </Button>
        </Space>
        <Button @click="handleExport">
          {{ $t('page.feijian.search.export') }}
        </Button>
      </div>

      <Table
        :columns="columns"
        :data-source="tableData"
        :loading="loading"
        :pagination="{
          current: queryParams.page,
          pageSize: queryParams.pageSize,
          total: total,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (t: number) => `共 ${t} 条记录`,
        }"
        row-key="id"
        size="middle"
        scroll="{ x: 1300 }"
        @change="(pag: any) => handlePageChange(pag.current, pag.pageSize)"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'result'">
            <Tag :color="getResultColor(record.result)">
              {{ record.resultLabel }}
            </Tag>
          </template>
          <template v-else-if="column.key === 'status'">
            <Tag :color="getStatusColor(record.status)">
              {{ record.statusLabel }}
            </Tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <Space>
              <a @click="handleDetail(record)">{{ $t('page.feijian.table.detail') }}</a>
              <a @click="handleEdit(record)">{{ $t('page.feijian.table.edit') }}</a>
              <Popconfirm
                :title="$t('page.feijian.confirmDelete')"
                ok-text="确认"
                cancel-text="取消"
                @confirm="handleDelete(record)"
              >
                <a class="text-red-500">{{ $t('page.feijian.table.delete') }}</a>
              </Popconfirm>
            </Space>
          </template>
        </template>
      </Table>
    </Card>

    <!-- 新增/编辑弹窗 -->
    <Modal
      v-model:open="modalVisible"
      :title="modalTitle"
      :width="900"
      :destroy-on-close="true"
      :footer="null"
    >
      <InspectionForm
        :record="editingRecord"
        @submit="handleModalSubmit"
        @cancel="modalVisible = false"
      />
    </Modal>

    <!-- 详情抽屉 -->
    <Drawer
      :title="$t('page.feijian.modal.detail')"
      :width="720"
      :open="detailVisible"
      @close="detailVisible = false"
    >
      <InspectionDetail v-if="detailRecord" :record="detailRecord" />
    </Drawer>
  </Page>
</template>