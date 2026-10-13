<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import type { RuleGenerateResult } from '#/api/rule';

import { CopyDocument, RefreshRight } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import {
  generateRuleApi,
  getRuleList,
  updateRule,
  validateRuleCodeApi,
} from '#/api/rule';
import {
  filterCompileRules,
  getDisplayRuleId,
  getRuleDescriptionEnglish,
  getRuleNameEnglish,
  getRuleTypeLabel,
} from '#/config/rule-type';

type RuleListItem = {
  id: number | string;
  ruleId: string;
  displayRuleId?: string;
  drugName: string;
  type: string;
  description: string;
  enabled: boolean;
  ruleCode: string;
  logicExpression?: string;
};

const loading = ref(false);
const compiling = ref(false);
const saving = ref(false);
const testing = ref(false);
const compiledReady = ref(false);
const list = ref<RuleListItem[]>([]);
const total = ref(0);
const currentPage = ref(1);
const pageSize = ref(10);
const selectedRuleId = ref<number | string | null>(null);
const generatedCode = ref('');
const compilationResult = ref<RuleGenerateResult | null>(null);

const searchForm = reactive({
  keyword: '',
});

const hasCode = (value?: null | string) => Boolean((value || '').trim());

const selectedRule = computed(() => {
  return list.value.find((item) => item.id === selectedRuleId.value) || null;
});

const canCompile = computed(() => {
  return Boolean(selectedRule.value && selectedRule.value.description.trim());
});

const canSave = computed(() => {
  return Boolean(
    selectedRule.value &&
      compiledReady.value &&
      generatedCode.value.trim() &&
      !saving.value,
  );
});

const resetCompileState = () => {
  generatedCode.value = '';
  compilationResult.value = null;
  compiledReady.value = false;
};

const displayIrr = computed(() => {
  if (!selectedRule.value) return null;
  return {
    ruleCategory: getRuleTypeLabel(selectedRule.value.type) || 'Translation unavailable',
    constraintObject:
      getRuleNameEnglish(selectedRule.value.drugName) || 'Translation unavailable',
    constraintCondition:
      getRuleDescriptionEnglish(selectedRule.value.description) ||
      'Translation unavailable',
  };
});

const formatParameters = (parameters: Record<string, any>) => {
  return Object.entries(parameters || {})
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
    .join('; ');
};

const getErrorMessage = (error: any, fallback: string) => {
  const data = error?.response?.data;
  if (typeof data === 'string') {
    if (data.includes('504 Gateway Time-out')) {
      return 'Rule compilation timed out. Please try again later or shorten the rule description.';
    }
    return data.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() || fallback;
  }
  return (
    data?.message ||
    data?.detail ||
    data?.error ||
    data?.result?.error ||
    error?.message ||
    fallback
  );
};

const normalizeList = (rawList: any[]) => {
  return rawList.map((item) => ({
    id: item.id,
    ruleId: item.ruleId || item.rule_id || `R-${item.id}`,
    displayRuleId: getDisplayRuleId(item.ruleId || item.rule_id || `R-${item.id}`),
    drugName: item.drugName || item.drug_name || '',
    type: item.type || '',
    description: item.description || '',
    enabled: Boolean(item.enabled),
    ruleCode: item.rule_code || item.ruleCode || '',
    logicExpression: item.logicExpression || item.logic_expression || '',
  })) as RuleListItem[];
};

const matchesKeyword = (item: RuleListItem, keyword: string) => {
  if (!keyword) return true;
  const text = [
    item.ruleId,
    item.drugName,
    item.type,
    item.description,
  ].join(' ');
  return text.toLowerCase().includes(keyword.toLowerCase());
};

