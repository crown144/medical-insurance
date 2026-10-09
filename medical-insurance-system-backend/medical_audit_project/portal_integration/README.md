# 统一门户用户权限集成

实现《统一门户接入说明文档 v1.9》3.3.1 / 3.4 的门户单点登录，以及 3.6 定义的全部 8 个用户权限回调，使用 Django ORM、事务和行锁。门户 iframe 角色管理页面和统一退出仍未实现。

## 门户登录与前端请求

支持两种接入方式，注册 `login_callback` 时选一种：

1. 按文档示例填写 `https://医保前端地址/#/oauth/login`。前端读取 `ticket`、`appid`、`callback`，调用 `POST /api/sso/login`；后端验证门户身份、同步本地账号并签发医保访问令牌。前端存储令牌、加载用户/权限后跳转原 `callback`，无回跳时进入任务列表。
2. 需要服务器 HTTP 302 回调时填写 `https://医保后端地址/api/portal/sso/callback`。配置 `PORTAL_FRONTEND_URL=https://医保前端地址`（部署子目录时包含子目录，不含 `#`）。后端校验 ticket 后，通过 302 跳到前端 `/oauth/login`，以两分钟有效、仅可消费一次的数据库交换码完成登录。数据库存储可跨多个 Django worker 工作；交换码不是长期访问令牌。

3.1 的未登录应用入口也已实现：配置 `PORTAL_CAS_LOGIN_URL` 为门户团队提供的 CAS 登录服务地址，`PORTAL_LOGIN_CALLBACK_URL` 为已注册的完整 `login_callback`，以及 `PORTAL_FRONTEND_URL`。前端发现没有本地令牌时查询 `GET /api/portal/sso/config?callback=...` 并跳转 CAS，携带匹配注册值的 `service` 和实际访问页 `callback`。也可直接用 `GET /api/portal/sso/start` 发起 HTTP 302 登录。未配置 CAS 地址时默认保留本地登录，直接进入 `/auth/login` 也可使用本地账号。登录服务地址不能根据登出地址猜测，应向门户确认。

`POST /api/sso/login` 的 JSON 请求为 `{"ticket":"ST-...","appid":"..."}`，或后端 302 回调发的 `{"code":"..."}`，不可混用。成功响应沿用本系统 `{code:0,result:{accessToken,token,username,roles,...}}`，与本地 `/api/auth/login` 相同。门户 ticket 只用于身份校验，不作为业务访问令牌。用户身份来自后端对门户的请求，不能由浏览器指定。

严格使用 3.4 的 `GET /api/security-manage-permission/app/cas/serviceValidate`，`ticket` 和 `appid` 放 query，`Content-Type: application/json`，响应为明文且成功 code 为整数 0；与权限回调的 SM2 加密无关。文档响应字段表包含 `expired`，示例却遗漏；实际响应遗漏时，补查 3.7.1 加密用户详情并验证，不能将缺失有效期当成永不过期。这种部署仍需配置真实门户/应用密钥。appid 必须匹配已注册应用。

首次门户登录创建 normal 账号，密码设为不可用；已绑定用户沿用原角色及密码。新登录不能恢复已停用或移除的应用权限，门户全局禁用及过期账号也不签发令牌。本地用户名/密码登录保留。

web-ele 两个请求客户端都携带 `Authorization: Bearer <token>` 和文档约定的 `accessToken: <token>`；后端支持这两种头，优先取 Authorization。保留原有 Axios 完整响应和 result 解包两种返回行为。报告下载改成携带令牌获取 Blob 后保存，支持服务端中文文件名。生产默认 API 为 `/api`；部署时反向代理 `/api` 到 Django。开发模拟接口关闭。

本次适配医保现有 Django 接口，不会将项目改成角色对接文档中的 FastAPI `/v2/rbac` 后端或更换令牌算法。读取 `token.access_token` 的兼容并不意味着第三方 JWT 能直接访问医保接口。

## 接口和行为

| 注册时的 action.type | 本应用 URL | 请求 |
|---|---|---|
| `app_admin_set` | `POST /api/portal/actions/app-admin-set` | `user_id` |
| `query_user_status` | `POST /api/portal/actions/query-user-status` | `user_ids` 字符串数组 |
| `remove_user` | `POST /api/portal/actions/remove-user` | `user_id` |
| `disable_user` | `POST /api/portal/actions/disable-user` | `user_id` |
| `enable_user` | `POST /api/portal/actions/enable-user` | `user_id` |
| `default_role_callback` | `POST /api/portal/actions/default-role` | `user_id` |
| `create_user_callback` | `POST /api/portal/actions/create-user` | 完整用户资料，以 `id` 标识用户 |
| `edit_user_callback` | `POST /api/portal/actions/edit-user` | 完整用户资料，以 `id` 标识用户 |

请求使用 `Content-Type: application/json`。成功响应为 `{"code":0,"message":"操作成功","data":...}`；除查询外，明文 `data` 为 `null`。查询结果按 v1.9 示例返回整数 `status` 和 `exists`、布尔 `admin` 和 `expired`，保留输入顺序及重复项。文档字段表将 `status` 写作 string，而 JSON 示例使用整数；本实现遵循示例。

