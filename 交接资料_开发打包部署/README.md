# 医保系统：从开发修改到三包交付、服务器部署完整交接教程

## 1. 文档目的

本文用于把当前医保系统完整交接给下一位开发或运维人员，覆盖以下全过程：

1. 找到正确的开发源码并进行修改；
2. 判断后端应使用增量镜像还是完整 Docker 构建；
3. 构建前端并同步 Nginx 静态目录；
4. 生成后端镜像包、后端部署包、前端包；
5. 生成并验证 SHA256；
6. 将三包传输到目标服务器；
7. 使用版本目录部署 backend、celery 和 frontend；
8. 验证服务、查看日志和执行应用回退。

本文对应当前项目目录：

```text
/home/ubuntu/yibao/260723yb
```

当前已经发布到：

```text
260723-22
```

下一版示例使用：

```text
上一版：260723-22
新版本：260723-23
```

## 2. 交接目录内容

```text
交接资料_开发打包部署/
├── README.md
├── 发布交接记录模板.md
├── release.conf.example
├── server-deploy.conf.example
└── scripts/
    ├── lib.sh
    ├── 01_build_frontend.sh
    ├── 02_build_backend_incremental.sh
    ├── 02_build_backend_full.sh
    ├── 03_package_release.sh
    ├── 04_verify_release.sh
    ├── build_release.sh
    ├── server_preflight.sh
    ├── deploy_release.sh
    └── rollback_release.sh
```

脚本职责：

| 脚本 | 运行位置 | 作用 |
|---|---|---|
| `01_build_frontend.sh` | 开发机 | 类型检查、生产构建并同步 `frontend/dist` |
| `02_build_backend_incremental.sh` | 开发机 | 基于上一版镜像追加最新 `/app` 层 |
| `02_build_backend_full.sh` | 开发机 | 完整执行 Docker build 和 docker save |
| `03_package_release.sh` | 开发机 | 生成后端部署包、前端包和 SHA256 |
| `04_verify_release.sh` | 开发机/服务器 | 校验三包、版本标签和包内结构 |
| `build_release.sh` | 开发机 | 一键执行构建、三包和校验 |
| `server_preflight.sh` | 服务器 | 检查依赖、空间、镜像、Redis、端口和三包 |
| `deploy_release.sh` | 服务器 | 校验、解包、加载镜像、启动和探活 |
| `rollback_release.sh` | 服务器 | 回切到已经保留的旧应用版本 |

## 3. 当前系统目录与源码边界

### 3.1 后端开发源码

```text
/home/ubuntu/yibao/260723yb/backend/app
```

常见修改范围：

```text
backend/app/rules/          规则管理和规则转换
backend/app/engine/         审核执行引擎
backend/app/tasks/          审核任务
backend/app/sql_analysis/   SQL 类规则
backend/app/cases/          病历缓存
backend/app/results/        审核结果
```

后端部署设置：

```text
backend/deploy_settings.py
```

后端容器构建文件：

```text
backend/Dockerfile
backend/docker-entrypoint.sh
backend/requirements-yibao.txt
backend/docker-compose.yml
```

### 3.2 前端开发源码

当前实际使用 Element Plus 版本：

```text
frontend/vue-vben-admin/apps/web-ele/src
```

主要目录：

```text
src/views/                  页面
src/router/routes/modules/  侧边栏和路由
src/api/                    API 请求和类型
src/locales/                国际化文案
```

生产构建首先输出到：

```text
frontend/vue-vben-admin/apps/web-ele/dist
```

Nginx 实际挂载：

```text
frontend/dist
```

因此每次构建后必须把前一个目录同步到后一个目录。交接脚本已经自动完成同步。

### 3.3 不要修改错误副本

项目中存在：

```text
source/medical-insurance-system-front
source/medical-insurance-system-backend
```

它们不是当前打包脚本使用的开发和部署目录。当前版本应修改根目录下的 `frontend` 和 `backend`，否则可能出现“代码改了但三包没有变化”。

