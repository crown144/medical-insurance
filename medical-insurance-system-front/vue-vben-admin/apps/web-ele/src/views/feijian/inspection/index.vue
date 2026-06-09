<script setup lang="ts">
import type { FeiJianRecord, FeiJianStats } from '../../api/model/feijianModel';

import { onMounted, reactive, ref, watch } from 'vue';

import {
  Delete,
  Edit,
  Plus,
  Refresh,
  Search,
  View,
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import { mockRecords, mockStats } from './mock';

// ==================== 状态定义 ====================

const isLoading = ref(false);

const stats = ref<FeiJianStats>({
  total: 0,
  inProgress: 0,
  completed: 0,
  withIssues: 0,
  totalViolationAmount: 0,
});

const searchForm = reactive({
  inspectionNo: '',
  hospitalName: '',
  hospitalType: '' as string,
  inspectionType: '' as string,
  status: '' as string,
  result: '' as string,
  dateRange: [] as string[],
});

const allItems = ref<FeiJianRecord[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

// 弹窗状态
const dialogVisible = ref(false);
const dialogTitle = ref('');
const isEdit = ref(false);
const editingRecord = ref<FeiJianRecord | null>(null);

// 详情弹窗状态
const detailVisible = ref(false);
const detailRecord = ref<FeiJianRecord | null>(null);

// 表单数据
const formData = reactive({
  inspectionNo: '',
  inspectionType: '' as string,
  inspectionDate: '',
  inspectionEndDate: '',
  status: '' as string,
  hospitalName: '',
  hospitalType: '' as string,
  hospitalAddress: '',
  contactPerson: '',
  contactPhone: '',
  teamLeader: '',
  teamMembers: [] as { id: string; name: string; role: string; phone: string }[],
  result: '' as string,
  findings: '',
  recommendation: '',
  violationAmount: 0,
});

// ==================== 枚举选项 ====================

const hospitalTypeOptions = [
  { value: 'general', label: '综合医院' },
  { value: 'specialist', label: '专科医院' },
  { value: 'community', label: '社区卫生中心' },
  { value: 'private', label: '民营医院' },
];

const inspectionTypeOptions = [
  { value: 'routine', label: '常规检查' },
  { value: 'special', label: '专项检查' },
  { value: 'unannounced', label: '飞行检查' },
  { value: 'follow-up', label: '复查' },
];

const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'pending', label: '待检查' },
  { value: 'in-progress', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'cancelled', label: '已取消' },
];

const resultOptions = [
  { value: 'none', label: '待定' },
  { value: 'compliant', label: '合规' },
  { value: 'minor-issue', label: '一般问题' },
  { value: 'major-issue', label: '严重问题' },
  { value: 'violation', label: '违规' },
];

// ==================== 标签颜色 ====================

function getStatusType(status: string) {
  const map: Record<string, string> = {
    'draft': 'info',
    'pending': '',
    'in-progress': 'warning',
    'completed': 'success',
    'cancelled': 'danger',
  };
  return map[status] || 'info';
}

function getResultType(result: string) {
  const map: Record<string, string> = {
    'none': 'info',
    'compliant': 'success',
    'minor-issue': 'warning',
    'major-issue': 'danger',
    'violation': 'danger',
  };
  return map[result] || 'info';
}

// ==================== 数据加载 ====================

function loadStats() {
  stats.value = { ...mockStats };
}

function loadData() {
  isLoading.value = true;

  let filtered = [...mockRecords];

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
      return r.inspectionDate >= start && r.inspectionDate <= end;
    });
  }

  total.value = filtered.length;
  const start = (currentPage.value - 1) * pageSize.value;
  allItems.value = filtered.slice(start, start + pageSize.value);
  isLoading.value = false;
}

// ==================== 事件处理 ====================

function handleSearch() {
  currentPage.value = 1;
  loadData();
}

function handleReset() {
  searchForm.inspectionNo = '';
  searchForm.hospitalName = '';
  searchForm.hospitalType = '';
  searchForm.inspectionType = '';
  searchForm.status = '';
  searchForm.result = '';
  searchForm.dateRange = [];
  currentPage.value = 1;
  loadData();
}

function handleAdd() {
  isEdit.value = false;
  dialogTitle.value = '新增检查';
  resetForm();
  dialogVisible.value = true;
}

