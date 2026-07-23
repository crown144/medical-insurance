import { requestClient } from '#/api/request';

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

export interface SqlRuleQuery {
  keyword?: string;
  page?: number;
  pageSize?: number;
  ruleType?: string;
  sqlStatus?: string;
}

export interface PaginatedResult<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SqlExecutePayload {
  sqlRuleId: number;
  startDate: string;
  endDate: string;
}

export async function getSqlRulesApi(params: SqlRuleQuery = {}) {
  return requestClient.get<PaginatedResult<SqlRule>>('/sql/rules', {
    params: {
      ...params,
      page_size: params.pageSize,
      rule_type: params.ruleType,
      sql_status: params.sqlStatus,
    },
  });
}

export async function getSqlRuleDetailApi(id: number) {
  return requestClient.get<SqlRule>(`/sql/rules/${id}`);
}

export async function createSqlRuleApi(data: Partial<SqlRule>) {
  return requestClient.post<SqlRule>('/sql/rules', data);
}

export async function updateSqlRuleApi(id: number, data: Partial<SqlRule>) {
  return requestClient.put<SqlRule>(`/sql/rules/${id}`, data);
}

export async function deleteSqlRuleApi(id: number) {
  return requestClient.delete(`/sql/rules/${id}`);
}

export async function executeSqlApi(data: SqlExecutePayload) {
  return requestClient.post<SqlExecutionRecord>('/sql/execute', data);
}

export async function getSqlHistoryApi(params: {
  page?: number;
  pageSize?: number;
  sqlRuleId?: number;
} = {}) {
  return requestClient.get<PaginatedResult<SqlExecutionRecord>>('/sql/history', {
    params: {
      page: params.page,
      page_size: params.pageSize,
      sqlRuleId: params.sqlRuleId,
    },
  });
}

export async function getSqlHistoryDetailApi(id: number) {
  return requestClient.get<SqlExecutionRecord>(`/sql/history/${id}`);
}

export async function deleteSqlHistoryApi(id: number) {
  return requestClient.delete(`/sql/history/${id}`);
}

