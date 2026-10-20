# 医保系统最新前后端离线部署使用说明

本说明适用现有 Docker 环境，沿用服务器的原镜像、Compose 项目、端口、数据库连接和数据卷。先部署后端，确认正常后再部署前端。所有命令使用 ASCII 半角符号；一条执行成功后再执行下一条，报错就停。

仓库中的 `RELEASE_COMMIT7` 是打包占位符；交付文件 `使用说明.md` 已替换为本次完整提交号的前 7 位。版本以随包 `DEPLOY_VERSION.json` 为准，不依赖服务器时间。下面的备份名不得覆盖已有同名目录。

## 交付文件与上传位置

交付目录包含：

- `backend-latest.tar.gz`：后端源码及安全启动、配置合并工具。
- `frontend-latest.tar.gz`：新版前端静态文件及 Nginx 安全配置。
- `使用说明.md`：本说明的对应提交版本。
- `DEPLOY_VERSION.json`：源码完整提交号、构建模式与版本信息。
- `SHA256SUMS`：交付文件校验值。

先把这些文件上传到同一目录。下文以 `~/uploads/insurance-latest` 为例，实际上传目录不同时只替换该路径。在上传目录执行：

```bash
cd ~/uploads/insurance-latest
```

```bash
sha256sum -c SHA256SUMS
```

所有项目应显示 `OK`；校验失败先重新上传，不继续部署。压缩包不是 Docker 镜像包，也不包含生产数据库、`.env`、`deploy_settings.py` 或实际密钥。

## 一、单独部署后端

### 1. 进入原来的部署目录

```bash
cd ~/workspace/hainan/yibao/backend
```

```bash
cd backend-1012
```

```bash
cd medical-insurance-system-backend
```

```bash
ls medical_audit_project/manage.py
```

原 `docker-compose.yml`、`.env`、生产 `deploy_settings.py` 和数据挂载继续使用。不要把 `medical_audit_project` 里面的文件解压到另一层，也不要删除该目录后再解压。

```bash
cp ~/uploads/insurance-latest/backend-latest.tar.gz .
```

### 2. 停止后端和 Celery，备份原代码

```bash
v=RELEASE_COMMIT7
```

```bash
docker-compose -p yibao-backend-1012 stop backend celery
```

若服务器只有新版 Compose 插件，上面这条命令将 `docker-compose` 换为 `docker compose`。之后的 `bash dc` 会自动选择现有命令。

先确认本版备份名未被使用：

```bash
test ! -e "../code-before-$v"
```

这条命令成功时没有输出；若失败，不继续复制，先保留并确认已有备份。

```bash
cp -a medical_audit_project "../code-before-$v"
```

这是代码和源码目录内生产配置的备份，不执行数据库命令，也不停止、删除或重建数据库和 Redis。不要使用 `down -v`。

### 3. 覆盖解压源码，合并门户配置

```bash
tar -xzf backend-latest.tar.gz
```

解压后当前目录包含：

```text
medical-insurance-system-backend/
├── docker-compose.yml       原部署文件，包内不覆盖
├── .env                     原生产环境，保留其他配置
├── deploy_settings.py       原生产文件（如原本在这一层）
├── medical_audit_project/   新源码，保留未随包覆盖的生产文件
├── dc                      原 Compose + 禁止迁移覆盖的短命令
├── setup-env.py             合并配置工具
├── portal-302.env            本次已确认的门户配置
├── compose-no-migrate.yml    跳过镜像的旧启动入口
└── DEPLOY_VERSION.json
```

```bash
python3 setup-env.py
```

工具只合并 `portal-302.env` 中的明确配置，备份原 `.env` 为 `.env.before-RELEASE_COMMIT7`。其他数据库连接、实际应用 ID、SM2 密钥、`DJANGO_SECRET_KEY`、规则导入密钥等保留，不打印秘密、不连接数据库。已有同名 `.env` 备份不会覆盖。

本次合并的配置为：

```ini
PORTAL_AUTH_MODE=existing
PORTAL_AUTO_CREATE_USERS=true
LEGACY_DATABASE_COMPATIBILITY=true
PORTAL_BASE_URL=http://10.130.76.194
PORTAL_CAS_LOGIN_URL=http://10.130.76.194/ucenter/uinfo/cas/js/login
PORTAL_FRONTEND_URL=https://10.130.76.47:8088/yibao
PORTAL_LOGIN_CALLBACK_URL="https://10.130.76.47:8088/yibao/#/auth/sso"
SSO_PORTAL_HOME_URL="http://10.130.76.194//home/#/home-page"
```

原 `backend`、`celery` 已配置 `env_file: .env`。真实 `PORTAL_APP_ID` 必须与门户 302 中的 `appid` 一致；历史应用 ID 仅作为注释参考，工具不覆盖现网值。三项 SM2 必须使用当前应用的正式配置，不能用文档示例或空值替换。验票响应缺少 `expired` 时，用户详情补查仍需要真实 SM2 密钥。

