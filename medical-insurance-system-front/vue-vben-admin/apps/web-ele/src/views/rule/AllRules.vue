<script lang="ts" setup>
import { onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { ElMessage, ElMessageBox } from 'element-plus';

import {
  createRule,
  deleteRule,
  getRuleList,
  toggleRuleStatus,
  updateRule,
} from '#/api/rule';
import { getRuleTypeLabel, RULE_TYPE_OPTIONS } from '#/config/rule-type';

const router = useRouter();

const loading = ref(false);
const list = ref<any[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const detailVisible = ref(false);
const currentDetail = ref<any>(null);
const dialogVisible = ref(false);
const editingId = ref<null | number | string>(null);

const searchForm = reactive({
  keyword: '',
  type: '',
  status: '',
});

const form = reactive({
  id: '',
  ruleId: '',
  drugName: '',
  type: '超限定用药',
  description: '',
  enabled: false,
  ruleCode: '',
});

const typeOptions = RULE_TYPE_OPTIONS;
const statusOptions = [
  { label: 'Enabled', value: 'true' },
  { label: 'Disabled', value: 'false' },
];

const routeMap: Record<string, string> = {
  '超限定用药': 'RuleLimitedDrug',
  '超标准收费': 'RuleOverStandardFee',
  '重复收费': 'RuleDuplicateCharge',
  '过度医疗': 'RuleOverMedical',
  '超频次收费': 'RuleFakeFee',
};

const hasExecutableCode = (value?: string | null) => Boolean((value || '').trim());
const isCompiled = (rule: { ruleCode?: string | null; rule_code?: string | null }) =>
  Boolean((rule.rule_code || rule.ruleCode || '').trim());
const normalizeEnabledState = (enabled: boolean, ruleCode?: string | null) =>
  hasExecutableCode(ruleCode) ? enabled : false;

const formatDate = (value?: string) => {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', { hour12: false });
};

const fetchData = async () => {
  loading.value = true;
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value,
    };
    if (searchForm.keyword.trim()) params.search = searchForm.keyword.trim();
    if (searchForm.type) params.type = searchForm.type;
    if (searchForm.status) params.status = searchForm.status === 'true';

    const res = await getRuleList(params);
    const rawList = res?.results || (Array.isArray(res) ? res : []);
    list.value = rawList.map((item: any) => ({
      ...item,
      ruleId: item.ruleId || item.rule_id || `R-${item.id}`,
      drugName: item.drugName || item.drug_name || '-',
      createdAt: item.created_at || '',
      updatedAt: item.updated_at || '',
      ruleCode: item.rule_code || item.ruleCode || '',
      rule_code: item.rule_code || item.ruleCode || '',
      enabled: normalizeEnabledState(
        Boolean(item.enabled),
        item.rule_code || item.ruleCode || '',
      ),
    }));
    total.value = res?.count || rawList.length || 0;
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to load all rules.');
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
  searchForm.type = '';
  searchForm.status = '';
  currentPage.value = 1;
  fetchData();
};

const openDetail = (row: any) => {
  currentDetail.value = { ...row };
  detailVisible.value = true;
};

const resetForm = () => {
  form.id = '';
  form.ruleId = '';
  form.drugName = '';
  form.type = '超限定用药';
  form.description = '';
  form.enabled = false;
  form.ruleCode = '';
};

const openAdd = () => {
  editingId.value = null;
  resetForm();
  dialogVisible.value = true;
};

const openEdit = (row: any) => {
  editingId.value = row.id;
  form.id = String(row.id || '');
  form.ruleId = row.ruleId || '';
  form.drugName = row.drugName || '';
  form.type = row.type || '超限定用药';
  form.description = row.description || '';
  form.ruleCode = row.ruleCode || row.rule_code || '';
  form.enabled = normalizeEnabledState(Boolean(row.enabled), form.ruleCode);
  dialogVisible.value = true;
};

const save = async () => {
  if (!form.description.trim()) {
    ElMessage.warning('Please enter the original description.');
    return;
  }
  if (!form.drugName.trim()) {
    ElMessage.warning('Please enter the rule name.');
    return;
  }

  const payload = {
    drugName: form.drugName,
    ruleId: form.ruleId || undefined,
    type: form.type,
    description: form.description,
    enabled: form.enabled,
    logicExpression: '',
    rule_code: form.ruleCode,
  };

  try {
    if (editingId.value) {
      await updateRule(editingId.value, payload);
      ElMessage.success('Rule updated.');
    } else {
      await createRule(payload);
      ElMessage.success('Rule created.');
    }
    dialogVisible.value = false;
    fetchData();
  } catch (error: any) {
    console.error(error);
    const message =
      error?.response?.data?.enabled?.[0] ||
      error?.response?.data?.enabled ||
      error?.response?.data?.detail ||
      'Failed to save the rule.';
    ElMessage.error(message);
  }
};

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`Delete rule "${row.drugName}"?`, 'Delete Confirmation', {
    type: 'warning',
    confirmButtonText: 'Delete',
    cancelButtonText: 'Cancel',
  });
  try {
    await deleteRule(row.id);
    ElMessage.success('Rule deleted.');
    fetchData();
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to delete the rule.');
  }
};

