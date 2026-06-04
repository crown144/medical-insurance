<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import axios from 'axios';

import {
  CircleCheck,
  CircleClose,
  Loading,
  VideoPlay,
} from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { storeToRefs } from 'pinia';

// 确保路径正确指向您的 store 文件
import { useRuleFlowStore } from '../../../store/modules/ruleFlow';

const router = useRouter();
const flowStore = useRuleFlowStore();
const { artifacts, activeTab, batchRules } = storeToRefs(flowStore);

// 单条模式状态
const isCompiling = ref(false);
const compileProgress = ref(0);
const executionCode = ref('');
const loadingText = ref('');

// 批量模式状态
const batchProgress = computed(() => {
  if (batchRules.value.length === 0) return 0;
  const finished = batchRules.value.filter(
    (i) => i.status === 'success' || i.status === 'error',
  ).length;
  return Math.floor((finished / batchRules.value.length) * 100);
});

const isBatchRunning = computed(
  () => batchProgress.value < 100 && batchProgress.value > 0,
);

// 批量详情抽屉
const detailDrawerVisible = ref(false);
const currentDetail = ref<any>(null);

// ========== 方法 ==========

// 1. 单条编译
const handleCompile = async () => {
  isCompiling.value = true;
  compileProgress.value = 0;
  executionCode.value = '';
  loadingText.value = '正在解析规则结构...';

  // 1. 模拟进度条 (1-5s)
  const duration = 1000 + Math.random() * 4000; // 1000ms - 5000ms
  const interval = 100;
  const steps = duration / interval;
  const increment = 100 / steps;

  const timer = setInterval(() => {
    if (compileProgress.value < 90) {
      compileProgress.value = Math.min(90, compileProgress.value + increment);
    }
  }, interval);

  try {
    // 等待随机时间
    await new Promise((resolve) => setTimeout(resolve, duration));
    clearInterval(timer);
    compileProgress.value = 100;
    loadingText.value = '编译完成，正在获取执行函数...';

    // 2. 调用后端 API
    // 使用规则输入内容匹配 description
    const response = await axios.get('http://127.0.0.1:8000/api/rules/', {
      params: { search: flowStore.ruleText },
    });

    if (
      response.data &&
      response.data.results &&
      response.data.results.length > 0
    ) {
      // 匹配成功，展示 rule_code
      executionCode.value = response.data.results[0].rule_code || '# 规则代码为空';
      // 🟢 修复：同步更新 Store 状态，确保下一步可以通行
      flowStore.artifacts = {
        generated_code: executionCode.value,
        logic_tree: {},
        atom_list: [],
      };
      ElMessage.success('编译生成成功');
    } else {
      executionCode.value =
        '# 未找到匹配的规则，请确保规则描述与数据库一致。\n# 输入内容: ' +
        flowStore.ruleText;
      ElMessage.warning('未找到匹配的规则');
    }
  } catch (error: any) {
    console.error(error);
    executionCode.value = '# 获取失败: ' + (error.message || '网络错误');
    ElMessage.error('请求失败');
  } finally {
    isCompiling.value = false;
  }
};

// 2. 批量编译
const handleBatchStart = async () => {
  if (batchRules.value.length === 0) return;
  // 重置状态
  batchRules.value.forEach((i) => (i.status = 'pending'));
  // 开始
  await flowStore.runBatchCompile();
  ElMessage.success('批量编译完成');
};

const viewBatchDetail = (row: any) => {
  if (row.status !== 'success') return;
  currentDetail.value = row;
  detailDrawerVisible.value = true;
};

const handleNext = () => {
  if (activeTab.value === 'manual' && !artifacts.value) {
    ElMessage.warning('请先完成编译');
    return;
  }
  if (activeTab.value === 'batch' && batchProgress.value < 100) {
    ElMessage.warning('请等待所有规则编译完成');
    return;
  }
  router.push({ name: 'RuleTestRun' }); // 更新为新的合并页面名称
};
</script>

