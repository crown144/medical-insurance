// src/api/model/taskModel.ts

// 1. 任务列表相关
export enum TaskStatus {
  COMPLETED = 'completed',
  FAILED = 'failed',
  PENDING = 'pending',
  RUNNING = 'running',
}

export interface TaskItem {
  id: number;
  name: string;
  status: TaskStatus;
  hospitalization_ids: string[];
  mdc_org_cd?: string;
  summary: null | string;
  created_at: string;
  started_at: null | string;
  completed_at: null | string;
  selectedSchemas?: string[];
}

export interface TaskListParams {
  page: number;
  page_size: number;
  id?: string;
  search?: string;
  status?: string;
}

export interface TaskListResult {
  count: number;
  results: TaskItem[];
}

// 2. 新增任务页面相关 (之前报错就是因为缺了下面这些！)

export interface RuleItem {
  id: number;
  drug_name: string;
  ruleId: string;
  description: string;
  type: string;
}

export interface RuleListParams {
  search?: string;
  type__in?: string;
  paginate?: string;
}

export interface InhosSearchParams {
  start_date?: string;
  end_date?: string;
  drug_name?: string;
  mdc_org_cd?: string;
}

export interface InhosSearchResponse {
  count: number;
  filter_type?: 'date_and_drug' | 'date_only' | 'drug_only';
  inhos_numbers: string[];
  limit: number;
  success: boolean;
  truncated: boolean;
  warning?: string;
}

export interface DemoCaseItem {
  hospitalization_id: string;
  patient_name?: string;
}

// 👇👇👇 重点检查这里，必须有 export 👇👇👇
export interface CreateTaskParams {
  name: string;
  hospitalization_ids: string[];
  mdc_org_cd: string;
  rule_ids: number[];
  selectedSchemas: string[];
  repeatChargingChildCodes?: string[];
  repeatChargingPairs?: string[];
}
