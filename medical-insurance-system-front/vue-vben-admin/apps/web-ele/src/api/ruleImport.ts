import type {
  ConfirmImportResponse,
  DrfPaginated,
  ExtractedRule,
  RuleImportParams,
  RuleImportTask,
  UploadResponse,
} from './model/ruleImportModel';

import { baseRequestClient } from '#/api/request';

// ==================== 上传并发起转换 ====================

/** 上传药品/收费目录文件并异步发起规则抽取 */
export async function uploadRuleImportApi(
  file: File,
  params: RuleImportParams & { task_name?: string } = {},
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (params.task_name) formData.append('task_name', params.task_name);
  if (params.max_pdf_pages != null)
    formData.append('max_pdf_pages', String(params.max_pdf_pages));
  if (params.max_rows_per_table != null)
    formData.append('max_rows_per_table', String(params.max_rows_per_table));
  if (params.max_tables != null)
    formData.append('max_tables', String(params.max_tables));

  const response = await baseRequestClient.post<any>(
    '/rule-import/upload/',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return response.data;
}

// ==================== 任务列表 ====================

/** 获取导入任务列表（DRF 分页） */
export async function getRuleImportTasksApi(params?: {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
}): Promise<DrfPaginated<RuleImportTask>> {
  const response = await baseRequestClient.get<any>('/rule-import/tasks/', {
    params,
  });
  return response.data;
}

// ==================== 任务详情（轮询状态/进度） ====================

export async function getRuleImportTaskApi(
  taskId: number,
): Promise<RuleImportTask> {
  const response = await baseRequestClient.get<any>(
    `/rule-import/tasks/${taskId}/`,
  );
  return response.data;
}

// ==================== 抽取规则明细 ====================

export async function getExtractedRulesApi(
  taskId: number,
  params?: { page?: number; page_size?: number; rule_type?: string },
): Promise<DrfPaginated<ExtractedRule>> {
  const response = await baseRequestClient.get<any>(
    `/rule-import/tasks/${taskId}/rules/`,
    { params },
  );
  return response.data;
}

// ==================== 确认入库 ====================

export async function confirmRuleImportApi(
  taskId: number,
  data: { rule_ids?: number[]; select_all?: boolean },
): Promise<ConfirmImportResponse> {
  const response = await baseRequestClient.post<any>(
    `/rule-import/tasks/${taskId}/confirm/`,
    data,
  );
  return response.data;
}

// ==================== 取消任务 ====================

export async function cancelRuleImportApi(
  taskId: number,
): Promise<{ status: string }> {
  const response = await baseRequestClient.post<any>(
    `/rule-import/tasks/${taskId}/cancel/`,
    {},
  );
  return response.data;
}

// ==================== 下载抽取结果 JSON ====================

/** 通过请求封装下载结果（返回 Blob，避免写死后端地址） */
export async function downloadRuleImportResultApi(
  taskId: number,
): Promise<Blob> {
  const response = await baseRequestClient.get<any>(
    `/rule-import/tasks/${taskId}/download/`,
    { responseType: 'blob' },
  );
  return response.data;
}
