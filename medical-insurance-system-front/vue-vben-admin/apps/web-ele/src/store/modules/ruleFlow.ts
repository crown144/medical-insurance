// src/store/modules/ruleFlow.ts
import { computed, ref } from 'vue';

import { defineStore } from 'pinia';

// ✅ 【修正 1】引用真实存在的 audit.ts，而不是不存在的 ruleEngine
import { startAuditApi } from '../../api/audit';

export const useRuleFlowStore = defineStore('rule-flow', () => {
  // ========== State (状态) ==========

  // 1. 页面模式
  const activeTab = ref('manual'); // 'manual' | 'batch'

  // 2. 单条模式数据
  const ruleText = ref('');

  // JSON 模板 (保持不变)
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

  // 3. 批量模式数据
  const batchRules = ref<any[]>([]);

  // 4. 存放产物与结果
  const artifacts = ref<any>(null); // 编译产物
  const runResult = ref<any>(null); // 执行结果

  // ========== Getters (计算属性) ==========
  const caseJsonValid = computed(() => {
    try {
      JSON.parse(caseJsonText.value);
      return { ok: true, msg: 'JSON格式正确' };
    } catch (error: any) {
      return { ok: false, msg: error?.message || 'JSON格式错误' };
    }
  });

  // ========== Actions (方法) ==========

  // --- 1. 编译逻辑 (保持 Mock，这部分目前不需要后端) ---
  async function mockCompile(_scenario: string) {
    artifacts.value = null;
    // 模拟延迟
    await new Promise((r) => setTimeout(r, 800));

    // 构造一些 Mock 的编译产物 (AST树、原子能力等)
    const atom_list = [
      { id: 'C1', text: '诊断包含：缺血性脑梗死', fnHint: 'match_field' },
      { id: 'C2', text: '是否为新发/急性期脑梗死', fnHint: 'llm_predicate' },
      { id: 'C3', text: '支付时长 ≤ 14天', fnHint: 'check_limit' },
    ];

    const logic_tree = {
      op: 'AND',
      children: [
        { op: 'ATOM', text: 'C1 诊断匹配' },
        { op: 'ATOM', text: 'C2 新发判断' },
        { op: 'ATOM', text: 'C3 14天限制' },
      ],
    };

    // 存入 State
    artifacts.value = {
      atom_list,
      logic_tree,
      standardize: [],
      // 模拟生成的 Python 代码
      generated_code: `def execute_rule(ctx):\n    # 1. Check Diagnosis\n    if not match_field(ctx, "diagnosis", "I63.9"): return False\n    # 2. Check Acute\n    if not llm_predicate(ctx, "is_acute"): return False\n    return True`,
    };
  }

  // --- 2. 模拟运行 (已接入真实后端) ---
  async function mockRun() {
    // 1. 基础检查
    if (!artifacts.value) return;
    runResult.value = null;

    // 2. 解析 JSON 参数
    let patientData = {};
    try {
      patientData = JSON.parse(caseJsonText.value);
    } catch (error) {
      console.error('JSON 解析失败', error);
      return;
    }

    const now = () => new Date().toLocaleTimeString();

    try {
      // 3. 【真实调用】调用 audit.ts 中的 startAuditApi
      // ✅ 【修正 2 & 3】构造正确的参数结构 { template_id, patient_data }
      const res = await startAuditApi({
        template_id: 'medication_template', // 这里暂时写死，后续可做成动态选择
        patient_data: patientData,
      });

      const violations = res.violations || [];

      // 4. 【适配层】将后端数据转换为前端 UI 需要的格式
      // 后端逻辑：isViolation === '是' 代表违规
      const firstViolation = violations.find((v) => v.isViolation === '是');
      const isPassed = !firstViolation;

      // 组装结果
      runResult.value = {
        passed: isPassed,

        // 步骤名：如果是违规，显示违规类型；如果是通过，显示完成
        step: isPassed
          ? 'audit_pass'
          : firstViolation?.violationType || 'violation_detected',

        // 原因：展示分析结果
        reason: isPassed
          ? '规则校验通过，未发现异常。'
          : firstViolation?.analysis ||
            firstViolation?.violationDetail ||
            '检测到违规风险',

        // 详情：将后端的 evidenceText 等放入这里，供右侧面板显示
        details: isPassed
          ? { 结果: '合规' }
          : {
              违规名称: firstViolation?.name,
              违规类型: firstViolation?.violationType,
              相关规则: firstViolation?.rule,
              证据摘要: firstViolation?.evidenceText, // UI 会尝试高亮匹配这个文本
            },

        // 日志：构造模拟日志，让控制台看起来有过程感
        logs: [
          {
            t: now(),
            level: 'INFO',
            msg: 'AuditClient: Sending request to /api/audit/...',
          },
          { t: now(), level: 'INFO', msg: `Template ID: medication_template` },
          {
            t: now(),
            level: 'INFO',
            msg: 'Engine: Analyzing patient context...',
          },
          // 根据结果追加日志
          ...(isPassed
            ? [
                {
                  t: now(),
                  level: 'INFO',
                  msg: 'RuleCheck: All rules passed.',
                },
                { t: now(), level: 'INFO', msg: 'Result: PASSED' },
              ]
            : [
                {
                  t: now(),
                  level: 'WARN',
                  msg: `RuleCheck: Violation found - ${firstViolation?.name}`,
                },
                {
                  t: now(),
                  level: 'ERROR',
                  msg: `Interceptor: Blocked. Reason: ${firstViolation?.analysis}`,
                },
              ]),
        ],
      };
    } catch (error: any) {
      // 5. 错误处理
      console.error('Audit API Error:', error);
      runResult.value = {
        passed: false,
        step: 'api_error',
        reason: `服务端请求失败: ${error.message || '网络错误'}`,
        logs: [
          { t: now(), level: 'INFO', msg: 'AuditClient: Sending request...' },
          {
            t: now(),
            level: 'ERROR',
            msg: `Connection Failed: ${error.message}`,
          },
        ],
      };
    }
  }

  // --- 3. 批量编译 (保持 Mock) ---
  async function compileSingleItem(index: number) {
    const item = batchRules.value[index];
    item.status = 'loading';
    await new Promise((r) => setTimeout(r, 500 + Math.random() * 1000));
    item.status = 'success';
    item.artifacts = {
      logic_summary: 'AND(诊断, 时长)',
      code_snippet: 'def execute_rule(ctx): ...',
    };
  }

  async function runBatchCompile() {
    const promises = batchRules.value.map((_, index) =>
      compileSingleItem(index),
    );
    await Promise.all(promises);
  }

  return {
    activeTab,
    ruleText,
    caseJsonText,
    batchRules,
    artifacts,
    runResult,
    caseJsonValid,
    mockCompile,
    mockRun, // 真实调用
    runBatchCompile,
  };
});
