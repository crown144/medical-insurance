// 规则批量导入转换 - 类型定义
// 字段严格对齐后端 rule_import 接口（蛇形命名）

/** 任务状态（对应后端 RuleImportTask.Status） */
export type RuleImportStatus =
  | 'canceled'
  | 'extracting'
  | 'failed'
  | 'parsing'
  | 'pending'
  | 'success';

/** 算法参数（数量类参数留空表示不限数量；分块行数由后端配置，前端不暴露） */
export interface RuleImportParams {
  max_pdf_pages?: null | number;
  max_rows_per_table?: null | number;
  max_tables?: null | number;
}

/** 导入任务（对应后端 RuleImportTaskSerializer） */
export interface RuleImportTask {
  id: number;
  task_name: string;
  status: RuleImportStatus;
  status_label: string;
  stage: string;
  progress: number;
  file_name: string;
  file_size: number;
  file_type: string;
  params: RuleImportParams;
  table_count: number;
  rule_count: number;
  imported_count: number;
  error_detail: string;
  celery_task_id: string;
  created_at: string;
  updated_at: string;
  started_at: null | string;
  finished_at: null | string;
}

/** 抽取出的规则（对应后端 ExtractedRuleSerializer） */
export interface ExtractedRule {
  id: number;
  import_task: number;
  seq: number;
  rule_type: string;
  constrained_object: string;
  constraint_value: string;
  evidence: Record<string, any>;
  source: Record<string, any>;
  is_selected: boolean;
  is_imported: boolean;
  imported_rule_id: string;
  created_at: string;
}

/** 上传返回 */
export interface UploadResponse {
  task: RuleImportTask;
}

/** 确认入库返回 */
export interface ConfirmImportResponse {
  imported: number;
  skipped: number;
  rule_ids: string[];
  task: RuleImportTask;
}

/** DRF 分页返回 */
export interface DrfPaginated<T> {
  count: number;
  next: null | string;
  previous: null | string;
  results: T[];
}