## 4. 开发机准备

### 4.1 必要命令

增量打包需要：

```text
bash、tar、gzip、rsync、jq、sha256sum、awk、stat、mktemp、sed
```

前端需要：

```text
Node.js >= 20.12
pnpm 10.x
```

完整后端构建还需要：

```text
Docker
Docker Compose v2
能够访问 Python/apt 镜像源，或本机已有构建缓存
```

检查示例：

```bash
node --version
pnpm --version
jq --version
rsync --version
docker --version
docker compose version
```

### 4.2 磁盘空间

当前后端镜像 TAR 约 4 GB。增量构建会同时保留：

- 上一版镜像包；
- 临时解包目录；
- 新应用层；
- 新版本镜像包。

建议开发机至少预留 15 GB 可用空间：

```bash
df -h /home/ubuntu /tmp
```

## 5. 开发修改标准流程

### 5.1 修改前

1. 确认当前生产版本和上一版部署包存在；
2. 建议创建 Git 分支或保存变更清单；
3. 记录本次修改涉及前端、后端、数据库迁移还是依赖；
4. 不要把 `.env`、数据库密码或 API Key 提交到代码仓库。

建议记录：

```text
版本：260723-23
上一版：260723-22
修改内容：
- ...
数据库迁移：有/无
后端构建方式：incremental/full
前端包方式：full/deploy-only
```

### 5.2 修改后端

普通 Python 业务代码修改位于 `backend/app`。

若修改 Django Model，需要生成和检查迁移：

```bash
cd /home/ubuntu/yibao/260723yb/backend/app
python manage.py makemigrations
python manage.py migrate --plan
```

开发机没有 Django 环境时，应在当前开发容器或标准开发环境执行，不能因为本机缺少依赖就跳过迁移文件。

建议至少运行相关测试：

```bash
python manage.py test
```

若全量测试成本过高，至少执行本次修改模块的测试，并保存测试结果。

### 5.3 修改前端

只修改：

```text
frontend/vue-vben-admin/apps/web-ele/src
```

修改后至少执行：

```bash
cd /home/ubuntu/yibao/260723yb/frontend/vue-vben-admin
pnpm -F @vben/web-ele run typecheck
pnpm -F @vben/web-ele run build
```

不要手工编辑 `frontend/dist/js/*.js`。这些是带哈希的构建产物，应由 Vite 重新生成。

## 6. 如何选择后端构建方式

这是交接中最重要的判断之一。

### 6.1 使用 incremental 的情况

仅修改以下内容时，可以使用增量镜像：

```text
backend/app/**
backend/deploy_settings.py
```

例如：

- Django View、Serializer、Model 和迁移；
- 审核规则执行逻辑；
- SQL 类规则逻辑；
- Celery 任务；
- 配置字段，但不增加新的 Python/系统依赖。

增量脚本基于上一版镜像，追加一个包含最新 `/app` 的新层。速度较快，但镜像会随着版本逐步增大。

### 6.2 必须使用 full 的情况

修改以下任一文件或依赖时，必须完整构建：

```text
backend/requirements-yibao.txt
backend/Dockerfile
backend/docker-entrypoint.sh
系统 apt 依赖
Python 运行版本
```

原因：当前增量脚本只覆盖 `/app`，不会重新安装依赖，也不会替换 `/usr/local/bin/docker-entrypoint.sh`。

### 6.3 定期完整构建

即使长期只有业务代码修改，也建议每若干版本完整构建一次，减少历史层累积，并确认 Dockerfile 能从头构建成功。

## 7. 版本号规则

当前格式：

```text
260723-22
```

前半段是项目版本前缀，最后一段是发布序号。新版本一般递增最后的序号：

```text
260723-22 -> 260723-23
```

目标目录：

```text
部署包/260723-23
```

目标三包：

```text
yibao_backend_260723-23.tar
260723yb-backend-deploy-23.tar.gz
260723yb-frontend-static-23.tar.gz
```

镜像标签：

```text
yibao_backend:260723-23
```

