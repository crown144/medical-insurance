<script lang="ts" setup>
import { onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';

import { portalEntryApi } from '#/api';
import { useAuthStore } from '#/store';

import { resolveSsoLogoutCallback, stripSsoCredentials } from './sso-callback';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

onMounted(async () => {
  const callback =
    typeof route.query.callback === 'string' ? route.query.callback : '';
  authStore.clearLoginState();
  window.history.replaceState(
    window.history.state,
    '',
    stripSsoCredentials(window.location.href),
  );
  try {
    const config = await portalEntryApi('');
    const target = resolveSsoLogoutCallback(
      callback,
      config.portalHomeUrl || '',
    );
    window.location.replace(target);
  } catch {
    await router.replace(LOGIN_PATH);
  }
});
</script>

<template>
  <div class="sso-bridge">
    <div class="sso-card">
      <div class="sso-title">正在退出登录</div>
      <div class="sso-desc">正在清理登录状态，请稍候…</div>
    </div>
  </div>
</template>

<style scoped>
.sso-bridge {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
}

.sso-card {
  width: min(420px, 100%);
  padding: 32px 28px;
  text-align: center;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 16px;
  box-shadow: 0 18px 40px rgb(0 0 0 / 8%);
}

.sso-title {
  margin-bottom: 10px;
  color: #303133;
  font-size: 22px;
  font-weight: 600;
}

.sso-desc {
  color: #606266;
  font-size: 14px;
}
</style>