function handleEdit(record: FeiJianRecord) {
  isEdit.value = true;
  dialogTitle.value = '编辑检查';
  formData.inspectionNo = record.inspectionNo;
  formData.inspectionType = record.inspectionType;
  formData.inspectionDate = record.inspectionDate;
  formData.inspectionEndDate = record.inspectionEndDate;
  formData.status = record.status;
  formData.hospitalName = record.hospital.name;
  formData.hospitalType = record.hospital.type;
  formData.hospitalAddress = record.hospital.address;
  formData.contactPerson = record.hospital.contactPerson;
  formData.contactPhone = record.hospital.contactPhone;
  formData.teamLeader = record.teamLeader;
  formData.teamMembers = record.inspectionTeam.map((m) => ({ ...m }));
  formData.result = record.result;
  formData.findings = record.findings;
  formData.recommendation = record.recommendation;
  formData.violationAmount = record.violationAmount;
  editingRecord.value = record;
  dialogVisible.value = true;
}

function handleDetail(record: FeiJianRecord) {
  detailRecord.value = record;
  detailVisible.value = true;
}

async function handleDelete(record: FeiJianRecord) {
  try {
    await ElMessageBox.confirm('确认删除该检查记录？', '警告', {
      type: 'warning',
    });
    const index = mockRecords.findIndex((r) => r.id === record.id);
    if (index > -1) {
      mockRecords.splice(index, 1);
    }
    ElMessage.success('删除成功');
    loadStats();
    loadData();
  } catch {
    // 取消
  }
}

function handleSubmit() {
  const hospitalTypeLabel =
    hospitalTypeOptions.find((o) => o.value === formData.hospitalType)?.label || '';
  const inspectionTypeLabel =
    inspectionTypeOptions.find((o) => o.value === formData.inspectionType)?.label || '';
  const resultLabel =
    resultOptions.find((o) => o.value === formData.result)?.label || '待定';
  const statusLabel =
    statusOptions.find((o) => o.value === formData.status)?.label || '';

  const record: FeiJianRecord = {
    id: editingRecord.value?.id || String(Date.now()),
    inspectionNo: formData.inspectionNo,
    hospital: {
      id: editingRecord.value?.hospital.id || String(Date.now()),
      name: formData.hospitalName,
      type: formData.hospitalType as any,
      typeLabel: hospitalTypeLabel,
      address: formData.hospitalAddress,
      contactPerson: formData.contactPerson,
      contactPhone: formData.contactPhone,
    },
    inspectionType: formData.inspectionType as any,
    inspectionTypeLabel,
    inspectionDate: formData.inspectionDate,
    inspectionEndDate: formData.inspectionEndDate,
    inspectionTeam: formData.teamMembers,
    teamLeader: formData.teamLeader,
    result: (formData.result as any) || 'none',
    resultLabel: resultLabel || '待定',
    status: formData.status as any,
    statusLabel: statusLabel || '草稿',
    findings: formData.findings,
    recommendation: formData.recommendation,
    violationAmount: formData.violationAmount || 0,
    createdAt: editingRecord.value?.createdAt || new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  if (isEdit.value && editingRecord.value) {
    const index = mockRecords.findIndex((r) => r.id === editingRecord.value!.id);
    if (index > -1) {
      mockRecords[index] = record;
    }
    ElMessage.success('更新成功');
  } else {
    mockRecords.unshift(record);
    ElMessage.success('新增成功');
  }

  dialogVisible.value = false;
  loadStats();
  loadData();
}

function handleExport() {
  ElMessage.info('导出功能需后端配合实现');
}

function resetForm() {
  const now = new Date().toISOString().slice(0, 10);
  const end = new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10);
  formData.inspectionNo = `FJ-${new Date().getFullYear()}-${String(Math.floor(Math.random() * 9000) + 1000)}`;
  formData.inspectionType = '';
  formData.inspectionDate = now;
  formData.inspectionEndDate = end;
  formData.status = 'draft';
  formData.hospitalName = '';
  formData.hospitalType = '';
  formData.hospitalAddress = '';
  formData.contactPerson = '';
  formData.contactPhone = '';
  formData.teamLeader = '';
  formData.teamMembers = [
    { id: '', name: '', role: '组长', phone: '' },
    { id: '', name: '', role: '检查员', phone: '' },
  ];
  formData.result = 'none';
  formData.findings = '';
  formData.recommendation = '';
  formData.violationAmount = 0;
  editingRecord.value = null;
}

function addTeamMember() {
  formData.teamMembers.push({ id: '', name: '', role: '检查员', phone: '' });
}

function removeTeamMember(index: number) {
  if (formData.teamMembers.length > 1) {
    formData.teamMembers.splice(index, 1);
  }
}