不要复用旧版本号覆盖已经发给服务器的包。确需重打同一版本时，必须通知接收方重新校验 SHA256。

## 8. 配置开发机一键打包

进入交接目录：

```bash
cd /home/ubuntu/yibao/260723yb/交接资料_开发打包部署
```

复制配置：

```bash
cp release.conf.example release.conf
```

编辑 `release.conf`：

```bash
PROJECT_ROOT=/home/ubuntu/yibao/260723yb
BASE_VERSION=260723-22
TARGET_VERSION=260723-23
BACKEND_BUILD_MODE=incremental
FRONTEND_PACKAGE_MODE=full
INCLUDE_BACKEND_ENV=1
INCLUDE_FRONTEND_ENV=1
FORCE=0
DOCKER_USE_SUDO=0
```

关键配置：

| 配置 | 可选值 | 说明 |
|---|---|---|
| `BACKEND_BUILD_MODE` | `incremental` / `full` | 后端镜像构建方式 |
| `FRONTEND_PACKAGE_MODE` | `full` / `deploy-only` | 完整前端工程包或精简部署包 |
| `INCLUDE_BACKEND_ENV` | `1` / `0` | 是否把开发目录的后端 `.env` 打入包 |
| `INCLUDE_FRONTEND_ENV` | `1` / `0` | 精简前端包是否带 `.env` |
| `FORCE` | `0` / `1` | 是否允许重打已有目标版本 |
| `DOCKER_USE_SUDO` | `0` / `1` | Docker 是否需要 sudo |

## 9. 一键生成三包

先赋予脚本执行权限；首次交接时执行一次即可：

```bash
chmod 0755 scripts/*.sh
```

执行：

```bash
./scripts/build_release.sh ./release.conf
```

脚本依次完成：

1. 前端类型检查；
2. 前端生产构建；
3. 使用 `rsync --delete` 精确同步到 `frontend/dist`；
4. 增量或完整构建后端镜像；
5. 生成后端部署包；
6. 生成前端包；
7. 生成 `SHA256SUMS`；
8. 重新读取三包并校验；
9. 检查镜像标签、Compose 标签和前端必要文件。

成功后输出：

```text
/home/ubuntu/yibao/260723yb/部署包/260723-23/
```

## 10. 分步执行方式

排查问题或只重做某一步时，可以分开执行。

### 10.1 构建前端

```bash
./scripts/01_build_frontend.sh /home/ubuntu/yibao/260723yb
```

### 10.2 增量后端镜像

```bash
./scripts/02_build_backend_incremental.sh \
  260723-22 \
  260723-23 \
  /home/ubuntu/yibao/260723yb
```

### 10.3 完整后端镜像

```bash
./scripts/02_build_backend_full.sh \
  260723-23 \
  /home/ubuntu/yibao/260723yb
```

### 10.4 生成另外两包和 SHA256

```bash
TARGET_VERSION=260723-23 \
FRONTEND_PACKAGE_MODE=full \
INCLUDE_BACKEND_ENV=1 \
INCLUDE_FRONTEND_ENV=1 \
./scripts/03_package_release.sh \
  260723-23 \
  /home/ubuntu/yibao/260723yb
```

### 10.5 校验

```bash
./scripts/04_verify_release.sh \
  260723-23 \
  /home/ubuntu/yibao/260723yb
```

## 11. 三包的具体内容

### 11.1 后端镜像包

```text
yibao_backend_260723-23.tar
```

用途：

```bash
docker load -i yibao_backend_260723-23.tar
```

### 11.2 后端部署包

```text
260723yb-backend-deploy-23.tar.gz
```

包含：

```text
backend/docker-compose.yml
backend/.env
backend/.env.example
```

如果 `INCLUDE_BACKEND_ENV=0`，则不会包含 `backend/.env`，目标服务器必须提供共享环境文件。

打包脚本使用临时 staging 修改 Compose 标签，不要求为了打包而手工修改开发目录中的 Compose。

### 11.3 前端包

