import { baseRequestClient } from '#/api/request';

const LLM_REQUEST_TIMEOUT = 120_000;

export interface RuleItem {
  id: number;
  ruleId: string;
  drug_name: string; // 对应后端 drug_name
  type: string;
  description: string;
  enabled: boolean; // 对应后端 status
  logicExpression?: string;
  // 其他可能需要的字段
  created_at?: string;
  updated_at?: string;
}

export interface RuleGenerateResult {
  generated_code: string;
  finish_reason?: string;
  llm_config?: Record<string, any>;
  raw_output?: any;
  rule_snapshot?: Record<string, any>;
  rule_text: string;
  runtime_label?: string;
  runtime_mode?: string;
  system_prompt?: string;
  tool_schema?: Record<string, any>;
  validation?: Record<string, any>;
}

/**
 * 获取规则列表
 * @param params 查询参数 (search, type, page, page_size 等)
 */
export async function getRuleList(params: any) {
  // Django REST Framework 返回结构通常是 { count: number, results: [...] }
  // 而不是 Vben 默认期望的 { code: 0, data: ... }
  // 因此使用 baseRequestClient 获取原始响应，避免被默认拦截器错误处理
  const response = await baseRequestClient.get<any>('/rules/', { params });
  return response.data;
}

/**
 * 更新规则状态 (启/停)
 * @param id 规则数据库ID
 * @param enabled 是否启用
 */
export function toggleRuleStatus(id: number | string, enabled: boolean) {
  return baseRequestClient.request(`/rules/${id}/`, {
    data: { enabled },
    method: 'PATCH',
  });
}

/**
 * 删除规则
 * @param id 规则数据库ID
 */
export function deleteRule(id: number | string) {
  return baseRequestClient.delete(`/rules/${id}/`);
}

/**
 * 新增规则
 */
export function createRule(data: Partial<RuleItem>) {
  return baseRequestClient.post('/rules/', data);
}

/**
 * 更新规则
 */
export function updateRule(id: number | string, data: Partial<RuleItem>) {
  return baseRequestClient.put(`/rules/${id}/`, data);
}

export async function generateRuleApi(ruleText: string) {
  const response = await baseRequestClient.post<any>(
    '/rules/agenta/generate/',
    {
      rule_text: ruleText,
    },
    { timeout: LLM_REQUEST_TIMEOUT },
  );
  return response.data?.result as RuleGenerateResult;
}

export async function validateRuleCodeApi(ruleCode: string) {
  const response = await baseRequestClient.post<any>('/rules/agenta/validate/', {
    rule_code: ruleCode,
  });
  return response.data?.result;
}

export async function runGeneratedRuleApi(ruleText: string, caseJson: any) {
  const response = await baseRequestClient.post<any>(
    '/rules/agenta/run/',
    {
      case_json: caseJson,
      rule_text: ruleText,
    },
    { timeout: LLM_REQUEST_TIMEOUT },
  );
  return response.data?.result;
}

export async function importGeneratedRuleApi(data: {
  description: string;
  drugName: string;
  ruleCode: string;
  ruleId?: string;
  status: boolean;
  type: string;
}) {
  const response = await baseRequestClient.post<any>(
    '/rules/agenta/import/',
    {
      description: data.description,
      drugName: data.drugName,
      ruleCode: data.ruleCode,
      ruleId: data.ruleId,
      status: data.status,
      type: data.type,
    },
    { timeout: LLM_REQUEST_TIMEOUT },
  );
  return response.data?.result;
}
