import type { Recordable, UserInfo } from '@vben/types';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';
import { preferences } from '@vben/preferences';
import { resetAllStores, useAccessStore, useUserStore } from '@vben/stores';

import { ElNotification } from 'element-plus';
import { defineStore } from 'pinia';

import { getAccessCodesApi, getUserInfoApi, loginApi, logoutApi } from '#/api';
import { $t } from '#/locales';

export const useAuthStore = defineStore('auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();
  const loginLoading = ref(false);

  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    try {
      loginLoading.value = true;

      // 1. 调用 API (baseRequestClient 返回完整 Axios 响应)
      const response = await loginApi(params);

      // 调试：看一眼原始数据
      console.warn('🔥 登录接口完整响应:', response);

      // 2. 🛡️【修正后的取值逻辑】🛡️
      // 您的日志显示数据在 response.data.result.accessToken
      // 为了保险，我们把所有可能的路径都试一遍
      const accessToken =
        response?.data?.result?.accessToken || // ✅ 命中您的当前结构
        response?.data?.result?.token || // 兼容 Django 返回 token 字段
        response?.data?.token || // 兼容没有 result 包裹的情况
        response?.data?.accessToken ||
        response?.result?.accessToken || // 兼容被拦截器解包后的情况
        response?.token;

      // 3. 判断是否成功
      if (accessToken) {
        console.warn('✅ 终于拿到 Token 了:', accessToken);
        accessStore.setAccessToken(accessToken);

        // 并行获取用户信息和权限
        const [fetchUserInfoResult, accessCodes] = await Promise.all([
          fetchUserInfo(),
          getAccessCodesApi(),
        ]);

        userInfo = fetchUserInfoResult;
        userStore.setUserInfo(userInfo);
        accessStore.setAccessCodes(accessCodes);

        if (accessStore.loginExpired) {
          accessStore.setLoginExpired(false);
        } else {
          onSuccess
            ? await onSuccess?.()
            : await router.push(
                userInfo?.homePath || preferences.app.defaultHomePath,
              );
        }

        if (userInfo?.realName) {
          ElNotification({
            message: `${$t('authentication.loginSuccessDesc')}:${userInfo?.realName}`,
            title: $t('authentication.loginSuccess'),
            type: 'success',
          });
        }
      } else {
        console.error('❌ 仍然无法提取 Token，请检查路径匹配', response);
      }
    } catch (error) {
      console.error('登录过程发生异常:', error);
    } finally {
      loginLoading.value = false;
    }

    return {
      userInfo,
    };
  }

  async function logout(redirect: boolean = true) {
    try {
      await logoutApi();
    } catch {}
    resetAllStores();
    accessStore.setLoginExpired(false);
    await router.replace({
      path: LOGIN_PATH,
      query: redirect
        ? { redirect: encodeURIComponent(router.currentRoute.value.fullPath) }
        : {},
    });
  }

  async function fetchUserInfo() {
    let userInfo: null | UserInfo = null;
    userInfo = await getUserInfoApi();
    userStore.setUserInfo(userInfo);
    return userInfo;
  }

  function $reset() {
    loginLoading.value = false;
  }

  return {
    $reset,
    authLogin,
    fetchUserInfo,
    loginLoading,
    logout,
  };
});