这里的“不改数据库”指不改表结构、不执行迁移、不清空数据。按照本次要求开启自动开户后，门户验票、状态和有效性通过的用户，可在现有 `auth_user`、`AccountProfile` 中建立同名 `normal` 普通账户或补齐缺失角色；新账户密码不可用、非管理员。已有密码、姓名、角色和激活状态保留，停用用户拒绝登录。不创建门户绑定、医院或新表；该模式不提供门户权限回调和撤权实时同步。

### 4. 检查并启动

```bash
bash dc config --quiet
```

```bash
bash dc up -d --no-deps --force-recreate backend celery
```

```bash
bash dc ps
```

```bash
docker logs --tail 50 yibao-backend-1012
```

```bash
docker logs --tail 50 yibao-celery-1012
```

`dc` 固定复用 `yibao-backend-1012`，同时加载 `compose-no-migrate.yml`。覆盖文件为两个服务设置 `entrypoint: []`，跳过可能自动执行迁移的镜像入口，继续运行原 Gunicorn/Celery `command`。后续更新也使用 `bash dc`，不要改回会加载旧入口的启动方法。

不运行 `manage.py migrate`、`migrate --fake`、数据库初始化或带这些步骤的旧一键脚本。原镜像若依赖入口脚本进行其他准备动作，应逐项核对，不能为解决启动问题重新启用自动迁移。

### 5. 后端验收

```bash
curl -i http://127.0.0.1:8018/api/menu/all
```

接口应能响应。HTTP 200 只证明连通，继续检查实际配置：

```bash
bash dc exec backend sh
```

```bash
python manage.py check
```

```bash
python manage.py check_portal_sso --database
```

```bash
exit
```

专项检查只读取兼容条件，不执行迁移。配置缺失、缺真实密钥、原账号表不兼容或门户不可达时，按具体错误处理，不靠执行迁移或关闭验票绕过。

## 二、单独部署前端

### 1. 进入现有 front 目录并记录项目名

```bash
cd ~/workspace/hainan/yibao/front
```

```bash
v=RELEASE_COMMIT7
```

```bash
fmt='{{ index .Config.Labels "com.docker.compose.project" }}'
```

```bash
project=$(docker inspect -f "$fmt" yibao_front_0830)
```

```bash
echo "$project"
```

项目名必须非空，且与原前端项目一致。保留这次输出，回滚时使用同一个项目名；不要随意指定新项目，避免接到另一组网络或挂载。

### 2. 解压并更新

```bash
cp ~/uploads/insurance-latest/frontend-latest.tar.gz .
```

```bash
tar -xzf frontend-latest.tar.gz
```

包内包含 `dist-RELEASE_COMMIT7/`、`security/`、`front-sec`、`apply-security.sh` 和 `DEPLOY_VERSION.json`。原前端仍挂载 `dist-1012`；新静态目录先单独解压，不直接叠加复制到旧目录。

新版 `_app.config.js` 使用相对 `/yibao-api`，静态资源基址为 `/yibao/`。不要整份复制旧运行配置回新版，以免恢复旧 IP 或旧地址；确有额外现网配置时核对后逐项合并，接口仍保留相对网关地址。旧配置会随整个旧目录完整备份。

```bash
bash apply-security.sh
```

脚本按顺序执行：

1. 用现有镜像检查新 Nginx 配置，执行 `nginx -t`。
2. 将旧 `dist-1012` 改名为 `dist-before-RELEASE_COMMIT7`，保留完整旧静态资源和运行配置。
3. 将 `dist-RELEASE_COMMIT7` 改名为 `dist-1012`，避免旧有敏感 chunk 继续留在在线静态目录中。
4. 使用原 Compose 项目、原静态挂载、8098 端口和网络，附加 `security/compose-security.yml` 重新创建 `yibao_front`。

出现错误立即停下，保留完整输出。**不要盲目重跑，不覆盖 `dist-before-RELEASE_COMMIT7`。** 如果错误发生在目录切换后，按下面的回滚步骤恢复，不能通过再次叠加复制解决。

后续管理新前端使用 `bash front-sec`，它会从当前容器标签读取原项目名，并带上安全配置覆盖；普通重启不会加载新增的 Compose 挂载。

## 三、页面、集成登录与安全验收

### 实际入口分别检查

- 门户实际 302 的医保入口：`https://10.130.76.47:8088/yibao/`。
- 原扫描报告使用的入口：`http://10.130.76.47:8080/yibao/`。

这是两个不同入口。新前端容器安全头可被外层代理覆盖或隐藏，因此两个入口都要验收；不能只测容器内部或只用其中一个端口证明报告已通过。原 API 网关 `/yibao-api/` 仍由外层代理转发到后端 `/api/`，本次不覆盖现有外层 TLS 和网关配置。

先在浏览器按 Ctrl+F5，确认页面、样式和图标正常，普通账号登录、任务列表和详情、规则详情、测试结果以及报告下载可用。再从已登录的门户主页点击医保图标，应经过 CAS 回调并免密进入任务执行页，刷新后保持可用。确认新增账号为普通用户，既有账户状态和角色不变。

检查版本和最终响应头：

