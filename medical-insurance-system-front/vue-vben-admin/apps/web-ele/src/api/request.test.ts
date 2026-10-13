import { beforeEach, describe, expect, it, vi } from 'vitest';

const { access } = vi.hoisted(() => ({
  access: { accessToken: null as null | string },
}));
vi.mock('@vben/stores', () => ({ useAccessStore: () => access }));
vi.mock('@vben/hooks', () => ({ useAppConfig: () => ({ apiURL: '/api' }) }));
vi.mock('@vben/preferences', () => ({
  preferences: { app: { locale: 'zh-CN', enableRefreshToken: false } },
}));
vi.mock('#/store', () => ({ useAuthStore: () => ({ logout: vi.fn() }) }));
vi.mock('./core', () => ({ refreshTokenApi: vi.fn() }));

import { baseRequestClient, requestClient } from './request';

describe('业务请求登录令牌', () => {
  const requests: any[] = [];
  beforeEach(() => {
    requests.length = 0;
    access.accessToken = 'first-token';
    for (const client of [baseRequestClient, requestClient]) {
      client.instance.defaults.adapter = async (config) => {
        requests.push(config);
        return {
          config,
          data: { code: 0, result: { id: 1 } },
          headers: {},
          status: 200,
          statusText: 'OK',
        };
      };
    }
  });
  it('两个客户端均携带令牌，并保留各自返回格式', async () => {
    const raw = await baseRequestClient.get('/tasks/');
    const unwrapped = await requestClient.get('/user/info');
    expect(raw.data.result).toEqual({ id: 1 });
    expect(unwrapped).toEqual({ id: 1 });
    for (const config of requests) {
      expect(config.headers.get('Authorization')).toBe('Bearer first-token');
      expect(config.headers.get('accessToken')).toBe('first-token');
    }
  });
  it('读取最新令牌，退出后不再携带旧令牌', async () => {
    await baseRequestClient.get('/tasks/');
    access.accessToken = 'new-token';
    await baseRequestClient.get('/tasks/');
    access.accessToken = null;
    await baseRequestClient.post('/auth/login', {});
    expect(requests[1].headers.get('Authorization')).toBe('Bearer new-token');
    expect(requests[2].headers.get('Authorization')).toBeNull();
    expect(requests[2].headers.get('accessToken')).toBeNull();
  });
});
