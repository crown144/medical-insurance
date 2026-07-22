import { baseRequestClient } from '#/api/request';

export interface SqlRule {
  id: number;
  ruleName: string;
  ruleType: string;
  description: string;
  sqlContent: string;
  remark: string;
  sqlStatus: string;
  createdAt: string;
  updatedAt: string;
}

export interface SqlExecutionRecord {
  id: number;
  sqlRuleId: number;
  ruleName: string;
  ruleType: string;
  startDate: string;
  endDate: string;
  executeStatus: 'failed' | 'success';
  executeTime: string;
  duration: number;
  rowCount: number;
  resultJson: {
    columns: string[];
    rows: Record<string, any>[];
    previewRowLimit: number;
    renderedSql?: string;
    truncated: boolean;
  };
  errorMessage: string;
  createdAt: string;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SqlRuleResultSummary {
  id: number;
  ruleName: string;
  ruleType: string;
  recentExecuteTime: null | string;
  executionCount: number;
  totalViolationCount: number;
  latestViolationCount: number;
  status: 'failed' | 'never' | 'success';
  updatedAt: string;
}

export interface SqlRuleResultStats {
  totalRules: number;
  executedRules: number;
  totalExecutions: number;
  totalViolations: number;
}

export interface SqlRuleResultDetail {
  id: number;
  ruleName: string;
  ruleType: string;
  description: string;
  sqlContent: string;
  remark: string;
  createdAt: string;
  updatedAt: string;
  recentExecuteTime: null | string;
  executionCount: number;
  totalViolationCount: number;
}

export async function getSqlRules(params: {
  keyword?: string;
  page?: number;
  pageSize?: number;
  ruleType?: string;
  sqlStatus?: string;
} = {}) {
  const response = await baseRequestClient.get<any>('/sql/rules', {
    params: {
      ...params,
      page_size: params.pageSize,
      rule_type: params.ruleType,
      sql_status: params.sqlStatus,
    },
  });
  return response.data?.result as PaginatedResult<SqlRule>;
}

export async function getSqlRuleDetail(id: number) {
  const response = await baseRequestClient.get<any>(`/sql/rules/${id}`);
  return response.data?.result as SqlRule;
}

export function createSqlRule(data: Partial<SqlRule>) {
  return baseRequestClient.post('/sql/rules', data);
}

export function updateSqlRule(id: number, data: Partial<SqlRule>) {
  return baseRequestClient.put(`/sql/rules/${id}`, data);
}

export function deleteSqlRule(id: number) {
  return baseRequestClient.delete(`/sql/rules/${id}`);
}

export async function executeSql(data: {
  sqlRuleId: number;
  startDate: string;
  endDate: string;
}) {
  const response = await baseRequestClient.post<any>('/sql/execute', data);
  return response.data?.result as SqlExecutionRecord;
}

export async function getSqlHistory(params: {
  page?: number;
  pageSize?: number;
  sqlRuleId?: number;
} = {}) {
  const response = await baseRequestClient.get<any>('/sql/history', {
    params: {
      page: params.page,
      page_size: params.pageSize,
      sqlRuleId: params.sqlRuleId,
    },
  });
  return response.data?.result as PaginatedResult<SqlExecutionRecord>;
}

export async function getSqlHistoryDetail(id: number) {
  const response = await baseRequestClient.get<any>(`/sql/history/${id}`);
  return response.data?.result as SqlExecutionRecord;
}

export function deleteSqlHistory(id: number) {
  return baseRequestClient.delete(`/sql/history/${id}`);
}

export async function downloadSqlHistoryResult(id: number) {
  return baseRequestClient.get(`/sql/history/${id}/download`, {
    responseType: 'blob',
  });
}

export async function getSqlResultRules(params: {
  keyword?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
  ruleType?: string;
} = {}) {
  const response = await baseRequestClient.get<any>('/sql/results/rules', {
    params: {
      keyword: params.keyword,
      ordering: params.ordering,
      page: params.page,
      page_size: params.pageSize,
      rule_type: params.ruleType,
    },
  });
  return response.data?.result as {
    items: SqlRuleResultSummary[];
    page: number;
    pageSize: number;
    stats: SqlRuleResultStats;
    total: number;
  };
}

export async function getSqlResultRuleDetail(id: number, params: {
  page?: number;
  pageSize?: number;
} = {}) {
  const response = await baseRequestClient.get<any>(`/sql/results/rules/${id}`, {
    params: {
      page: params.page,
      page_size: params.pageSize,
    },
  });
  return response.data?.result as {
    executions: PaginatedResult<SqlExecutionRecord>;
    rule: SqlRuleResultDetail;
  };
}
