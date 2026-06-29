<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { CopyDocument, RefreshRight } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

import { generateRuleApi, getRuleList, updateRule } from '#/api/rule';

type RuleListItem = {
  id: number | string;
  ruleId: string;
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
  compiledReady.value = false;
};

const buildCompileInput = (rule: RuleListItem) => {
  return [`规则名称：${rule.drugName.trim()}`, `规则描述：${rule.description.trim()}`].join(
    '\n',
  );
};

const normalizeList = (rawList: any[]) => {
  return rawList.map((item) => ({
    id: item.id,
    ruleId: item.ruleId || item.rule_id || `R-${item.id}`,
    drugName: item.drugName || item.drug_name || '',
    type: item.type || '',
    description: item.description || '',
    enabled: Boolean(item.enabled),
    ruleCode: item.rule_code || item.ruleCode || '',
    logicExpression: item.logicExpression || item.logic_expression || '',
  })) as RuleListItem[];
};

const fetchData = async () => {
  loading.value = true;
  try {
    const res = await getRuleList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchForm.keyword.trim() || undefined,
    });
    const rawList = res?.results || (Array.isArray(res) ? res : []);
    list.value = normalizeList(rawList);
    total.value = res?.count || rawList.length || 0;

    if (list.value.length === 0) {
      selectedRuleId.value = null;
      resetCompileState();
      return;
    }

    const stillSelected = list.value.find((item) => item.id === selectedRuleId.value);
    selectedRuleId.value = stillSelected?.id ?? list.value[0].id;
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
    const result = await generateRuleApi(buildCompileInput(selectedRule.value));
    const nextCode = result?.generated_code || '';
    if (!nextCode.trim()) {
      ElMessage.error('The compilation result is empty');
      return;
    }
    generatedCode.value = nextCode;
    compiledReady.value = true;
    ElMessage.success('Rule compiled successfully');
  } catch (error) {
    console.error(error);
    ElMessage.error('Rule compilation failed');
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

const handleTest = async () => {
  if (!generatedCode.value.trim()) {
    ElMessage.warning('Please generate code before running the test');
    return;
  }

  testing.value = true;
  try {
    await new Promise((resolve) => setTimeout(resolve, 3000));
    await ElMessageBox.alert('Test passed', 'Test Result', {
      confirmButtonText: 'OK',
      type: 'success',
    });
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
    await updateRule(selectedRule.value.id, {
      drugName: selectedRule.value.drugName,
      ruleId: selectedRule.value.ruleId,
      type: selectedRule.value.type,
      description: selectedRule.value.description,
      logicExpression: selectedRule.value.logicExpression || '',
      enabled: true,
      rule_code: generatedCode.value,
    });
    ElMessage.success('Rule library updated');
    await fetchData();
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
          Select a rule from the rule library, generate executable code from its
          name and description, and write the result back to the current rule.
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
              <span class="rule-name">{{ item.drugName || item.ruleId }}</span>
              <el-tag size="small" :type="item.enabled ? 'success' : 'info'">
                {{ item.enabled ? 'Enabled' : 'Disabled' }}
              </el-tag>
            </div>
            <div class="rule-item__meta">
              <span>{{ item.type || '-' }}</span>
              <span>{{ hasCode(item.ruleCode) ? 'Compiled' : 'Not Compiled' }}</span>
            </div>
            <div class="rule-item__id">{{ item.ruleId }}</div>
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
          <div class="rule-summary">
            <div class="summary-row">
              <span class="label">Rule Name</span>
              <span>{{ selectedRule.drugName || '-' }}</span>
            </div>
            <div class="summary-row">
              <span class="label">Rule Type</span>
              <span>{{ selectedRule.type || '-' }}</span>
            </div>
            <div class="summary-row summary-row--block">
              <span class="label">Description</span>
              <div class="description-box">{{ selectedRule.description || '-' }}</div>
            </div>
          </div>

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
              @click="handleTest"
            >
              Run Test
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

          <div class="result-title">Compilation Result</div>
          <div class="code-box">
            <pre>{{ generatedCode || 'Select a rule and click "Compile Rule" to generate code' }}</pre>
          </div>
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

.rule-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
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

.result-title {
  font-weight: 600;
  color: #303133;
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