```text
260723yb-frontend-static-23.tar.gz
```

`FRONTEND_PACKAGE_MODE=full`：

- 与当前 v22 交付口径一致；
- 包含整个 `frontend`；
- 含源码、依赖目录和静态产物；
- 体积较大，便于完整交接。

`FRONTEND_PACKAGE_MODE=deploy-only`：

- 只包含 `frontend/dist`、`frontend/nginx`、Compose 和环境文件；
- 体积小，适合纯服务器部署；
- 源码应通过代码仓库或本交接目录另行交接。

注意：`full` 模式会按当前目录原样打包，包括 `frontend/.env`。如果不希望分发环境配置，应先采用精简模式并设置 `INCLUDE_FRONTEND_ENV=0`，或在独立安全渠道交付服务器环境文件。

## 12. 开发机打包完成后的检查

进入新版本目录：

```bash
cd /home/ubuntu/yibao/260723yb/部署包/260723-23
```

检查文件：

```bash
ls -lh
```

检查 SHA256：

```bash
sha256sum -c SHA256SUMS
```

应全部显示：

```text
OK
```

检查镜像标签：

```bash
tar -xOf yibao_backend_260723-23.tar repositories
```

检查 Compose：

```bash
tar -xOzf 260723yb-backend-deploy-23.tar.gz \
  backend/docker-compose.yml | rg "image: yibao_backend"
```

应有两行：

```text
image: yibao_backend:260723-23
```

## 13. 将三包传输到服务器

建议传输整个版本目录，包括 `SHA256SUMS`：

```bash
scp -r \
  /home/ubuntu/yibao/260723yb/部署包/260723-23 \
  deploy-user@目标服务器:/tmp/yibao-release-260723-23
```

大文件也可使用支持断点续传的 rsync：

```bash
rsync -avP \
  /home/ubuntu/yibao/260723yb/部署包/260723-23/ \
  deploy-user@目标服务器:/tmp/yibao-release-260723-23/
```

不要只传三个包而遗漏 `SHA256SUMS`。

## 14. 目标服务器前置条件

服务器必须具备：

```text
Linux
Docker
Docker Compose v2
tar、gzip、sha256sum、curl、jq
```

端口和外部依赖：

| 项目 | 默认值 | 说明 |
|---|---:|---|
| 前端 | 8044 | Nginx 监听 |
| 后端 | 8018 | Gunicorn 监听 |
| Redis | 6379 | 当前 Compose 不包含 Redis |
| 业务数据库 | 由 `.env` 决定 | 必须可连接 |
| 源数据数据库 | 由 `.env` 决定 | 病历抽取依赖 |
| 规则语义模型 | 当前代码配置端口 54320 | 使用相关规则时需要 |

当前三包不包含 Nginx 镜像：

```text
hub.geekery.cn/nginx:alpine
```

目标服务器必须已经有该镜像，或者允许访问镜像仓库。完全离线部署时，应提前在有镜像的机器执行：

```bash
docker save -o yibao_nginx_alpine.tar hub.geekery.cn/nginx:alpine
```

然后在目标服务器加载：

```bash
docker load -i yibao_nginx_alpine.tar
```

该 Nginx 镜像是服务器基础依赖，目前不计入“三包”。

## 15. 数据库和环境配置准备

### 15.1 安装目录权限

推荐让专用部署账号拥有安装目录。例如部署账号为 `deploy-user`：

```bash
sudo mkdir -p /opt/yibao/releases /opt/yibao/shared
sudo chown -R deploy-user:deploy-user /opt/yibao
sudo chmod 0750 /opt/yibao /opt/yibao/releases /opt/yibao/shared
```

之后用该账号运行部署脚本。若不调整目录所有者，也可以用 root 执行部署脚本；此时配置中的 `DOCKER_USE_SUDO` 保持 `0`。

不要出现“普通账号无权写 `/opt/yibao`，同时脚本又没有 sudo”的混合状态。

### 15.2 数据库备份

