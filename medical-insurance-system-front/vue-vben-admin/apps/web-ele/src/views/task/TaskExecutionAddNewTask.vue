<script setup lang="ts">
import type {
  DemoCaseItem,
  InhosSearchParams,
  RuleItem,
} from '../../api/model/taskModel';

import { computed, nextTick, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { Delete, Plus, Refresh, Search } from '@element-plus/icons-vue';
import {
  ElAlert,
  ElButton,
  ElDatePicker,
  ElEmpty,
  ElIcon,
  ElInput,
  ElMessage,
  ElOption,
  ElSelect,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus';

// API 和 组件 (保持您的引用路径)
import {
  createTaskApi,
  getDemoCaseListApi,
  getRuleListApi,
  searchInhosApi,
} from '../../api/task';
import { DEMO_MODE } from '../../config/demo';
import {
  getDisplayRuleId,
  getRuleDescriptionEnglish,
  getRuleNameEnglish,
  getRuleTypeLabel,
} from '../../config/rule-type';
// import RepeatChargingRuleSelector from '../../components/RepeatChargingRuleSelector.vue'; // 已废弃

// --- 数据接口 ---
interface NewTaskForm {
  name: string;
  mdc_org_cd: string;
  hospitalization_ids: string[];
  selected_rule_ids: number[]; // 超限定用药选中的ID
  discharge_date_start: string;
  discharge_date_end: string;
  drug_name: string;
}

const router = useRouter();
const form = ref<NewTaskForm>({
  name: '',
  mdc_org_cd: '',
  hospitalization_ids: [],
  selected_rule_ids: [],
  discharge_date_start: '',
  discharge_date_end: '',
  drug_name: '',
});

// --- UI 状态 ---
const caseInputVisible = ref(false);
const caseInputValue = ref('');
const caseInputRef = ref<InstanceType<typeof ElInput>>();

const allRules = ref<RuleItem[]>([]);
const isLoadingRules = ref(true);
const isCreatingTask = ref(false);
const ruleSearchQuery = ref('');
const isLoadingInhos = ref(false);
const inhosSearchResults = ref<string[]>([]);
const inhosSearchWarning = ref('');
const inhosSearchLimit = ref(0);
const demoCases = ref<DemoCaseItem[]>([]);
const isLoadingDemoCases = ref(false);

/** 规则名提取：从描述中提取规则名 (复用自 RuleDetail.vue) */
function extractRuleName(desc: string) {
  const s = (desc || '').trim();
  if (!s) return '';

  const m1 = s.match(/^使用(.+?)(须有|[限且并，、]|需要)/);
  if (m1?.[1]) return m1[1].trim();

  if (s.includes(' ')) return (s.split(' ')[0] || '').trim();

  const m2 = s.match(/^"?(.+?)"?\s*与\s*"?(.+?)"?\s*不能/);
  if (m2?.[1] && m2?.[2]) return `${m2[1].trim()} & ${m2[2].trim()}`;

  return s.length > 14 ? `${s.slice(0, 14)}...` : s;
}

/** 处理规则数据：填充 drug_name */
function processRules(data: any): RuleItem[] {
  const list = Array.isArray(data)
    ? data
    : (data as any).items || (data as any).results || [];

  return list.map((item: any) => ({
    ...item,
    ruleId: item.ruleId || item.rule_id,
    displayRuleId: getDisplayRuleId(item.ruleId || item.rule_id),
    // 优先用后端返回的 drug_name，其次尝试 drugName，最后从描述提取
    drug_name:
      item.drug_name || item.drugName || extractRuleName(item.description),
  }));
}

function getDisplayRuleName(row: RuleItem) {
  return getRuleNameEnglish(row.drug_name) || (row as any).drugNameEnglish || row.drug_name || '-';
}

function getDisplayRuleDescription(row: RuleItem) {
  return (row as any).descriptionEnglish || getRuleDescriptionEnglish(row.description) || row.description || '-';
}

const supportedRuleTypes = new Set(['超限定用药', '超标准收费', '重复收费']);
const selectedRules = ref<RuleItem[]>([]);
const filteredRules = computed(() => {
  const query = ruleSearchQuery.value.trim().toLowerCase();
  if (!query) return allRules.value;
  return allRules.value.filter((rule) => [
    rule.ruleId, rule.drug_name, rule.type, rule.description,
    getDisplayRuleName(rule), getDisplayRuleDescription(rule),
    getRuleTypeLabel(rule.type),
  ].join(' ').toLowerCase().includes(query));
});
const unsupportedSelectedRules = computed(() =>
  selectedRules.value.filter((rule) => !supportedRuleTypes.has(rule.type)),
);

const loadAllRules = async () => {
  isLoadingRules.value = true;
  try {
    allRules.value = processRules(await getRuleListApi({ paginate: 'false', ordering: 'id' }));
  } catch (error) {
    console.error('Failed to load rules', error);
    ElMessage.error('Failed to load rules.');
  } finally {
    isLoadingRules.value = false;
  }
};
onMounted(loadAllRules);

const loadDemoCases = async () => {
  if (!DEMO_MODE) return;
  isLoadingDemoCases.value = true;
  try {
    const seenIds = new Set<string>();
    demoCases.value = (await getDemoCaseListApi())
      .map((item) => ({
        ...item,
        hospitalization_id: normalizeHospitalizationId(item.hospitalization_id),
      }))
      .filter((item) => {
        if (!item.hospitalization_id || seenIds.has(item.hospitalization_id)) {
          return false;
        }
        seenIds.add(item.hospitalization_id);
        return true;
      });
  } catch (error) {
    console.error('Failed to load demo cases', error);
    ElMessage.error('Failed to load demo cases.');
  } finally {
    isLoadingDemoCases.value = false;
  }
};

onMounted(loadDemoCases);

const searchInhosNumbers = async () => {
  if (!form.value.discharge_date_start && !form.value.drug_name.trim()) {
    ElMessage.warning('Please select a date or enter a drug name to filter.');
    return;
  }
  isLoadingInhos.value = true;
  try {
    const params: InhosSearchParams = {};
    if (form.value.discharge_date_start)
      params.start_date = form.value.discharge_date_start;
    if (form.value.discharge_date_end)
      params.end_date = form.value.discharge_date_end;
    if (form.value.drug_name.trim())
      params.drug_name = form.value.drug_name.trim();

    const res = await searchInhosApi(params);
    inhosSearchResults.value = res.inhos_numbers || [];
    inhosSearchWarning.value = res.truncated ? (res.warning || '') : '';
    inhosSearchLimit.value = res.limit;

    if (inhosSearchResults.value.length === 0) {
      ElMessage.info('No matching hospitalization IDs were found.');
    } else if (res.truncated) {
      ElMessage.warning(
        res.warning || `Only the first ${res.limit} records were returned. Please narrow the search scope.`,
      );
    } else {
      ElMessage.success(`${res.count} hospitalization IDs returned.`);
    }
  } catch (error) {
    console.error(error);
  } finally {
    isLoadingInhos.value = false;
  }
};

const selectInhosNumber = (inhosNo: string) => {
  if (!form.value.hospitalization_ids.includes(inhosNo)) {
    form.value.hospitalization_ids.push(inhosNo);
  }
};

const selectAllInhosNumbers = () => {
  const newNumbers = inhosSearchResults.value.filter(
    (inhosNo) => !form.value.hospitalization_ids.includes(inhosNo),
  );
  form.value.hospitalization_ids.push(...newNumbers);
  ElMessage.success(`${newNumbers.length} hospitalization IDs added.`);
};

const resetFilter = () => {
  form.value.discharge_date_start = '';
  form.value.discharge_date_end = '';
  form.value.drug_name = '';
  inhosSearchResults.value = [];
  inhosSearchWarning.value = '';
  inhosSearchLimit.value = 0;
};

const clearSelectedInhos = () => {
  form.value.hospitalization_ids = [];
};

const handleCaseClose = (tag: string) => {
  form.value.hospitalization_ids.splice(
    form.value.hospitalization_ids.indexOf(tag),
    1,
  );
};

const showCaseInput = () => {
  caseInputVisible.value = true;
  nextTick(() => {
    caseInputRef.value?.input?.focus();
  });
};

const handleCaseInputConfirm = () => {
  if (caseInputValue.value) {
    form.value.hospitalization_ids.push(caseInputValue.value.trim());
  }
  caseInputVisible.value = false;
  caseInputValue.value = '';
};

const handleRuleSelectionChange = (selectedRows: RuleItem[]) => {
  selectedRules.value = selectedRows;
  form.value.selected_rule_ids = selectedRows.map((row) => row.id);
};

const normalizeHospitalizationId = (value?: string) => {
  const text = (value || '').trim();
  return text.includes(':') ? text.split(':').pop()!.trim() : text;
};

const formatDemoCaseLabel = (item: DemoCaseItem) => {
  return normalizeHospitalizationId(item.hospitalization_id);
};

const createTask = async () => {
  if (!form.value.name.trim()) return ElMessage.warning('Please enter a task name.');
  if (form.value.hospitalization_ids.length === 0)
    return ElMessage.warning(
      DEMO_MODE
        ? 'Please select at least one demo case.'
        : 'Please enter at least one hospitalization ID.',
    );

  if (selectedRules.value.length === 0) {
    return ElMessage.warning('Please select at least one audit rule.');
  }
  if (unsupportedSelectedRules.value.length) {
    return ElMessage.warning('Some selected rule categories are not supported by task execution. Please deselect them.');
  }
  const selectedSchemas = [...new Set(selectedRules.value.map((rule) => rule.type).filter(Boolean))];
  const allSelectedRuleIds = selectedRules.value.map((rule) => rule.id);

  isCreatingTask.value = true;
  try {
    const payload = {
      name: form.value.name,
      mdc_org_cd: '',
      hospitalization_ids: form.value.hospitalization_ids.map(normalizeHospitalizationId),
      rule_ids: allSelectedRuleIds, // 统一提交
      selectedSchemas,
      selected_schemas: selectedSchemas,
      // 移除旧的重复收费字段
      repeatChargingChildCodes: [],
      repeatChargingPairs: [],
    };
    await createTaskApi(payload);
    ElMessage.success('Task created successfully.');
    await router.push({ name: 'ExecuteRun' });
  } catch (error) {
    console.error(error);
  } finally {
    isCreatingTask.value = false;
  }
};

const goBack = () => router.back();
</script>

<template>
  <div class="page-wrap">
    <div class="content-card">
      <div class="page-title">
        <div class="title-bar"></div>
        <div class="title-text">
          <div class="title-main">New Task</div>
          <div class="title-sub">Enter task information and configure case scope and rules</div>
        </div>
        <div class="header-actions">
          <ElButton @click="goBack">Cancel</ElButton>
          <ElButton
            type="primary"
            :loading="isCreatingTask"
            @click="createTask"
          >
            Submit Task
          </ElButton>
        </div>
      </div>

      <ElAlert
        v-if="DEMO_MODE"
        title="This demo environment uses preloaded anonymized patient cases and does not connect to the production medical database."
        type="info"
        show-icon
        :closable="false"
        class="mb-4"
      />

      <div class="section-title">1. Basic Information</div>
      <div class="query-card">
        <div class="form-row">
          <div class="query-item" style="width: 400px">
            <div class="query-label">
              Task Name <span class="required">*</span>
            </div>
            <ElInput
              v-model="form.name"
              placeholder="For example: Q1 2025 over-limit medication audit"
              size="large"
            />
          </div>
        </div>
      </div>

      <div class="section-title">
        2. {{ DEMO_MODE ? 'Demo Case Selection' : 'Audit Case Scope' }}
        <span class="section-badge">{{ form.hospitalization_ids.length }} selected</span>
      </div>

      <div class="query-card">
        <div v-if="DEMO_MODE" class="query-item demo-case-select">
          <div class="query-label">
            Demo Case Selection <span class="required">*</span>
            <span class="label-note">
              Choose by hospitalization ID; each option maps to a preloaded patient ID and case record.
            </span>
          </div>
          <ElSelect
            v-model="form.hospitalization_ids"
            multiple
            filterable
            clearable
            collapse-tags
            collapse-tags-tooltip
            placeholder="Select one or more preloaded cases for audit"
            :loading="isLoadingDemoCases"
            style="width: 100%"
          >
            <ElOption
              v-for="item in demoCases"
              :key="item.hospitalization_id"
              :label="formatDemoCaseLabel(item)"
              :value="normalizeHospitalizationId(item.hospitalization_id)"
            />
          </ElSelect>
          <div class="demo-case-hint">
            The selected values are hospitalization IDs used to locate the corresponding patient ID and inpatient record in the demo dataset.
          </div>
        </div>

        <div v-if="!DEMO_MODE" class="query-row">
          <div class="query-left">
            <div class="query-item">
              <div class="query-label">Discharge Date Range</div>
              <div class="flex gap-2">
                <ElDatePicker
                  v-model="form.discharge_date_start"
                  type="month"
                  placeholder="Start month"
                  value-format="YYYY-MM"
                  style="width: 140px"
                />
                <span class="self-center text-gray-400">-</span>
                <ElDatePicker
                  v-model="form.discharge_date_end"
                  type="month"
                  placeholder="End month"
                  value-format="YYYY-MM"
                  style="width: 140px"
                />
              </div>
            </div>

            <div class="query-item">
              <div class="query-label">Drug Name</div>
              <ElInput
                v-model="form.drug_name"
                placeholder="Enter a drug name to filter"
                style="width: 200px"
                clearable
                @keyup.enter="searchInhosNumbers"
              />
            </div>

            <div class="query-actions">
              <ElButton
                type="primary"
                :icon="Search"
                :loading="isLoadingInhos"
                @click="searchInhosNumbers"
              >
                Search
              </ElButton>
              <ElButton :icon="Refresh" @click="resetFilter">Reset</ElButton>
            </div>
          </div>
        </div>

        <ElAlert
          v-if="!DEMO_MODE && inhosSearchWarning"
          :title="inhosSearchWarning"
          type="warning"
          show-icon
          :closable="false"
          class="mb-3"
        />

        <div v-if="!DEMO_MODE && inhosSearchResults.length > 0" class="result-area">
          <div class="area-header">
            <span>
              Search Results ({{ inhosSearchResults.length }})
              <template v-if="inhosSearchWarning">
                , limited to {{ inhosSearchLimit }} items per request
              </template>
            </span>
            <ElButton
              type="primary"
              link
              size="small"
              @click="selectAllInhosNumbers"
            >
              Add All
            </ElButton>
          </div>
          <div class="tag-scroller">
            <ElTag
              v-for="no in inhosSearchResults"
              :key="no"
              class="result-tag"
              type="info"
              effect="plain"
              @click="selectInhosNumber(no)"
            >
              <ElIcon class="mr-1"><Plus /></ElIcon> {{ no }}
            </ElTag>
          </div>
        </div>

        <div class="selected-area">
          <div class="area-header">
            <span>{{ DEMO_MODE ? 'Selected Demo Cases' : 'Selected Case Pool' }}</span>
            <ElButton
              v-if="form.hospitalization_ids.length > 0"
              type="danger"
              link
              :icon="Delete"
              @click="clearSelectedInhos"
            >
              Clear
            </ElButton>
          </div>

          <div class="tag-wrapper">
            <ElTag
              v-for="tag in form.hospitalization_ids"
              :key="tag"
              closable
              class="selected-tag"
              @close="handleCaseClose(tag)"
            >
              {{ tag }}
            </ElTag>

            <div v-if="!DEMO_MODE" class="manual-input-wrapper">
              <ElInput
                v-if="caseInputVisible"
                ref="caseInputRef"
                v-model="caseInputValue"
                size="small"
                @keyup.enter="handleCaseInputConfirm"
                @blur="handleCaseInputConfirm"
                style="width: 120px"
              />
              <ElButton
                v-else
                size="small"
                class="dashed-btn"
                @click="showCaseInput"
              >
                + Add Manually
              </ElButton>
            </div>
          </div>
          <ElEmpty
            v-if="form.hospitalization_ids.length === 0"
            :image-size="40"
            description="No cases selected."
            class="mini-empty"
          />
        </div>
      </div>

      <div class="section-title">3. Audit Rule Configuration</div>
      <div class="query-card">
        <div class="rule-table-container">
          <div class="rule-header">
            <span class="sub-title">
              All Rules
              <span class="ml-2 text-xs text-blue-500">{{ selectedRules.length }} selected</span>
            </span>
            <ElInput
              v-model="ruleSearchQuery"
              placeholder="Search rules..."
              :prefix-icon="Search"
              clearable
              style="width: 250px"
              size="small"
            />
          </div>
          <ElAlert
            v-if="unsupportedSelectedRules.length"
            class="mb-3"
            type="warning"
            :closable="false"
            show-icon
            title="Some selected rule categories are not supported by task execution. Deselect them before creating the task."
          />
          <div class="table-card">
            <ElTable
              :data="filteredRules"
              v-loading="isLoadingRules"
              @selection-change="handleRuleSelectionChange"
              height="350"
              border
              class="task-table"
              row-key="id"
            >
              <ElTableColumn type="selection" width="50" align="center" :reserve-selection="true" />
              <ElTableColumn prop="displayRuleId" label="Rule ID" width="120" />
              <ElTableColumn label="Rule Name" min-width="180" show-overflow-tooltip>
                <template #default="{ row }">
                  <span class="font-bold text-gray-700">{{ getDisplayRuleName(row) }}</span>
                </template>
              </ElTableColumn>
              <ElTableColumn label="Rule Category" min-width="170" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ getRuleTypeLabel(row.type) || row.type || '—' }}
                </template>
              </ElTableColumn>
              <ElTableColumn label="Description" min-width="250" show-overflow-tooltip>
                <template #default="{ row }">
                  {{ getDisplayRuleDescription(row) }}
                </template>
              </ElTableColumn>
            </ElTable>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* =========================================
   复用“任务计算”的核心样式
   ========================================= */

