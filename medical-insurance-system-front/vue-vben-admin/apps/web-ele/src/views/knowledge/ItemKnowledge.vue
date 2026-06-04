<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { ElMessage, ElMessageBox } from 'element-plus';

interface ItemRow {
  id: string;
  code: string; // 医保统一编码
  nationalCode: string; // 国家编码
  categoryLarge: string; // 项目大类
  categoryType: string; // 项目类别
  categorySub: string; // 项目子类
  name: string; // 项目名称
  connotation: string; // 项目内涵
  excluded: string; // 除外内容
  unit: string; // 计价单位
  description: string; // 说明
  price1: string; // 一类价
  price2: string; // 二类价
  price3: string; // 三类价
  priceType: string; // 价格类型
}

// 模拟数据
const seedList: ItemRow[] = [
  {
    id: '1',
    code: '002101010010000-210101001',
    nationalCode: '210101001',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线透视检查',
    name: '普通透视',
    connotation: '包括胸、腹、盆腔、四肢等',
    excluded: '无',
    unit: '每个部位',
    description: '800MA以上加收3元',
    price1: '8',
    price2: '7',
    price3: '6',
    priceType: '最高指导价',
  },
  {
    id: '2',
    code: '002101010010000-210101002',
    nationalCode: '210101002',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线透视检查',
    name: '食管钡餐透视',
    connotation: '含胃异物、心脏透视检查',
    excluded: '无',
    unit: '次',
    description: '数字化摄影（DR）机加收50元',
    price1: '16',
    price2: '15',
    price3: '15',
    priceType: '最高指导价',
  },
  {
    id: '3',
    code: '002101010010000-210101003',
    nationalCode: '210101003',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线透视检查',
    name: '床旁透视与术中透视',
    connotation: '包括透视下定位',
    excluded: '无',
    unit: '半小时',
    description: '无',
    price1: '36',
    price2: '34',
    price3: '32',
    priceType: '最高指导价',
  },
  {
    id: '4',
    code: '002101010010000-210101004',
    nationalCode: '210101004',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线透视检查',
    name: 'C型臂术中透视',
    connotation: '包括透视下定位',
    excluded: '无',
    unit: '半小时',
    description: '3D数字化C型臂引导定位每小时收取300元',
    price1: '98',
    price2: '98',
    price3: '88',
    priceType: '最高指导价',
  },
  {
    id: '5',
    code: '002101020100000-210102010',
    nationalCode: '210102010',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线摄影',
    name: '曲面体层摄影（颌全景摄影）',
    connotation: '无',
    excluded: '无',
    unit: '片数',
    description: '无',
    price1: '55',
    price2: '53',
    price3: '50',
    priceType: '最高指导价',
  },
  {
    id: '6',
    code: '002101020100000-210102011',
    nationalCode: '210102011',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线摄影',
    name: '头颅定位测量摄影',
    connotation: '无',
    excluded: '无',
    unit: '片数',
    description: '无',
    price1: '33',
    price2: '31',
    price3: '28',
    priceType: '最高指导价',
  },
  {
    id: '7',
    code: '002101020100000-210102012',
    nationalCode: '210102012',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线摄影',
    name: '眼球异物定位摄影',
    connotation: '不含眼科放置定位器操作',
    excluded: '无',
    unit: '片数',
    description: '无',
    price1: '33',
    price2: '31',
    price3: '28',
    priceType: '最高指导价',
  },
  {
    id: '8',
    code: '002101020100000-210102013',
    nationalCode: '210102013',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线摄影',
    name: '乳腺钼靶摄片 8×10口寸',
    connotation: '无',
    excluded: '无',
    unit: '片数',
    description: '无',
    price1: '33',
    price2: '31',
    price3: '28',
    priceType: '最高指导价',
  },
  {
    id: '9',
    code: '002101020100000-210102014',
    nationalCode: '210102014',
    categoryLarge: '医学影像',
    categoryType: 'X线检查',
    categorySub: 'X线摄影',
    name: '乳腺钼靶摄片 18×24口寸',
    connotation: '无',
    excluded: '无',
    unit: '片数',
    description: '定位加收50元',
    price1: '55',
    price2: '53',
    price3: '50',
    priceType: '最高指导价',
  },
];

