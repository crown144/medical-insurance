<script setup lang="ts">
import { computed, ref } from 'vue';

import { ElMessage, ElMessageBox } from 'element-plus';
/** ========== 1) 输入 ========== */
const ruleText = ref('限新发的缺血性脑梗死，支付不超过14天。');
const caseJsonText = ref(
  JSON.stringify(
    {
      入院记录: {
        现病史: '患者突发右侧肢体无力2天，加重1天。考虑急性缺血性脑卒中。',
        初步诊断: '缺血性脑梗死',
      },
      首次病程记录: { 文档内容: '急性起病，发病约48小时。考虑新发脑梗死。' },
      日常病程记录: [
        { 创建时间: '2023-09-02', 文本: '病情稳定，继续抗血小板。' },
      ],
      诊断信息: [
        { 诊断名称: '缺血性脑梗死', ICD编码: 'I63.9', 主诊断标志: '是' },
      ],
      基本信息: { 入院日期: '2023-09-01', 出院日期: '2023-09-20' },
    },
    null,
    2,
  ),
);

const scenario = ref<'need_standardize' | 'need_tool' | 'success'>('success'); // 模拟不同分支

const caseJsonValid = computed(() => {
  try {
    JSON.parse(caseJsonText.value);
    return { ok: true, msg: 'JSON格式正确' };
  } catch (error: any) {
    return { ok: false, msg: error?.message || 'JSON格式错误' };
  }
});
// 入库弹窗
const importVisible = ref(false);

// 模拟“入库后的ID/版本”
const importedInfo = ref<null | {
  created_at: string;
  rule_id: string;
  version: number;
}>(null);

// 入库记录（展示用）
const importRecordText = computed(() => {
  if (!artifacts.value) return '';
  const payload = {
    rule_id: importedInfo.value?.rule_id || 'R-UNSAVED',
    version: importedInfo.value?.version || 0,
    created_at: importedInfo.value?.created_at || '',
    source_rule_nl: ruleText.value,
    ir: {
      atom_list: artifacts.value.atom_list,
      logic_tree: artifacts.value.logic_tree,
    },
    standardize: artifacts.value.standardize,
    tool_chain: artifacts.value.propose_tool
      ? {
          propose_tool: artifacts.value.propose_tool,
          tool_maker: artifacts.value.tool_maker,
        }
      : null,
    generated_code: artifacts.value.generated_code,
    last_run: runResult.value,
  };
  return JSON.stringify(payload, null, 2);
});

const mockImportToDB = async () => {
  if (!artifacts.value) {
    ElMessage.warning('请先编译生成代码');
    return;
  }

  try {
    await ElMessageBox.confirm(
      '将当前规则（NL + IR + 标准化 + 生成代码）打包为“入库记录”是否继续？',
      '导入到数据库',
      { type: 'warning', confirmButtonText: '导入', cancelButtonText: '取消' },
    );

    // 模拟生成 rule_id
    const ruleId = `R-${Date.now().toString(36).toUpperCase()}`;
    importedInfo.value = {
      rule_id: ruleId,
      version: 1,
      created_at: new Date().toLocaleString(),
    };
    importVisible.value = true;
    ElMessage.success(`已模拟入库：${ruleId}`);
  } catch {
    ElMessage.info('已取消导入');
  }
};
/** ========== 2) 中间产物（IR / 标准化 / 工具链路 / 代码 / 日志） ========== */
type StepStatus = 'fail' | 'running' | 'success' | 'wait';
interface AtomCond {
  id: string;
  text: string;
  fnHint: string; // 提示用哪个函数（match_field / llm_predicate / check_limit）
}
interface IRTreeNode {
  op: 'AND' | 'ATOM' | 'NOT' | 'OR';
  text?: string;
  children?: IRTreeNode[];
}
interface StandardizeItem {
  raw: string;
  standard_name: string;
  standard_code?: string;
  dict: 'ATC' | 'ICD-10' | 'LOCAL' | 'LOINC';
  confidence: number;
}
interface ToolProposal {
  action: 'propose_tool';
  name: string;
  reason: string;
  inputs: string[];
  outputs: string[];
}
interface ToolMakerOutput {
  function_code: string;
  schema: any;
  test_case: string;
}