/* 外层：浅灰背景 + 统一留白 */
.page-wrap {
  background: #f5f7fb;
  padding: 18px;
  min-height: calc(100vh - 36px);
  box-sizing: border-box;
}

/* 内层：白色卡片 */
.content-card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 18px 16px;
  box-shadow: 0 2px 10px rgba(16, 24, 40, 0.06);
}

/* 标题：左侧蓝色竖线 */
.page-title {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 6px 0 14px;
  border-bottom: 1px solid #eef2f7;
  margin-bottom: 20px;
  position: relative;
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
.header-actions {
  margin-left: auto; /* 推到右边 */
  display: flex;
  gap: 10px;
}

/* 区域容器（模仿 query-card） */
.query-card {
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 24px;
}

.query-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.form-row {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 16px;
}
.query-left {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px 16px;
}

/* 输入框组合 (Label + Input) */
.query-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.demo-case-select {
  width: 100%;
}
.query-label {
  font-size: 12px;
  color: #667085;
  font-weight: 500;
}
.label-note {
  margin-left: 8px;
  font-weight: 400;
  color: #98a2b3;
}
.demo-case-hint {
  font-size: 12px;
  color: #98a2b3;
}
.required {
  color: #f56c6c;
  margin-left: 2px;
}

.query-actions {
  display: flex;
  gap: 10px;
  padding-bottom: 2px; /* 对齐 Input */
}

/* 章节标题 (模仿 list-title) */
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #344054;
  margin: 0 0 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-badge {
  background: #f2f4f7;
  color: #667085;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: normal;
}

/* 表格容器 (模仿 table-card) */
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
  height: 50px;
}

/* =========================================
   新增页面特有的样式补充
   ========================================= */

/* 结果展示区 */
.result-area {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #eef2f7;
}
.area-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #667085;
}
.tag-scroller {
  max-height: 80px;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.result-tag {
  cursor: pointer;
  transition: all 0.2s;
}
.result-tag:hover {
  background-color: #ecf5ff;
  border-color: #d9ecff;
  color: #409eff;
}

/* 已选区域 */
.selected-area {
  margin-top: 16px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 6px;
  padding: 12px;
}
.tag-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.selected-tag {
  background-color: #fff;
}
.manual-input-wrapper {
  display: inline-flex;
}
.dashed-btn {
  border-style: dashed;
}
.mini-empty {
  padding: 10px 0;
}
.mini-empty :deep(.el-empty__description) {
  margin-top: 5px;
}

/* 规则配置 */
.checkbox-group-styled {
  display: flex;
  gap: 16px;
}
.rule-table-container {
  margin-top: 20px;
}
.rule-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.sub-title {
  font-size: 13px;
  color: #344054;
  font-weight: 600;
}

/* 滚动条美化 */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-thumb {
  background: #d0d5dd;
  border-radius: 3px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
</style>
