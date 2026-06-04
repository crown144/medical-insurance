<script setup lang="ts">
import { computed, reactive, ref } from 'vue';

import { ElMessage, ElMessageBox } from 'element-plus';

interface VectorRow {
  id: string; // 医保知识ID (作为主键)
  content: string; // 知识内容
  knowledgeType: string; // 知识类型 (项目内涵/医保药品)
  effectiveTime: string; // 生效时间
  vector: string; // 向量数组 (模拟显示前几位)
}

// 模拟数据：结合了之前的“项目内涵”和“医保药品”数据生成
const seedList: VectorRow[] = [
  // --- 项目内涵相关 (医学影像) ---
  {
    id: 'VEC-2024001',
    content:
      '项目：普通透视；编码：210101001；内涵：包括胸、腹、盆腔、四肢等；说明：800MA以上加收3元；价格：最高指导价8元',
    knowledgeType: '项目内涵',
    effectiveTime: '2024-01-01',
    vector: '[0.12, -0.56, 0.89, 0.04, -0.33, ...]',
  },
  {
    id: 'VEC-2024002',
    content:
      '项目：食管钡餐透视；编码：210101002；内涵：含胃异物、心脏透视检查；说明：数字化摄影(DR)机加收50元',
    knowledgeType: '项目内涵',
    effectiveTime: '2024-01-01',
    vector: '[0.05, 0.22, -0.71, 0.15, 0.48, ...]',
  },
  {
    id: 'VEC-2024003',
    content:
      '项目：床旁透视与术中透视；编码：210101003；内涵：包括透视下定位；计价单位：半小时',
    knowledgeType: '项目内涵',
    effectiveTime: '2024-01-01',
    vector: '[-0.31, 0.67, 0.12, -0.09, -0.55, ...]',
  },
  {
    id: 'VEC-2024004',
    content:
      '项目：C型臂术中透视；编码：210101004；说明：3D数字化C型臂引导定位每小时收取300元',
    knowledgeType: '项目内涵',
    effectiveTime: '2024-01-01',
    vector: '[0.88, -0.14, 0.33, 0.61, -0.02, ...]',
  },
  {
    id: 'VEC-2024005',
    content:
      '项目：曲面体层摄影(颌全景摄影)；编码：210102010；计价单位：片数；价格：一类价55元',
    knowledgeType: '项目内涵',
    effectiveTime: '2024-01-01',
    vector: '[-0.45, -0.29, 0.76, -0.18, 0.92, ...]',
  },

  // --- 医保药品相关 (地喹氯铵含片) ---
  {
    id: 'VEC-2024006',
    content:
      '药品：地喹氯铵含片；规格：0.25mg；厂家：汕头经济特区明治医药有限公司；批准文号：国药准字H20067255；剂型：片剂(口含)',
    knowledgeType: '医保药品',
    effectiveTime: '2023-12-15',
    vector: '[0.65, 0.11, -0.44, 0.73, -0.21, ...]',
  },
  {
    id: 'VEC-2024007',
    content:
      '药品：地喹氯铵含片；规格：(1)0.25mg(2)0.25mg(无糖型)；厂家：珠海同源药业有限公司；最小包装：12片/盒',
    knowledgeType: '医保药品',
    effectiveTime: '2023-12-15',
    vector: '[-0.19, 0.82, 0.55, -0.36, 0.08, ...]',
  },
  {
    id: 'VEC-2024008',
    content:
      '药品：地喹氯铵含片；厂家：华润双鹤药业股份有限公司；批准文号：国药准字H11021869；包装材质：双铝泡罩包装',
    knowledgeType: '医保药品',
    effectiveTime: '2023-12-15',
    vector: '[0.34, -0.68, -0.13, 0.49, 0.77, ...]',
  },
  {
    id: 'VEC-2024009',
    content:
      '药品：地喹氯铵含片；代码：XA01ABD075A002010300483；最小包装数量：6；最小包装单位：盒',
    knowledgeType: '医保药品',
    effectiveTime: '2023-12-15',
    vector: '[-0.52, 0.41, 0.95, -0.27, -0.63, ...]',
  },
  {
    id: 'VEC-2024010',
    content:
      '药品：地喹氯铵含片(无糖型)；本位码：86900594000335；规格：0.25mg(无糖型)；厂家：珠海同源药业有限公司',
    knowledgeType: '医保药品',
    effectiveTime: '2023-12-15',
    vector: '[0.78, 0.05, -0.39, 0.84, 0.16, ...]',
  },
];

