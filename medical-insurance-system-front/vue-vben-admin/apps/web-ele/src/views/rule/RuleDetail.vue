<script lang="ts" setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { Page, VbenModal } from '@vben/common-ui';

import {
  CircleCheck,
  Delete,
  Edit,
  Plus,
  Search,
  Warning,
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  createRule,
  deleteRule,
  getRuleList,
  toggleRuleStatus,
  updateRule,
} from '#/api/rule';
import { getRuleTypeLabel, RULE_TYPE_OPTIONS } from '#/config/rule-type';

type RuleType =
  | '超标准收费'
  | '超限定用药'
  | '重复收费'
  | '过度医疗'
  | '超频次收费';

const props = defineProps<{ ruleType?: RuleType }>();
const router = useRouter();

// 路由名称映射表
const ruleTypeToRouteName: Record<RuleType, string> = {
  超限定用药: 'RuleLimitedDrug',
  超标准收费: 'RuleOverStandardFee',
  重复收费: 'RuleDuplicateCharge',
  过度医疗: 'RuleOverMedical',
  超频次收费: 'RuleFakeFee',
};

/**
 * 规则导入同款：条件链结构
 * C1 / title / executorType / params
 */
interface ConditionNode {
  cid: string; // C1/C2/C3...
  title: string; // 例如：诊断包含：缺血性脑梗死
  executorType: string; // match_field / llm_predicate / check_limit ...
  params: Record<string, any>;
  paramsText?: string; // 仅用于弹窗编辑 JSON 字符串
}

interface RuleRow {
  id: string | number; // 兼容后端 number ID
  ruleId: string; // ② 规则ID
  drug_name: string; // ③ 规则名称
  ruleType: RuleType; // ④ 规则类型
  description: string; // ⑤ 原始描述 (对应后端 description)

  enabled: boolean; // ⑦ 状态
  ruleCode?: string; // ⑧ 规则代码 (对应后端 rule_code)

  // 前端辅助字段
  sourceLocate?: string;
  sourceHtml?: string;
}

let uid = 1;

function hasExecutableCode(ruleCode?: null | string) {
  return Boolean((ruleCode || '').trim());
}

function isCompiled(rule: { ruleCode?: null | string; rule_code?: null | string }) {
  return Boolean((rule.rule_code || rule.ruleCode || '').trim());
}

function normalizeEnabledState(enabled: boolean, ruleCode?: null | string) {
  return hasExecutableCode(ruleCode) ? enabled : false;
}

/** 规则名提取：符合你举例 */
function extractRuleName(desc: string) {
  const s = (desc || '').trim();
  if (!s) return '';

  // 1) “使用XXX须有...” -> XXX
  const m1 = s.match(/^使用(.+?)(须有|[限且并，。]|需要)/);
  if (m1?.[1]) return m1[1].trim();

  // 2) “XXX 插胃管加收10元” -> 取空格前作为规则名（胃肠减压）
  if (s.includes(' ')) return s.split(' ')[0].trim();

  // 3) “A与B不能同时开” -> A & B
  const m2 = s.match(/^“?(.+?)”?\s*与\s*“?(.+?)”?\s*不能/);
  if (m2?.[1] && m2?.[2]) return `${m2[1].trim()} & ${m2[2].trim()}`;

  // 4) fallback
  return s.length > 14 ? `${s.slice(0, 14)}…` : s;
}

/** 生成逻辑表达式：先默认 AND（后续你要 OR/分组，我再加） */
function buildLogicExpression(conditions: ConditionNode[]) {
  if (!conditions?.length) return '';
  return conditions.map((c) => c.cid).join(' AND ');
}

/** 展开里显示的“三段式文本” */
function buildChainText(conditions: ConditionNode[]) {
  if (!conditions?.length) return '';
  return conditions
    .map((c) => `${c.cid}\n${c.title}\n${c.executorType}`)
    .join('\n\n');
}

/**
 * 根据原始描述做一个“初始拆解”（纯前端占位版）
 * 目的：让页面立刻长得像规则导入的结构（C1/C2/C3）
 */
function autoInitConditions(ruleType: RuleType, raw: string): ConditionNode[] {
  const s = (raw || '').trim();
  const out: ConditionNode[] = [];
  // (保留原有逻辑作为兜底)
  // ...
  return out;
}

// ====== 页面状态 ======
const ruleTypeSelect = ref<RuleType>(props.ruleType || '超限定用药');
const keyword = ref('');
const list = ref<RuleRow[]>([]); // 动态数据
const loading = ref(false);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);

