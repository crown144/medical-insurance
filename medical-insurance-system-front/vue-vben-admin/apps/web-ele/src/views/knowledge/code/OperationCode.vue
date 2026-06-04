<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { View } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

interface OperationRow {
  id: string;
  code: string; // 操作代码
  name: string; // 手术名称
  department: string; // 临床学科

  // 详情字段 (详情弹窗展示)
  icd10pcs: string;
  category: string; // 操作类别
  systemCode: string; // 元码躯体器官系统元码
  mainCode: string; // 主操作元码
  partCode: string; // 躯体器官/部件元码
  approachCode: string; // 手术与操作入路元码
  deviceCode: string; // 装置器材元码
  qualifierCode: string; // 限定属性元码
}

// 模拟数据
const seedList: OperationRow[] = [
  {
    id: '1',
    department: '泌尿外科',
    name: '肾上腺区探查术，左侧',
    code: '0GJ20ZZ',
    icd10pcs: '0GJ20ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'J检查/探查术',
    partCode: '2左侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '2',
    department: '泌尿外科',
    name: '肾上腺区探查术，右侧',
    code: '0GJ30ZZ',
    icd10pcs: '0GJ30ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'J检查/探查术',
    partCode: '3右侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '3',
    department: '泌尿外科',
    name: '双侧肾上腺区探查术',
    code: '0GJ40ZZ',
    icd10pcs: '0GJ40ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'J检查/探查术',
    partCode: '4双侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '4',
    department: '泌尿外科',
    name: '肾上腺切除术，左侧',
    code: '0GT20ZZ',
    icd10pcs: '0GT20ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'T全切除术',
    partCode: '2左侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '5',
    department: '泌尿外科',
    name: '肾上腺切除术，右侧',
    code: '0GT30ZZ',
    icd10pcs: '0GT30ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'T全切除术',
    partCode: '3右侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '6',
    department: '泌尿外科',
    name: '双侧肾上腺切除术',
    code: '0GT40ZZ',
    icd10pcs: '0GT40ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'T全切除术',
    partCode: '4双侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '7',
    department: '泌尿外科',
    name: '肾上腺肿瘤切除术，左侧',
    code: '0GB20ZZ',
    icd10pcs: '0GB20ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'B部分切除术',
    partCode: '2左侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '8',
    department: '泌尿外科',
    name: '肾上腺肿瘤切除术，右侧',
    code: '0GB30ZZ',
    icd10pcs: '0GB30ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'B部分切除术',
    partCode: '3右侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '9',
    department: '泌尿外科',
    name: '肾上腺嗜铬细胞瘤切除术，左侧',
    code: '0GB20ZZ',
    icd10pcs: '0GB20ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'B部分切除术',
    partCode: '2左侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '10',
    department: '泌尿外科',
    name: '肾上腺嗜铬细胞瘤切除术，右侧',
    code: '0GB30ZZ',
    icd10pcs: '0GB30ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'B部分切除术',
    partCode: '3右侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '11',
    department: '泌尿外科',
    name: '肾上腺部分切除术，左侧',
    code: '0GB20ZZ',
    icd10pcs: '0GB20ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'B部分切除术',
    partCode: '2左侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
  {
    id: '12',
    department: '泌尿外科',
    name: '肾上腺部分切除术，右侧',
    code: '0GB30ZZ',
    icd10pcs: '0GB30ZZ',
    category: '0一般手术与操作',
    systemCode: 'G内分泌系统',
    mainCode: 'B部分切除术',
    partCode: '3右侧肾上腺',
    approachCode: '0开放入路',
    deviceCode: 'Z无置入装置',
    qualifierCode: 'Z无限定',
  },
];

const list = ref<OperationRow[]>(seedList);
const keyword = ref('');
const selectedRows = ref<OperationRow[]>([]);

// 过滤列表
const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return list.value;
  return list.value.filter(
    (item) =>
      item.code.toLowerCase().includes(kw) ||
      item.name.toLowerCase().includes(kw) ||
      item.department.toLowerCase().includes(kw),
  );
});

// 选中
function onSelectionChange(rows: OperationRow[]) {
  selectedRows.value = rows;
}

// 弹窗相关
const dialogVisible = ref(false);
const isEdit = ref(false);
const form = reactive<OperationRow>({
  id: '',
  code: '',
  name: '',
  department: '',
  icd10pcs: '',
  category: '',
  systemCode: '',
  mainCode: '',
  partCode: '',
  approachCode: '',
  deviceCode: '',
  qualifierCode: '',
});

// 详情弹窗相关
const detailVisible = ref(false);
const currentDetail = ref<null | OperationRow>(null);

function openAdd() {
  isEdit.value = false;
  Object.assign(form, {
    id: Date.now().toString(),
    code: '',
    name: '',
    department: '',
    icd10pcs: '',
    category: '',
    systemCode: '',
    mainCode: '',
    partCode: '',
    approachCode: '',
    deviceCode: '',
    qualifierCode: '',
  });
  dialogVisible.value = true;
}

function openEdit(row: OperationRow) {
  isEdit.value = true;
  Object.assign(form, { ...row });
  dialogVisible.value = true;
}

function openDetail(row: OperationRow) {
  currentDetail.value = { ...row };
  detailVisible.value = true;
}

function save() {
  if (!form.code || !form.name) {
    ElMessage.warning('请至少填写编码和名称');
    return;
  }

  if (isEdit.value) {
    const index = list.value.findIndex((item) => item.id === form.id);
    if (index !== -1) {
      list.value[index] = { ...form };
      ElMessage.success('更新成功');
    }
  } else {
    list.value.unshift({ ...form });
    ElMessage.success('新增成功');
  }
  dialogVisible.value = false;
}

