# 门户 302 环境配置与现有数据库兼容部署

本次使用旧库兼容登录模式：`PORTAL_AUTH_MODE=existing`、`LEGACY_DATABASE_COMPATIBILITY=true`，并按本次要求显式开启 `PORTAL_AUTO_CREATE_USERS=true`。不新增或修改表结构，不执行数据库迁移，不重置生产数据；门户验票及有效性检查通过后，允许向现有 `auth_user`、`AccountProfile` 表新增普通账号或补齐缺失角色记录。正常业务操作仍按原有权限读写业务数据。

## 已确认的入口

以下地址来自用户提供的 `302.txt` 请求记录与截图。它们替代旧部署说明中的 HTTP 8080 地址，但不能单凭两条 302 证明后端已经成功验票。

| 配置 | 当前地址 |
|---|---|
| `PORTAL_BASE_URL` | `http://10.130.76.194` |
| `PORTAL_CAS_LOGIN_URL` | `http://10.130.76.194/ucenter/uinfo/cas/js/login` |
| `PORTAL_FRONTEND_URL` | `https://10.130.76.47:8088/yibao` |
| `PORTAL_LOGIN_CALLBACK_URL` | `https://10.130.76.47:8088/yibao/#/auth/sso` |
| 任务执行页 | `https://10.130.76.47:8088/yibao/#/task/manage/execution` |
| `SSO_PORTAL_HOME_URL` | `http://10.130.76.194//home/#/home-page` |
| 票据校验路径 | `/api/security-manage-permission/app/cas/serviceValidate` |
| 浏览器 API 网关 | `/yibao-api`，转发至后端 `/api` |
| 后端监听端口 | `8018`，沿用现有部署 |

代码在 API 基址后追加完整 `/api/...` 路径，基址不能再填写 `/api/security-manage-permission`。登录回调包含 hash 路由，必须保留 `/yibao/`、HTTPS、8088 端口及 `#/auth/sso`，并与门户登记的 `login_callback` 完全相同。

历史 `jicheng` 应用 ID 为 `6E7aymY5E33X-qGK7NL6qKtn_oYNDZb0CVS7uHLx`。优先保留现网已有的实际 `PORTAL_APP_ID`；核对它与真实 302 中的 `appid` 一致后使用。不能用公共 PDF 示例 ID 替代正式应用 ID。

## 合并现有 .env

- `portal-302.env`：可用于合并的非敏感覆盖项，已写入上述地址、旧库兼容开关及本次明确开启的 `PORTAL_AUTO_CREATE_USERS=true`。
- `portal.env.example`：同一环境的注释模板，解释应用 ID、SM2 密钥和可选项。
- `frontend.env.example`：`/yibao/` 静态资源路径、hash 路由和 `/yibao-api` 网关构建配置。
- `compose-no-migrate.yml`：在原 Compose 上禁用镜像启动入口，避免旧入口自动迁移。

服务器确认的后端目录为：

```text
~/workspace/hainan/yibao/backend/backend-1012/medical-insurance-system-backend
```

配置位于该目录现有 `.env` 中。先备份，再将 `portal-302.env` 的有效键值逐项合并进去：同名键替换旧值，不能保留多条互相冲突的赋值。不要把 overlay 当完整 `.env` 覆盖生产文件，不要直接使用 `cp portal-302.env .env`。原数据库配置、`DJANGO_SECRET_KEY`、真实应用 ID、SM2 密钥、其他生产配置必须保留。

已核对的服务器 Compose 中，`backend` 和 `celery` 都有 `env_file: .env`，无需重复添加。Django 本身不会自动读取任意 `.env`；环境变量应由 Compose 传入。使用上述 IP 地址无需新增正式门户域名的 `extra_hosts`。现有其他 `extra_hosts` 可保留。

模板不包含空的 SM2、数据库、签名密钥或应用 ID 赋值，避免空值覆盖服务器已有配置。历史应用 ID 仅放在注释中。如果当前 `.env` 没有应用 ID，核对 302 的 `appid` 后再填写实际值。

代码已移除数据库密码、Django 签名密钥及规则导入服务 API Key 的硬编码默认值。部署时保留已有 `DB_PASSWORD`、`DJANGO_SECRET_KEY` 和 `RULE_IMPORT_LLM_API_KEY`，实际部署设置若从其他受管环境读取密钥则继续沿用。密钥不得随源码上传仓库；缺少规则导入密钥时先补齐该服务配置，再使用相关功能。

## 不改表结构的启动要求

保留原 Compose 项目 `yibao-backend-1012`、现有镜像、数据库连接和数据卷。不要执行 `manage.py migrate`、`migrate --fake`、数据库初始化、`docker-compose down -v`，也不要运行包含迁移步骤的旧“一键更新”脚本。

旧镜像的入口脚本可能在启动时自动迁移。本次提供的 `compose-no-migrate.yml` 为 `backend` 和 `celery` 设置 `entrypoint: []`，跳过镜像入口，继续使用原配置已经明确指定的 Gunicorn/Celery `command`。原 `working_dir`、环境变量、镜像、数据挂载和网络配置保持不变。若服务器原 `command` 依赖入口脚本中的其他准备动作，先将必要动作单独检查和保留，不能重新启用自动迁移。

在现有部署目录逐条执行，先检查合并后的配置可解析，再启动：

```bash
cp -an docker-compose.yml docker-compose.yml.before-302
```

```bash
cp medical_audit_project/portal_integration/deploy/compose-no-migrate.yml .
```

