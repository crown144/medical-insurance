#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

CONFIG_FILE="${1:-$SCRIPT_DIR/../server-deploy.conf}"
require_file "$CONFIG_FILE"
# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${TARGET_VERSION:?server-deploy.conf 缺少 TARGET_VERSION}"
: "${PACKAGE_DIR:?server-deploy.conf 缺少 PACKAGE_DIR}"
: "${INSTALL_ROOT:?server-deploy.conf 缺少 INSTALL_ROOT}"
validate_version "$TARGET_VERSION"

for command in docker tar sha256sum curl; do
  require_cmd "$command"
done

TARGET_NO="$(release_no "$TARGET_VERSION")"
IMAGE="$PACKAGE_DIR/yibao_backend_${TARGET_VERSION}.tar"
BACKEND_ARCHIVE="$PACKAGE_DIR/260723yb-backend-deploy-${TARGET_NO}.tar.gz"
FRONTEND_ARCHIVE="$PACKAGE_DIR/260723yb-frontend-static-${TARGET_NO}.tar.gz"
CHECKSUMS="$PACKAGE_DIR/SHA256SUMS"
RELEASES_ROOT="$INSTALL_ROOT/releases"
RELEASE_DIR="$RELEASES_ROOT/$TARGET_VERSION"
CURRENT_LINK="$INSTALL_ROOT/current"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-yibao}"

require_file "$IMAGE"
require_file "$BACKEND_ARCHIVE"
require_file "$FRONTEND_ARCHIVE"
require_file "$CHECKSUMS"

log "部署前验证三包 SHA256"
(cd "$PACKAGE_DIR" && sha256sum -c SHA256SUMS)

mkdir -p "$RELEASES_ROOT" "$INSTALL_ROOT/shared"
if [[ -e "$RELEASE_DIR" ]]; then
  [[ "${FORCE:-0}" == "1" ]] || die "版本目录已存在：$RELEASE_DIR；覆盖部署请设置 FORCE=1"
  BACKUP_DIR="$RELEASE_DIR.backup.$(date '+%Y%m%d%H%M%S')"
  log "备份已有版本目录到：$BACKUP_DIR"
  mv -- "$RELEASE_DIR" "$BACKUP_DIR"
fi
mkdir -p "$RELEASE_DIR"

log "解压后端和前端部署包"
tar -xzf "$BACKEND_ARCHIVE" -C "$RELEASE_DIR"
tar -xzf "$FRONTEND_ARCHIVE" -C "$RELEASE_DIR"

require_file "$RELEASE_DIR/backend/docker-compose.yml"
require_file "$RELEASE_DIR/frontend/docker-compose.yml"
require_file "$RELEASE_DIR/frontend/dist/index.html"

if [[ -n "${SERVER_BACKEND_ENV_FILE:-}" ]]; then
  require_file "$SERVER_BACKEND_ENV_FILE"
  install -m 0600 "$SERVER_BACKEND_ENV_FILE" "$RELEASE_DIR/backend/.env"
else
  require_file "$RELEASE_DIR/backend/.env"
fi

if [[ -n "${SERVER_FRONTEND_ENV_FILE:-}" ]]; then
  require_file "$SERVER_FRONTEND_ENV_FILE"
  install -m 0600 "$SERVER_FRONTEND_ENV_FILE" "$RELEASE_DIR/frontend/.env"
else
  require_file "$RELEASE_DIR/frontend/.env"
fi

log "加载后端镜像"
docker_run load -i "$IMAGE"
docker_run image inspect "yibao_backend:$TARGET_VERSION" >/dev/null

if ! docker_run image inspect hub.geekery.cn/nginx:alpine >/dev/null 2>&1; then
  if [[ "${ALLOW_NGINX_PULL:-0}" == "1" ]]; then
    log "拉取 Nginx 镜像"
    docker_run pull hub.geekery.cn/nginx:alpine
  else
    die "服务器缺少 hub.geekery.cn/nginx:alpine；先离线导入或设置 ALLOW_NGINX_PULL=1"
  fi
fi

log "启动 backend 和 celery；backend entrypoint 会执行迁移与 collectstatic"
compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/backend/docker-compose.yml" up -d --no-build

log "等待后端接口"
BACKEND_READY=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 3 http://127.0.0.1:8018/api/menu/all >/dev/null 2>&1; then
    BACKEND_READY=1
    break
  fi
  sleep 2
done
[[ "$BACKEND_READY" == "1" ]] || {
  compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/backend/docker-compose.yml" ps
  docker_run logs --tail 100 yibao-backend || true
  die "后端在 120 秒内未就绪"
}

log "启动前端 Nginx"
compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/frontend/docker-compose.yml" up -d --no-build

FRONTEND_READY=0
for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 http://127.0.0.1:8044/ >/dev/null 2>&1; then
    FRONTEND_READY=1
    break
  fi
  sleep 2
done
[[ "$FRONTEND_READY" == "1" ]] || {
  compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/frontend/docker-compose.yml" ps
  docker_run logs --tail 100 yibao-frontend || true
  die "前端在 60 秒内未就绪"
}

ln -sfn "$RELEASE_DIR" "$CURRENT_LINK.new"
mv -Tf "$CURRENT_LINK.new" "$CURRENT_LINK"

log "部署完成：$TARGET_VERSION"
compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/backend/docker-compose.yml" ps
compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/frontend/docker-compose.yml" ps
printf '后端检查：http://127.0.0.1:8018/api/menu/all\n'
printf '前端检查：http://127.0.0.1:8044/\n'
