import type { LoginParams, LoginResult } from './model/authModel';

// src/api/auth.ts
// 🔴 1. 确保引入了 baseRequestClient
import { baseRequestClient, requestClient } from '#/api/request';

enum Api {
  GetCodes = '/auth/codes',
  GetUserInfo = '/user/info',
  Login = '/auth/login',
  Logout = '/auth/logout',
}

/**
 * 登录接口 (保持您现在的正确代码)
 */
export async function loginApi(params: LoginParams) {
  return requestClient.post<LoginResult>(Api.Login, params);
}

/**
 * 获取用户信息接口
 * 🔴 2. 核心修改：使用 baseRequestClient 并手动解包
 */
export async function getUserInfoApi() {
  // 使用 baseRequestClient 绕过拦截器，拿到完整响应
  const response = await baseRequestClient.get<any>(Api.GetUserInfo);

  // 手动提取 result 里的数据
  // 您的后端返回格式是: { code: 0, result: { ...user info... } }
  return response.data?.result;
}

export async function logoutApi() {
  return requestClient.post(Api.Logout);
}

export async function getAccessCodesApi() {
  return requestClient.get<string[]>(Api.GetCodes);
}
