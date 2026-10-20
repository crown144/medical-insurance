# 医保系统安全整改

对应用户粘贴的扫描清单；未取得报告原始 DOC 和扫描器请求/响应证据，不能据此宣布原报告全部通过。

| 项目 | 代码核查与处理 | 上线验收 |
| --- | --- | --- |
| 内网 IP | 新 JS/HTML/JSON 未匹配到私网 IPv4；API 使用相对 `/yibao-api` | 对照报告精确 URL 检查外层网关、错误页和旧静态文件 |
| X-XSS-Protection | 设为 `0`，关闭已弃用的浏览器 XSS auditor | 若扫描器要求 `1; mode=block`，按弃用依据解释，实际防御使用 CSP 与安全渲染 |
| X-Content-Type-Options | `nosniff`，包括错误响应 | 检查实际 8080 和 8088 入口 |
| JavaScript Cookie 引用 | 业务认证使用 Bearer token；构建仍含 Axios 通用 Cookie helper，字符串出现不等同敏感 Cookie 泄露 | 核对报告调用链及实际 Set-Cookie；门户/管理后台 Cookie 另行核查 |
| CSP | 同源脚本/连接，禁止 inline script、eval、object；样式保留 unsafe-inline 兼容 Element Plus | 本地浏览器已验证登录、刷新、任务与下载；上线检查最终响应头和控制台 |
| 电话 | 演示手机号 42 处改掩码，保留真实业务字段 | 新构建手机号模式匹配为 0；部署移走旧 chunk，不能叠加复制 |
| X-Frame-Options | SAMEORIGIN，配合 frame-ancestors self | 门户新窗口跳转正常；若改用跨源 iframe，须单独明确允许的父站 |
| 邮箱 | 移除模板作者邮箱、banner 联系方式和占位符，保留作者、版权和许可证 | 新构建邮箱模式匹配为 0；不删除真实业务联系方式 |
| 存储型 XSS | RuleDetail 来源使用 Vue 文本渲染；额外修复 RuleTestRun JSON 键未转义 | img/svg/script 及嵌套 JSON 键和值回归通过；既有存储无需清洗或迁移即可安全显示 |

来源 HTML 现在显示为源码，不提供富文本预览。后端保留规则文本原文：比较符、Python 代码和业务描述不做粗暴字符替换，API 返回 JSON，由前端按显示上下文转义。本次不修改认证协议或数据库表。

## CSP 兼容与部署

`security-headers.conf` 在 server 级 include。传统 Nginx 中，location 如另有 add_header 会停止继承父级 add_header，需同时 include 安全头。外层代理也可能覆盖响应头，必须检查最终响应。

门户和生产构建关闭了内联启动 loading 脚本。不要把新策略直接套到旧构建。现有菜单/共享 UI 用到的 58 个图标已打包为 `apps/web-ele/src/offline-icons.json`，不依赖公网 Iconify API。新增图标后运行：

```bash
python3 scripts/deploy/security/generate-offline-icons.py
pnpm --filter @vben/web-ele run build:portal
```

图标数据来自已有依赖 `@iconify/json`，各集合作者及许可证保留在 JSON 的 info 中。

`default.conf` 适用当前静态服务 yibao_front，监听容器 80，同时支持直接 /yibao/ 和网关剥去前缀的请求。外部 /yibao-api 路由仍由原网关处理。保留原 Compose、8098 端口及网络。

本机没有 Docker/Nginx。浏览器测试由本地静态服务读取同一安全头文件，并不替代服务器 nginx -t。上线先用现有镜像检查 Nginx 配置，再重建前端并复扫。用户粘贴报告的 8080 与当前门户回调 8088 是不同入口，两者均需验收。

## 依据

- [MDN X-XSS-Protection：弃用及旧过滤器风险](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-XSS-Protection)
- [MDN CSP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP)