// ==================== 生命周期 ====================

watch(currentPage, loadData);

onMounted(() => {
  loadStats();
  loadData();
});
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <!-- 页面标题 -->
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">飞行检查管理</div>
          <div class="title-sub">飞行检查任务管理，支持检查任务的创建、跟踪、结果记录与统计导出</div>
        </div>
      </div>

      <!-- 统计卡片 -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-value" style="color: #1677ff">{{ stats.total }}</div>
          <div class="stat-label">检查总数</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #faad14">{{ stats.inProgress }}</div>
          <div class="stat-label">进行中</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #52c41a">{{ stats.completed }}</div>
          <div class="stat-label">已完成</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color: #ff4d4f">{{ stats.withIssues }}</div>
          <div class="stat-label">发现问题</div>
        </div>
        <div class="stat-card stat-card--wide">
          <div class="stat-value" style="color: #ff4d4f">
            {{ stats.totalViolationAmount.toFixed(2) }}
            <span class="stat-unit">万元</span>
          </div>
          <div class="stat-label">违规金额</div>
        </div>
      </div>

      <!-- 查询区域 -->
      <div class="query-card">
        <div class="query-row">
          <div class="query-left">
            <div class="query-item">
              <div class="query-label">检查编号</div>
              <el-input
                v-model="searchForm.inspectionNo"
                placeholder="输入检查编号"
                clearable
                style="width: 160px"
              />
            </div>
            <div class="query-item">
              <div class="query-label">医疗机构</div>
              <el-input
                v-model="searchForm.hospitalName"
                placeholder="输入医疗机构名称"
                clearable
                style="width: 180px"
              />
            </div>
            <div class="query-item">
              <div class="query-label">机构类型</div>
              <el-select
                v-model="searchForm.hospitalType"
                placeholder="请选择"
                clearable
                style="width: 140px"
              >
                <el-option
                  v-for="opt in hospitalTypeOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </div>
            <div class="query-item">
              <div class="query-label">检查类型</div>
              <el-select
                v-model="searchForm.inspectionType"
                placeholder="请选择"
                clearable
                style="width: 140px"
              >
                <el-option
                  v-for="opt in inspectionTypeOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </div>
            <div class="query-item">
              <div class="query-label">状态</div>
              <el-select
                v-model="searchForm.status"
                placeholder="请选择"
                clearable
                style="width: 120px"
              >
                <el-option
                  v-for="opt in statusOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </div>
            <div class="query-item">
              <div class="query-label">检查结果</div>
              <el-select
                v-model="searchForm.result"
                placeholder="请选择"
                clearable
                style="width: 120px"
              >
                <el-option
                  v-for="opt in resultOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </div>
            <div class="query-item">
              <div class="query-label">检查日期</div>
              <el-date-picker
                v-model="searchForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
                style="width: 240px"
              />
            </div>
            <div class="query-actions">
              <el-button type="primary" :icon="Search" @click="handleSearch">
                查询
              </el-button>
              <el-button :icon="Refresh" @click="handleReset">重置</el-button>
            </div>
          </div>
          <div class="query-right">
            <el-button type="success" class="create-btn" @click="handleAdd">
              + 新增检查
            </el-button>
          </div>
        </div>
      </div>

      <!-- 表格 -->
      <div class="list-title">检查记录列表</div>
      <div class="table-card">
        <el-table
          :data="allItems"
          v-loading="isLoading"
          border
          style="width: 100%"
          class="task-table"
        >
          <el-table-column
            prop="inspectionNo"
            label="检查编号"
            width="160"
            align="center"
          />
          <el-table-column
            prop="hospital.name"
            label="医疗机构名称"
            min-width="200"
          />
          <el-table-column
            prop="hospital.typeLabel"
            label="机构类型"
            width="120"
            align="center"
          />
          <el-table-column
            prop="inspectionTypeLabel"
            label="检查类型"
            width="110"
            align="center"
          />
          <el-table-column
            prop="inspectionDate"
            label="检查日期"
            width="120"
            align="center"
          />
          <el-table-column
            prop="teamLeader"
            label="检查组组长"
            width="100"
            align="center"
          />
          <el-table-column label="检查结果" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="getResultType(row.result)" size="small">
                {{ row.resultLabel }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row.status)" size="small">
                {{ row.statusLabel }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" align="center" fixed="right">
            <template #default="{ row }">
              <div class="op-cell">
                <div class="op-line">
                  <el-button
                    link
                    type="primary"
                    :icon="View"
                    class="op-btn"
                    @click="handleDetail(row)"
                  >
                    详情
                  </el-button>
                  <span class="op-sep">|</span>
                  <el-button
                    link
                    type="primary"
                    :icon="Edit"
                    class="op-btn"
                    @click="handleEdit(row)"
                  >
                    编辑
                  </el-button>
                  <span class="op-sep">|</span>
                  <el-button
                    link
                    type="danger"
                    :icon="Delete"
                    class="op-btn op-btn--danger"
                    @click="handleDelete(row)"
                  >
                    删除
                  </el-button>
                </div>
              </div>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="暂无数据" />
          </template>
        </el-table>

        <div class="pager">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next, jumper"
            background
            @size-change="(val: number) => { pageSize = val; loadData(); }"
          />
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="900px"
      destroy-on-close
      @closed="resetForm"
    >
      <div class="dialog-body">
        <div class="dialog-section">
          <div class="section-title">基本信息</div>
          <el-form :model="formData" label-width="100px" label-position="top">
            <el-row :gutter="16">
              <el-col :span="8">
                <el-form-item label="检查编号">
                  <el-input v-model="formData.inspectionNo" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="检查类型">
                  <el-select v-model="formData.inspectionType" style="width: 100%">
                    <el-option
                      v-for="opt in inspectionTypeOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="状态">
                  <el-select v-model="formData.status" style="width: 100%">
                    <el-option
                      v-for="opt in statusOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="检查开始日期">
                  <el-date-picker
                    v-model="formData.inspectionDate"
                    type="date"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="检查结束日期">
                  <el-date-picker
                    v-model="formData.inspectionEndDate"
                    type="date"
                    value-format="YYYY-MM-DD"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <div class="dialog-section">
          <div class="section-title">医疗机构信息</div>
          <el-form :model="formData" label-width="100px" label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="医疗机构名称">
                  <el-input v-model="formData.hospitalName" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="机构类型">
                  <el-select v-model="formData.hospitalType" style="width: 100%">
                    <el-option
                      v-for="opt in hospitalTypeOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="24">
                <el-form-item label="机构地址">
                  <el-input v-model="formData.hospitalAddress" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="联系人">
                  <el-input v-model="formData.contactPerson" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="联系电话">
                  <el-input v-model="formData.contactPhone" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>

        <div class="dialog-section">
          <div class="section-title">检查组信息</div>
          <el-form :model="formData" label-width="100px" label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="检查组组长">
                  <el-input v-model="formData.teamLeader" />
                </el-form-item>
              </el-col>
            </el-row>
            <div class="sub-label">检查组成员</div>
            <div
              v-for="(member, index) in formData.teamMembers"
              :key="index"
              class="team-member-row"
            >
              <el-row :gutter="12">
                <el-col :span="7">
                  <el-input v-model="member.name" placeholder="姓名" />
                </el-col>
                <el-col :span="7">
                  <el-input v-model="member.role" placeholder="角色" />
                </el-col>
                <el-col :span="7">
                  <el-input v-model="member.phone" placeholder="联系电话" />
                </el-col>
                <el-col :span="3">
                  <el-button
                    v-if="formData.teamMembers.length > 1"
                    type="danger"
                    :icon="Delete"
                    circle
                    size="small"
                    @click="removeTeamMember(index)"
                  />
                </el-col>
              </el-row>
            </div>
            <el-button type="primary" link :icon="Plus" @click="addTeamMember">
              添加成员
            </el-button>
          </el-form>
        </div>

        <div class="dialog-section">
          <div class="section-title">检查结果</div>
          <el-form :model="formData" label-width="100px" label-position="top">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="检查结果">
                  <el-select v-model="formData.result" style="width: 100%" clearable>
                    <el-option
                      v-for="opt in resultOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="违规金额(元)">
                  <el-input-number
                    v-model="formData.violationAmount"
                    :min="0"
                    :precision="2"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="24">
                <el-form-item label="检查发现">
                  <el-input
                    v-model="formData.findings"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入检查发现的问题..."
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="16">
              <el-col :span="24">
                <el-form-item label="处理建议">
                  <el-input
                    v-model="formData.recommendation"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入处理建议..."
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>
      </div>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      title="检查详情"
      width="800px"
      destroy-on-close
    >
      <div v-if="detailRecord" class="detail-body">
        <div class="dialog-section">
          <div class="section-title">基本信息</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="检查编号">
              {{ detailRecord.inspectionNo }}
            </el-descriptions-item>
            <el-descriptions-item label="检查类型">
              {{ detailRecord.inspectionTypeLabel }}
            </el-descriptions-item>
            <el-descriptions-item label="检查开始日期">
              {{ detailRecord.inspectionDate }}
            </el-descriptions-item>
            <el-descriptions-item label="检查结束日期">
              {{ detailRecord.inspectionEndDate }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(detailRecord.status)" size="small">
                {{ detailRecord.statusLabel }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="检查结果">
              <el-tag :type="getResultType(detailRecord.result)" size="small">
                {{ detailRecord.resultLabel }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="dialog-section">
          <div class="section-title">医疗机构信息</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="医疗机构名称">
              {{ detailRecord.hospital.name }}
            </el-descriptions-item>
            <el-descriptions-item label="机构类型">
              {{ detailRecord.hospital.typeLabel }}
            </el-descriptions-item>
            <el-descriptions-item label="机构地址" :span="2">
              {{ detailRecord.hospital.address }}
            </el-descriptions-item>
            <el-descriptions-item label="联系人">
              {{ detailRecord.hospital.contactPerson }}
            </el-descriptions-item>
            <el-descriptions-item label="联系电话">
              {{ detailRecord.hospital.contactPhone }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="dialog-section">
          <div class="section-title">检查组信息</div>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="检查组组长">
              {{ detailRecord.teamLeader }}
            </el-descriptions-item>
          </el-descriptions>
          <el-table
            :data="detailRecord.inspectionTeam"
            border
            size="small"
            style="margin-top: 10px"
          >
            <el-table-column prop="name" label="成员姓名" />
            <el-table-column prop="role" label="角色" />
            <el-table-column prop="phone" label="联系电话" />
          </el-table>
        </div>

        <div class="dialog-section">
          <div class="section-title">检查结果</div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="违规金额">
              <span style="color: #f56c6c; font-weight: bold">
                {{
                  detailRecord.violationAmount > 0
                    ? detailRecord.violationAmount.toLocaleString() + ' 元'
                    : '无'
                }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="检查发现">
              {{ detailRecord.findings || '暂无' }}
            </el-descriptions-item>
            <el-descriptions-item label="处理建议">
              {{ detailRecord.recommendation || '暂无' }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 外层 */
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
  box-sizing: border-box;
}

.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 18px 16px;
  box-shadow: 0 2px 10px rgba(16, 24, 40, 0.06);
}

/* 标题 */
.page-title {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0 14px;
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
  line-height: 1.2;
}
.title-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}
.stat-card {
  flex: 1;
  min-width: 120px;
  background: #f7f9fc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
}
.stat-card--wide {
  flex: 2;
  min-width: 180px;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-unit {
  font-size: 14px;
  font-weight: 400;
}
.stat-label {
  margin-top: 6px;
  font-size: 13px;
  color: #667085;
}

/* 查询区 */
.query-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 14px 14px 12px;
  margin-bottom: 14px;
}
.query-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.query-left {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px 16px;
}
.query-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.query-label {
  font-size: 12px;
  color: #667085;
}
.query-actions {
  display: flex;
  gap: 10px;
  padding-bottom: 2px;
}
.query-right {
  display: flex;
  align-items: flex-end;
}
.create-btn {
  padding: 10px 14px;
  border-radius: 6px;
  font-weight: 600;
}

/* 列表标题 */
.list-title {
  font-size: 14px;
  font-weight: 600;
  color: #344054;
  margin: 10px 0 10px;
}

/* 表格卡片 */
.table-card {
  border: 1px solid #eef2f7;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}
.task-table :deep(.el-table__header th) {
  background: #f7f9fc !important;
  color: #475467;
  font-weight: 600;
  height: 46px;
}
.task-table :deep(.el-table__row td) {
  height: 56px;
}

/* 操作列 */
.op-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}
.op-line {
  display: flex;
  align-items: center;
  gap: 0;
}
.op-btn {
  padding: 0 4px;
  font-size: 13px;
}
.op-sep {
  color: #dcdfe6;
  margin: 0 2px;
}

/* 分页 */
.pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 16px;
}

/* 弹窗样式 */
.dialog-body {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: 4px;
}
.dialog-section {
  margin-bottom: 16px;
}
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  padding-left: 8px;
  border-left: 3px solid #409eff;
}
.sub-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}
.team-member-row {
  margin-bottom: 8px;
}

/* 详情 */
.detail-body {
  max-height: 65vh;
  overflow-y: auto;
}
</style>