interface CompileArtifacts {
  atom_list: AtomCond[];
  logic_tree: IRTreeNode;
  standardize: StandardizeItem[];
  propose_tool?: ToolProposal;
  tool_maker?: ToolMakerOutput;
  generated_code: string;
}

interface RunResult {
  passed: boolean;
  step: string;
  reason: string;
  details?: any;
  logs: Array<{ level: 'ERROR' | 'INFO' | 'WARN'; msg: string; t: string }>;
}

const stepStatus = ref<Record<string, StepStatus>>({
  decompose: 'wait',
  standardize: 'wait',
  toolcheck: 'wait',
  codegen: 'wait',
  run: 'wait',
});

const artifacts = ref<CompileArtifacts | null>(null);
const runResult = ref<null | RunResult>(null);

const isCompiling = ref(false);
const isRunning = ref(false);

/** ========== 3) 模拟编译（用你的 A/B/C 框架思路硬编码） ========== */
const mockCompile = async () => {
  // 统一清空
  artifacts.value = null;
  runResult.value = null;
  stepStatus.value = {
    decompose: 'running',
    standardize: 'wait',
    toolcheck: 'wait',
    codegen: 'wait',
    run: 'wait',
  };

  // Step 1: 文本拆解（Agent A）
  await sleep(250);
  stepStatus.value.decompose = 'success';

  const atom_list: AtomCond[] = [
    { id: 'C1', text: '诊断包含：缺血性脑梗死', fnHint: 'match_field' },
    { id: 'C2', text: '是否为新发/急性期脑梗死', fnHint: 'llm_predicate' },
    { id: 'C3', text: '支付时长 ≤ 14天', fnHint: 'check_limit' },
  ];
  const logic_tree: IRTreeNode = {
    op: 'AND',
    children: [
      { op: 'ATOM', text: 'C1 诊断匹配' },
      { op: 'ATOM', text: 'C2 新发判断' },
      { op: 'ATOM', text: 'C3 14天限制' },
    ],
  };

  // Step 2: 标准化（Agent C）
  stepStatus.value.standardize = 'running';
  await sleep(250);

  let standardize: StandardizeItem[] = [
    {
      raw: '缺血性脑梗死',
      standard_name: '缺血性脑梗死',
      standard_code: 'I63.9',
      dict: 'ICD-10',
      confidence: 0.92,
    },
    {
      raw: '新发',
      standard_name: '急性/新发（语义属性）',
      dict: 'LOCAL',
      confidence: 0.78,
    },
  ];

  if (scenario.value === 'need_standardize') {
    // 假设输入里是“脑梗”，需要映射
    standardize = [
      {
        raw: '脑梗',
        standard_name: '缺血性脑梗死',
        standard_code: 'I63.*',
        dict: 'ICD-10',
        confidence: 0.86,
      },
      {
        raw: '新发',
        standard_name: '急性/新发（语义属性）',
        dict: 'LOCAL',
        confidence: 0.78,
      },
    ];
  }
  stepStatus.value.standardize = 'success';

  // Step 3: 工具覆盖性检查（Agent A -> Function Lib）
  stepStatus.value.toolcheck = 'running';
  await sleep(250);

  let propose_tool: ToolProposal | undefined;
  let tool_maker: ToolMakerOutput | undefined;

  if (scenario.value === 'need_tool') {
    // 假设缺少一个更精确的“新发判断”工具（仅为演示：真实场景你也可以不缺，直接 llm_predicate）
    propose_tool = {
      action: 'propose_tool',
      name: 'is_new_onset_stroke',
      reason:
        '现有函数库无法稳定识别“新发/急性期”在多段病程中的证据与否定（如“陈旧性脑梗死”），需要专用语义判别工具。',
      inputs: [
        '入院记录.现病史',
        '首次病程记录.文档内容',
        '日常病程记录[*].文本',
      ],
      outputs: ['bool', 'evidence_spans'],
    };

    // Agent B 输出新工具（代码 + schema + test_case）
    tool_maker = {
      function_code: String.raw`def is_new_onset_stroke(ctx, context_fields, condition="是否为新发/急性期脑梗死"):
    # 仅示意：实际应由你们的安全策略 + llm/规则组合实现
    # 这里仍然要求通过 ctx.get_value() 安全取值
    texts = []
    for fp in context_fields:
        v = ctx.get_value(fp)
        if isinstance(v, list):
            texts.extend([str(x) for x in v])
        elif v is not None:
            texts.append(str(v))
    joined = "\n".join(texts)
    # 简单关键词示意（真实应更严谨）
    neg = ("陈旧" in joined) or ("既往" in joined) or ("恢复期" in joined)
    pos = ("新发" in joined) or ("急性" in joined) or ("发病" in joined) or ("48小时" in joined)
    return (pos and (not neg))`,
      schema: {
        name: 'is_new_onset_stroke',
        description:
          '专用语义判别：识别是否为新发/急性期脑梗死，并避免被“陈旧性/既往”误判。',
        parameters: {
          type: 'dict',
          required: ['context_fields'],
          properties: {
            context_fields: { type: 'array', items: { type: 'string' } },
            condition: { type: 'string' },
          },
        },
      },
      test_case: `# sandbox test (demo)
class DummyCtx:
    def __init__(self, data): self.data=data
    def get_value(self, path):
        # 简化：实际你们用真实路径解析
        if path=="入院记录.现病史": return self.data["入院记录"]["现病史"]
        if path=="首次病程记录.文档内容": return self.data["首次病程记录"]["文档内容"]
        if path.startswith("日常病程记录"): return [x["文本"] for x in self.data["日常病程记录"]]
        return None

data = {
  "入院记录": {"现病史":"突发无力2天，考虑急性脑梗死"},
  "首次病程记录": {"文档内容":"发病48小时内，新发脑梗死"},
  "日常病程记录": [{"文本":"继续治疗"}]
}
ctx = DummyCtx(data)
assert is_new_onset_stroke(ctx, ["入院记录.现病史","首次病程记录.文档内容","日常病程记录[*].文本"]) is True
print("PASS")`,
    };

    stepStatus.value.toolcheck = 'fail'; // 注意：这里 fail 代表“现有工具不够，需要走 tool 提案链路”
  } else {
    stepStatus.value.toolcheck = 'success';
  }

  // Step 4: 代码生成（Agent A）
  stepStatus.value.codegen = 'running';
  await sleep(250);

  const generated_code =
    scenario.value === 'need_tool'
      ? `def execute_rule(ctx):
    # Step 1: 诊断匹配
    if not match_field(ctx, field_path="诊断信息[*].诊断名称", target_values=["缺血性脑梗死"]):
        return {"passed": False, "reason": "未匹配到缺血性脑梗死诊断", "step": "match_diagnosis"}

    # Step 2: 新发判断（缺少稳定工具，需 propose_tool）
    return {"passed": False, "reason": "缺少专用工具：is_new_onset_stroke（请走工具生成/审核流程）", "step": "tool_missing"}`
      : `def execute_rule(ctx):
    # Step 1: 诊断匹配（结构化）
    ok1 = match_field(ctx, field_path="诊断信息[*].诊断名称", target_values=["缺血性脑梗死"])
    if not ok1:
        return {"passed": False, "reason": "未匹配到缺血性脑梗死诊断", "step": "match_diagnosis"}

    # Step 2: 新发/急性期判断（语义）
    ok2 = llm_predicate(
        ctx,
        context_fields=[
            "入院记录.现病史",
            "首次病程记录.文档内容",
            "日常病程记录[*].文本"
        ],
        condition="判断缺血性脑梗死是否为新发/急性期；若为陈旧性/既往/恢复期则否"
    )
    if not ok2:
        return {"passed": False, "reason": "非新发/非急性期脑梗死", "step": "judge_new_onset"}

    # Step 3: 支付时长限制
    ok3 = check_limit(ctx, limit_type="pay_duration", threshold="14", unit="day")
    if not ok3:
        return {"passed": False, "reason": "支付时长超过14天", "step": "check_pay_duration"}

    return {"passed": True, "reason": "OK", "step": "done"}`;
  stepStatus.value.codegen = 'success';

  artifacts.value = {
    atom_list,
    logic_tree,
    standardize,
    propose_tool,
    tool_maker,
    generated_code,
  };
};

