<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { LOGIN_PATH } from '@vben/constants';
import { preferences } from '@vben/preferences';
import { useAuthStore } from '#/store';
import { resolveSsoCallback } from './sso-callback';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const errorMessage = ref('');

function queryString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

onMounted(async () => {
  try {
    // Vue Router 已解码 query；不要二次 decodeURIComponent 破坏回跳查询参数。
    const callback = resolveSsoCallback(
      queryString(route.query.callback),
      window.location.origin,
      import.meta.env.BASE_URL,
    );
    const code = queryString(route.query.code);
    const ticket = queryString(route.query.ticket);
    const appid = queryString(route.query.appid);
    if (!code && (!ticket || !appid))
      throw new Error('缺少门户登录凭据，请从统一门户重新进入');
    const user = await authStore.ssoLogin(code ? { code } : { ticket, appid });
    await router.replace(
      callback || user?.homePath || preferences.app.defaultHomePath,
    );
  } catch (error: any) {
    errorMessage.value =
      error?.response?.data?.message ||
      error?.message ||
      '门户登录失败，请从统一门户重新进入';
  }
});
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-6">
    <el-result
      v-if="errorMessage"
      icon="error"
      title="门户登录失败"
      :sub-title="errorMessage"
    >
      <template #extra
        ><el-button @click="router.replace(LOGIN_PATH)"
          >返回账号登录</el-button
        ></template
      >
    </el-result>
    <p v-else role="status">正在验证门户登录并加载医保权限，请稍候…</p>
  </div>
</template>