const list = ref<ItemRow[]>(seedList);
const keyword = ref('');
const selectedRows = ref<ItemRow[]>([]);

// 过滤列表
const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return list.value;
  return list.value.filter(
    (item) =>
      item.code.includes(kw) ||
      item.name.includes(kw) ||
      item.categoryLarge.includes(kw),
  );
});

// 选中
function onSelectionChange(rows: ItemRow[]) {
  selectedRows.value = rows;
}

// 弹窗相关
const dialogVisible = ref(false);
const isEdit = ref(false);
const form = reactive<ItemRow>({
  id: '',
  code: '',
  nationalCode: '',
  categoryLarge: '',
  categoryType: '',
  categorySub: '',
  name: '',
  connotation: '',
  excluded: '',
  unit: '',
  description: '',
  price1: '',
  price2: '',
  price3: '',
  priceType: '',
});

function openAdd() {
  isEdit.value = false;
  Object.assign(form, {
    id: '',
    code: '',
    nationalCode: '',
    categoryLarge: '',
    categoryType: '',
    categorySub: '',
    name: '',
    connotation: '',
    excluded: '',
    unit: '',
    description: '',
    price1: '',
    price2: '',
    price3: '',
    priceType: '',
  });
  dialogVisible.value = true;
}

function openEdit(row: ItemRow) {
  isEdit.value = true;
  Object.assign(form, { ...row });
  dialogVisible.value = true;
}

function save() {
  if (!form.code || !form.name) {
    ElMessage.warning('请至少填写医保统一编码和项目名称');
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

function remove(row: ItemRow) {
  ElMessageBox.confirm(`确定删除项目【${row.name}】吗？`, '提示', {
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
    `确定删除选中的 ${selectedRows.value.length} 个项目吗？`,
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
        <span>项目内涵知识库</span>
      </div>

      <div class="header-actions">
        <el-input
          v-model="keyword"
          clearable
          style="width: 320px"
          placeholder="搜索：编码/名称/大类"
        />
        <el-button type="primary" @click="openAdd">新增项目</el-button>
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
        label="医保统一编码"
        width="140"
        show-overflow-tooltip
        fixed
      />
      <el-table-column
        prop="nationalCode"
        label="国家编码"
        width="140"
        show-overflow-tooltip
      />
      <el-table-column
        prop="categoryLarge"
        label="项目大类"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="categoryType"
        label="项目类别"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="categorySub"
        label="项目子类"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="name"
        label="项目名称"
        min-width="180"
        show-overflow-tooltip
      />
      <el-table-column
        prop="connotation"
        label="项目内涵"
        min-width="200"
        show-overflow-tooltip
      />
      <el-table-column
        prop="excluded"
        label="除外内容"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="unit"
        label="计价单位"
        width="100"
        align="center"
      />
      <el-table-column
        prop="description"
        label="说明"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column label="价格" align="center">
        <el-table-column
          prop="price1"
          label="一类价"
          width="100"
          align="right"
        />
        <el-table-column
          prop="price2"
          label="二类价"
          width="100"
          align="right"
        />
        <el-table-column
          prop="price3"
          label="三类价"
          width="100"
          align="right"
        />
        <el-table-column
          prop="priceType"
          label="价格类型"
          width="120"
          align="center"
        />
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right" align="center">
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
      :title="isEdit ? '编辑项目' : '新增项目'"
      width="800px"
      destroy-on-close
    >
      <el-form :model="form" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="医保统一编码" required>
              <el-input v-model="form.code" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="国家编码">
              <el-input v-model="form.nationalCode" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="项目大类">
              <el-input v-model="form.categoryLarge" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="项目类别">
              <el-input v-model="form.categoryType" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="项目子类">
              <el-input v-model="form.categorySub" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="项目内涵">
          <el-input v-model="form.connotation" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="除外内容">
          <el-input v-model="form.excluded" type="textarea" :rows="2" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="计价单位">
              <el-input v-model="form.unit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="价格类型">
              <el-input v-model="form.priceType" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="一类价">
              <el-input v-model="form.price1" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="二类价">
              <el-input v-model="form.price2" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="三类价">
              <el-input v-model="form.price3" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
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
