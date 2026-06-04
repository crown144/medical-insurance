<script setup lang="ts">
import type { UploadFile } from 'element-plus';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { Delete, Document, UploadFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { storeToRefs } from 'pinia';

// 确保路径正确指向您的 store 文件
import { useRuleFlowStore } from '../../../store/modules/ruleFlow';

// 1. 获取 Store 和 Router
const flowStore = useRuleFlowStore();
const { ruleText, caseJsonText, caseJsonValid } = storeToRefs(flowStore);
const router = useRouter();

// 2. 页面状态
const activeTab = ref('manual'); // 'manual' | 'batch'
const isUploading = ref(false);
const batchList = ref<any[]>([]); // 模拟解析后的Excel数据

// 3. 上传逻辑 (模拟解析 Excel)
const handleUploadChange = (uploadFile: UploadFile) => {
  isUploading.value = true;

  // 模拟读取 Excel 的延迟
  setTimeout(() => {
    isUploading.value = false;
    // 模拟解析出的数据
    batchList.value = [
      {
        id: 101,
        rule: '限新发的缺血性脑梗死，支付不超过14天。',
        category: '限定支付',
      },
      {
        id: 102,
        rule: '门诊统筹支付限额为每人每年2000元。',
        category: '限额管理',
      },
      {
        id: 103,
        rule: '参保人住院分娩，统筹基金定额支付1000元。',
        category: '生育保险',
      },
      {
        id: 104,
        rule: '高血压门诊用药，需在定点医疗机构开具。',
        category: '慢病管理',
      },
    ];
    ElMessage.success(`成功解析 ${batchList.value.length} 条规则`);
  }, 600);
};

const removeBatchItem = (index: number) => {
  batchList.value.splice(index, 1);
};

const clearBatch = () => {
  batchList.value = [];
};

// 4. 下一步逻辑 (关键修复部分)
const handleNext = () => {
  // 校验 JSON
  if (!caseJsonValid.value.ok) {
    ElMessage.error('病例JSON格式错误，无法继续');
    return;
  }

  // 【修复 1】同步页面模式到 Store
  flowStore.activeTab = activeTab.value;

  // 分支处理
  if (activeTab.value === 'manual') {
    // 模式 A: 单条录入
    if (!ruleText.value.trim()) {
      ElMessage.warning('请输入规则文本');
      return;
    }
    // ruleText 已经是响应式的，无需额外操作
  } else {
    // 模式 B: 批量导入
    if (batchList.value.length === 0) {
      ElMessage.warning('请上传包含规则的 Excel 文件');
      return;
    }

    // 【修复 2】将本地解析的数据，格式化后存入 Store 的 batchRules
    // 这样下一页 (RuleCompileGenerate) 才能读取到列表并显示
    flowStore.batchRules = batchList.value.map((item) => ({
      id: item.id,
      rule: item.rule,
      status: 'pending', // 初始化状态为等待中
      artifacts: null, // 清空产物
    }));

    ElMessage.success(`已加载 ${batchList.value.length} 条规则进入批量队列`);
  }

  router.push({ name: 'RuleCompileGenerate' });
};

const copyText = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制');
  } catch {
    ElMessage.error('复制失败');
  }
};

const handleConfirm = () => {
  if (!ruleText.value.trim()) {
    ElMessage.warning('请输入规则文本');
    return;
  }
  ElMessage.success('规则已确认');
};

