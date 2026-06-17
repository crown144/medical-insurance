<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import {
  ArrowLeft,
  ArrowRight,
  Document,
  Search,
  User,
  Warning,
} from '@element-plus/icons-vue';
import axios from 'axios';
import { ElButton, ElEmpty, ElIcon, ElMessage, ElTag } from 'element-plus';

const API_BASE_URL = '/api';
const PATIENT_CASE_API = '/api/cases/patient-case/';

interface Highlight {
  field_path: string;
  highlighted_text: string;
}
interface ViolationItem {
  id: number;
  hospitalization_id: string;
  reason: string;
  rule: {
    description: string;
    drug_name: string;
    type?: string;
  };
  highlights: Highlight[];
}

const route = useRoute();
const router = useRouter();

// --- 状态 ---
const isLoading = ref(true);
const error = ref('');
const taskId = ref<string>('');
const hospitalizationId = ref<string>('');
const allViolationsInCase = ref<ViolationItem[]>([]);
const selectedViolation = ref<null | ViolationItem>(null);

// 🆕 新增：记录上一次找到的高亮行索引，初始为 -1
const lastFoundLine = ref(-1);

// 🟢 性能优化：存纯文本行，而非大对象
const jsonLines = shallowRef<string[]>([]);
const medicalRecordRaw = shallowRef<any>(null);

// --- 虚拟滚动配置 ---
const scrollerRef = ref<HTMLDivElement | null>(null);
const scrollTop = ref(0);
const viewportHeight = ref(600); // 容器高度，改为响应式
const defaultItemHeight = 24; // 默认单行高度
const buffer = 15; // 缓冲区
const containerWidth = ref(1000); // 容器宽度，默认给个安全值

// --- ResizeObserver 逻辑 ---
let resizeObserver: ResizeObserver | null = null;

onMounted(() => {
  if (scrollerRef.value) {
    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect) {
          // 减去 padding (24 * 2 = 48)
          containerWidth.value = Math.max(entry.contentRect.width - 48, 100);
          // 实时更新视口高度，解决底部留白问题
          viewportHeight.value = entry.contentRect.height;
        }
      }
    });
    resizeObserver.observe(scrollerRef.value);
  }
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});

// --- 1. 加载数据 ---
const loadPageData = async () => {
  taskId.value = String(route.query.taskId || '');
  hospitalizationId.value = String(route.query.hospitalizationId || '');

  if (!taskId.value || !hospitalizationId.value) {
    error.value = '参数缺失';
    isLoading.value = false;
    return;
  }

  isLoading.value = true;
  try {
    // 1.1 并发获取违规列表
    const fetchViolations = async () => {
      let all: ViolationItem[] = [];
      let next = `${API_BASE_URL}/results/`;
      let page = 1;
      while (next) {
        const params =
          page === 1
            ? {
                task_id: taskId.value,
                hospitalization_id: hospitalizationId.value,
              }
            : {};
        const res = await axios.get(next, page === 1 ? { params } : {});
        if (res.data?.results) {
          all = all.concat(res.data.results);
          next = res.data.next;
        } else break;
        page++;
      }
      return all;
    };

    // 1.2 获取病历全文
    const fetchRecord = () =>
      axios.get(PATIENT_CASE_API, {
        params: { hospitalization_id: hospitalizationId.value },
      });

    const [resViolations, resRecord] = await Promise.allSettled([
      fetchViolations(),
      fetchRecord(),
    ]);

    allViolationsInCase.value =
      resViolations.status === 'fulfilled' ? resViolations.value : [];

    if (resRecord.status === 'fulfilled' && resRecord.value.data) {
      const raw = resRecord.value.data;
      medicalRecordRaw.value = Object.freeze(raw);
      // 格式化 JSON，2空格缩进
      const jsonStr = JSON.stringify(raw, null, 2);
      jsonLines.value = Object.freeze(jsonStr.split('\n'));
    } else {
      jsonLines.value = Object.freeze([
        `// 暂无病历数据或加载失败`,
        `// 请检查后端服务`,
      ]);
    }
  } catch (error_: any) {
    error.value = error_.message;
  } finally {
    isLoading.value = false;
  }
};

// --- 2. 核心：虚拟滚动与智能高亮 ---

const escapeHtml = (unsafe: string) => {
  return unsafe
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
};