后端容器启动时会自动执行：

```text
python manage.py migrate --noinput
python manage.py ensure_audit_users
python manage.py collectstatic --noinput
```

因此包含数据库迁移的版本部署前必须备份数据库。应用回退不会自动回滚数据库迁移。

### 15.3 推荐使用服务器共享环境文件

建议：

```text
/opt/yibao/shared/backend.env
/opt/yibao/shared/frontend.env
```

创建目录：

```bash
sudo mkdir -p /opt/yibao/shared
sudo chmod 0750 /opt/yibao/shared
```

将服务器真实环境配置写入上述文件，并限制权限：

```bash
sudo chown deploy-user:deploy-user /opt/yibao/shared/backend.env /opt/yibao/shared/frontend.env
sudo chmod 0600 /opt/yibao/shared/backend.env
sudo chmod 0600 /opt/yibao/shared/frontend.env
```

不要在本文、聊天记录或公共代码仓库中记录真实密码。

## 16. 配置服务器部署脚本

把整个 `交接资料_开发打包部署` 目录一并复制到服务器，或至少复制 `scripts` 和配置模板。

进入交接目录：

```bash
cd 交接资料_开发打包部署
cp server-deploy.conf.example server-deploy.conf
```

编辑：

```bash
TARGET_VERSION=260723-23
PACKAGE_DIR=/tmp/yibao-release-260723-23
INSTALL_ROOT=/opt/yibao
COMPOSE_PROJECT_NAME=yibao
SERVER_BACKEND_ENV_FILE=/opt/yibao/shared/backend.env
SERVER_FRONTEND_ENV_FILE=/opt/yibao/shared/frontend.env
ALLOW_NGINX_PULL=0
DOCKER_USE_SUDO=0
FORCE=0
```

如果 Docker 必须通过 sudo 使用：

```bash
DOCKER_USE_SUDO=1
```

## 17. 一键部署到服务器

建议先执行服务器预检查：

```bash
./scripts/server_preflight.sh ./server-deploy.conf
```

确认检查结果后再部署：

```bash
chmod 0755 scripts/*.sh
./scripts/deploy_release.sh ./server-deploy.conf
```

脚本会执行：

1. 重新验证三包 SHA256；
2. 创建 `/opt/yibao/releases/260723-23`；
3. 解压后端和前端包；
4. 用服务器共享 `.env` 覆盖包内环境文件；
5. 执行 `docker load`；
6. 确认后端目标镜像存在；
7. 确认 Nginx 镜像存在，或按配置拉取；
8. 使用固定 Compose 项目名 `yibao` 启动 backend 和 celery；
9. 等待后端 `/api/menu/all` 返回成功；
10. 启动前端 Nginx；
11. 等待 `http://127.0.0.1:8044/` 返回成功；
12. 将 `/opt/yibao/current` 切换到新版本目录。

脚本不会使用 `docker compose build`，因为后端部署包没有完整构建上下文；后端镜像必须先成功加载。

## 18. 手工部署方式

无法使用脚本时，可以按以下顺序手工执行。

### 18.1 校验

```bash
cd /tmp/yibao-release-260723-23
sha256sum -c SHA256SUMS
```

### 18.2 解压

```bash
sudo mkdir -p /opt/yibao/releases/260723-23
sudo tar -xzf 260723yb-backend-deploy-23.tar.gz \
  -C /opt/yibao/releases/260723-23
sudo tar -xzf 260723yb-frontend-static-23.tar.gz \
  -C /opt/yibao/releases/260723-23
```

### 18.3 放置服务器环境文件

```bash
sudo install -m 0600 /opt/yibao/shared/backend.env \
  /opt/yibao/releases/260723-23/backend/.env
sudo install -m 0600 /opt/yibao/shared/frontend.env \
  /opt/yibao/releases/260723-23/frontend/.env
```

### 18.4 加载后端镜像

```bash
docker load -i yibao_backend_260723-23.tar
docker image inspect yibao_backend:260723-23
```

### 18.5 启动后端和 Celery

