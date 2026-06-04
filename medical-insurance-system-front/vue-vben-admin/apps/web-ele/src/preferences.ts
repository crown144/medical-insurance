// apps/web-ele/src/preferences.ts
import { defineOverridesPreferences } from '@vben/preferences';

/**
 * 更改配置后请清空缓存（localStorage 里带 vben-web-ele / preferences 的都删掉）
 */
export const overridesPreferences = defineOverridesPreferences({
  app: {
    // 左上角标题：建议给一个更短的（更像业务系统）
    // 如果你一定要用 env，也可以换成 import.meta.env.VITE_APP_TITLE
    name: '医保控费',

    // 登录后默认进入任务列表（你之前已把 mock 的 homePath 也改了，这里再兜底一次）
    defaultHomePath: '/task/execution',

    // 关掉“偏好设置/个性化”（右上角齿轮通常也会一起没了）
    enablePreferences: false,

    // 如果不需要检查更新也关掉
    enableCheckUpdates: false,
  },

  // ✅ 默认亮色（不是 dark）
  theme: {
    mode: 'light',
  },

  // ✅ 右上角那排大多数按钮都在这里
  widget: {
    globalSearch: false,
    languageToggle: false,
    notification: false,
    refresh: false,
    themeToggle: false,
    fullscreen: false,
    lockScreen: false,
    // 侧边栏折叠按钮要不要保留：要就 true，不要就 false
    sidebarToggle: true,
  },

  // ✅ 顺手把快捷键也关掉（Ctrl K 之类）
  shortcutKeys: {
    enable: false,
    globalSearch: false,
    globalPreferences: false,
    globalLockScreen: false,
    globalLogout: false,
  },
  navigation: {
    accordion: false, // ✅ 允许多个一级菜单同时展开
  },
});
