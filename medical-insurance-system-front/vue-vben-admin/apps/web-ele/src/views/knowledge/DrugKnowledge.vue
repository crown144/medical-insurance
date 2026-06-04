<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { ElMessage, ElMessageBox } from 'element-plus';

interface DrugRow {
  id: string;
  drugCode: string; // 药品代码
  regName: string; // 注册名称
  regDosage: string; // 注册剂型
  regSpec: string; // 注册规格
  productName: string; // 商品名称
  dosage: string; // 剂型
  spec: string; // 规格
  packageMaterial: string; // 包装材质
  minPackageCount: string; // 最小包装数量
  minPrepUnit: string; // 最小制剂单位
  minPackageUnit: string; // 最小包装单位
  company: string; // 药品企业
  approvalNumber: string; // 批准文号
  standardCode: string; // 药品本位码

  // 国家医保药品目录
  insuranceCategory: string; // 甲乙类
  insuranceCode: string; // 编号
  insuranceName: string; // 药品名称
  insuranceDosage: string; // 剂型
  insuranceRemark: string; // 备注
}

// 模拟数据
const seedList: DrugRow[] = [
  {
    id: '1',
    drugCode: 'XA01ABD075A002010100483',
    regName: '地喹氯铵含片',
    regDosage: '片剂(口含)',
    regSpec: '0.25mg',
    productName: '无',
    dosage: '片剂(口含)',
    spec: '0.25mg',
    packageMaterial: '铝塑',
    minPackageCount: '24',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '汕头经济特区明治医药有限公司',
    approvalNumber: '国药准字H20067255',
    standardCode: '86900483000019',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '2',
    drugCode: 'XA01ABD075A002010100594',
    regName: '地喹氯铵含片',
    regDosage: '片剂(含片)',
    regSpec: '(1)0.25mg(2)0.25mg(无糖型)',
    productName: '无',
    dosage: '含片',
    spec: '0.25mg',
    packageMaterial: '铝塑包装',
    minPackageCount: '12',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '珠海同源药业有限公司',
    approvalNumber: '国药准字H44024254',
    standardCode: '86900594000342',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '3',
    drugCode: 'XA01ABD075A002010200144',
    regName: '地喹氯铵含片',
    regDosage: '片剂',
    regSpec: '0.25mg',
    productName: '无',
    dosage: '片剂',
    spec: '0.25mg',
    packageMaterial: '双铝泡罩包装',
    minPackageCount: '12',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '华润双鹤药业股份有限公司',
    approvalNumber: '国药准字H11021869',
    standardCode: '86900144005704',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '4',
    drugCode: 'XA01ABD075A002010200483',
    regName: '地喹氯铵含片',
    regDosage: '片剂(口含)',
    regSpec: '0.25mg',
    productName: '无',
    dosage: '片剂(口含)',
    spec: '0.25mg',
    packageMaterial: '铝塑',
    minPackageCount: '12',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '汕头经济特区明治医药有限公司',
    approvalNumber: '国药准字H20067255',
    standardCode: '86900483000019',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '5',
    drugCode: 'XA01ABD075A002010200594',
    regName: '地喹氯铵含片',
    regDosage: '片剂(含片)',
    regSpec: '(1)0.25mg(2)0.25mg(无糖型)',
    productName: '无',
    dosage: '含片',
    spec: '0.25mg',
    packageMaterial: '铝塑包装',
    minPackageCount: '24',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '珠海同源药业有限公司',
    approvalNumber: '国药准字H44024254',
    standardCode: '86900594000342',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '6',
    drugCode: 'XA01ABD075A002010300144',
    regName: '地喹氯铵含片',
    regDosage: '片剂',
    regSpec: '0.25mg',
    productName: '无',
    dosage: '片剂',
    spec: '0.25mg',
    packageMaterial: '双铝泡罩包装',
    minPackageCount: '6',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '华润双鹤药业股份有限公司',
    approvalNumber: '国药准字H11021869',
    standardCode: '86900144005704',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '7',
    drugCode: 'XA01ABD075A002010300483',
    regName: '地喹氯铵含片',
    regDosage: '片剂(口含)',
    regSpec: '0.25mg',
    productName: '无',
    dosage: '片剂(口含)',
    spec: '0.25mg',
    packageMaterial: '铝塑',
    minPackageCount: '6',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '汕头经济特区明治医药有限公司',
    approvalNumber: '国药准字H20067255',
    standardCode: '86900483000019',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '8',
    drugCode: 'XA01ABD075A002010400144',
    regName: '地喹氯铵含片',
    regDosage: '片剂',
    regSpec: '0.25mg',
    productName: '无',
    dosage: '片剂',
    spec: '0.25mg',
    packageMaterial: '双铝泡罩包装',
    minPackageCount: '18',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '华润双鹤药业股份有限公司',
    approvalNumber: '国药准字H11021869',
    standardCode: '86900144005704',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '9',
    drugCode: 'XA01ABD075A002020100594',
    regName: '地喹氯铵含片',
    regDosage: '片剂',
    regSpec: '(1)0.25mg(2)0.25mg(无糖型)',
    productName: '无',
    dosage: '片剂(含片)',
    spec: '0.25mg(无糖型)',
    packageMaterial: '铝塑包装',
    minPackageCount: '6',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '珠海同源药业有限公司',
    approvalNumber: '国药准字H44024254',
    standardCode: '86900594000335',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '10',
    drugCode: 'XA01ABD075A002020200594',
    regName: '地喹氯铵含片',
    regDosage: '片剂',
    regSpec: '(1)0.25mg(2)0.25mg(无糖型)',
    productName: '无',
    dosage: '片剂(含片)',
    spec: '0.25mg(无糖型)',
    packageMaterial: '铝塑包装',
    minPackageCount: '12',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '珠海同源药业有限公司',
    approvalNumber: '国药准字H44024254',
    standardCode: '86900594000335',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
  {
    id: '11',
    drugCode: 'XA01ABD075A002020300594',
    regName: '地喹氯铵含片',
    regDosage: '片剂',
    regSpec: '(1)0.25mg(2)0.25mg(无糖型)',
    productName: '无',
    dosage: '片剂(含片)',
    spec: '0.25mg(无糖型)',
    packageMaterial: '铝塑包装',
    minPackageCount: '24',
    minPrepUnit: '片',
    minPackageUnit: '盒',
    company: '珠海同源药业有限公司',
    approvalNumber: '国药准字H44024254',
    standardCode: '86900594000335',
    insuranceCategory: '无',
    insuranceCode: '无',
    insuranceName: '无',
    insuranceDosage: '无',
    insuranceRemark: '无',
  },
];

const list = ref<DrugRow[]>(seedList);
const keyword = ref('');
const selectedRows = ref<DrugRow[]>([]);

// 过滤列表
const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return list.value;
  return list.value.filter(
    (item) =>
      item.drugCode.includes(kw) ||
      item.regName.includes(kw) ||
      item.productName.includes(kw),
  );
});