```bash
docker compose \
  -p yibao \
  -f /opt/yibao/releases/260723-23/backend/docker-compose.yml \
  up -d --no-build
```

### 18.6 检查后端

```bash
curl -fsS http://127.0.0.1:8018/api/menu/all
docker logs --tail 200 yibao-backend
docker logs --tail 200 yibao-celery
```

### 18.7 启动前端

```bash
docker compose \
  -p yibao \
  -f /opt/yibao/releases/260723-23/frontend/docker-compose.yml \
  up -d --no-build
```

### 18.8 检查前端

```bash
curl -I http://127.0.0.1:8044/
docker logs --tail 100 yibao-frontend
```

## 19. 部署后验收

### 19.1 容器状态

```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
```

应至少看到：

```text
yibao-backend
yibao-celery
yibao-frontend
```

### 19.2 后端接口

```bash
curl -fsS http://127.0.0.1:8018/api/menu/all
```

### 19.3 前端页面

```bash
curl -I http://127.0.0.1:8044/
```

浏览器访问服务器对应地址，并完成：

1. 登录；
2. 检查侧边栏；
3. 打开本次修改页面；
4. 执行一条低风险测试任务；
5. 检查 Celery 是否收到任务；
6. 检查结果保存和下载；
7. 检查浏览器控制台和 Network 是否有 404/500。

### 19.4 日志

```bash
docker logs --tail 200 yibao-backend
docker logs --tail 200 yibao-celery
docker logs --tail 100 yibao-frontend
```

持续查看：

```bash
docker logs -f yibao-backend
docker logs -f yibao-celery
```

## 20. 应用回退

前提：旧版本目录仍存在，例如：

```text
/opt/yibao/releases/260723-22
```

执行：

```bash
COMPOSE_PROJECT_NAME=yibao \
DOCKER_USE_SUDO=0 \
./scripts/rollback_release.sh 260723-22 /opt/yibao
```

回退脚本会用旧版本 Compose 重新启动容器，并把 `/opt/yibao/current` 指回旧版本。

重要：

- 应用代码和容器可以回切；
- 数据库迁移不会自动回滚；
- 若新版本迁移与旧代码不兼容，必须使用部署前数据库备份或经过审核的反向迁移；
- 不要未经确认直接执行数据库回滚命令。

## 21. 重打同一版本

默认脚本检测到目标文件或版本目录存在时会停止，防止覆盖已经交付的包。

确需重打：

```bash
FORCE=1
```

或在配置中：

```bash
FORCE=1
```

重打后必须：

1. 重新生成 `SHA256SUMS`；
2. 通知接收方旧包作废；
3. 重新上传全部三包和校验文件；
4. 服务器重新运行 `sha256sum -c SHA256SUMS`。

## 22. 常见问题

### 22.1 前端修改没有生效

检查：

```text
是否修改了 apps/web-ele/src，而不是 source 副本
是否执行了 web-ele build
是否把 apps/web-ele/dist 同步到 frontend/dist
前端包中是否是新 index.html
浏览器是否仍缓存旧 index.html
```

使用交接脚本会通过带哈希的新资源文件降低缓存影响。

### 22.2 后端代码没有生效

检查：

```bash
docker image inspect yibao_backend:260723-23
docker inspect yibao-backend --format '{{.Config.Image}}'
```

确认 Compose 包中的标签和实际容器镜像一致。

### 22.3 增量镜像缺少新依赖

原因：修改了 `requirements-yibao.txt`，却使用了 incremental。

处理：改用：

```text
BACKEND_BUILD_MODE=full
```

重新生成新版本镜像。

### 22.4 Compose 尝试 build 但缺少上下文

部署必须使用：

```bash
docker compose up -d --no-build
```

并先完成 `docker load`。

### 22.5 后端一直等待数据库

容器 entrypoint 会等待 `DB_HOST:DB_PORT`。检查：

```bash
docker logs --tail 200 yibao-backend
```

核对服务器 `.env`、网络、数据库地址和防火墙。

