import { describe, expect, it } from 'vitest';
import { resolveSsoCallback } from './sso-callback';

describe('门户回跳', () => {
  const origin = 'https://insurance.example.test';
  it('支持 iframe hash 页面并保持内部查询参数编码', () => {
    expect(
      resolveSsoCallback(`${origin}/#/task/execution?search=a%26b`, origin),
    ).toBe('/task/execution?search=a%26b');
    expect(resolveSsoCallback('/task/execution', origin)).toBe(
      '/task/execution',
    );
  });
  it('支持部署到子目录以及空回跳', () => {
    expect(
      resolveSsoCallback(
        `${origin}/medical/#/task/execution`,
        origin,
        '/medical/',
      ),
    ).toBe('/task/execution');
    expect(
      resolveSsoCallback(
        `${origin}/medical/task/execution?q=x`,
        origin,
        '/medical/',
      ),
    ).toBe('/task/execution?q=x');
    expect(resolveSsoCallback('', origin)).toBe('');
  });
  it('拒绝外部地址、错误子目录和回调循环', () => {
    for (const callback of [
      'https://other.example.test/#/task',
      '//other.example.test',
      'javascript:alert(1)',
      '/#/oauth/login',
    ]) {
      expect(() => resolveSsoCallback(callback, origin)).toThrow();
    }
    expect(() =>
      resolveSsoCallback('/other/task', origin, '/medical/'),
    ).toThrow();
  });
});