// 选中
function onSelectionChange(rows: DrugRow[]) {
  selectedRows.value = rows;
}

// 弹窗相关
const dialogVisible = ref(false);
const isEdit = ref(false);
const form = reactive<DrugRow>({
  id: '',
  drugCode: '',
  regName: '',
  regDosage: '',
  regSpec: '',
  productName: '',
  dosage: '',
  spec: '',
  packageMaterial: '',
  minPackageCount: '',
  minPrepUnit: '',
  minPackageUnit: '',
  company: '',
  approvalNumber: '',
  standardCode: '',
  insuranceCategory: '',
  insuranceCode: '',
  insuranceName: '',
  insuranceDosage: '',
  insuranceRemark: '',
});

function openAdd() {
  isEdit.value = false;
  Object.assign(form, {
    id: '',
    drugCode: '',
    regName: '',
    regDosage: '',
    regSpec: '',
    productName: '',
    dosage: '',
    spec: '',
    packageMaterial: '',
    minPackageCount: '',
    minPrepUnit: '',
    minPackageUnit: '',
    company: '',
    approvalNumber: '',
    standardCode: '',
    insuranceCategory: '',
    insuranceCode: '',
    insuranceName: '',
    insuranceDosage: '',
    insuranceRemark: '',
  });
  dialogVisible.value = true;
}

function openEdit(row: DrugRow) {
  isEdit.value = true;
  Object.assign(form, { ...row });
  dialogVisible.value = true;
}

function save() {
  if (!form.drugCode || !form.regName) {
    ElMessage.warning('请至少填写药品代码和注册名称');
    return;
  }

  if (isEdit.value) {
    const index = list.value.findIndex((item) => item.id === form.id);
    if (index !== -1) {
      list.value[index] = { ...form };
      ElMessage.success('更新成功');
    }
  } else {
    const newRow = { ...form, id: Date.now().toString() };
    list.value.unshift(newRow);
    ElMessage.success('新增成功');
  }
  dialogVisible.value = false;
}

