import type { RouteRecordRaw } from 'vue-router';

function mergeRouteModules(
  routeModules: Record<string, unknown>,
): RouteRecordRaw[] {
  const mergedRoutes: RouteRecordRaw[] = [];

  for (const [key, mod] of Object.entries(routeModules)) {
    // 兼容两种 glob 结果：
    // 1) eager: true        => mod = { default: ... }
    // 2) import: 'default'  => mod = 默认导出本身
    const routes = (mod as any)?.default ?? mod;

    if (Array.isArray(routes)) {
      mergedRoutes.push(...routes);
      continue;
    }

    // 兼容单个 RouteRecordRaw 对象
    if (routes && typeof routes === 'object') {
      mergedRoutes.push(routes as RouteRecordRaw);
      continue;
    }

    // 兜底：直接告诉你哪个文件/模块有问题
    console.warn(`[router] invalid route module: ${key}`, mod);
  }

  return mergedRoutes;
}

export { mergeRouteModules };
