// src/api/model/authModel.ts

/**
 * 登录返回结果类型定义
 */
export interface LoginResult {
  userId: number | string;
  // ✅ 必须加上这一行，解决 "类型 LoginResult 上不存在属性 token" 的报错
  token?: string;
  accessToken?: string;
  username?: string;
  realName?: string;
  roles?: string[];
  desc?: string;
  homePath?: string;
}

/**
 * 登录参数类型定义
 */
export interface LoginParams {
  username?: string;
  password?: string;
}
