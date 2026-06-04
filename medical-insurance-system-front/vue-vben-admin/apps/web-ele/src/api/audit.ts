// 👇 重点：这里加上 type 关键字
import type { AuditParams, AuditResponse } from './model/auditModel';

import { requestClient } from '#/api/request';

enum Api {
  Audit = '/audit/',
}

/**
 * @description: 发起审计检测
 */
export const startAuditApi = (params: AuditParams) => {
  // Vben 5.0 写法: requestClient.post(url, data)
  return requestClient.post<AuditResponse>(Api.Audit, params);
};
