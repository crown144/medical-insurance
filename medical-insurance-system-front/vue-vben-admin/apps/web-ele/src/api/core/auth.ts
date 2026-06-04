// src/api/core/auth.ts
import { baseRequestClient, requestClient } from '#/api/request';

export namespace AuthApi {
  export interface LoginParams {
    password?: string;
    username?: string;
  }
  export interface LoginResult {
    token?: string;
    accessToken?: string;
    username?: string;
    roles?: string[];
  }
  export interface RefreshTokenResult {
    data: string;
    status: number;
  }
}

/**
 * 登录 (保留这个修改，因为它是对的)
 */
export async function loginApi(data: AuthApi.LoginParams) {
  return baseRequestClient.post<any>('/auth/login', data);
}

export async function refreshTokenApi() {
  return baseRequestClient.post<AuthApi.RefreshTokenResult>('/auth/refresh', {
    withCredentials: true,
  });
}

export async function logoutApi() {
  return baseRequestClient.post('/auth/logout', {
    withCredentials: true,
  });
}

export async function getAccessCodesApi() {
  return requestClient.get<string[]>('/auth/codes');
}

// ❌ 务必确认这里没有 getUserInfoApi 了！
