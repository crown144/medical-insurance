import { addIcon } from '@vben/icons';

export const OFFLINE_ICON_NAMES = [
  'ant-design:unordered-list-outlined',
  'carbon:workspace',
  'ic:baseline-view-in-ar',
  'logos:naiveui',
  'lucide:area-chart',
  'lucide:book-open-text',
  'lucide:copyright',
  'lucide:layout-dashboard',
  'lucide:user',
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
] as const;

const fallbackIcon = {
  body: '<path fill="currentColor" d="M4 4h16v16H4V4Zm3 3v10h10V7H7Zm2 2h6v2H9V9Zm0 4h6v2H9v-2Z"/>',
  height: 24,
  width: 24,
};

export function registerOfflineIcons() {
  for (const name of OFFLINE_ICON_NAMES) {
    addIcon(name, fallbackIcon);
  }
}