const list = ref<VectorRow[]>(seedList);
const keyword = ref('');
const selectedRows = ref<VectorRow[]>([]);

// 过滤列表
const filteredList = computed(() => {
  const kw = keyword.value.trim().toLowerCase();
  if (!kw) return list.value;
  return list.value.filter(
    (item) =>
      item.id.toLowerCase().includes(kw) ||
      item.content.toLowerCase().includes(kw) ||
      item.knowledgeType.includes(kw),
  );
});

// 选中
function onSelectionChange(rows: VectorRow[]) {
  selectedRows.value = rows;
}

// 弹窗相关
const dialogVisible = ref(false);
const isEdit = ref(false);
const form = reactive<VectorRow>({
  id: '',
  content: '',
  knowledgeType: '',
  effectiveTime: '',
  vector: '',
});

function openAdd() {
  isEdit.value = false;
  Object.assign(form, {
    id: `VEC-${Date.now()}`,
    content: '',
    knowledgeType: '项目内涵',
    effectiveTime: new Date().toISOString().split('T')[0],
    vector: '[0.00, 0.00, ...]', // 默认占位
  });
  dialogVisible.value = true;
}

function openEdit(row: VectorRow) {
  isEdit.value = true;
  Object.assign(form, { ...row });
  dialogVisible.value = true;
}

function save() {
  if (!form.content) {
    ElMessage.warning('请填写知识内容');
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

function remove(row: VectorRow) {
  ElMessageBox.confirm(`确定删除知识ID为【${row.id}】的数据吗？`, '提示', {
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
        <span>医保知识向量库</span>
      </div>

      <div class="header-actions">
        <el-input
          v-model="keyword"
          clearable
          style="width: 320px"
          placeholder="搜索：ID/内容/类型"
        />
        <el-button type="primary" @click="openAdd">新增向量知识</el-button>
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
        prop="id"
        label="医保知识ID"
        width="140"
        show-overflow-tooltip
        fixed
      />
      <el-table-column
        prop="content"
        label="知识内容"
        min-width="300"
        show-overflow-tooltip
      />
      <el-table-column
        prop="knowledgeType"
        label="知识类型"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          <el-tag
            :type="row.knowledgeType === '项目内涵' ? 'primary' : 'success'"
            disable-transitions
          >
            {{ row.knowledgeType }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="effectiveTime"
        label="生效时间"
        width="120"
        align="center"
      />
      <el-table-column
        prop="vector"
        label="向量数组"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <span style="font-family: monospace; color: #666">
            {{ row.vector }}
          </span>
        </template>
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
      :title="isEdit ? '编辑向量知识' : '新增向量知识'"
      width="700px"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="医保知识ID">
          <el-input v-model="form.id" disabled placeholder="自动生成" />
        </el-form-item>
        <el-form-item label="知识类型" required>
          <el-radio-group v-model="form.knowledgeType">
            <el-radio value="项目内涵">项目内涵</el-radio>
            <el-radio value="医保药品">医保药品</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="生效时间">
          <el-date-picker
            v-model="form.effectiveTime"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="知识内容" required>
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            placeholder="请输入知识的文本描述"
          />
        </el-form-item>
        <el-form-item label="向量数组">
          <el-input
            v-model="form.vector"
            type="textarea"
            :rows="2"
            placeholder="[0.1, 0.2, ...]"
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
