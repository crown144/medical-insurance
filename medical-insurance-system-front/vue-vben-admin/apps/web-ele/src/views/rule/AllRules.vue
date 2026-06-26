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
  enabled: true,
  ruleCode: '',
});

const typeOptions = ['超限定用药', '重复收费', '超标准收费', '过度医疗', '超频次收费'];
const statusOptions = [
  { label: '启用', value: 'true' },
  { label: '停用', value: 'false' },
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
      enabled: Boolean(item.enabled),
      ruleCode: item.rule_code || item.ruleCode || '',
      rule_code: item.rule_code || item.ruleCode || '',
    }));
    total.value = res?.count || rawList.length || 0;
  } catch (error) {
    console.error(error);
    ElMessage.error('获取全部规则列表失败');
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
  form.enabled = true;
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
  form.enabled = Boolean(row.enabled);
  form.ruleCode = row.ruleCode || row.rule_code || '';
  dialogVisible.value = true;
};

const save = async () => {
  if (!form.description.trim()) {
    ElMessage.warning('请填写原始描述');
    return;
  }
  if (!form.drugName.trim()) {
    ElMessage.warning('请填写规则名称');
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
      ElMessage.success('已更新');
    } else {
      await createRule(payload);
      ElMessage.success('已新增');
    }
    dialogVisible.value = false;
    fetchData();
  } catch (error: any) {
    console.error(error);
    const message =
      error?.response?.data?.enabled?.[0] ||
      error?.response?.data?.enabled ||
      error?.response?.data?.detail ||
      '保存失败';
    ElMessage.error(message);
  }
};

const handleDelete = async (row: any) => {
  await ElMessageBox.confirm(`确定删除规则【${row.drugName}】？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  });
  try {
    await deleteRule(row.id);
    ElMessage.success('已删除');
    fetchData();
  } catch (error) {
    console.error(error);
    ElMessage.error('删除失败');
  }
};

const handleStatusChange = async (row: any) => {
  if (!hasExecutableCode(row.ruleCode || row.rule_code)) {
    row.enabled = false;
    ElMessage.warning('该规则未生成执行代码，无法启用');
    return;
  }
  const originalStatus = !row.enabled;
  try {
    await toggleRuleStatus(row.id, row.enabled);
    ElMessage.success(row.enabled ? '已启用' : '已停用');
  } catch (error: any) {
    row.enabled = originalStatus;
    const message =
      error?.response?.data?.enabled?.[0] ||
      error?.response?.data?.enabled ||
      error?.response?.data?.detail ||
      '状态更新失败';
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
        <span>全部规则</span>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openAdd">新增</el-button>
        <el-input
          v-model="searchForm.keyword"
          clearable
          style="width: 260px"
          placeholder="搜索规则名称/编码/描述"
          @keyup.enter="handleSearch"
        />
        <el-select
          v-model="searchForm.type"
          clearable
          style="width: 160px"
          placeholder="规则分类"
        >
          <el-option
            v-for="item in typeOptions"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
        <el-select
          v-model="searchForm.status"
          clearable
          style="width: 120px"
          placeholder="状态"
        >
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
        <el-button @click="handleReset">重置</el-button>
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
      <el-table-column prop="drugName" label="规则名称" min-width="180">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">
            {{ row.drugName }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column prop="ruleId" label="规则编码" width="160" />
      <el-table-column prop="type" label="规则分类" width="160" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="goToTypeRule(row.type)">
            {{ row.type }}
          </el-button>
        </template>
      </el-table-column>
      <el-table-column label="编译状态" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="isCompiled(row) ? 'success' : 'warning'">
            {{ isCompiled(row) ? '已编译' : '未编译' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120" align="center">
        <template #default="{ row }">
          <el-tooltip
            :disabled="hasExecutableCode(row.ruleCode || row.rule_code)"
            content="该规则未生成执行代码，无法启用"
            placement="top"
          >
            <span class="switch-wrapper">
              <el-switch
                v-model="row.enabled"
                inline-prompt
                active-text="启"
                inactive-text="停"
                :disabled="!hasExecutableCode(row.ruleCode || row.rule_code)"
                @change="handleStatusChange(row)"
              />
            </span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="180">
        <template #default="{ row }">
          {{ formatDate(row.createdAt) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="description"
        label="规则描述"
        min-width="280"
        show-overflow-tooltip
      />
      <el-table-column label="操作" width="220" fixed="right" align="center">
        <template #default="{ row }">
          <div class="op-links">
            <el-button link type="primary" class="op-btn" @click="openDetail(row)">
              详情
            </el-button>
            <span class="op-sep">|</span>
            <el-button link type="primary" class="op-btn" @click="openEdit(row)">
              编辑
            </el-button>
            <span class="op-sep">|</span>
            <el-button link type="danger" class="op-btn" @click="handleDelete(row)">
              删除
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
      title="规则详情"
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
        <el-descriptions-item label="规则编码">
          {{ currentDetail.ruleId }}
        </el-descriptions-item>
        <el-descriptions-item label="规则名称">
          {{ currentDetail.drugName }}
        </el-descriptions-item>
        <el-descriptions-item label="规则分类">
          {{ currentDetail.type }}
        </el-descriptions-item>
        <el-descriptions-item label="规则状态">
          <el-tag :type="currentDetail.enabled ? 'success' : 'danger'">
            {{ currentDetail.enabled ? '启用' : '停用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">
          {{ formatDate(currentDetail.createdAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatDate(currentDetail.updatedAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="规则描述" :span="2">
          {{ currentDetail.description || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="规则执行代码" :span="2">
          <div class="code-scroll-box">
            <pre>{{ currentDetail.ruleCode || currentDetail.rule_code || '暂无代码' }}</pre>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-dialog
      v-model="dialogVisible"
      width="980px"
      :title="editingId ? '编辑规则' : '新增规则'"
      destroy-on-close
    >
      <el-form label-width="140px">
        <el-form-item label="规则名称">
          <el-input v-model="form.drugName" />
        </el-form-item>

        <el-form-item label="规则类型">
          <el-select v-model="form.type" style="width: 220px">
            <el-option
              v-for="item in typeOptions"
              :key="item"
              :label="item"
              :value="item"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="原始描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item label="是否启用">
          <el-tooltip
            :disabled="hasExecutableCode(form.ruleCode)"
            content="该规则未生成执行代码，无法启用"
            placement="top"
          >
            <span class="switch-wrapper">
              <el-switch
                v-model="form.enabled"
                :disabled="!hasExecutableCode(form.ruleCode)"
              />
            </span>
          </el-tooltip>
        </el-form-item>

        <el-form-item label="规则代码 (Python)">
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
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
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
