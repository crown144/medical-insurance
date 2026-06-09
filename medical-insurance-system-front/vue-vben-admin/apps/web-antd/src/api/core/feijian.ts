/**
 * 飞行检查 API 接口定义
 * 后端实现后替换为真实接口调用
 */
import { requestClient } from '#/api/request';

// ==================== 类型定义 ====================

/** 医疗机构类型 */
export type HospitalType = 'general' | 'specialist' | 'community' | 'private';

/** 检查类型 */
export type InspectionType = 'routine' | 'special' | 'unannounced' | 'follow-up';

/** 检查状态 */
export type InspectionStatus =
  | 'draft'
  | 'pending'
  | 'in-progress'
  | 'completed'
  | 'cancelled';

/** 检查结果 */
export type InspectionResult =
  | 'none'
  | 'compliant'
  | 'minor-issue'
  | 'major-issue'
  | 'violation';

/** 医疗机构信息 */
export interface HospitalInfo {
  id: string;
  name: string;
  type: HospitalType;
  typeLabel: string;
  address: string;
  contactPerson: string;
  contactPhone: string;
}

/** 检查组成员 */
export interface InspectorMember {
  id: string;
  name: string;
  role: string;
  phone: string;
}

/** 飞行检查记录 */
export interface FeiJianRecord {
  id: string;
  /** 检查编号 */
  inspectionNo: string;
  /** 医疗机构 */
  hospital: HospitalInfo;
  /** 检查类型 */
  inspectionType: InspectionType;
  inspectionTypeLabel: string;
  /** 检查日期 */
  inspectionDate: string;
  /** 检查结束日期 */
  inspectionEndDate: string;
  /** 检查组 */
  inspectionTeam: InspectorMember[];
  /** 检查组组长 */
  teamLeader: string;
  /** 检查结果 */
  result: InspectionResult;
  resultLabel: string;
  /** 状态 */
  status: InspectionStatus;
  statusLabel: string;
  /** 检查内容/发现 */
  findings: string;
  /** 处理建议 */
  recommendation: string;
  /** 涉及违规金额 */
  violationAmount: number;
  /** 创建时间 */
  createdAt: string;
  /** 更新时间 */
  updatedAt: string;
}

/** 统计数据 */
export interface FeiJianStats {
  total: number;
  inProgress: number;
  completed: number;
  withIssues: number;
  totalViolationAmount: number;
}

/** 列表查询参数 */
export interface FeiJianQueryParams {
  page: number;
  pageSize: number;
  inspectionNo?: string;
  hospitalName?: string;
  hospitalType?: HospitalType;
  inspectionType?: InspectionType;
  status?: InspectionStatus;
  result?: InspectionResult;
  dateRange?: [string, string];
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

// ==================== API 接口 ====================

/** 获取统计数据 */
export async function getFeiJianStatsApi(): Promise<FeiJianStats> {
  return requestClient.get('/feijian/stats');
}

/** 获取飞行检查列表 */
export async function getFeiJianListApi(
  params: FeiJianQueryParams,
): Promise<PaginatedResponse<FeiJianRecord>> {
  return requestClient.get('/feijian/list', { params });
}

/** 获取飞行检查详情 */
export async function getFeiJianDetailApi(
  id: string,
): Promise<FeiJianRecord> {
  return requestClient.get(`/feijian/detail/${id}`);
}

/** 新增飞行检查 */
export async function createFeiJianApi(
  data: Partial<FeiJianRecord>,
): Promise<FeiJianRecord> {
  return requestClient.post('/feijian/create', data);
}

/** 更新飞行检查 */
export async function updateFeiJianApi(
  id: string,
  data: Partial<FeiJianRecord>,
): Promise<FeiJianRecord> {
  return requestClient.put(`/feijian/update/${id}`, data);
}

/** 删除飞行检查 */
export async function deleteFeiJianApi(id: string): Promise<void> {
  return requestClient.delete(`/feijian/delete/${id}`);
}

/** 导出飞行检查 */
export async function exportFeiJianApi(
  params: Partial<FeiJianQueryParams>,
): Promise<Blob> {
  return requestClient.get('/feijian/export', { params, responseType: 'blob' });
}