const fetchData = async () => {
  loading.value = true;
  try {
    const res = await getRuleList({
      compile: true,
      paginate: false,
      ordering: 'id',
    });
    const rawList = res?.results || (Array.isArray(res) ? res : []);
    const keyword = searchForm.keyword.trim();
    const demoList = filterCompileRules(normalizeList(rawList)).filter((item) =>
      matchesKeyword(item, keyword),
    );
    total.value = demoList.length;
    const start = (currentPage.value - 1) * pageSize.value;
    list.value = demoList.slice(start, start + pageSize.value);

    if (list.value.length === 0) {
      selectedRuleId.value = null;
      resetCompileState();
      return;
    }

    const stillSelected = list.value.find((item) => item.id === selectedRuleId.value);
    selectedRuleId.value = stillSelected?.id ?? list.value[0]!.id;
    resetCompileState();
  } catch (error) {
    console.error(error);
    ElMessage.error('Failed to load the rule list');
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
  currentPage.value = 1;
  fetchData();
};

const handleSelectRule = (rule: RuleListItem) => {
  selectedRuleId.value = rule.id;
  resetCompileState();
};

const handleCompile = async () => {
  if (!selectedRule.value) {
    ElMessage.warning('Please select a rule first');
    return;
  }
  if (!selectedRule.value.description.trim()) {
    ElMessage.warning('The selected rule has no description and cannot be compiled');
    return;
  }

  compiling.value = true;
  resetCompileState();
  try {
    const result = await generateRuleApi(selectedRule.value.id);
    compilationResult.value = result;
    const nextCode = result?.generated_code || '';
    if (!nextCode.trim()) {
      const validationError = result?.validation?.errors?.join('; ');
      ElMessage.error(validationError || 'The compilation result is empty');
      return;
    }
    generatedCode.value = nextCode;
    compiledReady.value = true;
    ElMessage.success('Rule compiled successfully');
  } catch (error) {
    console.error(error);
    ElMessage.error(getErrorMessage(error, 'Rule compilation failed'));
  } finally {
    compiling.value = false;
  }
};

const handleCopy = async () => {
  if (!generatedCode.value.trim()) {
    ElMessage.warning('There is no code available to copy');
    return;
  }
  try {
    await navigator.clipboard.writeText(generatedCode.value);
    ElMessage.success('Generated code copied');
  } catch (error) {
    console.error(error);
    ElMessage.error('Copy failed');
  }
};

const handleValidate = async () => {
  if (!generatedCode.value.trim()) {
    ElMessage.warning('Please generate code before validation');
    return;
  }

  testing.value = true;
  try {
    const validation = await validateRuleCodeApi(generatedCode.value);
    const valid = Boolean(validation?.valid);
    const message = valid
      ? 'The generated program is valid.'
      : validation?.errors?.join('\n') || 'Program validation failed.';
    await ElMessageBox.alert(message, 'Program Validation', {
      confirmButtonText: 'OK',
      type: valid ? 'success' : 'error',
    });
  } catch (error) {
    ElMessage.error(getErrorMessage(error, 'Program validation failed'));
  } finally {
    testing.value = false;
  }
};

const handleSave = async () => {
  if (!selectedRule.value) {
    ElMessage.warning('Please select a rule first');
    return;
  }
  if (!compiledReady.value || !generatedCode.value.trim()) {
    ElMessage.warning('Please complete compilation first');
    return;
  }

  saving.value = true;
  try {
    await updateRule(
      selectedRule.value.id,
      {
        drug_name: selectedRule.value.drugName,
        ruleId: selectedRule.value.ruleId,
        type: selectedRule.value.type,
        description: selectedRule.value.description,
        logicExpression:
          compilationResult.value?.logical_expression ||
          selectedRule.value.logicExpression ||
          '',
        enabled: true,
        rule_code: generatedCode.value,
      },
      { compileScope: true },
    );
    ElMessage.success('Rule library updated');
    selectedRule.value.ruleCode = generatedCode.value;
    selectedRule.value.enabled = true;
  } catch (error: any) {
    console.error(error);
    const message =
      error?.response?.data?.enabled?.[0] ||
      error?.response?.data?.enabled ||
      error?.response?.data?.detail ||
      'Failed to update the rule library';
    ElMessage.error(message);
  } finally {
    saving.value = false;
  }
};

onMounted(fetchData);
</script>

<template>
  <div class="compile-page">
    <div class="page-title">
      <div class="title-bar"></div>
      <div>
        <div class="title-main">Rule Compilation</div>
        <div class="title-sub">
          Decompose an existing rule, bind it to approved EMR capabilities, and
          compile a deterministic Python program.
        </div>
      </div>
    </div>

    <div class="compile-layout">
      <el-card class="left-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>Rule Library</span>
            <el-button link type="primary" :icon="RefreshRight" @click="fetchData">Refresh</el-button>
          </div>
        </template>

        <div class="search-bar">
          <el-input
            v-model="searchForm.keyword"
            clearable
            placeholder="Search by rule name, code, or description"
            @keyup.enter="handleSearch"
          />
          <div class="search-actions">
            <el-button type="primary" @click="handleSearch">Search</el-button>
            <el-button @click="handleReset">Reset</el-button>
          </div>
        </div>

        <div v-loading="loading" class="rule-list">
          <div
            v-for="item in list"
            :key="item.id"
            class="rule-item"
            :class="{ active: item.id === selectedRuleId }"
            @click="handleSelectRule(item)"
          >
            <div class="rule-item__top">
              <span class="rule-name">
                {{ getRuleNameEnglish(item.drugName) || 'Translation unavailable' }}
              </span>
              <el-tag size="small" :type="item.enabled ? 'success' : 'info'">
                {{ item.enabled ? 'Enabled' : 'Disabled' }}
              </el-tag>
            </div>
            <div class="rule-item__meta">
              <span>{{ getRuleTypeLabel(item.type) || 'Translation unavailable' }}</span>
              <span>{{ hasCode(item.ruleCode) ? 'Compiled' : 'Not Compiled' }}</span>
            </div>
            <div class="rule-item__id">{{ item.displayRuleId || getDisplayRuleId(item.ruleId) }}</div>
          </div>
          <el-empty
            v-if="!loading && list.length === 0"
            description="No rules available"
          />
        </div>

        <div class="pager">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next"
            small
            background
            @current-change="fetchData"
            @size-change="fetchData"
          />
        </div>
      </el-card>

      <el-card class="right-panel" shadow="never">
        <template #header>
          <div class="panel-header">
            <span>Compilation Workspace</span>
            <el-tag :type="selectedRule ? 'primary' : 'info'">
              {{
                selectedRule
                  ? hasCode(selectedRule.ruleCode)
                    ? 'Compiled'
                    : 'Not Compiled'
                  : 'No Rule Selected'
              }}
            </el-tag>
          </div>
        </template>

        <template v-if="selectedRule">
          <section class="pipeline-section">
            <div class="section-title">1. Intermediate Rule Representation (IRR)</div>
            <div class="summary-row">
              <span class="label">Rule Category</span>
              <span>{{ displayIrr?.ruleCategory }}</span>
            </div>
            <div class="summary-row">
              <span class="label">Constraint Object</span>
              <span>{{ displayIrr?.constraintObject }}</span>
            </div>
            <div class="summary-row summary-row--block">
              <span class="label">Constraint Condition</span>
              <div class="description-box">
                {{ displayIrr?.constraintCondition }}
              </div>
            </div>
          </section>

          <div class="toolbar">
            <el-button
              type="primary"
              :disabled="!canCompile"
              :loading="compiling"
              @click="handleCompile"
            >
              Compile Rule
            </el-button>
            <el-button
              :icon="CopyDocument"
              :disabled="!generatedCode.trim()"
              @click="handleCopy"
            >
              Copy Code
            </el-button>
            <el-button
              :disabled="!generatedCode.trim()"
              :loading="testing"
              @click="handleValidate"
            >
              Validate Program
            </el-button>
            <el-button
              type="success"
              :disabled="!canSave"
              :loading="saving"
              @click="handleSave"
            >
              Confirm Writeback
            </el-button>
          </div>

          <section class="pipeline-section">
            <div class="section-title">2. Atomic Constraints</div>
            <el-table
              v-if="compilationResult?.atomic_constraints?.length"
              :data="compilationResult.atomic_constraints"
              border
              size="small"
            >
              <el-table-column prop="id" label="Atomic Constraint ID" width="170" />
              <el-table-column
                prop="normalized_constraint"
                label="Normalized Constraint"
                min-width="260"
              />
              <el-table-column prop="source_span" label="Source Span" min-width="260" />
            </el-table>
            <el-empty v-else description="Compile the selected rule to view atomic constraints" />
          </section>

          <section class="pipeline-section">
            <div class="section-title">3. Logical Expression</div>
            <div class="expression-box">
              {{ compilationResult?.logical_expression || 'Compile the selected rule to view its logical expression' }}
            </div>
          </section>

          <section class="pipeline-section">
            <div class="section-title">4. Execution Bindings</div>
            <el-table
              v-if="compilationResult?.execution_bindings?.length"
              :data="compilationResult.execution_bindings"
              border
              size="small"
            >
              <el-table-column
                prop="atomic_constraint_id"
                label="Atomic Constraint ID"
                width="170"
              />
              <el-table-column label="EMR Data Source / Field" min-width="190">
                <template #default="scope">
                  {{ scope.row.data_source }} / {{ scope.row.field }}
                </template>
              </el-table-column>
              <el-table-column prop="audit_function" label="Audit Function" width="140" />
              <el-table-column label="Function Parameters" min-width="220">
                <template #default="scope">
                  {{ formatParameters(scope.row.function_parameters) || '-' }}
                </template>
              </el-table-column>
              <el-table-column
                prop="expected_condition"
                label="Expected Condition"
                min-width="220"
              />
            </el-table>
            <el-empty v-else description="Compile the selected rule to view execution bindings" />
          </section>

          <section class="pipeline-section generated-program-section">
            <div class="section-title">5. Generated Python Program</div>
            <div class="code-box">
              <pre>{{ generatedCode || 'Select a rule and click "Compile Rule" to generate code' }}</pre>
            </div>
          </section>
        </template>
        <el-empty
          v-else
          description="Please select a rule from the left panel first"
        />
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.compile-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 120px);
  padding: 18px;
  background: #f5f7fb;
}

