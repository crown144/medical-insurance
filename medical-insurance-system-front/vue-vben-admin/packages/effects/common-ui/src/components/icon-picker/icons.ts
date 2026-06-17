import type { Recordable } from '@vben/types';

/**
 * 一个缓存对象，在不刷新页面时，无需重复请求远程接口
 */
export const ICONS_MAP: Recordable<string[]> = {};
const OFFLINE_ICONS_MAP: Recordable<string[]> = {
  'ant-design': ['ant-design:unordered-list-outlined'],
  carbon: ['carbon:workspace'],
  ic: ['ic:baseline-view-in-ar'],
  logos: ['logos:naiveui'],
  lucide: [
    'lucide:area-chart',
    'lucide:book-open-text',
    'lucide:copyright',
    'lucide:layout-dashboard',
    'lucide:user',
  ],
  mdi: [
    'mdi:alert-circle-outline',
    'mdi:book-medical',
    'mdi:cash-multiple',
    'mdi:check-decagram-outline',
    'mdi:clipboard-check-outline',
    'mdi:clipboard-text-outline',
    'mdi:clipboard-text-search-outline',
    'mdi:cog-outline',
    'mdi:code-tags',
    'mdi:database-outline',
    'mdi:database-search-outline',
    'mdi:file-document-outline',
    'mdi:file-eye-outline',
    'mdi:file-search-outline',
    'mdi:folder-cog-outline',
    'mdi:format-list-bulleted',
    'mdi:format-list-bulleted-type',
    'mdi:github',
    'mdi:knife',
    'mdi:marker-check',
    'mdi:pill',
    'mdi:play-circle-outline',
    'mdi:plus-box-outline',
    'mdi:repeat',
    'mdi:script-text-outline',
    'mdi:shape-outline',
    'mdi:stethoscope',
    'mdi:tray-arrow-up',
    'mdi:vector-arrange-above',
    'mdi:view-dashboard-variant-outline',
  ],
};

/**
 * 通过Iconify接口获取图标集数据。
 * 同一时间多个图标选择器同时请求同一个图标集时，实际上只会发起一次请求（所有请求共享同一份结果）。
 * 请求结果会被缓存，刷新页面前同一个图标集不会再次请求
 * @param prefix 图标集名称
 * @returns 图标集中包含的所有图标名称
 */
export async function fetchIconsData(prefix: string): Promise<string[]> {
  if (Reflect.has(ICONS_MAP, prefix) && ICONS_MAP[prefix]) {
    return ICONS_MAP[prefix];
  }
  ICONS_MAP[prefix] = OFFLINE_ICONS_MAP[prefix] || [];
  return ICONS_MAP[prefix];
}