```bash
docker-compose -p yibao-backend-1012 \
  -f docker-compose.yml -f compose-no-migrate.yml \
  config --quiet
```

```bash
docker-compose -p yibao-backend-1012 \
  -f docker-compose.yml -f compose-no-migrate.yml \
  up -d --no-build --no-deps --force-recreate backend celery
```

后续重新创建容器也必须带上 `-f compose-no-migrate.yml`；或者将 `entrypoint: []` 分别合并进原 `backend`、`celery` 服务以长期保留。普通 `docker restart` 不会加载新的 `.env`。不要将这份仅含两服务入口覆盖的文件当作完整 Compose 使用。

在当前运行的后端容器及其实际 `deploy_settings` 中检查：

```bash
python manage.py check
python manage.py check_portal_sso --database
```

`check_portal_sso --database` 只检查数据库兼容条件，不执行迁移。已有账号模式不以门户新增表的迁移状态作为验收要求；仍须满足现有账号表结构、账号映射、地址和票据校验条件。所有开发验证只使用本地临时数据库，不能连接服务器数据库运行测试。

## 已有账号模式的边界

门户票据仍须由真实门户校验，并通过有效期、状态及应用身份检查，不能信任浏览器自行提交的账号名称或跳过验票。`PORTAL_AUTO_CREATE_USERS` 默认是 `false`，只在 `PORTAL_AUTH_MODE=existing` 生效；本次 `portal-302.env` 按用户要求明确设为 `true`。

开启自动开户时，校验通过的门户登录名在本地不存在，就在现有 `auth_user`、`AccountProfile` 表建立同名普通账号：角色为 `normal`，密码不可用，`is_staff`、`is_superuser` 均为 `false`。不创建门户绑定表、医院或其他同步数据，不赋予管理员权限。既有用户缺少 `AccountProfile` 时，只补一条 `normal` 角色记录。

已有用户的密码、姓名、已有角色及激活状态保留；停用账号仍拒绝登录，不会借 SSO 恢复或提权。关闭该开关后，未知登录名和缺少角色记录的用户仍被拒绝，不自动写入账号数据。启用自动开户会写入用户数据，但不改变任何表结构；与数据库迁移是两件事。

此模式不支持门户用户/权限同步回调，也不提供门户撤权的实时同步。如果需要这些能力，应另行制定数据库变更和正式迁移方案，不能在当前“不改表结构”的部署中启用。

SM2 不能用假密钥补齐：`PORTAL_PUBLIC_KEY` 是正式门户公钥，`PORTAL_APP_PUBLIC_KEY` 是当前应用在门户登记的公钥，`PORTAL_APP_PRIVATE_KEY` 必须与其配对。保留服务器真实密钥，不使用文档示例值，不将密钥写入 Git 或发到聊天中。

即使使用已有账号模式，若 `serviceValidate` 未返回 `expired`，仍需加密调用用户详情接口补查；这条路径必须具备上述三项真实 SM2 密钥。只关闭回调加密无法代替这些密钥。登录 302 记录没有确认登出 URL，因此本次不填写或猜测统一登出相关地址。

旧规则库没有 `is_deleted` 列时，兼容模式的删除请求返回明确的 HTTP 409，规则数据保留；可继续使用停用操作，不退化为物理删除。

## 前端和网关

前端构建使用 `/yibao/` 基址和 hash 路由。现网 `_app.config.js` 的 API 入口应为 `/yibao-api`；更新静态文件时保留并核对现有运行配置，不能把浏览器网关改成内部 Django 的 `/api`。

网关应将 `/yibao-api/` 转发到后端 `/api/`。以下只表示宿主机 Nginx 的映射方式，合并到现有 HTTPS 8088 的 server 中，不能用它覆盖整份配置：

```nginx
location /yibao-api/ {
    proxy_pass http://127.0.0.1:8018/api/;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

若 Nginx 运行在容器内，`127.0.0.1` 是 Nginx 容器自身，必须沿用它实际能访问的后端地址。保留现有 `/yibao/` 静态目录配置、TLS 证书和其他服务代理。

## 门户图标验收

门户首页图标按 v1.9 3.3.4 打开应用登记 URL，无需假设它一开始就附带票据。应用发现无本地登录态后跳转 CAS；门户已有会话时，CAS 回到已登记的 `#/auth/sso` 页面并附带 `ticket`、`appid`、`callback`。后端验票并匹配已有账号，或在开启自动开户时建立普通账号，再建立本地登录态并进入任务执行页。

1. 在能访问内网的浏览器先登录门户，再点击医保系统图标。
2. 应到达 `https://10.130.76.47:8088/yibao/#/task/manage/execution`，不再输入医保账号密码。
3. 检查任务 API 返回业务 JSON，刷新任务页后仍可使用；再验证原本的普通账号登录和任务详情功能。
4. 用经门户成功认证、但本地尚无同名账号的身份验证自动开户：应建立 `normal` 非管理员账号，密码不可用；失败、过期或停用身份应被拒绝。已有账号的密码、姓名、角色和激活状态应保持原值。
5. 出现 503 时同时看 `/yibao-api/...` 的响应正文和后端日志，区分网关不可达、门户验票、密钥/过期时间补查等原因。记录时遮住真实 `ticket`、`code`、Cookie 和密钥。

配置检查、本地测试及门户两条 302 都不能替代最终现网验收。本次开发验证没有连接或修改服务器数据库；现网启用自动开户后的 SSO 登录会按上述规则写入现有用户表。