.page-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 6px 0 14px;
}

.title-bar {
  width: 4px;
  height: 18px;
  margin-top: 3px;
  background: #409eff;
  border-radius: 3px;
}

.title-main {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}

.title-sub {
  margin-top: 4px;
  font-size: 13px;
  color: #8a94a6;
}

.compile-layout {
  display: grid;
  grid-template-columns: minmax(320px, 30%) minmax(0, 70%);
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  border-radius: 10px;
}

.left-panel :deep(.el-card__body),
.right-panel :deep(.el-card__body) {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.search-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.search-actions {
  display: flex;
  gap: 8px;
}

.rule-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  overflow-y: auto;
}

.rule-item {
  padding: 12px;
  cursor: pointer;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  transition: all 0.2s ease;
}

.rule-item:hover,
.rule-item.active {
  border-color: #409eff;
  box-shadow: 0 0 0 1px rgb(64 158 255 / 18%);
}

.rule-item__top {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  justify-content: space-between;
}

.rule-name {
  font-weight: 600;
  color: #1f2937;
}

.rule-item__meta,
.rule-item__id {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}

.rule-item__meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.pager {
  display: flex;
  justify-content: flex-end;
}

.pipeline-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}

.section-title {
  font-weight: 600;
  color: #303133;
}

.summary-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.summary-row--block {
  flex-direction: column;
  gap: 8px;
}

.label {
  min-width: 72px;
  font-weight: 600;
  color: #4b5563;
}

.description-box {
  width: 100%;
  padding: 12px;
  line-height: 1.7;
  color: #374151;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  white-space: pre-wrap;
}

.toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.expression-box {
  padding: 14px;
  color: #24364a;
  font-family:
    'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.generated-program-section {
  flex: 1;
}

.code-box {
  flex: 1;
  min-height: 320px;
  overflow: auto;
  background: #f3f8ff;
  border: 1px solid #cfe0f5;
  border-radius: 10px;
}

.code-box pre {
  margin: 0;
  padding: 16px;
  color: #24364a;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  font-family:
    'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
}

@media (width <= 1024px) {
  .compile-layout {
    grid-template-columns: 1fr;
  }

  .code-box {
    min-height: 240px;
  }
}
</style>
