/** 支持本项目 result.accessToken 和对接文档 token.access_token 两种响应。 */
export function readAccessToken(response: any): string {
  const body = response?.data ?? response;
  const data = body?.result ?? body;
  const token = data?.accessToken ?? data?.token?.access_token ?? data?.token;
  if (typeof token !== 'string' || !token.trim()) {
    throw new Error('登录接口未返回有效令牌');
  }
  return token;
}
