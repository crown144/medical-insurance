<script lang="ts" setup>
import { onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { preferences } from '@vben/preferences';
import { resetAllStores, useAccessStore, useUserStore } from '@vben/stores';

import { ElMessage } from 'element-plus';

import { getAccessCodesApi, getUserInfoApi, loginSsoApi } from '#/api';

const router = useRouter();
const route = useRoute();
const accessStore = useAccessStore();
const userStore = useUserStore();

function clearCurrentUrl() {
  const cleanHash = window.location.hash.split('?')[0] || '#/auth/sso';
  window.history.replaceState(
    {},
    document.title,
    `${window.location.pathname}${cleanHash}`,
  );
}

async function bootstrapSsoLogin() {
  const ticket = String(route.query.ticket || '').trim();
  const appid = String(route.query.appid || '').trim();
  const callback = String(route.query.callback || '').trim();

  try {
    if (!ticket || !appid || !callback) {
      throw new Error('Missing SSO params.');
    }

    const response = await loginSsoApi({ ticket, appid, callback });
    const result = response?.data?.result ?? response?.result ?? {};
    const accessToken = result.accessToken || result.token;
    const targetCallback = result.callback || callback;

    if (!accessToken || !targetCallback) {
      throw new Error('SSO login response is incomplete.');
    }

    clearCurrentUrl();
    resetAllStores();
    accessStore.setAccessToken(accessToken);

    const [userInfo, accessCodes] = await Promise.all([
      getUserInfoApi(),
      getAccessCodesApi(),
    ]);

    userStore.setUserInfo(userInfo);
    accessStore.setAccessCodes(accessCodes);
    accessStore.setLoginExpired(false);

    window.location.replace(
      targetCallback || userInfo?.homePath || preferences.app.defaultHomePath,
    );
  } catch {
    accessStore.setAccessToken(null);
    ElMessage.error('SSO login failed. Please confirm this account is enabled.');
    await router.replace('/auth/login');
  }
}

onMounted(() => {
  void bootstrapSsoLogin();
});
</script>

<template>
  <div class="sso-bridge">
    <div class="sso-card">
      <div class="sso-title">Signing you in</div>
      <div class="sso-desc">Preparing your session. Please wait...</div>
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
