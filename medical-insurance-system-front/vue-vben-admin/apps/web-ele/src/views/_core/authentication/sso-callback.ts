export function resolveSsoCallback(
  callback: string,
  origin: string,
  base = '/',
): string {
  if (!callback) return '';
  const url = new URL(callback, `${origin}${base}`);
  if (url.origin !== origin || url.username || url.password) {
    throw new Error('回跳地址必须属于医保应用');
  }
  let path = url.hash.startsWith('#/')
    ? url.hash.slice(1)
    : `${url.pathname}${url.search}${url.hash}`;
  if (!url.hash.startsWith('#/') && base !== '/') {
    const prefix = base.endsWith('/') ? base.slice(0, -1) : base;
    if (!url.pathname.startsWith(`${prefix}/`))
      throw new Error('回跳地址不属于医保应用');
    path = path.slice(prefix.length);
  }
  const routePath = path.split(/[?#]/)[0] || '';
  if (
    routePath.startsWith('/oauth/') ||
    ['/auth/sso', '/auth/sso-logout'].includes(routePath.replace(/\/$/, ''))
  )
    throw new Error('回跳地址不能是登录回调页面');
  return path === '/' ? '' : path;
}

export function resolveSsoLogoutCallback(
  callback: string,
  portalHomeUrl: string,
): string {
  if (!portalHomeUrl) throw new Error('未配置门户退出地址');
  const portal = new URL(portalHomeUrl);
  const target = new URL(callback || portalHomeUrl, portalHomeUrl);
  if (
    !['http:', 'https:'].includes(target.protocol) ||
    target.origin !== portal.origin ||
    target.username ||
    target.password
  ) {
    throw new Error('退出回跳地址必须属于统一门户');
  }
  return target.href;
}

/** Remove one-time credentials from both history-mode and hash-mode URLs. */
export function stripSsoCredentials(href: string): string {
  const url = new URL(href);
  const [path, query] = url.hash.slice(1).split('?');
  const hashQuery = new URLSearchParams(query);
  for (const key of ['ticket', 'code', 'appid', 'callback']) {
    url.searchParams.delete(key);
    hashQuery.delete(key);
  }
  if (query !== undefined) {
    const search = hashQuery.toString();
    url.hash = `${path}${search ? `?${search}` : ''}`;
  }
  return url.href;
}