```bash
curl -I http://127.0.0.1:8080/yibao/
```

```bash
curl -I https://10.130.76.47:8088/yibao/
```

HTTPS 命令应使用服务器信任的证书链；证书校验失败时先核对证书或浏览器实际响应，不据此判断应用不可用。最终响应预期包含 `X-Content-Type-Options: nosniff`、`X-Frame-Options: SAMEORIGIN`、`Referrer-Policy: no-referrer` 以及新的 CSP。`X-XSS-Protection` 明确为 `0`，关闭已弃用且可能引入问题的旧 XSS auditor；实际防护由文本安全渲染和 CSP 提供，不改为 `1; mode=block`。

本次安全整改包括两个 XSS 显示入口：规则详情来源按 Vue 文本渲染；规则测试 JSON 键和值按 HTML 显示上下文转义。数据库中的原规则文本和比较符保持原样，不清洗历史数据。模板样例电话已掩码，模板联系邮箱及样例外链已清理，新的前端静态目录不继承旧 chunk。

认证继续使用 Bearer token。构建依赖中的 Axios 通用 Cookie helper 可能仍被扫描器检出 `document.cookie` 字符串；字符串存在本身不能证明敏感 Cookie 泄露。结合报告精确 URL、调用链、真实 `Set-Cookie` 和外层门户 Cookie 分别确认，不能直接声称这一项已全部通过。API 地址使用相对网关，不删除真实业务联系方式或必要运行配置。

CSP 禁止内联脚本与 `eval`；样式保留 `unsafe-inline` 以兼容 Element Plus。图标已随包离线提供，不依赖公网图标 API。新策略只与本次构建配套，不能单独套到旧内联启动脚本上。门户按当前新窗口跳转验收；跨源 iframe 嵌入受 `SAMEORIGIN` 和 `frame-ancestors 'self'` 限制，若有这种新需求须单独配置。

出现 503 时保留请求路径、响应正文和后端日志，区分外层代理与门户验票失败；截图和日志中遮住真实 `ticket`、`code`、Cookie 和密钥。

## 四、回滚

### 后端回滚

在原后端部署目录执行，`v` 使用本次版本号：

```bash
v=RELEASE_COMMIT7
```

```bash
bash dc stop backend celery
```

```bash
mv medical_audit_project "../code-failed-$v"
```

```bash
cp -a "../code-before-$v" medical_audit_project
```

```bash
cp ".env.before-$v" .env
```

```bash
bash dc up -d --no-deps --force-recreate backend celery
```

保留失败版本目录，不重复运行覆盖已有 `code-failed`。此操作恢复代码与本次合并前 `.env`，不迁移或回滚数据库，不删除更新后正常产生的业务数据或 SSO 新建账号。若 `.env` 备份不存在，先核对实际备份位置，不用模板代替生产配置。

### 前端回滚

在现有 `front` 目录中，先按前端步骤重新读取并确认 `project`，`v` 仍为本次版本号：

```bash
v=RELEASE_COMMIT7
```

```bash
bash front-sec stop yibao_front
```

```bash
mv dist-1012 "dist-failed-$v"
```

```bash
mv "dist-before-$v" dist-1012
```

用**原 Compose 文件，不附加本次 security 覆盖**恢复服务，避免旧构建的内联脚本被新 CSP 拦截：

```bash
docker-compose -p "$project" -f docker-compose.yml \
  up -d --no-deps --force-recreate yibao_front
```

若服务器只有 Compose 插件，将命令开头换成 `docker compose`。如果部署脚本在目录切换前失败、`dist-before` 不存在，原目录尚在，不执行上述目录回滚；如果只完成了部分切换，先 `ls -d dist*` 确认实际状态再处理。

回滚后再次强制刷新，检查页面、普通登录、业务 API 和响应头。前端回滚恢复旧功能，也撤回本次前端安全整改，不代表旧版本符合新的扫描要求。

## 五、离线环境与构建复现

现有 `yibao:v1` 和 Nginx 镜像继续复用。包内没有完整 Python/Node 依赖或 Docker 镜像；服务器原镜像缺少新代码必需依赖时，先在联网构建环境制作与离线服务器系统、CPU 架构匹配的镜像，通过 `docker save`/`docker load` 另行传入，再部署。不要在离线服务器临时拉公网镜像或安装未知版本依赖。

从相同提交复现构建，在已备好锁文件依赖的开发环境中执行：

```bash
cd medical-insurance-system-front/vue-vben-admin
```

```bash
pnpm --filter @vben/web-ele run build:portal
```

回到仓库根目录执行：

```bash
python3 deployment/package_release.py --output /tmp/insurance-release
```

交付目录以打包脚本实际打印的位置为准。脚本应记录当前提交，写入版本元数据、替换本说明占位符并生成校验文件；不要混用不同提交的前端产物和后端源码。

本机没有 Docker/Nginx；本地源码检查、临时数据库及模拟门户浏览器测试不能替代服务器镜像启动、`nginx -t`、真实门户验票和两个外部端口的安全复扫。本次没有连接或执行服务器数据库操作。