// 获取数据函数
const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      type: ruleTypeSelect.value, // 按类型筛选
      search: keyword.value, // 搜索关键词
    };
    const res = await getRuleList(params);
    console.log('API Response:', res); // 调试日志

    if (res) {
      // 兼容 Django DRF 分页结构 { results: [] } 和直接数组结构
      const rawList = res.results || (Array.isArray(res) ? res : []) || [];

      // 适配后端数据
      list.value = rawList.map((item: any) => ({
        id: item.id,
        ruleId: item.ruleId || `R-${item.id}`,
        drug_name: item.drugName || item.drug_name || extractRuleName(item.description),
        ruleType: item.type as RuleType,
        description: item.description,
        ruleCode: item.rule_code || item.ruleCode || '',
        enabled: normalizeEnabledState(
          Boolean(item.enabled),
          item.rule_code || item.ruleCode || '',
        ),
        // 其他字段若后端未返回，给默认值
        sourceLocate: '《国家基本医疗保险、工伤保险和生育保险药品目录》',
        sourceHtml: '',
      }));
      total.value = res.count || rawList.length || 0;
    }
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to load the rule list.');
  } finally {
    loading.value = false;
  }
};

// 监听 props 变化（路由切换 -> 更新下拉框）
watch(
  () => props.ruleType,
  (newVal) => {
    if (newVal) {
      ruleTypeSelect.value = newVal;
    }
  },
  { immediate: true },
);

// 监听下拉框变化（下拉框切换 -> 更新路由 & 刷新数据）
watch(
  () => ruleTypeSelect.value,
  (newVal) => {
    const targetRouteName = ruleTypeToRouteName[newVal];
    // 如果当前路由不是目标路由，则进行跳转
    if (targetRouteName && router.currentRoute.value.name !== targetRouteName) {
      router.push({ name: targetRouteName });
    }
    currentPage.value = 1;
    fetchData();
  },
);

// 监听搜索
watch(keyword, () => {
  currentPage.value = 1;
  fetchData();
});

// 状态切换处理
const handleStatusChange = async (row: RuleRow) => {
  if (!hasExecutableCode(row.ruleCode)) {
    row.enabled = false;
    ElMessage.warning('Compile the rule before enabling it.');
    return;
  }
  const originalStatus = !row.enabled;
  try {
    await toggleRuleStatus(row.id, row.enabled);
    ElMessage.success(row.enabled ? 'Rule enabled.' : 'Rule disabled.');
  } catch (error) {
    row.enabled = originalStatus; // 回滚
    ElMessage.error('Failed to update the rule status.');
  }
};

// 删除处理
async function handleDelete(row: RuleRow) {
  await ElMessageBox.confirm(`Delete rule "${row.drug_name}"?`, 'Delete Confirmation', {
    type: 'warning',
    confirmButtonText: 'Delete',
    cancelButtonText: 'Cancel',
  });
  try {
    await deleteRule(row.id);
    ElMessage.success('Rule deleted.');
    fetchData(); // 刷新
  } catch (error) {
    ElMessage.error('Failed to delete the rule.');
  }
}

// 选择（批量操作）
const selectedRows = ref<RuleRow[]>([]);
function onSelectionChange(rows: RuleRow[]) {
  selectedRows.value = rows ?? [];
}

const filteredList = computed(() => {
  // 前端过滤已不再需要，因为已经接入后端搜索
  // 但为了兼容某些未分页场景或快速响应，可以保留基础过滤
  // 这里直接返回 list 即可，因为 list 已经是后端筛选过的
  return list.value;
});

// 初始加载
onMounted(() => {
  fetchData();
});

// ====== CRUD ======
const dialogVisible = ref(false);
const editingId = ref<null | string>(null);

const form = reactive<RuleRow>({
  id: '',
  ruleId: '',
  drug_name: '',
  ruleType: '超限定用药',
  description: '',
  sourceLocate: '',
  sourceHtml: '',
  enabled: false,
  ruleCode: '',
});

function resetForm() {
  form.id = '';
  form.ruleId = '';
  form.drug_name = '';
  form.ruleType = ruleTypeSelect.value;
  form.description = '';
  form.sourceLocate = '';
  form.sourceHtml = '';
  form.enabled = false;
  form.ruleCode = '';
}

