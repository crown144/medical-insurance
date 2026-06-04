<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { ElMessage, ElMessageBox } from 'element-plus';

interface ICDRow {
  id: string;
  chapter: string; // 章
  chapterRange: string; // 章代码范围
  chapterName: string; // 章的名称
  sectionRange: string; // 节代码范围
  sectionName: string; // 节名称
  categoryCode: string; // 类目代码
  categoryName: string; // 类目名称
  subcategoryCode: string; // 亚目代码
  subcategoryName: string; // 亚目名称
  diagnosisCode: string; // 诊断代码
  diagnosisName: string; // 诊断名称
}

// 模拟数据
const seedList: ICDRow[] = [
  {
    id: '1',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.0',
    subcategoryName: '霍乱，由于 O1 群霍乱弧菌，霍乱生物型所致',
    diagnosisCode: 'A00.000',
    diagnosisName: '霍乱，由于 O1 群霍乱弧菌，霍乱生物型所致',
  },
  {
    id: '2',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.0',
    subcategoryName: '霍乱，由于 O1 群霍乱弧菌，霍乱生物型所致',
    diagnosisCode: 'A00.000x001',
    diagnosisName: '古典生物型霍乱',
  },
  {
    id: '3',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.1',
    subcategoryName: '霍乱，由于 O1 群霍乱弧菌，埃尔托生物型所致',
    diagnosisCode: 'A00.100',
    diagnosisName: '霍乱，由于 O1 群霍乱弧菌，埃尔托生物型所致',
  },
  {
    id: '4',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.1',
    subcategoryName: '霍乱，由于 O1 群霍乱弧菌，埃尔托生物型所致',
    diagnosisCode: 'A00.100x001',
    diagnosisName: '埃尔托生物型霍乱',
  },
  {
    id: '5',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.9',
    subcategoryName: '未特指的霍乱',
    diagnosisCode: 'A00.900',
    diagnosisName: '霍乱',
  },
  {
    id: '6',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.9',
    subcategoryName: '未特指的霍乱',
    diagnosisCode: 'A00.900x002',
    diagnosisName: '霍乱轻型',
  },
  {
    id: '7',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.9',
    subcategoryName: '未特指的霍乱',
    diagnosisCode: 'A00.900x003',
    diagnosisName: '霍乱中型',
  },
  {
    id: '8',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.9',
    subcategoryName: '未特指的霍乱',
    diagnosisCode: 'A00.900x004',
    diagnosisName: '霍乱重型',
  },
  {
    id: '9',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A00',
    categoryName: '霍乱',
    subcategoryCode: 'A00.9',
    subcategoryName: '未特指的霍乱',
    diagnosisCode: 'A00.900x005',
    diagnosisName: '霍乱暴发型',
  },
  {
    id: '10',
    chapter: '1',
    chapterRange: 'A00-B99',
    chapterName: '某些传染病和寄生虫病',
    sectionRange: 'A00-A09',
    sectionName: '肠道传染病',
    categoryCode: 'A01',
    categoryName: '伤寒和副伤寒',
    subcategoryCode: 'A01.0',
    subcategoryName: '伤寒',
    diagnosisCode: 'A01.000',
    diagnosisName: '伤寒',
  },
];

const list = ref<ICDRow[]>(seedList);
const keyword = ref('');
const selectedRows = ref<ICDRow[]>([]);

// 过滤列表
const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return list.value;
  return list.value.filter(
    (item) =>
      item.diagnosisCode.toLowerCase().includes(kw) ||
      item.diagnosisName.toLowerCase().includes(kw) ||
      item.categoryName.toLowerCase().includes(kw) ||
      item.chapterName.toLowerCase().includes(kw),
  );
});

// 选中
function onSelectionChange(rows: ICDRow[]) {
  selectedRows.value = rows;
}

// 弹窗相关
const dialogVisible = ref(false);
const isEdit = ref(false);
const form = reactive<ICDRow>({
  id: '',
  chapter: '',
  chapterRange: '',
  chapterName: '',
  sectionRange: '',
  sectionName: '',
  categoryCode: '',
  categoryName: '',
  subcategoryCode: '',
  subcategoryName: '',
  diagnosisCode: '',
  diagnosisName: '',
});