const handleReset = () => {
  ruleText.value = '';
  ElMessage.info('已重置输入');
};
</script>
<template>
  <div class="qms-page">
    <el-card class="qms-card header-card" shadow="never">
      <div class="qms-titlebar">
        <div class="qms-title">
          <span class="qms-title__bar"></span>
          <div class="qms-title__text">
            <div class="qms-title__name">规则导入</div>
            <div class="qms-title__desc">
              步骤 1/3：支持单条录入或批量 Excel 上传，并配置基准测试病例。
            </div>
          </div>
        </div>
        <div class="qms-actions">
          <el-button type="primary" size="large" @click="handleNext">
            下一步：编译生成
          </el-button>
        </div>
      </div>
    </el-card>

    <div class="qms-content-wrapper">
      <el-row :gutter="16" class="h-full">
        <el-col :span="12" class="h-full">
          <el-card class="qms-card content-card" shadow="never">
            <template #header>
              <div class="qms-card-header no-border">
                <el-radio-group v-model="activeTab" size="default">
                  <el-radio-button label="manual">
                    <el-icon class="mr-1"><Document /></el-icon> 单条录入
                  </el-radio-button>
                  <el-radio-button label="batch">
                    <el-icon class="mr-1"><UploadFilled /></el-icon> 批量导入
                  </el-radio-button>
                </el-radio-group>

                <el-tag type="info" effect="plain" size="small">
                  Natural Language
                </el-tag>
              </div>
            </template>

            <div v-show="activeTab === 'manual'" class="input-wrapper">
              <el-input
                v-model="ruleText"
                type="textarea"
                class="qms-textarea full-height-input"
                placeholder="请输入医保规则，例如：限新发的缺血性脑梗死，支付不超过14天..."
                resize="none"
              />
              <div class="manual-actions mt-2 mb-2" style="display: flex; gap: 10px; justify-content: flex-end;">
                <el-button type="default" @click="handleReset">重置</el-button>
                <el-button type="primary" @click="handleConfirm">确认</el-button>
              </div>
              <div class="qms-hint">
                <i class="el-icon-info"></i>
                示例：限新发的缺血性脑梗死，支付不超过14天。
              </div>
            </div>

            <div v-show="activeTab === 'batch'" class="batch-wrapper">
              <div v-if="batchList.length === 0" class="upload-area">
                <el-upload
                  class="upload-box"
                  drag
                  action="#"
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="handleUploadChange"
                  accept=".xlsx, .xls"
                >
                  <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
                  <div class="el-upload__text">
                    拖拽 Excel 文件到此处，或 <em>点击上传</em>
                  </div>
                  <template #tip>
                    <div class="el-upload__tip">
                      支持 .xlsx / .xls 文件，第一列为规则描述
                    </div>
                  </template>
                </el-upload>
              </div>

              <div v-else class="preview-area">
                <div class="preview-header">
                  <span>已解析 <b>{{ batchList.length }}</b> 条规则</span>
                  <el-button
                    link
                    type="danger"
                    size="small"
                    @click="clearBatch"
                  >
                    重新上传
                  </el-button>
                </div>
                <div class="table-scroll">
                  <el-table
                    :data="batchList"
                    stripe
                    size="small"
                    style="width: 100%"
                  >
                    <el-table-column prop="id" label="ID" width="50" />
                    <el-table-column
                      prop="rule"
                      label="规则描述"
                      show-overflow-tooltip
                    />
                    <el-table-column prop="category" label="分类" width="80">
                      <template #default="{ row }">
                        <el-tag size="small" type="info">
                          {{ row.category }}
                        </el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column width="50" align="center">
                      <template #default="scope">
                        <el-button
                          link
                          type="danger"
                          :icon="Delete"
                          @click="removeBatchItem(scope.$index)"
                        />
                      </template>
                    </el-table-column>
                  </el-table>
                </div>
                <div class="qms-hint">
                  * 点击“下一步”将对列表中的规则进行批量编译与校验。
                </div>
              </div>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12" class="h-full">
          <el-card class="qms-card content-card" shadow="never">
            <template #header>
              <div class="qms-card-header">
                <div class="qms-card-title">
                  基准病例模板 (JSON)
                  <el-tag
                    size="small"
                    class="qms-ml"
                    :type="caseJsonValid.ok ? 'success' : 'danger'"
                    effect="light"
                  >
                    {{ caseJsonValid.msg }}
                  </el-tag>
                </div>
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click="copyText(caseJsonText)"
                >
                  复制
                </el-button>
              </div>
            </template>

            <div class="input-wrapper">
              <el-input
                v-model="caseJsonText"
                type="textarea"
                class="qms-textarea code-input full-height-input"
                placeholder="{ ... }"
                resize="none"
              />
              <div class="qms-hint">
                * 该病例将作为“单条测试”或“批量校验”的基准上下文环境。
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<style scoped>
/* 页面容器 */
.qms-page {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background-color: #f0f2f5;
}

.header-card {
  flex-shrink: 0;
}
.qms-content-wrapper {
  flex: 1;
  min-height: 0;
}
.h-full {
  height: 100%;
}

/* 卡片通用 */
.qms-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  transition: all 0.3s;
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
  padding: 16px;
  height: 0;
}

/* 输入框容器 */
.input-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 批量导入容器 */
.batch-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Upload 样式 */
.upload-area {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  border: 2px dashed #e5e7eb;
  border-radius: 8px;
  background: #fafafa;
}
.upload-box {
  width: 100%;
  text-align: center;
}
.upload-box :deep(.el-upload-dragger) {
  border: none;
  background: transparent;
}

/* 预览列表样式 */
.preview-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 13px;
  color: #606266;
}
.table-scroll {
  flex: 1;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

/* 文本域样式 */
.qms-textarea {
  flex: 1;
}
.qms-textarea :deep(.el-textarea__inner) {
  height: 100% !important;
  border-radius: 4px;
  padding: 12px;
  font-size: 14px;
  line-height: 1.6;
  box-shadow: none;
  border: 1px solid #dcdfe6;
}
.qms-textarea :deep(.el-textarea__inner):focus {
  border-color: #2f6dff;
}

.code-input :deep(.el-textarea__inner) {
  font-family: 'Menlo', 'Monaco', 'Consolas', monospace;
  background-color: #fafafa;
  color: #2c3e50;
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

.qms-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.qms-card-title {
  font-weight: 600;
  color: #303133;
  font-size: 15px;
  display: flex;
  align-items: center;
}
.qms-ml {
  margin-left: 8px;
}
.qms-hint {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}
.mr-1 {
  margin-right: 4px;
}
</style>