创建、修改通知接收 `id`、`username`、`fullname`、`phone`、`organization_code`、`department`、`create_time`、`update_time`、`expired`、`status`；`email` 可选。`expired` 是秒时间戳，`-1` 表示永不过期；`status` 为整数 1（正常）或 2（禁用）。手机号等资料允许空字符串。保留旧版查询资料中部分字段别名及毫秒时间戳兼容性。

创建/修改通知按不可变的门户 ID 更新已有绑定，支持登录名修改；不会覆盖本地密码或角色，也不会恢复已停用/移除的应用权限。门户账号全局禁用时，即使收到应用启用或管理员授权，也不能访问业务接口。修改通知可更新有效期，并即时影响已签发 token 的访问。

移除采用逻辑移除，保留业务历史，查询 `exists=0`。启用允许重新添加已移除用户并恢复先前角色，符合 3.6.5 允许恢复/添加用户的描述。未知用户的停用/移除幂等成功且不建号。默认角色为 normal，延续原实现保留已有 developer 的行为。首次建号设置不可用密码，可通过 SSO 登录或使用已有本地密码。

## 加密协议

按 v1.9 附录的 Bouncy Castle 1.70 示例实现：

- 密钥曲线为 `sm2p256v1`。平台/应用公钥支持 URL-safe Base64 编码的 X.509 SPKI；应用私钥支持 URL-safe Base64 编码的 PKCS#8。也支持相应 PEM，以及旧配置的原始十六进制密钥。
- 密文为 Base64 编码的 SM2 C1C2C3，C1 使用带 `04` 前缀的未压缩曲线点。补充校验 gmssl 未核对的 C3 完整性，并使用 `secrets` 提供随机数。
- 签名为 Base64 编码的 DER SM3withSM2。签名对象是 **Base64 解码后的密文字节**，不是 Base64 字符串。
- 入站使用 `eywa-signature` 请求头，请求体可以直接是 Base64 密文；兼容 JSON 字符串及旧版 `{"data":"..."}` 包装。
- 响应只加密 `data` 字段，使用 `App-Signature` 响应头。加密后的 `null`、对象及列表均已验证互通。

旧客户端若签名的是 Base64 文本，必须调整为文档要求的密文字节。不能通过跳过验签兼容旧错误实现。

3.7.1 用户详情查询采用 `POST /api/security-manage-permission/v1/user/info`，`appid` 放在请求头，请求 JSON 为 `{"id":"..."}`。该接口的请求为明文、响应始终为加密，与回调 action 的 encrypt 设置独立；必须验签解密后才创建用户。非零/无效业务 code、身份不匹配、缺失有效期或错误状态均拒绝入库。

## 环境变量

| 变量 | 说明 |
|---|---|
| `PORTAL_BASE_URL` | 门户 API 基址 |
| `PORTAL_APP_ID` | 应用 ID |
| `PORTAL_USER_DETAIL_PATH` | 默认 `/api/security-manage-permission/v1/user/info` |
| `PORTAL_SSO_VALIDATE_PATH` | 默认 `/api/security-manage-permission/app/cas/serviceValidate`，网关前缀不同时覆盖 |
| `PORTAL_FRONTEND_URL` | 发起 CAS 登录及后端 302 回调使用的医保前端地址；仅被动接收前端回调时可不配置 |
| `PORTAL_CAS_LOGIN_URL` | 门户 CAS 登录服务完整地址；未配置则不自动发起门户登录 |
| `PORTAL_LOGIN_CALLBACK_URL` | 发起 CAS 登录时的 service，必须与注册 login_callback 完全一致 |
| `PORTAL_REQUEST_TIMEOUT_SECONDS` | 查询超时，默认 10 秒 |
| `PORTAL_ENCRYPT_ENABLED` | 是否启用回调加密；需与注册的 actions.encrypt 一致 |
| `PORTAL_ALLOW_PLAINTEXT` | 默认 false；仅在 DEBUG=True 时显式允许本地明文调试 |
| `PORTAL_PUBLIC_KEY` | 门户 SM2 公钥 |
| `PORTAL_APP_PUBLIC_KEY` | 应用 SM2 公钥 |
| `PORTAL_APP_PRIVATE_KEY` | 应用 SM2 私钥 |

v1.9 允许将注册的 action 配置为明文，但本实现默认拒绝未验签的权限请求。明文仅允许显式开启的开发环境；生产应设置 `PORTAL_ENCRYPT_ENABLED=true`、`PORTAL_ALLOW_PLAINTEXT=false`，并在门户同步开启所有回调的加密。

真实私钥只能通过受控环境变量注入，不得提交到 Git。测试 fixtures 中的密钥来自 v1.9 文档公开示例，仅供隔离测试，不能用于真实部署。

## 异常与发布

建号、资料/权限变更、成功审计与成功响应签名都在同一事务中；任何环节失败都会回滚。动作重复调用不会额外建号或错误恢复旧角色。上游超时、无效上游响应及数据库并发唯一约束冲突返回 HTTP 503，使门户按 3.6 的 HTTP 失败机制进行重试；参数等业务错误用非零 code 表示。不能仅返回 HTTP 200 的错误 code 来期待门户重试。

