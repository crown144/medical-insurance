import type { Recordable, UserInfo } from '@vben/types';

import { ref } from 'vue';
import { useRouter } from 'vue-router';

import { LOGIN_PATH } from '@vben/constants';
import { preferences } from '@vben/preferences';
import { resetAllStores, useAccessStore, useUserStore } from '@vben/stores';

import { ElNotification } from 'element-plus';
import { defineStore } from 'pinia';

import {
  getAccessCodesApi,
  getUserInfoApi,
  loginApi,
  logoutApi,
  portalLoginApi,
} from '#/api';
import type { PortalLoginParams } from '#/api/core/auth';
import { $t } from '#/locales';
import { readAccessToken } from './login-response';

export const useAuthStore = defineStore('auth', () => {
  const accessStore = useAccessStore();
  const userStore = useUserStore();
  const router = useRouter();
  const loginLoading = ref(false);

  function clearLoginState() {
    accessStore.setAccessToken(null);
    resetAllStores();
    accessStore.setLoginExpired(false);
  }

  async function establishLogin(response: any) {
    const token = readAccessToken(response);
    const wasLoading = loginLoading.value;
    clearLoginState();
    loginLoading.value = wasLoading;
    accessStore.setAccessToken(token);
    try {
      const [userInfo, accessCodes] = await Promise.all([
        fetchUserInfo(),
        getAccessCodesApi(),
      ]);
      userStore.setUserInfo(userInfo);
      accessStore.setAccessCodes(accessCodes);
      return userInfo;
    } catch (error) {
      clearLoginState();
      throw error;
    }
  }

  async function ssoLogin(params: PortalLoginParams) {
    clearLoginState();
    return establishLogin(await portalLoginApi(params));
  }

  async function authLogin(
    params: Recordable<any>,
    onSuccess?: () => Promise<void> | void,
  ) {
    let userInfo: null | UserInfo = null;
    try {
      loginLoading.value = true;

      const wasExpired = accessStore.loginExpired;
      userInfo = await establishLogin(await loginApi(params));
      if (!wasExpired) {
        onSuccess
          ? await onSuccess()
          : await router.push(
              userInfo?.homePath || preferences.app.defaultHomePath,
            );
      }
      if (userInfo?.realName) {
        ElNotification({
          message: `${$t('authentication.loginSuccessDesc')}:${userInfo.realName}`,
          title: $t('authentication.loginSuccess'),
          type: 'success',
        });
      }
    } catch (error) {
      ElNotification({
        title: '登录失败',
        message:
          (error as any)?.response?.data?.message ||
          (error as Error)?.message ||
          '请重试',
        type: 'error',
      });
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
    // 退出不依赖后端会话：无论接口是否可用，都必须立即移除本地访问令牌。
    clearLoginState();
    await router.replace({
      path: LOGIN_PATH,
      query: redirect
        ? { redirect: encodeURIComponent(router.currentRoute.value.fullPath) }
        : {},
    });
  }

  async function fetchUserInfo(): Promise<UserInfo> {
    const userInfo = await getUserInfoApi();
    if (!userInfo || !Array.isArray(userInfo.roles)) {
      throw new Error('登录用户资料缺少角色信息');
    }
    userStore.setUserInfo(userInfo);
    return userInfo;
  }

  function $reset() {
    loginLoading.value = false;
  }

  return {
    $reset,
    authLogin,
    clearLoginState,
    fetchUserInfo,
    loginLoading,
    logout,
    ssoLogin,
  };
});