/** ========== 4) 模拟执行（运行期 Safe Executor 日志） ========== */
const mockRun = async () => {
  if (!artifacts.value) {
    ElMessage.warning('请先编译生成代码');
    return;
  }
  if (!caseJsonValid.value.ok) {
    ElMessage.error('病例JSON格式错误，无法执行');
    return;
  }

  stepStatus.value.run = 'running';
  runResult.value = null;
  await sleep(300);

  if (scenario.value === 'need_tool') {
    stepStatus.value.run = 'fail';
    runResult.value = {
      passed: false,
      step: 'tool_missing',
      reason:
        '缺少专用工具 is_new_onset_stroke，需走 Tool Maker 流程后才能执行该规则',
      logs: [
        {
          t: now(),
          level: 'INFO',
          msg: 'SafeExecutor: start execute_rule(ctx)',
        },
        { t: now(), level: 'INFO', msg: 'Step match_diagnosis: PASS' },
        {
          t: now(),
          level: 'ERROR',
          msg: 'Step judge_new_onset: missing tool is_new_onset_stroke',
        },
      ],
    };
    return;
  }

  // success / need_standardize 分支：模拟“超过14天拒付”
  stepStatus.value.run = 'success';
  runResult.value = {
    passed: false,
    step: 'check_pay_duration',
    reason: '支付时长超过14天（示例：入院-出院=19天）',
    details: {
      admitted: '2023-09-01',
      discharged: '2023-09-20',
      days: 19,
      threshold: 14,
    },
    logs: [
      { t: now(), level: 'INFO', msg: 'SafeExecutor: start execute_rule(ctx)' },
      {
        t: now(),
        level: 'INFO',
        msg: 'Step match_diagnosis: PASS (缺血性脑梗死)',
      },
      {
        t: now(),
        level: 'INFO',
        msg: 'Step judge_new_onset: PASS (evidence: "发病48小时内/新发")',
      },
      {
        t: now(),
        level: 'WARN',
        msg: 'Step check_pay_duration: FAIL (19 > 14)',
      },
    ],
  };
};

