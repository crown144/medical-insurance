import autoprefixer from 'autoprefixer';
import cssnano from 'cssnano';
import antdFixes from 'postcss-antd-fixes';
import postcssImport from 'postcss-import';
import postcssPresetEnv from 'postcss-preset-env';
import tailwindcss from 'tailwindcss';
import nesting from 'tailwindcss/nesting';

import config from '.';

export default {
  // Resolve plugins in this package, where pnpm installs their dependencies.
  plugins: [
    ...(process.env.NODE_ENV === 'production' ? [cssnano({})] : []),
    // Specifying the config is not necessary in most cases, but it is included
    autoprefixer({}),
    // 修复 element-plus 和 ant-design-vue 的样式和tailwindcss冲突问题
    antdFixes({ prefixes: ['ant', 'el'] }),
    postcssImport({}),
    postcssPresetEnv({}),
    tailwindcss({ config }),
    nesting(),
  ],
};