const handleStatusChange = async (row: any) => {
  if (!hasExecutableCode(row.ruleCode || row.rule_code)) {
    row.enabled = false;
    ElMessage.warning('Compile the rule before enabling it.');
    return;
  }
  const originalStatus = !row.enabled;
  try {
    await toggleRuleStatus(row.id, row.enabled);
    ElMessage.success(row.enabled ? 'Rule enabled.' : 'Rule disabled.');
  } catch (error: any) {
    row.enabled = originalStatus;
    const message =
      error?.response?.data?.enabled?.[0] ||
      error?.response?.data?.enabled ||
      error?.response?.data?.detail ||
      'Failed to update the rule status.';
    ElMessage.error(message);
  }
};

const goToTypeRule = (type: string) => {
  const routeName = routeMap[type];
  if (routeName) router.push({ name: routeName });
};

onMounted(fetchData);
</script>

<template>
  <div class="page-card">
    <div class="header">
      <div class="title">
        <span class="bar"></span>
        <span>All Rules</span>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openAdd">Add</el-button>
        <el-input
          v-model="searchForm.keyword"
          clearable
          style="width: 260px"
          placeholder="Search by rule name / ID / description"
          @keyup.enter="handleSearch"
        />
        <el-select
          v-model="searchForm.type"
          clearable
          style="width: 160px"
          placeholder="Rule Type"
        >
          <el-option
            v-for="item in typeOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-select
          v-model="searchForm.status"
          clearable
          style="width: 120px"
          placeholder="Status"
        >
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" @click="handleSearch">Search</el-button>
        <el-button @click="handleReset">Reset</el-button>
      </div>
    </div>

    <el-table
      v-loading="loading"
      :data="list"
      border
      stripe
      row-key="id"
      style="width: 100%"
    >
      <el-table-column prop="drugName" label="Rule Name" min-width="180">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">
            {{ row.drugName }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column prop="ruleId" label="Rule ID" width="160" />
      <el-table-column prop="type" label="Rule Type" width="160" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="goToTypeRule(row.type)">
            {{ getRuleTypeLabel(row.type) }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="Compilation" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="isCompiled(row) ? 'success' : 'warning'">
            {{ isCompiled(row) ? 'Compiled' : 'Not Compiled' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Status" width="120" align="center">
        <template #default="{ row }">
          <el-tooltip
            :disabled="hasExecutableCode(row.ruleCode || row.rule_code)"
            content="Compile the rule before enabling it."
            placement="top"
          >
            <span class="switch-wrapper">
              <el-switch
                v-model="row.enabled"
                inline-prompt
                active-text="On"
                inactive-text="Off"
                active-color="#16a34a"
                inactive-color="#64748b"
                :disabled="!hasExecutableCode(row.ruleCode || row.rule_code)"
                @change="handleStatusChange(row)"
              />
            </span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="Created At" min-width="180">
        <template #default="{ row }">
          {{ formatDate(row.createdAt) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="description"
        label="Description"
        min-width="280"
        show-overflow-tooltip
      />
      <el-table-column label="Actions" width="220" fixed="right" align="center">
        <template #default="{ row }">
          <div class="op-links">
            <el-button link type="primary" class="op-btn" @click="openDetail(row)">
              View
            </el-button>
            <span class="op-sep">|</span>
            <el-button link type="primary" class="op-btn" @click="openEdit(row)">
              Edit
            </el-button>
            <span class="op-sep">|</span>
            <el-button link type="danger" class="op-btn" @click="handleDelete(row)">
              Delete
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="footer-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @current-change="fetchData"
        @size-change="fetchData"
      />
    </div>

    <el-dialog
      v-model="detailVisible"
      title="Rule Details"
      width="900px"
      append-to-body
    >
      <el-descriptions
        v-if="currentDetail"
        border
        :column="2"
        size="large"
        class="detail-table"
      >
        <el-descriptions-item label="Rule ID">
          {{ currentDetail.ruleId }}
        </el-descriptions-item>
        <el-descriptions-item label="Rule Name">
          {{ currentDetail.drugName }}
        </el-descriptions-item>
        <el-descriptions-item label="Rule Type">
          {{ getRuleTypeLabel(currentDetail.type) }}
        </el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag :type="currentDetail.enabled ? 'success' : 'danger'">
            {{ currentDetail.enabled ? 'Enabled' : 'Disabled' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Created At">
          {{ formatDate(currentDetail.createdAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="Updated At">
          {{ formatDate(currentDetail.updatedAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="Description" :span="2">
          {{ currentDetail.description || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="Execution Code" :span="2">
          <div class="code-scroll-box">
            <pre>{{ currentDetail.ruleCode || currentDetail.rule_code || 'No code available.' }}</pre>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      width="980px"
      :title="editingId ? 'Edit Rule' : 'Add Rule'"
      destroy-on-close
    >
      <el-form label-width="140px">
        <el-form-item label="Rule Name">
          <el-input v-model="form.drugName" />
        </el-form-item>

        <el-form-item label="Rule Type">
          <el-select v-model="form.type" style="width: 220px">
            <el-option
              v-for="item in typeOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="Original Description">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item label="Enabled">
          <el-tooltip
            :disabled="hasExecutableCode(form.ruleCode)"
            content="Compile the rule before enabling it."
            placement="top"
          >
            <span class="switch-wrapper">
              <el-switch
                v-model="form.enabled"
                active-color="#16a34a"
                inactive-color="#64748b"
                :disabled="!hasExecutableCode(form.ruleCode)"
              />
            </span>
          </el-tooltip>
        </el-form-item>

        <el-form-item label="Rule Code (Python)">
          <el-input
            v-model="form.ruleCode"
            type="textarea"
            :rows="6"
            placeholder="def execute_rule(ctx): ..."
            style="font-family: monospace"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-card {
  background: #fff;
  border-radius: 14px;
  padding: 18px 18px 14px;
  box-shadow: 0 8px 26px rgba(16, 24, 40, 0.08);
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.bar {
  width: 4px;
  height: 18px;
  border-radius: 10px;
  background: #3b82f6;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

:deep(.el-table th) {
  background: #f8fafc !important;
}

.op-links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.op-sep {
  color: #dcdfe6;
  font-size: 12px;
}

.op-btn {
  padding: 0;
  font-size: 13px;
}

.switch-wrapper {
  display: inline-flex;
}

:deep(.el-switch.is-disabled) {
  opacity: 0.85;
}

:deep(.el-switch.is-disabled .el-switch__core) {
  border-color: #475569;
  background-color: #64748b;
}

:deep(.el-switch.is-disabled .el-switch__inner .is-text) {
  color: #f8fafc;
}

.detail-table :deep(.el-descriptions__label) {
  width: 140px;
  font-weight: 600;
  color: #606266;
  background-color: #f9fafb;
}

.detail-table :deep(.el-descriptions__content) {
  color: #303133;
}

.code-scroll-box {
  max-height: 400px;
  overflow-y: auto;
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
}

.code-scroll-box pre {
  margin: 0;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.footer-pagination {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
</style>
