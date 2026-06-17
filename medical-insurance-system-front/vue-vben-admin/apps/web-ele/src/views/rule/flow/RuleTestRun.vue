<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  CircleCheck,
  Document,
  Loading,
  Upload,
  VideoPlay,
} from '@element-plus/icons-vue';
import { ElLoading, ElMessage, ElMessageBox } from 'element-plus';
import { storeToRefs } from 'pinia';

import {
  importGeneratedRuleApi,
  runGeneratedRuleApi,
} from '../../../api/rule';
import { useRuleFlowStore } from '../../../store/modules/ruleFlow';

const flowStore = useRuleFlowStore();
const { ruleText, runResult, activeTab, batchRules, caseJsonText, artifacts } =
  storeToRefs(flowStore);

const isRunning = ref(false);
const importVisible = ref(false);
const importedInfo = ref<any>(null);
const batchImportInfo = ref<any>(null);

// 高亮相关状态
const highlightPaths = ref<Set<string>>(new Set());

// ================== JSON 高亮渲染核心逻辑 ==================

const escapeHtml = (text: any): string => {
  if (text === null || text === undefined) return '';
  const map: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;',
  };
  return String(text).replaceAll(/[&<>"']/g, (m) => map[m] ?? m);
};

// 递归将 JSON 转为带高亮的 HTML
const jsonToHtml = (
  data: any,
  currentPath: string = '$',
  indentLevel: number = 0,
): string => {
  const indent = '  '.repeat(indentLevel);
  const nextIndent = '  '.repeat(indentLevel + 1);

  let content = '';
  if (data === null) content = `<span class="json-null">null</span>`;
  else if (typeof data === 'string')
    content = `<span class="json-string">"${escapeHtml(data)}"</span>`;
  else if (typeof data === 'number')
    content = `<span class="json-number">${data}</span>`;
  else if (typeof data === 'boolean')
    content = `<span class="json-boolean">${data}</span>`;
  else if (Array.isArray(data)) {
    if (data.length === 0) return '[]';
    const items = data
      .map((item, index) => {
        const itemPath = `${currentPath}[${index}]`;
        return `${nextIndent}${jsonToHtml(item, itemPath, indentLevel + 1)}`;
      })
      .join(',\n');
    return `[\n${items}\n${indent}]`;
  } else if (typeof data === 'object') {
    const entries = Object.entries(data);
    if (entries.length === 0) return '{}';
    const items = entries
      .map(([key, value]) => {
        const keyHtml = `<span class="json-key">"${key}"</span>`;
        const itemPath = `${currentPath}.${key}`; // 简单路径构建
        const valueHtml = jsonToHtml(value, itemPath, indentLevel + 1);
        return `${nextIndent}${keyHtml}: ${valueHtml}`;
      })
      .join(',\n');
    return `{\n${items}\n${indent}}`;
  }

  // 匹配高亮路径 (这里做简单的包含匹配模拟)
  // 实际项目中可以使用 jsonpath 库来精确匹配
  if (highlightPaths.value.has(currentPath)) {
    return `<mark class="highlight-evidence">${content}</mark>`;
  }
  return content;
};

// 计算属性：生成的 HTML
const displayJsonHtml = computed(() => {
  try {
    const data = JSON.parse(caseJsonText.value);
    return jsonToHtml(data);
  } catch {
    return `<span class="text-red-500">JSON 格式错误，无法渲染</span>`;
  }
});

// ================== 核心动作 ==================

const handleRun = async () => {
  isRunning.value = true;
  highlightPaths.value.clear(); // 清除旧高亮

  try {
    if (activeTab.value === 'manual') {
      let patientData = {};
      try {
        patientData = JSON.parse(caseJsonText.value);
      } catch (error: any) {
        ElMessage.error(error?.message || '病例JSON格式错误');
        return;
      }

      const result = await runGeneratedRuleApi(ruleText.value, patientData);
      const firstViolation = result?.violations?.[0];
      runResult.value = {
        ...result,
        details: firstViolation || result,
        logs: [
          {
            level: 'INFO',
            msg: 'RuleAgent: POST /api/rules/agenta/run/',
            t: new Date().toLocaleTimeString(),
          },
          {
            level: result?.passed ? 'INFO' : 'WARN',
            msg: result?.reason || '规则执行完成',
            t: new Date().toLocaleTimeString(),
          },
        ],
      };

      firstViolation?.highlights?.forEach((item: any) => {
        if (item?.field_path) {
          highlightPaths.value.add(item.field_path);
          highlightPaths.value.add(`$.${item.field_path}`);
        }
      });

      // 模拟高亮逻辑：如果拦截了，高亮一些关键字段
      if (runResult.value && !runResult.value.passed) {
        // 这里硬编码一些路径演示效果，实际应由后端返回 evidence_paths
        highlightPaths.value.add('$.visit.admission_date');
        highlightPaths.value.add('$.visit.discharge_date');
        highlightPaths.value.add('$.diagnosis.primary[0]');
        highlightPaths.value.add('$.medication_orders[0].drug_name');
        highlightPaths.value.add('$.medication_orders[0].pay_days');
      }
    } else {
      // 批量逻辑保持不变
      let patientData = {};
      try {
        patientData = JSON.parse(caseJsonText.value);
      } catch (error: any) {
        ElMessage.error(error?.message || '病例JSON格式错误');
        return;
      }
      if (batchRules.value.length === 0) return;
      for (const item of batchRules.value) {
        if (item.status !== 'success') continue;
        item.testStatus = 'running';
        try {
          const result = await runGeneratedRuleApi(
            item.rule || item.ruleText || '',
            patientData,
          );
          item.testStatus = 'finished';
          item.testResult = result?.passed ? 'PASS' : 'INTERCEPTED';
          item.runResult = result;
        } catch (error: any) {
          item.testStatus = 'finished';
          item.testResult = 'ERROR';
          item.error = error?.response?.data?.message || error?.message || '规则执行失败';
        }
      }
    }
    ElMessage.success('执行完成');
  } finally {
    isRunning.value = false;
  }
};

const handleImport = async () => {
  await (activeTab.value === 'manual'
    ? handleImportSingle()
    : handleImportBatch());
};

const handleImportSingle = async () => {
  if (!runResult.value) return;
  try {
    await ElMessageBox.confirm(
      '确认将当前规则逻辑发布至生产环境吗？',
      '入库确认',
      {
        confirmButtonText: '确认入库',
        cancelButtonText: '取消',
        type: 'success',
      },
    );
    const loading = ElLoading.service({
      fullscreen: true,
      text: '正在入库...',
    });
    const imported = await importGeneratedRuleApi({
      description: ruleText.value,
      drugName: '规则转换导入',
      ruleCode: artifacts.value?.generated_code || runResult.value?.generated_code || '',
      status: true,
      type: '智能转换',
    });
    loading.close();

    importedInfo.value = {
      rule_id: imported?.ruleId || imported?.id,
      version: 1,
      status: imported?.enabled ? 'ACTIVE' : 'DISABLED',
      created_at: new Date().toLocaleString(),
    };
    importVisible.value = true;
  } catch {
    /* cancel */
  }
};

const handleImportBatch = async () => {
  const count = batchRules.value.filter((i) => i.testResult).length;
  try {
    await ElMessageBox.confirm(`确认批量发布 ${count} 条规则？`, '批量入库', {
      type: 'success',
    });
    const loading = ElLoading.service({
      fullscreen: true,
      text: '批量处理中...',
    });
    const importedIds: any[] = [];
    for (const item of batchRules.value) {
      if (!item.testResult || item.testResult === 'ERROR') continue;
      try {
        const imported = await importGeneratedRuleApi({
          description: item.rule || item.ruleText || '',
          drugName: item.category || `批量规则${item.id}`,
          ruleCode: item.artifacts?.generated_code || item.artifacts?.code_snippet || '',
          ruleId: item.ruleId,
          status: true,
          type: item.category || '智能转换',
        });
        item.importStatus = 'success';
        importedIds.push(imported?.ruleId || imported?.id || `R-${item.id}`);
      } catch (error: any) {
        item.importStatus = 'error';
        item.error = error?.response?.data?.message || error?.message || '规则入库失败';
      }
    }
    loading.close();
    batchImportInfo.value = {
      count,
      ids: importedIds,
    };
    importVisible.value = true;
  } catch {
    /* cancel */
  }
};

// ================== 辅助计算 ==================

const canImport = computed(() => {
  if (activeTab.value === 'manual') {
    // 只要有结果且没有系统错误(tool_missing)，无论是通过还是拦截，都可以入库
    return runResult.value && runResult.value.step !== 'tool_missing';
  } else {
    const finished = batchRules.value.filter(
      (i) => i.testStatus === 'finished',
    ).length;
    return finished > 0 && finished === batchRules.value.length;
  }
});

const batchStats = computed(() => {
  const total = batchRules.value.length;
  const finished = batchRules.value.filter(
    (i) => i.testStatus === 'finished',
  ).length;
  const passed = batchRules.value.filter((i) => i.testResult === 'PASS').length;
  const intercepted = batchRules.value.filter(
    (i) => i.testResult === 'INTERCEPTED',
  ).length;
  return {
    total,
    finished,
    passed,
    intercepted,
    progress: total ? Math.floor((finished / total) * 100) : 0,
  };
});

const handleFinish = () => {
  importVisible.value = false;
  ElMessage.success('流程结束');
};
</script>

<template>
  <div class="qms-page">
    <el-card class="qms-card header-card" shadow="never">
      <div class="qms-titlebar">
        <div class="qms-title">
          <span class="qms-title__bar"></span>
          <div class="qms-title__text">
            <div class="qms-title__name">执行与校验</div>
            <div class="qms-title__desc">
              步骤 3/3：运行验证，确认无误后直接发布至生产环境。
            </div>
          </div>
        </div>
        <div class="qms-actions">
          <el-button
            type="primary"
            size="large"
            :icon="VideoPlay"
            :loading="isRunning"
            @click="handleRun"
            plain
          >
            {{
              activeTab === 'batch'
                ? batchStats.progress === 0
                  ? '开始批量测试'
                  : '重新测试'
                : '运行模拟'
            }}
          </el-button>

          <el-button
            type="success"
            size="large"
            :icon="Upload"
            :disabled="!canImport"
            @click="handleImport"
          >
            {{
              activeTab === 'batch'
                ? `批量入库 (${batchStats.finished})`
                : '确认入库'
            }}
          </el-button>
        </div>
      </div>
    </el-card>

    <template v-if="activeTab === 'manual'">
      <div class="qms-content-wrapper">
        <el-row :gutter="16" class="h-full-row">
          <el-col :span="8" class="h-full">
            <el-card
              class="qms-card content-card"
              shadow="never"
              body-style="padding: 0; background-color: #f5f7fa;"
            >
              <div class="audit-list-header">
                <span class="title">结果条目</span>
                <el-tag
                  v-if="runResult"
                  :type="runResult.passed ? 'success' : 'danger'"
                  effect="dark"
                  size="small"
                  round
                >
                  {{ runResult.passed ? '合规通过' : '发现违规' }}
                </el-tag>
              </div>

              <div class="audit-list-body">
                <div v-if="!runResult && !isRunning" class="empty-placeholder">
                  <el-icon :size="40" color="#909399"><VideoPlay /></el-icon>
                  <p>点击上方“运行模拟”查看结果</p>
                </div>

                <div v-if="isRunning" class="loading-placeholder">
                  <el-icon class="is-loading" :size="30"><Loading /></el-icon>
                  <p>规则引擎计算中...</p>
                </div>

                <div
                  v-if="runResult && !isRunning"
                  class="audit-card"
                  :class="runResult.passed ? 'card-pass' : 'card-fail'"
                >
                  <div class="card-header">
                    <div class="rule-name">
                      <span
                        class="status-dot"
                        :class="runResult.passed ? 'bg-green' : 'bg-red'"
                      ></span>
                      当前规则逻辑
                    </div>
                    <el-tag size="small" effect="plain" type="info">
                      单据审核
                    </el-tag>
                  </div>

                  <div class="card-desc">
                    {{ ruleText }}
                  </div>

                  <div
                    class="card-result-box"
                    :class="runResult.passed ? 'box-pass' : 'box-fail'"
                  >
                    <div class="result-title">
                      判定结论：{{
                        runResult.passed ? '通过 (PASS)' : '拦截 (INTERCEPTED)'
                      }}
                    </div>
                    <div class="result-reason">
                      {{ runResult.reason || '规则运行正常，未触发拦截条件。' }}
                    </div>
                  </div>

                  <div class="evidence-link" v-if="!runResult.passed">
                    关联证据：{{ highlightPaths.size }} 处高亮
                  </div>
                </div>
              </div>
            </el-card>
          </el-col>

          <el-col :span="16" class="h-full">
            <el-card
              class="qms-card content-card"
              shadow="never"
              body-style="padding: 0;"
            >
              <template #header>
                <div class="qms-card-header">
                  <div class="qms-card-title">
                    <el-icon class="mr-1"><Document /></el-icon> 原始病历预览
                    (JSON Evidence)
                  </div>
                  <el-button
                    v-if="highlightPaths.size > 0"
                    size="small"
                    type="warning"
                    plain
                  >
                    跳转高亮 ({{ highlightPaths.size }})
                  </el-button>
                </div>
              </template>
              <div class="json-viewer">
                <pre v-html="displayJsonHtml"></pre>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>
    </template>

    <template v-else>
      <div class="qms-content-wrapper batch-container">
        <el-row :gutter="16" class="mb-4">
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-num">{{ batchStats.total }}</div>
              <div class="stat-label">总任务数</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-num success-text">{{ batchStats.passed }}</div>
              <div class="stat-label">测试通过</div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-num warning-text">
                {{ batchStats.intercepted }}
              </div>
              <div class="stat-label">成功拦截</div>
            </div>
          </el-col>
        </el-row>

        <el-card
          class="qms-card flex-1"
          shadow="never"
          body-style="padding: 0; height: 100%; display: flex; flex-direction: column;"
        >
          <template #header>
            <div class="batch-list-header">
              <span>测试结果与发布状态</span>
              <el-progress
                :percentage="batchStats.progress"
                :stroke-width="10"
                style="width: 200px"
                :show-text="false"
              />
            </div>
          </template>
          <el-table
            :data="batchRules"
            style="width: 100%; flex: 1"
            height="100%"
          >
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column
              prop="rule"
              label="规则描述"
              min-width="300"
              show-overflow-tooltip
            />
            <el-table-column label="测试结果" width="140" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.testResult === 'PASS'" type="success">
                  PASS
                </el-tag>
                <el-tag
                  v-else-if="row.testResult === 'INTERCEPTED'"
                  type="warning"
                >
                  INTERCEPTED
                </el-tag>
                <span v-else class="text-gray">-</span>
              </template>
            </el-table-column>
            <el-table-column label="发布状态" width="140" align="center">
              <template #default="{ row }">
                <div v-if="row.importStatus === 'success'" class="text-green">
                  <el-icon><CircleCheck /></el-icon> 已发布
                </div>
                <div v-else class="text-gray">待发布</div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </template>

    <el-dialog
      v-model="importVisible"
      title="🎉 操作成功"
      width="600px"
      align-center
    >
      <div style="text-align: center; padding: 20px">
        <el-icon :size="60" color="#67c23a"><CircleCheck /></el-icon>
        <h2 style="margin: 10px 0">规则已成功入库</h2>
        <p style="color: #666">
          {{
            activeTab === 'manual'
              ? `规则 ID: ${importedInfo?.rule_id}`
              : `批量处理: ${batchImportInfo?.count} 条规则`
          }}
        </p>
      </div>
      <template #footer>
        <el-button type="primary" @click="handleFinish"> 完成 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 基础布局 */
.qms-page {
  padding: 16px;
  background-color: #f0f2f5;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.header-card {
  flex-shrink: 0;
}
.qms-content-wrapper {
  flex: 1;
  min-height: 0;
}
.h-full-row,
.h-full {
  height: 100%;
}
.qms-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.content-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.content-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 标题栏 */
.qms-titlebar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.qms-title {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.qms-title__bar {
  width: 4px;
  height: 20px;
  background: #2f6dff;
  border-radius: 2px;
  margin-top: 3px;
}
.qms-title__name {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}
.qms-title__desc {
  margin-top: 4px;
  font-size: 13px;
  color: #909399;
}
.qms-actions {
  display: flex;
  gap: 12px;
}

/* 左侧：审计条目列表风格 */
.audit-list-header {
  padding: 12px 16px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.audit-list-header .title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}
.audit-list-body {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
}

.empty-placeholder,
.loading-placeholder {
  text-align: center;
  margin-top: 40px;
  color: #909399;
}
.loading-placeholder p,
.empty-placeholder p {
  font-size: 13px;
  margin-top: 8px;
}

/* 卡片样式复刻 */
.audit-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  position: relative;
  transition: all 0.2s;
  cursor: pointer;
}
.audit-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}
.card-pass {
  border-left: 4px solid #67c23a;
}
.card-fail {
  border-left: 4px solid #f56c6c;
  border-color: #fab6b6;
  background: #fff;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.rule-name {
  font-weight: 700;
  font-size: 15px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.bg-green {
  background: #67c23a;
}
.bg-red {
  background: #f56c6c;
}

.card-desc {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
  line-height: 1.5;
}

.card-result-box {
  padding: 10px;
  border-radius: 4px;
  font-size: 12px;
  margin-bottom: 10px;
}
.box-pass {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px dashed #c2e7b0;
}
.box-fail {
  background: #fef0f0;
  border: 1px dashed #f56c6c;
  color: #f56c6c;
}
.result-title {
  font-weight: bold;
  margin-bottom: 4px;
}

.evidence-link {
  text-align: right;
  font-size: 12px;
  color: #409eff;
  cursor: pointer;
  font-weight: 500;
}

/* 右侧：JSON 预览器 */
.qms-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.qms-card-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}
.json-viewer {
  flex: 1;
  padding: 20px;
  overflow: auto;
  background: #fff;
}
.json-viewer :deep(pre) {
  margin: 0;
  font-family: 'Menlo', 'Monaco', monospace;
  font-size: 13px;
  color: #2c3e50;
  line-height: 1.6;
  white-space: pre-wrap;
}

/* JSON 语法高亮色 */
.json-viewer :deep(.json-key) {
  color: #0451a5;
  font-weight: 600;
}
.json-viewer :deep(.json-string) {
  color: #a31515;
}
.json-viewer :deep(.json-number) {
  color: #098658;
}
.json-viewer :deep(.json-boolean) {
  color: #0000ff;
}
.json-viewer :deep(.json-null) {
  color: #0000ff;
}

/* 核心高亮样式 */
.json-viewer :deep(mark.highlight-evidence) {
  background-color: #fff8c5;
  border-bottom: 2px solid #d2a106;
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

/* 批量样式 */
.batch-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  text-align: center;
}
.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}
.stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.success-text {
  color: #67c23a;
}
.warning-text {
  color: #e6a23c;
}
.mb-4 {
  margin-bottom: 16px;
}
.batch-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 10px;
}
.text-green {
  color: #67c23a;
  display: flex;
  align-items: center;
  gap: 4px;
}
.text-gray {
  color: #c0c4cc;
}
.flex-1 {
  flex: 1;
}
.mr-1 {
  margin-right: 6px;
}
</style>
