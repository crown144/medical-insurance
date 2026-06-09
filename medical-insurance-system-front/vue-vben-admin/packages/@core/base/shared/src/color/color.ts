import { TinyColor } from '@ctrl/tinycolor/dist/module/index.js';

export function isDarkColor(color: string) {
  return new TinyColor(color).isDark();
}

export function isLightColor(color: string) {
  return new TinyColor(color).isLight();
}