function openAdd() {
  isEdit.value = false;
  Object.assign(form, {
    id: Date.now().toString(),
    chapter: '',
    chapterRange: '',
    chapterName: '',
    sectionRange: '',
    sectionName: '',
    categoryCode: '',
    categoryName: '',
    subcategoryCode: '',
    subcategoryName: '',
    diagnosisCode: '',
    diagnosisName: '',
  });
  dialogVisible.value = true;
}

function openEdit(row: ICDRow) {
  isEdit.value = true;
  Object.assign(form, { ...row });
  dialogVisible.value = true;
}

function save() {
  if (!form.diagnosisCode || !form.diagnosisName) {
    ElMessage.warning('请至少填写诊断代码和诊断名称');
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

function remove(row: ICDRow) {
  ElMessageBox.confirm(`确定删除【${row.diagnosisName}】吗？`, '提示', {
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
        <span>ICD编码库</span>
      </div>

      <div class="header-actions">
        <el-input
          v-model="keyword"
          clearable
          style="width: 320px"
          placeholder="搜索：诊断代码/名称/分类"
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
      <el-table-column type="selection" width="45" align="center" fixed />
      <el-table-column
        prop="diagnosisCode"
        label="诊断代码"
        width="150"
        show-overflow-tooltip
        fixed
      />
      <el-table-column
        prop="diagnosisName"
        label="诊断名称"
        min-width="200"
        show-overflow-tooltip
      />
      <el-table-column
        prop="chapter"
        label="章"
        width="80"
        align="center"
        show-overflow-tooltip
      />
      <el-table-column
        prop="chapterRange"
        label="章代码范围"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="chapterName"
        label="章的名称"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="sectionRange"
        label="节代码范围"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="sectionName"
        label="节名称"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="categoryCode"
        label="类目代码"
        width="100"
        show-overflow-tooltip
      />
      <el-table-column
        prop="categoryName"
        label="类目名称"
        min-width="150"
        show-overflow-tooltip
      />
      <el-table-column
        prop="subcategoryCode"
        label="亚目代码"
        width="100"
        show-overflow-tooltip
      />
      <el-table-column
        prop="subcategoryName"
        label="亚目名称"
        min-width="180"
        show-overflow-tooltip
      />

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
      :title="isEdit ? '编辑' : '新增'"
      width="800px"
      destroy-on-close
    >
      <el-form :model="form" label-width="120px" class="dialog-form">
        <div class="form-row">
          <el-form-item label="诊断代码" required class="full-width">
            <el-input v-model="form.diagnosisCode" />
          </el-form-item>
          <el-form-item label="诊断名称" required class="full-width">
            <el-input v-model="form.diagnosisName" />
          </el-form-item>
        </div>

        <el-divider content-position="left">分类信息</el-divider>

        <div class="form-grid">
          <el-form-item label="章">
            <el-input v-model="form.chapter" />
          </el-form-item>
          <el-form-item label="章代码范围">
            <el-input v-model="form.chapterRange" />
          </el-form-item>
          <el-form-item label="章的名称">
            <el-input v-model="form.chapterName" />
          </el-form-item>
          <el-form-item label="节代码范围">
            <el-input v-model="form.sectionRange" />
          </el-form-item>
          <el-form-item label="节名称">
            <el-input v-model="form.sectionName" />
          </el-form-item>
          <el-form-item label="类目代码">
            <el-input v-model="form.categoryCode" />
          </el-form-item>
          <el-form-item label="类目名称">
            <el-input v-model="form.categoryName" />
          </el-form-item>
          <el-form-item label="亚目代码">
            <el-input v-model="form.subcategoryCode" />
          </el-form-item>
          <el-form-item label="亚目名称">
            <el-input v-model="form.subcategoryName" />
          </el-form-item>
        </div>
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

/* Dialog Form Styles */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 20px;
}
.full-width {
  width: 100%;
}
</style>