<template>
  <div class="qms-page">
    <el-card class="qms-card header-card" shadow="never">
      <div class="qms-titlebar">
        <div class="qms-title">
          <span class="qms-title__bar"></span>
          <div class="qms-title__text">
            <div class="qms-title__name">规则编译生成</div>
            <div class="qms-title__desc">
              步骤 2/3：
              <span v-if="activeTab === 'batch'">批量处理队列中... Agent 集群正在并行解析。</span>
              <span v-else>解析自然语言规则，映射为标准编码，编写对应的的 Python 执行函数</span>
            </div>
          </div>
        </div>
        <div class="qms-actions">
          <el-button type="primary" size="large" @click="handleNext">
            下一步：执行与校验
          </el-button>
        </div>
      </div>
    </el-card>

    <template v-if="activeTab === 'manual'">
      <el-card class="qms-card control-card" shadow="never">
        <div class="control-bar">
          <el-button
            type="primary"
            :loading="isCompiling"
            @click="handleCompile"
            :icon="VideoPlay"
          >
            开始编译生成
          </el-button>

          <div v-if="isCompiling || executionCode" class="progress-area" style="flex: 1; margin-left: 20px;">
             <div v-if="isCompiling" class="compile-progress">
                <span class="label">{{ loadingText }}</span>
                <el-progress :percentage="Math.floor(compileProgress)" :stroke-width="10" />
             </div>
          </div>
        </div>
      </el-card>

      <div v-if="executionCode" class="qms-content-wrapper mt-4">
        <el-card class="qms-card flex-1" shadow="never">
            <template #header>
              <div class="qms-card-header">
                <div class="qms-card-title">执行函数 (Execute Rule)</div>
                <el-tag type="success" size="small">Python</el-tag>
              </div>
            </template>
            <el-input
                v-model="executionCode"
                type="textarea"
                :rows="20"
                readonly
                class="code-textarea"
                style="font-family: monospace;"
            />
        </el-card>
      </div>
      <div v-else-if="!isCompiling" class="empty-state">
        <el-empty description="请点击“开始编译生成”以生成产物" />
      </div>
    </template>

    <template v-else>
      <div class="qms-content-wrapper batch-container">
        <el-card class="qms-card mb-4" shadow="never">
          <div class="batch-header">
            <div class="progress-box">
              <div class="label">
                批处理进度 ({{ batchRules.length }} 条规则)
              </div>
              <el-progress
                :percentage="batchProgress"
                :status="batchProgress === 100 ? 'success' : ''"
                :stroke-width="18"
                text-inside
              />
            </div>
            <el-button
              type="primary"
              size="large"
              :icon="VideoPlay"
              @click="handleBatchStart"
              :disabled="batchProgress > 0 && batchProgress < 100"
            >
              {{ batchProgress === 0 ? '启动批量编译' : '重新编译' }}
            </el-button>
          </div>
        </el-card>

        <el-card
          class="qms-card flex-1"
          shadow="never"
          body-style="padding: 0; height: 100%; display: flex; flex-direction: column;"
        >
          <el-table
            :data="batchRules"
            style="width: 100%; flex: 1"
            height="100%"
          >
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column
              prop="rule"
              label="原始规则文本"
              min-width="300"
              show-overflow-tooltip
            />

            <el-table-column label="状态" width="150" align="center">
              <template #default="{ row }">
                <div v-if="row.status === 'loading'" class="status-loading">
                  <el-icon class="is-loading"><Loading /></el-icon> 编译中...
                </div>
                <div
                  v-else-if="row.status === 'success'"
                  class="status-success"
                >
                  <el-icon><CircleCheck /></el-icon> 成功
                </div>
                <div v-else-if="row.status === 'error'" class="status-error">
                  <el-icon><CircleClose /></el-icon> 失败
                </div>
                <div v-else class="status-pending">等待中</div>
              </template>
            </el-table-column>

            <el-table-column label="产物" min-width="200">
              <template #default="{ row }">
                <div v-if="row.artifacts" class="artifact-tags">
                  <el-tag size="small" type="info">逻辑树</el-tag>
                  <el-tag size="small" type="info">Python 代码</el-tag>
                </div>
              </template>
            </el-table-column>

            <el-table-column
              label="操作"
              width="120"
              fixed="right"
              align="center"
            >
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  :disabled="row.status !== 'success'"
                  @click="viewBatchDetail(row)"
                >
                  详情
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </template>

    <el-drawer v-model="detailDrawerVisible" title="规则编译详情" size="60%">
      <div
        v-if="currentDetail && currentDetail.artifacts"
        class="drawer-content"
      >
        <h3>逻辑摘要</h3>
        <div class="code-box">{{ currentDetail.artifacts.logic_summary }}</div>

        <h3 class="mt-4">生成的代码</h3>
        <div class="code-box">{{ currentDetail.artifacts.code_snippet }}</div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
/* 复用之前的样式 */
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
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.qms-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
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
.qms-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.qms-card-title {
  font-weight: 600;
  color: #303133;
  font-size: 15px;
}

/* 单条模式样式 */
.control-card {
  flex-shrink: 0;
}
.control-bar {
  display: flex;
  align-items: center;
  gap: 24px;
}
.control-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.label {
  font-size: 14px;
  color: #606266;
}
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.h-full-row {
  height: 100%;
  display: flex;
  align-items: stretch;
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
.flex-1 {
  flex: 1;
}
.flex-col {
  flex-direction: column;
}
.gap-4 {
  gap: 16px;
}
.h-full {
  height: 100%;
}
.qms-prebox {
  background: #fafafa;
  border-radius: 4px;
  border: 1px solid #eee;
  padding: 12px;
  flex: 1;
  overflow: auto;
}
.qms-pre {
  margin: 0;
  font-family: 'Menlo', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.8;
  color: #2c3e50;
}

/* 批量模式样式 */
.batch-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.batch-header {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
}
.progress-box {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.progress-box .label {
  font-size: 14px;
  color: #606266;
  font-weight: 600;
}

.status-loading {
  color: #409eff;
}
.status-success {
  color: #67c23a;
}
.status-error {
  color: #f56c6c;
}
.status-pending {
  color: #909399;
}

.artifact-tags {
  display: flex;
  gap: 6px;
}
.drawer-content {
  padding: 0 10px;
}
.code-box {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  font-family: monospace;
  border: 1px solid #e4e7ed;
}
.mt-4 {
  margin-top: 16px;
}
.mb-4 {
  margin-bottom: 16px;
}
</style>
