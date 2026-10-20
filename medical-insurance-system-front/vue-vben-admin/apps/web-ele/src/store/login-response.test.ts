import { describe, expect, it } from 'vitest';
import { readAccessToken } from './login-response';

describe('登录响应兼容', () => {
  it('读取医保 Axios 响应和已解包响应', () => {
    expect(
      readAccessToken({ data: { result: { accessToken: 'medical-token' } } }),
    ).toBe('medical-token');
    expect(readAccessToken({ result: { token: 'medical-token' } })).toBe(
      'medical-token',
    );
  });
  it('读取前端对接文档的嵌套令牌', () => {
    expect(
      readAccessToken({
        data: {
          token: { access_token: 'document-token', token_type: 'bearer' },
        },
      }),
    ).toBe('document-token');
  });
  it('拒绝空令牌和对象，避免把 [object Object] 作为令牌', () => {
    for (const response of [
      {},
      { token: {} },
      { accessToken: '' },
      { token: true },
    ]) {
      expect(() => readAccessToken(response)).toThrow('有效令牌');
    }
  });
});
