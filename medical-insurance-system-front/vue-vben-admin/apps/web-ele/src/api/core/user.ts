// src/api/core/user.ts
import { requestClient } from '#/api/request';

/**
 * 获取用户信息
 */
export async function getUserInfoApi() {
  // requestClient 会携带 Authorization，并自动解包 Django 的 { code, result } 响应。
  return await requestClient.get<any>('/user/info');
}
