import type {
  AlignResultsResponse,
  BuildAuditTaskResponse,
  ConfirmImportResponse,
  FeiJianImportBatch,
  FeiJianRawRecord,
  FeiJianStats,
  PreviewResponse,
  UploadAnalysisResponse,
} from './model/feijianModel';

import { baseRequestClient } from '#/api/request';

// ==================== 统计 ====================

export async function getFeiJianStatsApi(): Promise<FeiJianStats> {
  const response = await baseRequestClient.get('/feijian/stats/');
  return response.data;
}

// ==================== 上传并分析 ====================

/** 上传飞检文件，自动分析列结构 */
export async function uploadFeiJianFileApi(
  file: File,
): Promise<UploadAnalysisResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const response = await baseRequestClient.post<any>(
    '/feijian/upload/',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return response.data;
}

// ==================== 预览 ====================

/** 预览导入结果 */
export async function previewFeiJianImportApi(data: {
  batch_id: number;
  column_mapping: Record<string, string>;
  limit?: number;
}): Promise<PreviewResponse> {
  const response = await baseRequestClient.post<any>(
    '/feijian/preview/',
    data,
  );
  return response.data;
}

// ==================== 确认导入 ====================

/** 确认列映射并执行导入 */
export async function confirmFeiJianImportApi(data: {
  batch_id: number;
  column_mapping: Record<string, string>;
}): Promise<ConfirmImportResponse> {
  const response = await baseRequestClient.post<any>(
    '/feijian/confirm-import/',
    data,
  );
  return response.data;
}

// ==================== 导入批次 ====================

/** 获取导入批次列表 */
export async function getImportBatchesApi(params?: any): Promise<{
  items: FeiJianImportBatch[];
  total: number;
}> {
  const response = await baseRequestClient.get<any>(
    '/feijian/import-batches/',
    { params },
  );
  return {
    items: response.data?.results || response.data || [],
    total: response.data?.count || 0,
  };
}

// ==================== 原始记录 ====================

/** 获取原始记录列表 */
export async function getRawRecordsApi(params?: any): Promise<{
  items: FeiJianRawRecord[];
  total: number;
}> {
  const response = await baseRequestClient.get<any>(
    '/feijian/raw-records/',
    { params },
  );
  return {
    items: response.data?.results || [],
    total: response.data?.count || 0,
  };
}

// ==================== 自动审查构建 ====================

export async function buildFeiJianAuditTaskApi(
  batchId: number,
  data: {
    execute?: boolean;
    name?: string;
    rule_ids?: number[];
    selectedSchemas?: string[];
  },
): Promise<BuildAuditTaskResponse> {
  const response = await baseRequestClient.post<any>(
    `/feijian/import-batches/${batchId}/build-audit-task/`,
    data,
  );
  return response.data;
}

// ==================== 结果对齐 ====================

export async function alignFeiJianResultsApi(
  batchId: number,
  params?: { page?: number; page_size?: number; task_id?: number; use_llm?: boolean },
): Promise<AlignResultsResponse> {
  const response = await baseRequestClient.get<any>(
    `/feijian/import-batches/${batchId}/align-results/`,
    { params },
  );
  return response.data;
}
