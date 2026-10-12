import { baseRequestClient } from '#/api/request';

const LLM_REQUEST_TIMEOUT = 300_000;
const COMPILE_POLL_INTERVAL = 1500;
const COMPILE_POLL_TIMEOUT = 300_000;

export interface RuleItem {
  id: number;
  ruleId: string;
  drug_name: string;
  type: string;
  description: string;
  enabled: boolean;
  rule_code?: string | null;
  logicExpression?: string;
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

interface RuleCompileTaskStatus {
  data?: RuleGenerateResult | { error?: string; error_type?: string } | null;
  status: 'failed' | 'pending' | 'running' | 'success';
  task_id: string;
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getRuleList(params: any) {
  const response = await baseRequestClient.get<any>('/rules/', { params });
  return response.data;
}

export function toggleRuleStatus(id: number | string, enabled: boolean) {
  return baseRequestClient.request(`/rules/${id}/`, {
    data: { enabled },
    method: 'PATCH',
  });
}

export function deleteRule(id: number | string) {
  return baseRequestClient.delete(`/rules/${id}/`);
}

export function createRule(data: Partial<RuleItem>) {
  return baseRequestClient.post('/rules/', data);
}

export function updateRule(id: number | string, data: Partial<RuleItem>) {
  return baseRequestClient.put(`/rules/${id}/`, data);
}

export async function generateRuleApi(ruleText: string) {
  const startResponse = await baseRequestClient.post<any>(
    '/rules/agenta/generate/start/',
    {
      rule_text: ruleText,
    },
  );
  const taskId = startResponse.data?.result?.task_id;
  if (!taskId) {
    throw new Error('Rule compilation task was not created');
  }

  const startedAt = Date.now();
  while (Date.now() - startedAt < COMPILE_POLL_TIMEOUT) {
    await wait(COMPILE_POLL_INTERVAL);
    const statusResponse = await baseRequestClient.get<any>(
      `/rules/agenta/generate/status/${taskId}/`,
    );
    const task = statusResponse.data?.result as RuleCompileTaskStatus | undefined;
    if (!task) continue;

    if (task.status === 'success') {
      return task.data as RuleGenerateResult;
    }
    if (task.status === 'failed') {
      const data = task.data as { error?: string } | null | undefined;
      throw new Error(data?.error || statusResponse.data?.message || 'Rule compilation failed');
    }
  }

  throw new Error('Rule compilation timed out. Please try again later or shorten the rule description.');
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