function remove(row: DrugRow) {
  ElMessageBox.confirm(`确定删除药品【${row.regName}】吗？`, '提示', {
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
    `确定删除选中的 ${selectedRows.value.length} 个药品吗？`,
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
        <span>医保药品知识库</span>
      </div>

      <div class="header-actions">
        <el-input
          v-model="keyword"
          clearable
          style="width: 320px"
          placeholder="搜索：药品代码/名称"
        />
        <el-button type="primary" @click="openAdd">新增药品</el-button>
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
        prop="drugCode"
        label="药品代码"
        width="140"
        show-overflow-tooltip
        fixed
      />
      <el-table-column
        prop="regName"
        label="注册名称"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="regDosage"
        label="注册剂型"
        width="100"
        show-overflow-tooltip
      />
      <el-table-column
        prop="regSpec"
        label="注册规格"
        min-width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="productName"
        label="商品名称"
        min-width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="dosage"
        label="剂型"
        width="100"
        show-overflow-tooltip
      />
      <el-table-column
        prop="spec"
        label="规格"
        min-width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="packageMaterial"
        label="包装材质"
        width="100"
        show-overflow-tooltip
      />
      <el-table-column
        prop="minPackageCount"
        label="最小包装数量"
        width="110"
        align="center"
      />
      <el-table-column
        prop="minPrepUnit"
        label="最小制剂单位"
        width="110"
        align="center"
      />
      <el-table-column
        prop="minPackageUnit"
        label="最小包装单位"
        width="110"
        align="center"
      />
      <el-table-column
        prop="company"
        label="药品企业"
        min-width="180"
        show-overflow-tooltip
      />
      <el-table-column
        prop="approvalNumber"
        label="批准文号"
        width="140"
        show-overflow-tooltip
      />
      <el-table-column
        prop="standardCode"
        label="药品本位码"
        width="140"
        show-overflow-tooltip
      />

      <el-table-column label="国家医保药品目录" align="center">
        <el-table-column
          prop="insuranceCategory"
          label="甲乙类"
          width="70"
          align="center"
        />
        <el-table-column
          prop="insuranceCode"
          label="编号"
          width="100"
          show-overflow-tooltip
        />
        <el-table-column
          prop="insuranceName"
          label="药品名称"
          min-width="120"
          show-overflow-tooltip
        />
        <el-table-column
          prop="insuranceDosage"
          label="剂型"
          min-width="120"
          show-overflow-tooltip
        />
        <el-table-column
          prop="insuranceRemark"
          label="备注"
          min-width="120"
          show-overflow-tooltip
        />
      </el-table-column>

      <el-table-column label="操作" width="140" fixed="right" align="center">
        <template #default="scope">
          <el-button link type="primary" @click="openEdit(scope.row)">
            编辑
          </el-button>
          <el-button link type="danger" @click="remove(scope.row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑药品' : '新增药品'"
      width="900px"
      destroy-on-close
    >
      <el-form :model="form" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="药品代码" required>
              <el-input v-model="form.drugCode" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="注册名称" required>
              <el-input v-model="form.regName" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="注册剂型">
              <el-input v-model="form.regDosage" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="注册规格">
              <el-input v-model="form.regSpec" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="商品名称">
              <el-input v-model="form.productName" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="剂型">
              <el-input v-model="form.dosage" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="规格">
              <el-input v-model="form.spec" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="包装材质">
              <el-input v-model="form.packageMaterial" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最小包装数量">
              <el-input v-model="form.minPackageCount" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="最小制剂单位">
              <el-input v-model="form.minPrepUnit" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="最小包装单位">
              <el-input v-model="form.minPackageUnit" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="批准文号">
              <el-input v-model="form.approvalNumber" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="药品企业">
              <el-input v-model="form.company" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="药品本位码">
              <el-input v-model="form.standardCode" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">国家医保药品目录</el-divider>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="甲乙类">
              <el-input v-model="form.insuranceCategory" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="编号">
              <el-input v-model="form.insuranceCode" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="药品名称">
              <el-input v-model="form.insuranceName" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="剂型">
              <el-input v-model="form.insuranceDosage" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注">
              <el-input v-model="form.insuranceRemark" />
            </el-form-item>
          </el-col>
        </el-row>
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
</style>