// 简单的行高估算（为了支持长文本折行）
// 动态计算每行能容纳的字符数
const getLineHeight = (line: string) => {
  const base = defaultItemHeight;
  // 假设字体大小 14px，按最宽字符（中文）估算以确保安全
  // 如果全是英文，虽然会高估行数导致留白，但绝不会重叠
  const charsPerLine = Math.floor(containerWidth.value / 14);

  if (line.length > charsPerLine) {
    return base * Math.ceil(line.length / charsPerLine);
  }
  return base;
};

// 计算累加高度（用于撑开滚动条）
const linePositions = computed(() => {
  const positions: number[] = [0];
  let current = 0;
  for (let i = 0; i < jsonLines.value.length; i++) {
    const h = getLineHeight(jsonLines.value[i]);
    current += h;
    positions.push(current);
  }
  return positions;
});

const totalHeight = computed(
  () => linePositions.value[linePositions.value.length - 1],
);

const visibleData = computed(() => {
  const scroll = scrollTop.value;
  // 二分查找当前可视的起始行（因为行高不固定）
  let startIdx = 0;
  let high = linePositions.value.length - 1;
  let low = 0;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (linePositions.value[mid] < scroll) {
      startIdx = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  const start = Math.max(0, startIdx - buffer);
  // 向下预加载
  // 🟢 修复空白关键点：
  // 之前根据 getLineHeight（高估值）累加来判断是否填满视口，导致实际渲染行数不足。
  // 现在改用 defaultItemHeight（最小行高）来计算需要的行数，确保宁多勿少，填满视口。
  const itemsNeeded =
    Math.ceil(viewportHeight.value / defaultItemHeight) + buffer * 2;
  const end = Math.min(start + itemsNeeded, jsonLines.value.length);

  const lines = jsonLines.value.slice(start, end);

  // 获取高亮词 Set
  const highlightSet = new Set(
    selectedViolation.value?.highlights
      ?.map((h) => String(h.highlighted_text).trim())
      .filter(Boolean) || [],
  );

  // 🟢 新增：同时高亮违规项目名称
  if (selectedViolation.value) {
    const violationName = getViolationName(selectedViolation.value);
    if (violationName && violationName !== '未知项目') {
       // 处理包含引号的组合名称，例如：“静脉注射”与“静脉采血”不能同时开
       // 提取出引号内的内容作为高亮关键词
       const matches = violationName.match(/[“"']([^”"']+)["”']/g);
       if (matches && matches.length > 0) {
          matches.forEach(m => {
             // 去除引号
             const clean = m.replace(/[“"']|["”']/g, '');
             if (clean) highlightSet.add(clean);
          });
       } else {
          highlightSet.add(violationName);
       }
    }

    // 兜底：始终尝试高亮规则对应的药品名称（即使 violation_item 解析失败）
    if (selectedViolation.value.rule?.drug_name) {
       highlightSet.add(selectedViolation.value.rule.drug_name);
    }
  }

  return {
    startOffset: linePositions.value[start],
    items: lines.map((line, index) => {
      const realIndex = start + index;
      // 1. 先转义 HTML，防止 XSS，同时为了匹配 &quot;
      let html = escapeHtml(line);

      if (highlightSet.size > 0) {
        highlightSet.forEach((val) => {
          // 🟢 智能匹配修正：
          // 1. 转义 keyword，使其能匹配到 &quot; 等转义后的字符
          const safeVal = escapeHtml(val);

          // 2. 构造正则：如果是纯数字，要求两边不能是数字（防止匹配到 "123" 里的 "1"）
          let regex: RegExp;
          if (/^\d+(\.\d+)?$/.test(val)) {
            // 数字边界匹配：前面不能是数字，后面也不能是数字
            regex = new RegExp(String.raw`(?<!\d)(${safeVal})(?!\d)`, 'g');
          } else {
            // 普通文本，直接全局匹配
            // 这里的 split/join 替换比正则快且安全
            // 但为了不破坏已有的 <mark> 标签，我们得小心。
            // 简单起见，我们假设高亮词不重叠。
            regex = new RegExp(
              safeVal.replaceAll(/[.*+?^${}()|[\]\\]/g, String.raw`\$&`),
              'g',
            );
          }

          // 🟢 修复 bug：使用回调函数避免 $1 被错误解析
          html = html.replace(regex, (match) => `<mark class="hl">${match}</mark>`);
        });
      }

      return {
        index: realIndex,
        content: html,
      };
    }),
  };
});

const onScroll = (e: Event) => {
  scrollTop.value = (e.target as HTMLElement).scrollTop;
};

// --- 跳转逻辑 ---
const jumpToNextHighlight = () => {
  if (!selectedViolation.value) return;

  // 1. 构造与渲染逻辑(visibleData)完全一致的搜索集合
  const targetSet = new Set<string>();

  // A. 后端返回的高亮证据
  if (selectedViolation.value.highlights?.length) {
    selectedViolation.value.highlights.forEach((h) => {
      if (h.highlighted_text) {
        targetSet.add(String(h.highlighted_text).trim());
      }
    });
  }

  // B. 违规项目名称（支持自动提取引号内容）
  const violationName = getViolationName(selectedViolation.value);
  if (violationName && violationName !== '未知项目') {
    const matches = violationName.match(/[“"']([^”"']+)["”']/g);
    if (matches && matches.length > 0) {
      matches.forEach((m) => {
        const clean = m.replace(/[“"']|["”']/g, '');
        if (clean) targetSet.add(clean);
      });
    } else {
      targetSet.add(violationName);
    }
  }

  // C. 规则对应的药品名称兜底
  if (selectedViolation.value.rule?.drug_name) {
    targetSet.add(selectedViolation.value.rule.drug_name);
  }

  const targets = Array.from(targetSet).filter(Boolean);

  if (targets.length === 0) {
    ElMessage.info('当前条目无高亮关键词');
    return;
  }

  // 查找算法
  let foundIndex = -1;
  // 从当前可视区域之后开始找
  // 修正 startLine 计算：scrollTop 对应的行数应该是 Math.floor(scrollTop.value / getLineHeight)，但因为 getLineHeight 不固定，这里简单估算可能不准
  // 更准确的做法是根据 linePositions 二分查找当前 scrollTop 对应的行索引
  let startLine = 0;
  if (lastFoundLine.value !== -1) {
    // 场景 A: 已经跳转过，从上一处高亮的下一行开始找，实现“Next”功能
    startLine = lastFoundLine.value + 1;
  } else {
    // 场景 B: 首次跳转，计算当前视口对应的起始行（保留原有逻辑）
    // 这样可以查找当前视口下方的第一个高亮
    let currentLineIdx = 0;
    {
      let low = 0,
        high = linePositions.value.length - 1;
      while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        if (linePositions.value[mid] <= scrollTop.value) {
          // 修正：使用 <=
          currentLineIdx = mid;
          low = mid + 1;
        } else {
          high = mid - 1;
        }
      }
    }
    startLine = currentLineIdx;
  }

  const search = (from: number, to: number) => {
    for (let i = from; i < to; i++) {
      const line = jsonLines.value[i];
      if (targets.some((t) => line.includes(t))) return i;
    }
    return -1;
  };

  // 先向下找
  foundIndex = search(startLine, jsonLines.value.length);
  // 没找到则从头找
  if (foundIndex === -1) foundIndex = search(0, startLine);

  if (foundIndex !== -1 && scrollerRef.value) {
    // 🆕 新增：更新最后找到的行号
    lastFoundLine.value = foundIndex;

    const targetTop = linePositions.value[foundIndex];
    scrollerRef.value.scrollTo({
      top: Math.max(0, targetTop - 100),
      behavior: 'smooth',
    });

    // 给用户一个反馈
    ElMessage({
      message: `已定位到第 ${foundIndex + 1} 行`,
      type: 'success',
      duration: 1500,
      icon: Search,
    });
  } else {
    ElMessage.warning('全文中未找到匹配的高亮文本');
  }
};

// --- 交互 ---
const selectViolation = (v: ViolationItem) => {
  selectedViolation.value = v;
  // 切换违规项时，重置搜索起始位置
  lastFoundLine.value = -1;
  nextTick(() => jumpToNextHighlight());
};

watch(
  () => [route.query.taskId, route.query.hospitalizationId],
  ([t, h]) => {
    if (t && h) {
      selectedViolation.value = null;
      allViolationsInCase.value = [];
      jsonLines.value = [];
      loadPageData();
    }
  },
  { immediate: true },
);

watch(allViolationsInCase, (newVal) => {
  if (newVal.length > 0 && !selectedViolation.value) {
    selectViolation(newVal[0]);
  }
});

const goBack = () => window.history.back();

const patientSummary = computed(() => {
  const d = medicalRecordRaw.value || {};
  const p = d.patient || {};
  const v = d.visit || {};
  return {
    name: p.name || '未知',
    sex: p.sex || '-',
    age: p.age || '-',
    dept: v.department || '-',
    total: d.charges?.total_amount_yuan || '-',
  };
});

const formatRuleType = (t?: string) => t || '规则';

const getViolationName = (v: ViolationItem) => {
  // 1. 尝试从 violation_item (这里假设后端API如果包含了它，需要添加到 ViolationItem 接口定义) 获取
  // 注意：我们需要先在 ViolationItem 接口中添加 violation_item 字段
  const rawItem = (v as any).violation_item;

  let parsedName = '';
  if (rawItem) {
    try {
       // 如果是 JSON 字符串
       if (rawItem.trim().startsWith('{')) {
          const validJson = rawItem.replaceAll("'", '"').replaceAll('None', 'null');
          const obj = JSON.parse(validJson);
          parsedName = obj.name || obj.drug_name || obj.item_name || obj.xmname || obj.xmmc || obj['收费项目名称'] || obj['收费项目代码'];
       } else {
          parsedName = rawItem;
       }
    } catch {}
  }

  return parsedName || v.rule?.drugName || '未知项目';
};
</script>

<template>
  <div class="page-wrap">
    <div class="page-header-card">
      <div class="title-row">
        <div class="title-left">
          <div class="title-bar"></div>
          <div class="title-text">
            <h1 class="page-title">结果审计详情</h1>
            <div class="sub-info">
              <span class="sub-item">任务: {{ taskId }}</span>
              <span class="dot">•</span>
              <span class="sub-item">住院号: {{ hospitalizationId }}</span>
            </div>
          </div>
        </div>
        <div class="header-actions">
          <ElButton @click="goBack" class="back-btn">
            <ElIcon class="el-icon--left"><ArrowLeft /></ElIcon>返回列表
          </ElButton>
        </div>
      </div>

      <!-- <div class="patient-bar">
        <div class="pitem">
          <div class="k">
            <ElIcon><User /></ElIcon> 患者信息
          </div>
          <div class="v user-name">
            {{ patientSummary.name }}
            <span class="sub-v"
              >({{ patientSummary.sex }}/{{ patientSummary.age }})</span
            >
          </div>
        </div>
        <div class="pitem">
          <div class="k">科室</div>
          <div class="v">{{ patientSummary.dept }}</div>
        </div>
        <div class="pitem">
          <div class="k">费用总额</div>
          <div class="v fee">¥ {{ patientSummary.total }}</div>
        </div>
      </div> -->
    </div>

    <div class="page-body" v-loading="isLoading">
      <div v-if="error" class="error-container">
        <ElIcon><Warning /></ElIcon> {{ error }}
      </div>

      <div v-else class="grid-layout">
        <div class="panel list-panel">
          <div class="panel-header">
            <div class="panel-title">
              <ElIcon class="mr-1"><Warning /></ElIcon> 违规条目
            </div>
            <div class="panel-badge">{{ allViolationsInCase.length }}</div>
          </div>
          <div class="list-content">
            <div
              v-for="v in allViolationsInCase"
              :key="v.id"
              class="violation-card"
              :class="{ active: selectedViolation?.id === v.id }"
              @click="selectViolation(v)"
            >
              <div class="card-header-row">
                <div class="rule-title">
                  {{ getViolationName(v) }}
                </div>
                <div class="tags">
                  <ElTag size="small" effect="plain">
                    {{ formatRuleType(v.rule?.type) }}
                  </ElTag>
                </div>
              </div>
              <div class="desc-text">{{ v.rule?.description }}</div>
              <div class="reason-box">
                <div class="reason-title">判定原因：</div>
                <div class="reason-content">{{ v.reason }}</div>
              </div>
              <div
                class="card-footer"
                v-if="v.highlights && v.highlights.length > 0"
              >
                <div class="evidence-link">
                  关联证据 {{ v.highlights.length }} 处
                  <ElIcon><ArrowRight /></ElIcon>
                </div>
              </div>
            </div>
            <ElEmpty
              v-if="allViolationsInCase.length === 0"
              description="暂无违规数据"
            />
          </div>
        </div>

        <div class="panel preview-panel">
          <div class="panel-header">
            <div class="panel-title">
              <ElIcon class="mr-1"><Document /></ElIcon> 原始病历全文 ({{
                jsonLines.length
              }}
              行)
            </div>
            <div class="panel-actions">
              <!-- 新增：跳转到高亮按钮 -->
              <ElButton
                type="primary"
                plain
                size="small"
                @click="jumpToNextHighlight"
                :disabled="!selectedViolation"
              >
                跳转到高亮
              </ElButton>
            </div>
          </div>

          <div class="virtual-scroller" ref="scrollerRef" @scroll="onScroll">
            <div class="phantom" :style="{ height: `${totalHeight}px` }"></div>
            <div
              class="render-area"
              :style="{ transform: `translateY(${visibleData.startOffset}px)` }"
            >
              <div
                v-for="line in visibleData.items"
                :key="line.index"
                class="line-item"
                v-html="line.content"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 布局与配色 */
.page-wrap {
  background: #f5f7fb;
  padding: 20px;
  min-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  gap: 16px;
  font-family:
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei',
    sans-serif;
}
.page-header-card {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  padding: 20px 24px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.title-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title-bar {
  width: 4px;
  height: 24px;
  background: #409eff;
  border-radius: 2px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.sub-info {
  margin-left: 12px;
  font-size: 13px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f4f4f5;
  padding: 4px 10px;
  border-radius: 4px;
}
.sub-item {
  font-family: monospace;
}
.dot {
  color: #dcdfe6;
}

.patient-bar {
  background: #fcfcfc;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 16px 20px;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}
.pitem {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.k {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 4px;
}
.v {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub-v {
  font-size: 13px;
  color: #909399;
  font-weight: normal;
  margin-left: 4px;
}
.v.fee {
  color: #f56c6c;
  font-family: monospace;
  font-size: 16px;
}

.page-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.grid-layout {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
  height: 100%;
  min-height: 600px;
}

.panel {
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}
.panel-header {
  height: 50px;
  padding: 0 20px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  display: flex;
  align-items: center;
}
.mr-1 {
  margin-right: 6px;
  font-size: 16px;
  color: #909399;
}
.panel-badge {
  background: #f56c6c;
  color: #fff;
  min-width: 20px;
  height: 20px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: bold;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  margin-left: 8px;
}

.list-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #f5f7fa;
}
.violation-card {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
}
.violation-card:hover {
  border-color: #c6e2ff;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.violation-card.active {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 0 0 1px #409eff;
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
  gap: 8px;
}
.rule-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  line-height: 1.4;
  word-break: break-all;
}
.desc-text {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
  line-height: 1.5;
}
.reason-box {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
  background: #fdf6ec;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #faecd8;
}
.active .reason-box {
  background: #fff;
  border-color: #d9ecff;
}
.reason-title {
  font-weight: 700;
  color: #e6a23c;
  margin-bottom: 4px;
}
.card-footer {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
.evidence-link {
  font-size: 12px;
  color: #409eff;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 2px;
}

/* 虚拟滚动优化版 */
.virtual-scroller {
  flex: 1;
  overflow-y: auto;
  position: relative;
  background: #fff;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 14px;
  /* 允许长文本换行，解决横向滚动问题 */
  white-space: pre-wrap;
  word-break: break-all;
  color: #606266;
}
.phantom {
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  z-index: -1;
}
.render-area {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  padding: 0 24px; /* 左右留白 */
}
.line-item {
  /* 行高需与计算逻辑一致 */
  line-height: 24px;
}

/* 高亮样式 */
.render-area :deep(mark.hl) {
  background-color: #ffeb3b; /* 亮黄色 */
  color: #000;
  border-radius: 2px;
  padding: 0 1px;
  box-shadow: 0 0 2px rgba(0, 0, 0, 0.2);
  font-weight: bold;
}

.back-btn {
  font-weight: 500;
}
.error-container {
  padding: 40px;
  text-align: center;
  color: #909399;
}
</style>
