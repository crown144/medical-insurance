import { defineConfig } from '@vben/vite-config';

export default defineConfig(async () => {
  const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000';

  return {
    application: {},
    vite: {
      // ❌ 删除 plugins: [ ElementPlus(...) ]，Vben 内部已处理，无需重复配置
      server: {
        proxy: {
          '/api': {
            // ✅ 1. 指向 Django 后端
            target: proxyTarget,

            // ✅ 2. 允许跨域
            changeOrigin: true,

            // ✅ 3. 支持 WebSocket (可选)
            ws: true,

            // ⚠️ 重点：如果 Django 路由包含 /api (如 path('api/', ...))，
            // 绝对不要写 rewrite，否则后端会报 404！
          },
        },
      },
    },
  };
});