function openAdd() {
  editingId.value = null;
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row: RuleRow) {
  editingId.value = row.id as string;
  const copy = JSON.parse(JSON.stringify(row)) as RuleRow;
  Object.assign(form, copy);
  form.enabled = normalizeEnabledState(Boolean(copy.enabled), copy.ruleCode);
  dialogVisible.value = true;
}

const detailVisible = ref(false);
const currentDetail = ref<null | RuleRow>(null);

function openDetail(row: RuleRow) {
  currentDetail.value = { ...row };
  detailVisible.value = true;
}

function validateAndNormalizeConditions() {
  // cid 自动修正为 C1..Cn（避免用户乱写）
  form.conditions.forEach((c, idx) => {
    c.cid = `C${idx + 1}`;
  });

  // 解析 paramsText -> params
  for (const c of form.conditions) {
    const txt = (c.paramsText ?? '').trim();
    if (!txt) {
      c.params = {};
      continue;
    }
    try {
      c.params = JSON.parse(txt);
    } catch {
      throw new Error(`${c.cid} 的 params JSON 格式不正确`);
    }
  }
}

async function save() {
  if (!form.description.trim()) return ElMessage.warning('Please enter the original description.');

  // 规则名：空则自动提取
  if (!form.drug_name.trim()) form.drug_name = extractRuleName(form.description);

  // 构造提交给后端的数据
  const payload = {
    drugName: form.drug_name,
    ruleId: editingId.value
      ? form.ruleId || `R-${editingId.value}`
      : form.ruleId || `R-${Date.now()}`,
    type: form.ruleType,
    description: form.description,
    enabled: form.enabled,
    logicExpression: '', // 已废弃，传空
    rule_code: form.ruleCode, // 提交 rule_code
  };

  try {
    if (editingId.value) {
      // 更新
      await updateRule(editingId.value, payload);
      ElMessage.success('Rule updated.');
    } else {
      // 新增
      await createRule(payload);
      ElMessage.success('Rule created.');
    }
    dialogVisible.value = false;
    fetchData(); // 刷新列表
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to save the rule.');
  }
}

async function remove(row: RuleRow) {
  await ElMessageBox.confirm(`Delete rule "${row.drug_name}"?`, 'Delete Confirmation', {
    type: 'warning',
    confirmButtonText: 'Delete',
    cancelButtonText: 'Cancel',
  });
  list.value = list.value.filter((x) => x.id !== row.id);
  ElMessage.success('Rule deleted.');
}

// ====== 批量操作 ======
async function bulkDelete() {
  if (selectedRows.value.length === 0) return;
  await ElMessageBox.confirm(
    `Delete ${selectedRows.value.length} selected rules?`,
    'Bulk Delete',
    {
      type: 'warning',
      confirmButtonText: 'Delete',
      cancelButtonText: 'Cancel',
    },
  );
  const ids = new Set(selectedRows.value.map((r) => r.id));
  list.value = list.value.filter((x) => !ids.has(x.id));
  selectedRows.value = [];
  ElMessage.success('Bulk deletion completed.');
}

async function bulkSetEnabled(val: boolean) {
  if (selectedRows.value.length === 0) return;
  const ids = new Set(selectedRows.value.map((r) => r.id));
  list.value = list.value.map((x) =>
    ids.has(x.id) ? { ...x, enabled: val } : x,
  );
  ElMessage.success(val ? 'Selected rules enabled.' : 'Selected rules disabled.');
}

async function bulkExportJson() {
  if (selectedRows.value.length === 0) return;
  const text = JSON.stringify(selectedRows.value, null, 2);
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('Copied to clipboard (JSON).');
  } catch {
    ElMessage.warning('Copy failed due to browser permission limits. You can inspect selectedRows in the console.');
    // console.log(selectedRows.value)
  }
}

// ====== 来源HTML弹窗（可选）=====
const htmlVisible = ref(false);
const htmlTitle = ref('');
const htmlContent = ref('');

function openHtml(row: RuleRow) {
  htmlTitle.value = `Source HTML - ${row.drug_name}`;
  htmlContent.value =
    row.sourceHtml?.trim() ||
    `<p style="color:#999">No source HTML available.</p>`;
  htmlVisible.value = true;
}