发布前重建完整后端依赖，并执行：

```bash
python manage.py migrate --plan
python manage.py migrate
```

生产须启用 `accounts.middleware.ApiAccessMiddleware`，设置 `DJANGO_DEBUG=false` 和独立随机的 `DJANGO_SECRET_KEY`；使用仓库公开的开发密钥会拒绝启动。使用外部部署 settings 时，应核对最终中间件及环境变量。

业务 `/api/` 请求统一校验 token、账号状态和门户有效期。例外为本地登录/退出、门户登录 `/api/sso/login`、空菜单健康探测 `/api/menu/all`、独立验签或校验门户 ticket 的 `/api/portal/` 和 OPTIONS。未绑定门户的本地账号仍可登录。

迁移 `0002_restore_expiration` 从历史 profile_data 恢复有效期，不覆盖已有值。异常资料会停止迁移并指出绑定主键。原代码未保存的 `expired` 无法凭空恢复；上线前必须让门户补发这些用户的修改通知或重新核对其真实有效期，不能将缺失资料直接视为无限期。

## 验证

在后端项目目录建立 Python 3.10–3.12 虚拟环境：

```bash
python -m pip install -r requirements-portal-tests.txt
python manage.py test portal_integration accounts tasks results rule_import --settings=medical_audit_project.test_settings
python manage.py makemigrations accounts portal_integration --check --dry-run --settings=medical_audit_project.test_settings
```

web-ele 前端验证，在 `medical-insurance-system-front/vue-vben-admin` 下使用锁定的 pnpm 10.22.0：

```bash
pnpm install --frozen-lockfile
pnpm run build:ele
pnpm exec vitest run --config apps/web-ele/vitest.sso.config.ts
pnpm exec playwright install chromium
pnpm exec playwright test --config apps/web-ele/playwright.sso.config.ts
```

浏览器测试模拟门户和业务 API，覆盖自动发起 CAS、回调进入任务页、认证下载、刷新保留登录态、后端交换码和无效 ticket。不能替代真实门户/MySQL/Celery/ARM64 服务器联调。已有 Chromium 可通过 `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` 指定。

测试使用独立 SQLite 与内存 Celery，不连接真实门户、生产数据库或 Redis。覆盖 8 个接口、全局/应用状态、有效期更新、登录名冲突、失败回滚、重复请求、访问拦截和历史修复；同时使用文档及独立 Java 生成的固定报文测试协议兼容性。

2026-10-02 在 macOS ARM64 / Python 3.12.14 / Django 4.2.23 上运行上述 106 项测试，全部通过；迁移检查无遗漏。另用文档指定的 Bouncy Castle 1.70 独立验证 Python 响应的签名及 `null`/列表解密，并验证 Java 生成的创建通知能进入本应用。

2026-10-09 登录桥接验证：后端完整 129 项、前端 Vitest 10 项、Playwright 浏览器 3 项全部通过；`pnpm run build:ele` 生产打包成功，迁移检查无遗漏。包含真实 Word 生成接口测试，但门户、数据源和队列仍为本地隔离测试。完整前端类型检查仍失败：相同锁文件及依赖下，改动前 90 条、改动后 87 条，没有新增诊断；其余错误涉及原有业务页和组件库，未在本次登录接入中扩改。

文档附录 1 的请求签名可以验证、响应密文可以正确解密；其响应签名与附带密文及平台公钥不匹配，Python 与 Bouncy Castle 均拒绝它。真实联调应使用门户实际发出的成对报文，不能据此关闭验签。

## 验收范围与剩余工作

- 尚无真实门户环境联调；需要注册本表中的全部回调，并验证真实密钥、路径、请求和重试行为。已有账号的历史有效期需核对。
- 文档未规定 action、应用标识、时间戳或 nonce 的签名绑定及重放校验。当前遵循文档，不擅自新增必填字段。指纹和 X-Trace-Id 仅作审计；跨动作复用合法报文的风险仍需与门户共同确定防护协议，并限制接口网络访问范围。
- 《三方应用接入说明》是阶段说明，部分章节号与 v1.9 不同；详细协议以 v1.9 为准。《角色管理与权限授权》描述 FastAPI `/v2/rbac`、accessToken 头和细粒度角色模型，与本仓库 Django API 不一致，不能直接把它当作当前医保已有接口。
- SSO 回调与 ticket 交换已实现。统一退出和 iframe 角色/用户授权页面仍需单独实现；SSO 登录与 8 个回调不等于完整统一门户接入。
- SQLite 测试不验证 MySQL 行锁、死锁与并发竞争，需在隔离的生产同版本 MySQL 中验收。
- 尚未构建 Linux ARM64 生产镜像。交接脚本引用的外部 Dockerfile、部署 settings 和 Compose 不在仓库中。原 requirements.txt 中 `tensorflow-io-gcs-filesystem==0.31.0` 没有 Python 3.12 安装包，生产完整依赖需按实际 Python 和 ARM64 环境核对。
