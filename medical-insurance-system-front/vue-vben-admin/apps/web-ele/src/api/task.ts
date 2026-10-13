import type {
  InhosSearchParams,
  InhosSearchResponse,
  TaskListParams,
} from './model/taskModel';

import { downloadFileFromBlob } from '@vben/utils';

// src/api/task.ts
import { baseRequestClient, requestClient } from '#/api/request';

enum Api {
  Inhos = '/inhos-numbers/',
  Rule = '/rules/',
  Task = '/tasks/',
  RepeatCharging = '/repeat-charging/father-child/',
}

/**
 * 获取任务列表
 * 🔴 核心修复：同时返回 items 和 results，防止组件报错
 */
export const getTaskListApi = async (params: TaskListParams) => {
  const response = await baseRequestClient.get<any>(Api.Task, { params });
  const data = response.data;

  return {
    // Vben 标准写法：用 items
    items: data.results || [],

    // 🟢 新增：保留 Django 的 results 字段，防止您的组件报错
    results: data.results || [],

    // 分页总数
    total: data.count || 0,
    count: data.count || 0,
  };
};

// ... 下面的 executeTaskApi, deleteTaskApi 等保持不变 ...
export const executeTaskApi = (id: number) => {
  return baseRequestClient.post(`${Api.Task}${id}/execute/`);
};

export const deleteTaskApi = (id: number) => {
  return baseRequestClient.delete(`${Api.Task}${id}/`);
};

export const getRuleListApi = async (params: any) => {
  const response = await baseRequestClient.get<any>(Api.Rule, { params });
  return response.data?.results || response.data;
};

export const searchInhosApi = (params: InhosSearchParams) => {
  return requestClient.get<InhosSearchResponse>(Api.Inhos, { params });
};

export const createTaskApi = (data: any) => {
  return baseRequestClient.post(Api.Task, data);
};

export const getFatherChildRulesApi = async (params?: any) => {
  const response = await baseRequestClient.get<any>(Api.RepeatCharging, {
    params,
  });
  return response.data;
};

export const downloadTaskReportApi = async (
  id: number,
  issueNumber: string | number,
) => {
  const response = await baseRequestClient.get(
    `${Api.Task}${id}/download-report/`,
    {
      params: { issue_number: issueNumber },
      responseType: 'blob',
    },
  );
  const disposition = response.headers['content-disposition'] || '';
  const encodedName = /filename\*=utf-8''([^;]+)/i.exec(disposition)?.[1];
  const plainName = /filename="?([^";]+)"?/i.exec(disposition)?.[1];
  let fileName = plainName || `审核报告_任务${id}.docx`;
  if (encodedName) {
    try {
      fileName = decodeURIComponent(encodedName);
    } catch {
      /* 使用默认文件名 */
    }
  }
  downloadFileFromBlob({ source: response.data, fileName });
};
