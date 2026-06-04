// src/api/core/user.ts
// 🔴 1. 引入 baseRequestClient (用来绕过拦截器)
import { baseRequestClient } from '#/api/request';

/**
 * 获取用户信息
 */
export async function getUserInfoApi() {
  // 🔴 2. 改用 baseRequestClient 获取原始响应
  const response = await baseRequestClient.get<any>('/user/info');

  // 调试日志 (修好后可删除)
  console.warn('🔥 用户信息原始数据:', response);

  // 🔴 3. 手动解包：兼容 Django 返回的 { code: 0, result: { ... } }
  // 必须返回 result 里的内容，Store 才能拿到 roles
  return response.data?.result || response.data;
}
