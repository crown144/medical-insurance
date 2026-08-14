<script lang="ts" setup>
import { onMounted } from 'vue';
import { useRoute } from 'vue-router';

import { resetAllStores, useAccessStore } from '@vben/stores';

const route = useRoute();
const accessStore = useAccessStore();

function clearCurrentUrl() {
  const cleanHash = window.location.hash.split('?')[0] || '#/auth/sso-logout';
  window.history.replaceState(
    {},
    document.title,
    `${window.location.pathname}${cleanHash}`,
  );
}

function completeLogout() {
  clearCurrentUrl();
  accessStore.setAccessToken(null);
  resetAllStores();
  accessStore.setLoginExpired(false);

  const callback = String(route.query.callback || '').trim();
  window.location.replace(
    callback || 'http://nova.hnzhjkd.yiducloud.cn/home/%E6%97%A0#/home-page',
  );
}

onMounted(() => {
  completeLogout();
});
</script>

<template>
  <div class="sso-bridge">
    <div class="sso-card">
      <div class="sso-title">Signing you out</div>
      <div class="sso-desc">Clearing your session. Please wait...</div>
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