// ====== 条件链编辑器 ======
function addCondition() {
  const n = form.conditions.length + 1;
  form.conditions.push({
    cid: `C${n}`,
    title: '',
    executorType: 'match_field',
    params: {},
    paramsText: `{\n  \n}`,
  });
  // 同步逻辑表达式预览
  form.logicExpression = buildLogicExpression(form.conditions);
}
function removeCondition(index: number) {
  form.conditions.splice(index, 1);
  // 修正 cid
  form.conditions.forEach((c, i) => (c.cid = `C${i + 1}`));
  form.logicExpression = buildLogicExpression(form.conditions);
}
function moveCondition(index: number, dir: -1 | 1) {
  const to = index + dir;
  if (to < 0 || to >= form.conditions.length) return;
  const tmp = form.conditions[index];
  form.conditions[index] = form.conditions[to];
  form.conditions[to] = tmp;
  form.conditions.forEach((c, i) => (c.cid = `C${i + 1}`));
  form.logicExpression = buildLogicExpression(form.conditions);
}

function formatParams(params: any) {
  if (!params) return [];
  // 标准结构：match_field / check_limit
  if (params.field || params.op) {
    return [
      {
        field: params.field || '-',
        op: params.op || '-',
        value: String(params.value ?? '-'),
      },
    ];
  }
  // LLM 结构
  if (params.question) {
    return [
      { field: 'question', op: ':', value: params.question },
      { field: 'expected', op: '==', value: String(params.expected) },
    ];
  }
  // 互斥结构
  if (params.a && params.b) {
    return [
      { field: '互斥项A', op: '-', value: params.a },
      { field: '互斥项B', op: '-', value: params.b },
    ];
  }
  // 默认兜底：KV展示
  return Object.entries(params).map(([k, v]) => ({
    field: k,
    op: ':',
    value: String(v),
  }));
}
</script>