function remove(row: OperationRow) {
  ElMessageBox.confirm(`确定删除【${row.name}】吗？`, '提示', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => {
    list.value = list.value.filter((item) => item.id !== row.id);
    ElMessage.success('删除成功');
  });
}

function bulkDelete() {
  if (selectedRows.value.length === 0) return;
  ElMessageBox.confirm(
    `确定删除选中的 ${selectedRows.value.length} 条数据吗？`,
    '提示',
    {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    },
  ).then(() => {
    const ids = new Set(selectedRows.value.map((r) => r.id));
    list.value = list.value.filter((item) => !ids.has(item.id));
    selectedRows.value = [];
    ElMessage.success('批量删除成功');
  });
}
</script>

<template>
  <div class="page-card">
    <!-- Header -->
    <div class="header">
      <div class="title">
        <span class="bar"></span>
        <span>手术与操作编码库</span>
      </div>

      <div class="header-actions">
        <el-input
          v-model="keyword"
          clearable
          style="width: 320px"
          placeholder="搜索：编码/名称/学科"
        />
        <el-button type="primary" @click="openAdd">新增</el-button>
      </div>
    </div>

    <!-- Bulk Action -->
    <div v-if="selectedRows.length > 0" class="bulk-bar">
      <div class="bulk-left">已选择 {{ selectedRows.length }} 条</div>
      <div class="bulk-right">
        <el-button type="danger" @click="bulkDelete">批量删除</el-button>
      </div>
    </div>

    <!-- Table -->
    <el-table
      :data="filteredList"
      border
      stripe
      row-key="id"
      style="width: 100%"
      @selection-change="onSelectionChange"
    >
      <el-table-column type="selection" width="45" align="center" />
      <el-table-column
        prop="code"
        label="操作代码"
        width="150"
        show-overflow-tooltip
        fixed
      />
      <el-table-column
        prop="name"
        label="手术名称"
        min-width="200"
        show-overflow-tooltip
      />
      <el-table-column
        prop="department"
        label="临床学科"
        width="180"
        show-overflow-tooltip
      />

      <el-table-column label="操作" width="220" fixed="right" align="center">
        <template #default="scope">
          <div class="op-links">
            <el-button
              link
              type="primary"
              :icon="View"
              class="op-btn"
              @click="openDetail(scope.row)"
            >
              详情
            </el-button>
            <span class="op-sep">|</span>
            <el-button
              link
              type="primary"
              class="op-btn"
              @click="openEdit(scope.row)"
            >
              编辑
            </el-button>
            <span class="op-sep">|</span>
            <el-button
              link
              type="danger"
              class="op-btn"
              @click="remove(scope.row)"
            >
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑' : '新增'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="form" label-width="140px">
        <el-form-item label="操作代码" required>
          <el-input v-model="form.code" />
        </el-form-item>
        <el-form-item label="手术名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="临床学科">
          <el-input v-model="form.department" />
        </el-form-item>
        <el-divider content-position="left">详情信息</el-divider>
        <el-form-item label="ICD10-PCS">
          <el-input v-model="form.icd10pcs" />
        </el-form-item>
        <el-form-item label="操作类别">
          <el-input v-model="form.category" />
        </el-form-item>
        <el-form-item label="元码躯体器官系统">
          <el-input v-model="form.systemCode" />
        </el-form-item>
        <el-form-item label="主操作元码">
          <el-input v-model="form.mainCode" />
        </el-form-item>
        <el-form-item label="躯体器官/部件">
          <el-input v-model="form.partCode" />
        </el-form-item>
        <el-form-item label="手术与操作入路">
          <el-input v-model="form.approachCode" />
        </el-form-item>
        <el-form-item label="装置器材元码">
          <el-input v-model="form.deviceCode" />
        </el-form-item>
        <el-form-item label="限定属性元码">
          <el-input v-model="form.qualifierCode" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- Detail Dialog -->
    <el-dialog
      v-model="detailVisible"
      title="手术详情"
      width="700px"
      append-to-body
    >
      <el-descriptions
        v-if="currentDetail"
        border
        :column="1"
        size="large"
        class="detail-table"
      >
        <el-descriptions-item label="ICD10-PCS">
          {{ currentDetail.icd10pcs || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="操作类别">
          {{ currentDetail.category || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="元码躯体器官系统元码">
          {{ currentDetail.systemCode || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="主操作元码">
          {{ currentDetail.mainCode || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="躯体器官/部件元码">
          {{ currentDetail.partCode || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="手术与操作入路元码">
          {{ currentDetail.approachCode || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="装置器材元码">
          {{ currentDetail.deviceCode || 'NULL' }}
        </el-descriptions-item>
        <el-descriptions-item label="限定属性元码">
          {{ currentDetail.qualifierCode || 'NULL' }}
        </el-descriptions-item>
      </el-descriptions>
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
}
.bulk-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #f6f9ff;
  border: 1px solid #dbeafe;
  color: #1f2937;
  padding: 10px 12px;
  border-radius: 12px;
  margin-bottom: 10px;
}
.bulk-left {
  font-weight: 600;
}
:deep(.el-table th) {
  background: #f8fafc !important;
}

/* 操作列样式 */
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

/* 详情表格样式 */
.detail-table :deep(.el-descriptions__label) {
  width: 180px;
  font-weight: 600;
  color: #606266;
  background-color: #f9fafb;
}
.detail-table :deep(.el-descriptions__content) {
  color: #303133;
}
</style>
