// src/api/result.ts
import { baseRequestClient } from '#/api/request';

enum Api {
  // 🟢 修正：只保留一个基础路径，供列表和详情共用
  Results = '/results/',
}

/**
 * 获取任务结果列表
 * 请求路径: /results/?task=...
 */
export const getTaskResultListApi = (params: any) => {
  return baseRequestClient.get<any>(Api.Results, { params });
};

/**
 * 获取单个病例的审核详情
 * 请求路径: /results/{id}/
 */
export const getAuditDetailApi = (id: number | string) => {
  // 🟢 拼接 ID
  return baseRequestClient.get<any>(`${Api.Results}${id}/`);
};

/**
 * 获取违规统计概览 (如果有的话)
 */
export const getResultOverviewApi = (taskId: number | string) => {
  return baseRequestClient.get<any>(`/tasks/${taskId}/overview/`);
};