### 22.6 Celery 反复重启

优先检查 Redis：

```bash
docker logs --tail 200 yibao-celery
```

当前 Compose 不包含 Redis，默认依赖服务器 `127.0.0.1:6379`。

### 22.7 前端容器无法启动

确认目标服务器存在：

```bash
docker image inspect hub.geekery.cn/nginx:alpine
```

若服务器完全离线，需要提前单独导入该基础镜像。

### 22.8 容器显示 Up，但页面不可用

当前 Compose 没有 Docker healthcheck，`Up` 只表示进程没有退出。必须同时检查：

```bash
curl -fsS http://127.0.0.1:8018/api/menu/all
curl -I http://127.0.0.1:8044/
```

## 23. 安全注意事项

1. `.env` 包含数据库、源数据库和其他连接配置，不能公开分发；
2. 三包和 `SHA256SUMS` 应通过受控渠道传输；
3. 服务器共享环境文件权限建议为 `0600`；
4. 不要把真实密码写进本教程、示例配置或 Git；
5. 后端规则代码使用动态执行机制，新增规则必须经过代码审查；
6. 部署前应确认目标版本来源、修改清单和 SHA256；
7. 数据库迁移前必须确认备份和回退方案；
8. 不要用 `docker compose down -v`，该命令会删除命名卷；
9. 不要删除 `/opt/yibao/releases` 中仍可能需要回退的旧版本；
10. 不要清理后端镜像，直到新版本验收完成。

## 24. 发布记录建议

每次发布至少保存：

```text
目标版本
上一版本
修改内容
修改文件
数据库迁移清单
后端构建方式
前端包方式
三包文件名和 SHA256
开发机验证结果
服务器部署时间
服务器验收结果
执行人和复核人
回退版本
```

## 25. 发布前最终检查清单

### 开发与测试

- [ ] 修改的是根目录 `backend` / `frontend`，不是 `source` 副本。
- [ ] 已记录修改内容和影响范围。
- [ ] 后端相关测试通过。
- [ ] 数据库迁移文件已生成并审核。
- [ ] 前端类型检查通过。
- [ ] 前端生产构建成功。
- [ ] `frontend/dist` 已同步。

### 版本与构建

- [ ] 上一版镜像 TAR 存在。
- [ ] 新版本号未与已交付版本冲突。
- [ ] 已正确选择 incremental 或 full。
- [ ] 依赖或 Dockerfile 改动时没有误用 incremental。
- [ ] 前端包模式符合本次交付要求。

### 三包

- [ ] 后端镜像包生成成功。
- [ ] 后端部署包生成成功。
- [ ] 前端包生成成功。
- [ ] `SHA256SUMS` 生成成功。
- [ ] `04_verify_release.sh` 校验通过。
- [ ] 镜像标签和 Compose 标签均为目标版本。

### 服务器

- [ ] 数据库已备份。
- [ ] 服务器共享 `.env` 已核对。
- [ ] Redis 可用。
- [ ] Nginx 基础镜像可用。
- [ ] 磁盘空间足够。
- [ ] 三包传输后 SHA256 校验通过。
- [ ] backend、celery、frontend 均启动。
- [ ] 后端和前端探活成功。
- [ ] 本次功能完成业务验收。
- [ ] 旧版本目录和镜像仍保留，可用于回退。

## 26. 当前 v22 实例

当前已经生成的交付目录：

```text
/home/ubuntu/yibao/260723yb/部署包/260723-22
```

包含：

```text
yibao_backend_260723-22.tar
260723yb-backend-deploy-22.tar.gz
260723yb-frontend-static-22.tar.gz
SHA256SUMS
```

该版本已经完成：

- 三包 SHA256 校验；
- 后端镜像标签检查；
- backend、celery Compose 标签检查；
- 前端构建产物抽检。

后续发布可直接复制 `release.conf.example`，将上一版设为 `260723-22`，目标版设为 `260723-23`，然后使用 `build_release.sh`。
