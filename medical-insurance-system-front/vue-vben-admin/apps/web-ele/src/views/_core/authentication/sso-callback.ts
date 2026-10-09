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
  if (path.split('?')[0]?.startsWith('/oauth/'))
    throw new Error('回跳地址不能是登录回调页面');
  return path === '/' ? '' : path;
}