<template>
  <div class="page-card">
    <!-- Header -->
    <div class="header">
      <div class="title">
        <span class="bar"></span>
        <span>Rule Library</span>
      </div>

      <div class="header-actions">
        <el-select v-model="ruleTypeSelect" style="width: 160px">
          <el-option
            v-for="item in RULE_TYPE_OPTIONS"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <el-input
          v-model="keyword"
          clearable
          style="width: 320px"
          placeholder="Search: rule / original description / source / logic expression"
        />

        <el-button type="primary" @click="openAdd">Add</el-button>
      </div>
    </div>

    <!-- Bulk bar -->
    <div v-if="selectedRows.length > 0" class="bulk-bar">
      <div class="bulk-left">{{ selectedRows.length }} selected</div>
      <div class="bulk-right">
        <el-button @click="bulkExportJson">Export JSON</el-button>
        <el-button @click="bulkSetEnabled(true)">Enable Selected</el-button>
        <el-button @click="bulkSetEnabled(false)">Disable Selected</el-button>
        <el-button type="danger" @click="bulkDelete">Delete Selected</el-button>
      </div>
    </div>

    <!-- Table -->
    <el-table
      :data="filteredList"
      border
      stripe
      row-key="id"
      style="flex: 1; width: 100%"
      @selection-change="onSelectionChange"
    >
      <!-- selection for bulk -->
      <el-table-column type="selection" width="44" align="center" />

      <!-- ② 规则ID -->
      <el-table-column prop="ruleId" label="Rule ID" width="120" sortable />

      <!-- ③ 规则名称 -->
      <el-table-column prop="drug_name" label="Rule Name" min-width="160" />

      <!-- ④ 规则类型 -->
      <el-table-column
        prop="ruleType"
        label="Rule Type"
        width="120"
        align="center"
      >
        <template #default="{ row }">
          {{ getRuleTypeLabel(row.ruleType) }}
        </template>
      </el-table-column>

      <!-- ⑤ 原始描述 -->
      <el-table-column label="Compilation" width="120" align="center">
        <template #default="{ row }">
          <el-tag :type="isCompiled(row) ? 'success' : 'warning'" size="small">
            {{ isCompiled(row) ? 'Compiled' : 'Not Compiled' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="description"
        label="Original Description"
        min-width="360"
        show-overflow-tooltip
      />

      <!-- ⑦ 操作 (启停对应后端 status) -->
      <el-table-column label="Actions" width="280" fixed="right" align="center">
        <template #default="scope">
          <div class="op-links">
            <el-tooltip
              :disabled="hasExecutableCode(scope.row.ruleCode)"
              content="Compile the rule before enabling it."
              placement="top"
            >
              <span class="switch-wrapper">
                <el-switch
                  v-model="scope.row.enabled"
                  inline-prompt
                  active-text="On"
                  inactive-text="Off"
                  active-color="#16a34a"
                  inactive-color="#64748b"
                  :disabled="!hasExecutableCode(scope.row.ruleCode)"
                  @change="handleStatusChange(scope.row)"
                />
              </span>
            </el-tooltip>
            <span class="op-sep">|</span>
            <el-button
              link
              type="primary"
              :icon="View"
              class="op-btn"
              @click="openDetail(scope.row)"
            >
              View
            </el-button>
            <span class="op-sep">|</span>
            <el-button
              link
              type="primary"
              class="op-btn"
              @click="openEdit(scope.row)"
            >
              Edit
            </el-button>
            <span class="op-sep">|</span>
            <el-button
              link
              type="danger"
              class="op-btn"
              @click="handleDelete(scope.row)"
            >
              Delete
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination -->
    <div class="footer-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </div>

    <!-- Add/Edit dialog -->
    <el-dialog
      v-model="dialogVisible"
      width="980px"
      :title="editingId ? 'Edit Rule' : 'Add Rule'"
      destroy-on-close
    >
      <el-form label-width="140px">
        <el-form-item label="Rule Name (Auto-extracted)">
          <el-input
            v-model="form.drug_name"
            placeholder="Optional: auto-extracted from the original description."
          />
        </el-form-item>

        <el-form-item label="Rule Type">
          <el-select v-model="form.ruleType" style="width: 220px">
            <el-option
              v-for="item in RULE_TYPE_OPTIONS"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="Original Description (Required)">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item label="Source Reference">
          <el-input
            v-model="form.sourceLocate"
            placeholder="Leave blank if unknown, or enter the rule source text."
          />
        </el-form-item>

        <el-form-item label="Source HTML (Optional)">
          <el-input
            v-model="form.sourceHtml"
            type="textarea"
            :rows="4"
            placeholder="Leave blank if unknown."
          />
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

    <!-- Detail Dialog -->
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
          {{ currentDetail.drug_name }}
        </el-descriptions-item>
        <el-descriptions-item label="Rule Type">
          {{ getRuleTypeLabel(currentDetail.ruleType) }}
        </el-descriptions-item>
        <el-descriptions-item label="Status">
          <el-tag :type="currentDetail.enabled ? 'success' : 'danger'">
            {{ currentDetail.enabled ? 'Enabled' : 'Disabled' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="Source Reference" :span="2">
          {{ currentDetail.sourceLocate || 'Not available.' }}
        </el-descriptions-item>
        <el-descriptions-item label="Source HTML" :span="2">
          <el-button link type="primary" @click="openHtml(currentDetail!)">
            View HTML
          </el-button>
        </el-descriptions-item>
        <el-descriptions-item label="Original Description" :span="2">
          {{ currentDetail.description }}
        </el-descriptions-item>
        <el-descriptions-item label="Execution Code" :span="2">
          <div class="code-scroll-box">
            <pre>{{ currentDetail.ruleCode || 'No code available.' }}</pre>
          </div>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- HTML dialog -->
    <el-dialog
      v-model="htmlVisible"
      width="900px"
      :title="htmlTitle"
      destroy-on-close
    >
      <div class="html-box" v-html="htmlContent"></div>
      <template #footer>
        <el-button @click="htmlVisible = false">Close</el-button>
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
  /* 使用 Flex 布局确保表格自动撑开 */
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
.bulk-right {
  display: flex;
  gap: 10px;
}

.source-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.source-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #4b5563;
}

.expand-box {
  padding: 12px;
  background: #fafafa;
  border-radius: 10px;
}
.expand-title {
  font-weight: 700;
  color: #111827;
  margin: 6px 0 10px;
}
.params-box {
  margin: 0;
  padding: 8px 10px;
  background: #f3f4f6;
  border-radius: 8px;
  white-space: pre-wrap;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    monospace;
  color: #111827;
}
.chain-box {
  margin: 0;
  padding: 10px 12px;
  background: #f3f4f6;
  border-radius: 10px;
  white-space: pre-wrap;
  line-height: 1.5;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    monospace;
  color: #111827;
}

.html-box {
  max-height: 60vh;
  overflow: auto;
  padding: 12px;
  border: 1px solid #eee;
  border-radius: 10px;
  background: white;
}

.cond-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 10px 0 8px;
}
.cond-tip {
  color: #6b7280;
  font-size: 12px;
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

/* 详情表格样式 */
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
