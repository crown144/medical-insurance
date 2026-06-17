// 飞检结果管理 - 类型定义

// ==================== 导入 ====================

/** 导入批次（匹配后端蛇形命名） */
export interface FeiJianImportBatch {
  id: number;
  file_name: string;
  file_size: number;
  status: 'uploading' | 'analyzing' | 'mapping' | 'importing' | 'success' | 'failed';
  status_label: string;
  record_count: number;
  success_count: number;
  error_count: number;
  error_detail: string;
  detected_columns: string[];
  column_mapping: Record<string, { column: string; confidence: number; method: string; label: string }>;
  sample_rows: Record<string, any>[];
  created_at: string;
  updated_at: string;
}

/** 列映射匹配结果（返回给前端供用户确认） */
export interface ColumnMatch {
  field_key: string;
  field_label: string;
  column_name: string;
  column_index: number;
  confidence: number;
  method: string;
}

/** 上传分析返回 */
export interface UploadAnalysisResponse {
  batch: FeiJianImportBatch;
  analysis: {
    columns: string[];
    sample_rows: Record<string, any>[];
    mappings: ColumnMatch[];
    unmapped_fields: string[];
    unmapped_columns: string[];
    llm_analysis: string | null;
  };
}

/** 确认导入返回 */
export interface ConfirmImportResponse {
  batch: FeiJianImportBatch;
  summary: {
    total: number;
    success: number;
    error: number;
  };
}

export interface BuildAuditTaskResponse {
  task: {
    id: number;
    name: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    hospitalization_ids: string[];
    summary?: string;
    selectedSchemas?: string[];
    created_at?: string;
  };
  batch: FeiJianImportBatch;
  hospitalization_count: number;
  queued: boolean;
}

/** 预览返回 */
export interface PreviewResponse {
  preview: PreviewRecord[];
  totalRows: number;
}

export interface PreviewRecord {
  row_index: number;
  hospitalization_no: string;
  patient_name: string;
  hospital_name: string;
  issue_category: string;
  issue_description: string;
  involved_amount: number;
  audit_org: string;
  audit_date: string;
}

// ==================== 原始记录 ====================

export interface FeiJianRawRecord {
  id: number;
  import_batch: number;
  import_file_name: string;
  row_index: number;
  hospitalization_no: string;
  patient_name: string;
  hospital_name: string;
  admission_date: string;
  discharge_date: string;
  issue_category: string;
  issue_description: string;
  involved_amount: number;
  audit_org: string;
  audit_date: string;
  audit_task_id: string;
  raw_data: Record<string, any>;
  created_at: string;
}

// ==================== 审查任务 ====================

export interface AuditTask {
  id: string;
  taskName: string;
  importBatchId: string;
  totalCases: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  statusLabel: string;
  progress: number;
  createdAt: string;
  completedAt?: string;
}

// ==================== 结果对齐 ====================

export interface AlignmentResult {
  id: string;
  auditTaskId: string;
  feijianRecordId?: null | number;
  systemResultId?: null | number;
  hospitalizationNo: string;
  patientName?: string;
  hospitalName?: string;
  feijianIssue: string;
  feijianAmount: number;
  feijianCategory: string;
  systemIssue: string;
  systemAmount: number;
  systemCategory: string;
  matchStatus: 'matched' | 'partial' | 'unmatched' | 'system-only';
  matchStatusLabel: string;
  matchScore: number;
  matchReasons: string[];
}

export interface AlignmentSummary {
  alignmentRate: number;
  diffCount: number;
  matched: number;
  partial: number;
  systemOnly: number;
  total: number;
  unmatched: number;
  unresolvedDiffCount: number;
}

export interface AlignResultsResponse {
  batch_id: number;
  items: AlignmentResult[];
  llm_enabled?: boolean;
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
  summary: AlignmentSummary;
  task_id: null | number;
}

// ==================== 差异分析 ====================

export interface DiffRecord {
  id: string;
  auditTaskId: string;
  hospitalizationNo: string;
  patientName: string;
  hospitalName: string;
  issueSummary: string;
  feijianFindings: string;
  systemFindings: string;
  discrepancyType: 'feijian-extra' | 'system-extra' | 'amount-mismatch' | 'category-mismatch';
  discrepancyTypeLabel: string;
  amountDiff: number;
  severity: 'high' | 'medium' | 'low';
  severityLabel: string;
  status: 'pending' | 'reviewed' | 'confirmed' | 'dismissed';
  statusLabel: string;
  remark?: string;
}

// ==================== 结果管理 ====================

export interface FeiJianManageRecord {
  id: string;
  hospitalizationNo: string;
  patientName: string;
  hospitalName: string;
  importBatchId: string;
  importDate: string;
  issueCategory: string;
  issueDescription: string;
  involvedAmount: number;
  auditTaskId?: string;
  auditStatus?: string;
  matchStatus?: string;
  diffSeverity?: string;
  diffStatus?: string;
  status: 'imported' | 'audited' | 'aligned' | 'diff-analyzed' | 'resolved';
  statusLabel: string;
}

// ==================== 统计 ====================

export interface FeiJianStats {
  totalImports: number;
  totalRawRecords: number;
  auditTaskCount: number;
  alignmentRate: number;
  diffCount: number;
  unresolvedDiffCount: number;
}

// ==================== 分页 ====================

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}