/** ========== 5) 交互按钮 ========== */
const compile = async () => {
  if (!ruleText.value.trim()) return ElMessage.warning('请输入规则文本');
  if (!caseJsonValid.value.ok) return ElMessage.error('病例JSON格式错误');
  isCompiling.value = true;
  try {
    await mockCompile();
    ElMessage.success('编译完成（演示）');
  } finally {
    isCompiling.value = false;
  }
};

const run = async () => {
  isRunning.value = true;
  try {
    await mockRun();
    ElMessage.success('执行完成（演示）');
  } finally {
    isRunning.value = false;
  }
};

const copyText = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text);
    ElMessage.success('已复制');
  } catch {
    ElMessage.error('复制失败（可能是浏览器权限限制）');
  }
};

const downloadAsFile = (filename: string, content: string) => {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

/** ========== utils ========== */
function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
function now() {
  const d = new Date();
  return d.toLocaleTimeString();
}

const logicTreeText = computed(() => {
  if (!artifacts.value) return '';
  const dfs = (n: IRTreeNode, depth = 0): string => {
    const pad = '  '.repeat(depth);
    if (n.op === 'ATOM') return `${pad}- ${n.text}`;
    const head = `${pad}${n.op}`;
    const kids = (n.children || []).map((c) => dfs(c, depth + 1)).join('\n');
    return `${head}\n${kids}`;
  };
  return dfs(artifacts.value.logic_tree);
});

const toolProposalText = computed(() =>
  artifacts.value?.propose_tool
    ? JSON.stringify(artifacts.value.propose_tool, null, 2)
    : '',
);
const toolSchemaText = computed(() =>
  artifacts.value?.tool_maker?.schema
    ? JSON.stringify(artifacts.value.tool_maker.schema, null, 2)
    : '',
);
void [
  importRecordText,
  mockImportToDB,
  compile,
  run,
  copyText,
  downloadAsFile,
  logicTreeText,
  toolProposalText,
  toolSchemaText,
];
</script>
<template>
  <div class="qms-page">
    <!-- 顶部：标题 + 操作（和你参考图一致：左蓝线标题，右侧按钮） -->
    <el-card class="qms-card" shadow="never">
      <div class="qms-titlebar">
        <div class="qms-title">
          <span class="qms-title__bar"></span>
          <div class="qms-title__text">
            <div class="qms-title__name">规则导入与校验</div>
            <div class="qms-title__desc">
              输入自然语言规则与病例模板，展示
              IR（拆解/逻辑树）、标准化映射、工具链路与最终代码，并进行模拟验证。
            </div>
          </div>
        </div>

        <div class="qms-actions">
          <el-select v-model="scenario" style="width: 220px">
            <el-option label="演示：正常编译" value="success" />
            <el-option
              label="演示：需要 Standardizer"
              value="need_standardize"
            />
            <el-option label="演示：缺工具 → propose_tool" value="need_tool" />
          </el-select>

          <el-button type="primary" :loading="isCompiling" @click="compile">
            编译生成
          </el-button>
          <el-button
            type="success"
            :disabled="!artifacts"
            @click="run"
            :loading="isRunning"
          >
            模拟执行
          </el-button>

          <!-- 更像你参考图的“更多操作” -->
          <el-dropdown trigger="click">
            <el-button>
              更多操作
              <span style="margin-left: 6px">▾</span>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item
                  :disabled="!artifacts"
                  @click="mockImportToDB"
                >
                  导入到数据库
                </el-dropdown-item>
                <el-dropdown-item
                  :disabled="!artifacts"
                  @click="artifacts && copyText(artifacts.generated_code)"
                >
                  复制生成代码
                </el-dropdown-item>
                <el-dropdown-item
                  :disabled="!artifacts"
                  @click="
                    artifacts &&
                    downloadAsFile('execute_rule.py', artifacts.generated_code)
                  "
                >
                  导出生成代码
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-card>

    <!-- 内容区：两列布局（更接近你给的页面布局） -->
    <el-row :gutter="16" class="qms-grid">
      <!-- 左列：输入 -->
      <el-col :span="12">
        <el-card class="qms-card" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">原始规则描述</div>
            </div>
          </template>

          <el-input
            v-model="ruleText"
            type="textarea"
            :rows="8"
            placeholder="输入自然语言医保规则..."
          />
          <div class="qms-hint">
            示例：限新发的缺血性脑梗死，支付不超过14天。
          </div>
        </el-card>

        <el-card class="qms-card qms-mt" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">
                病例模板（JSON）
                <el-tag
                  size="small"
                  class="qms-ml"
                  :type="caseJsonValid.ok ? 'success' : 'danger'"
                  effect="light"
                >
                  {{ caseJsonValid.msg }}
                </el-tag>
              </div>
              <div class="qms-card-extra">
                <el-button size="small" @click="copyText(caseJsonText)">
                  复制
                </el-button>
              </div>
            </div>
          </template>

          <el-input
            v-model="caseJsonText"
            type="textarea"
            :rows="14"
            class="mono"
          />
          <div class="qms-hint">
            运行期将通过 ctx.get_value(path) 安全取值（此处为演示模板）。
          </div>
        </el-card>
      </el-col>

      <!-- 右列：编译产物 -->
      <el-col :span="12">
        <el-card class="qms-card" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">解析后的规则逻辑树</div>
              <div class="qms-card-extra">
                <el-button
                  size="small"
                  :disabled="!artifacts"
                  @click="copyText(logicTreeText)"
                >
                  复制
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="!artifacts" class="qms-empty">点击“编译生成”后展示</div>
          <div v-else class="qms-prebox">
            <pre class="qms-pre">{{ logicTreeText }}</pre>
          </div>
        </el-card>

        <el-card class="qms-card qms-mt" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">拆解后的原子条件（IR-Atom）</div>
            </div>
          </template>

          <div v-if="!artifacts" class="qms-empty">点击“编译生成”后展示</div>
          <el-table
            v-else
            :data="artifacts.atom_list"
            border
            size="small"
            class="qms-table"
          >
            <el-table-column prop="id" label="编号" width="80" />
            <el-table-column prop="text" label="原子条件" min-width="260" />
            <el-table-column prop="fnHint" label="推荐函数" width="140">
              <template #default="{ row }">
                <el-tag size="small" effect="light">{{ row.fnHint }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="qms-card qms-mt" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">Agent C：术语标准化映射</div>
            </div>
          </template>

          <div v-if="!artifacts" class="qms-empty">—</div>
          <el-table
            v-else
            :data="artifacts.standardize"
            border
            size="small"
            class="qms-table"
          >
            <el-table-column prop="raw" label="原术语" width="140" />
            <el-table-column
              prop="standard_name"
              label="标准名"
              min-width="220"
            />
            <el-table-column prop="standard_code" label="编码" width="120">
              <template #default="{ row }">
                <span>{{ row.standard_code || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="dict" label="字典" width="100" />
            <el-table-column prop="confidence" label="置信度" width="110">
              <template #default="{ row }">
                <el-tag
                  size="small"
                  :type="row.confidence >= 0.85 ? 'success' : 'warning'"
                  effect="light"
                >
                  {{ (row.confidence * 100).toFixed(0) }}%
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card class="qms-card qms-mt" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">
                工具覆盖性检查（Agent A → Function Lib）
              </div>
              <div class="qms-card-extra" v-if="artifacts?.propose_tool">
                <el-button size="small" @click="copyText(toolProposalText)">
                  复制 propose_tool
                </el-button>
                <el-button
                  size="small"
                  @click="downloadAsFile('propose_tool.json', toolProposalText)"
                >
                  导出
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="!artifacts" class="qms-empty">—</div>

          <template v-else>
            <el-alert
              v-if="artifacts.propose_tool"
              type="warning"
              show-icon
              :closable="false"
              title="现有函数库不足：触发 propose_tool（需走 Tool Maker 沙箱测试 + 人工审核后入库）"
            />
            <div v-if="artifacts.propose_tool" class="qms-mt-sm qms-prebox">
              <pre class="qms-pre">{{ toolProposalText }}</pre>
            </div>

            <el-alert
              v-else
              type="success"
              show-icon
              :closable="false"
              title="函数库覆盖充足：可直接生成规则代码"
            />
          </template>
        </el-card>
      </el-col>

      <!-- 跨两列：生成代码 -->
      <el-col :span="24" class="qms-mt">
        <el-card class="qms-card" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">生成代码（execute_rule(ctx)）</div>
              <div class="qms-card-extra">
                <el-button
                  size="small"
                  :disabled="!artifacts"
                  @click="artifacts && copyText(artifacts.generated_code)"
                >
                  复制
                </el-button>
                <el-button
                  size="small"
                  :disabled="!artifacts"
                  @click="
                    artifacts &&
                    downloadAsFile('execute_rule.py', artifacts.generated_code)
                  "
                >
                  导出
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="!artifacts" class="qms-empty">点击“编译生成”后展示</div>
          <div v-else class="qms-code-dark">
            <pre class="qms-pre qms-pre-dark">{{
              artifacts.generated_code
            }}</pre>
          </div>

          <!-- 如果走 tool_maker，也在这里展示（更像“结果详情”区） -->
          <template v-if="artifacts?.tool_maker">
            <el-divider />

            <div class="qms-subtitle">
              Agent B：Tool Maker 输出（函数 / Schema / test_case）
            </div>

            <el-row :gutter="16" class="qms-mt-sm">
              <el-col :span="8">
                <el-card shadow="never" class="qms-innercard">
                  <template #header>
                    <div class="qms-innerhead">
                      <span>function_code</span>
                      <el-button
                        size="small"
                        @click="
                          copyText(artifacts.tool_maker?.function_code || '')
                        "
                      >
                        复制
                      </el-button>
                    </div>
                  </template>
                  <div class="qms-prebox">
                    <pre class="qms-pre">{{
                      artifacts.tool_maker?.function_code
                    }}</pre>
                  </div>
                </el-card>
              </el-col>

              <el-col :span="8">
                <el-card shadow="never" class="qms-innercard">
                  <template #header>
                    <div class="qms-innerhead">
                      <span>schema</span>
                      <el-button size="small" @click="copyText(toolSchemaText)">
                        复制
                      </el-button>
                    </div>
                  </template>
                  <div class="qms-prebox">
                    <pre class="qms-pre">{{ toolSchemaText }}</pre>
                  </div>
                </el-card>
              </el-col>

              <el-col :span="8">
                <el-card shadow="never" class="qms-innercard">
                  <template #header>
                    <div class="qms-innerhead">
                      <span>test_case</span>
                      <el-button
                        size="small"
                        @click="copyText(artifacts.tool_maker?.test_case || '')"
                      >
                        复制
                      </el-button>
                    </div>
                  </template>
                  <div class="qms-prebox">
                    <pre class="qms-pre">{{
                      artifacts.tool_maker?.test_case
                    }}</pre>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </template>
        </el-card>
      </el-col>

      <!-- 跨两列：执行结果 -->
      <el-col :span="24" class="qms-mt">
        <el-card class="qms-card" shadow="never">
          <template #header>
            <div class="qms-card-header">
              <div class="qms-card-title">
                执行日志与结果（Runtime / Safe Executor）
              </div>
              <div class="qms-card-extra">
                <el-tag
                  class="qms-ml"
                  effect="light"
                  :type="
                    stepStatus.run === 'success'
                      ? 'success'
                      : stepStatus.run === 'fail'
                        ? 'danger'
                        : 'info'
                  "
                >
                  状态：{{ stepStatus.run }}
                </el-tag>
              </div>
            </div>
          </template>

          <!-- step chips（接近你系统里状态 tag 的感觉） -->
          <div class="qms-stepchips">
            <el-tag
              size="small"
              effect="light"
              :type="
                stepStatus.decompose === 'success'
                  ? 'success'
                  : stepStatus.decompose === 'running'
                    ? 'primary'
                    : 'info'
              "
            >
              拆解
            </el-tag>
            <el-tag
              size="small"
              effect="light"
              :type="
                stepStatus.standardize === 'success'
                  ? 'success'
                  : stepStatus.standardize === 'running'
                    ? 'primary'
                    : 'info'
              "
            >
              标准化
            </el-tag>
            <el-tag
              size="small"
              effect="light"
              :type="
                stepStatus.toolcheck === 'success'
                  ? 'success'
                  : stepStatus.toolcheck === 'fail'
                    ? 'warning'
                    : stepStatus.toolcheck === 'running'
                      ? 'primary'
                      : 'info'
              "
            >
              工具检查
            </el-tag>
            <el-tag
              size="small"
              effect="light"
              :type="
                stepStatus.codegen === 'success'
                  ? 'success'
                  : stepStatus.codegen === 'running'
                    ? 'primary'
                    : 'info'
              "
            >
              代码生成
            </el-tag>
            <el-tag
              size="small"
              effect="light"
              :type="
                stepStatus.run === 'success'
                  ? 'success'
                  : stepStatus.run === 'fail'
                    ? 'danger'
                    : stepStatus.run === 'running'
                      ? 'primary'
                      : 'info'
              "
            >
              模拟执行
            </el-tag>
          </div>

          <div v-if="!runResult" class="qms-empty">点击“模拟执行”后展示</div>

          <template v-else>
            <el-alert
              :type="runResult.passed ? 'success' : 'error'"
              show-icon
              :closable="false"
              :title="
                runResult.passed ? 'PASSED：规则通过' : 'REJECTED：规则未通过'
              "
              :description="`step：${runResult.step}  |  reason：${runResult.reason}`"
            />

            <div v-if="runResult.details" class="qms-mt-sm qms-prebox">
              <div class="qms-blocktitle">details</div>
              <pre class="qms-pre">{{
                JSON.stringify(runResult.details, null, 2)
              }}</pre>
            </div>

            <div class="qms-mt-sm qms-prebox">
              <div class="qms-blocktitle">logs</div>
              <pre class="qms-pre">{{
                runResult.logs
                  .map((l) => `[${l.t}] ${l.level} ${l.msg}`)
                  .join('\n')
              }}</pre>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 入库结果弹窗（保留你的逻辑，只换风格不改功能） -->
    <el-dialog v-model="importVisible" title="入库结果" width="900px">
      <div class="qms-import-meta" v-if="importedInfo">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="rule_id">
            {{ importedInfo.rule_id }}
          </el-descriptions-item>
          <el-descriptions-item label="version">
            {{ importedInfo.version }}
          </el-descriptions-item>
          <el-descriptions-item label="created_at">
            {{ importedInfo.created_at }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="qms-prebox qms-mt-sm">
        <div class="qms-blocktitle qms-blocktitle--row">
          <span>入库记录（JSON）</span>
          <div style="display: flex; gap: 8px">
            <el-button size="small" @click="copyText(importRecordText)">
              复制
            </el-button>
            <el-button
              size="small"
              @click="downloadAsFile('rule_record.json', importRecordText)"
            >
              导出
            </el-button>
          </div>
        </div>
        <pre class="qms-pre">{{ importRecordText }}</pre>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<style scoped>
.qms-page {
  padding: 16px;
}

/* 卡片整体：更像你参考图的“白底、轻边框” */
.qms-card {
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

/* 顶部标题条：左侧蓝线 + 右侧按钮 */
.qms-titlebar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.qms-title {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.qms-title__bar {
  width: 4px;
  height: 18px;
  background: #2f6dff;
  border-radius: 2px;
  margin-top: 4px;
}

.qms-title__name {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
  line-height: 1.2;
}

.qms-title__desc {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.qms-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.qms-alert {
  margin-top: 12px;
}

.qms-grid {
  margin-top: 16px;
}

.qms-mt {
  margin-top: 16px;
}

.qms-mt-sm {
  margin-top: 10px;
}

.qms-ml {
  margin-left: 8px;
}

/* card header：标题左对齐，右侧小按钮 */
.qms-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.qms-card-title {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.qms-card-extra {
  display: flex;
  gap: 8px;
}

.qms-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.qms-empty {
  padding: 10px 0;
  color: #909399;
  font-size: 13px;
}

/* 表格：更接近你系统的清爽表格 */
.qms-table :deep(.el-table__header th) {
  background: #f5f7fa;
  color: #606266;
  font-weight: 600;
}

.qms-table :deep(.el-table__cell) {
  padding: 10px 0;
}

/* 代码块展示：白底盒子 + 滚动 */
.qms-prebox {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  overflow: hidden;
}

.qms-blocktitle {
  padding: 10px 12px;
  font-size: 12px;
  color: #606266;
  background: #f5f7fa;
  border-bottom: 1px solid #ebeef5;
  font-weight: 600;
}

.qms-blocktitle--row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.qms-pre {
  margin: 0;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}

/* 深色代码块：类似你“生成代码”区域的深色板 */
.qms-code-dark {
  border-radius: 6px;
  border: 1px solid #22304b;
  background: #0b1220;
  overflow: hidden;
}

.qms-pre-dark {
  color: rgba(255, 255, 255, 0.92);
}

/* 子卡片（tool maker 三列） */
.qms-innercard {
  border: 1px solid #ebeef5;
  border-radius: 6px;
}

.qms-innerhead {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

/* step chips */
.qms-stepchips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

/* JSON textarea monospace */
.mono :deep(textarea),
.mono :deep(.el-textarea__inner) {
  font-family:
    ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
}
</style>
