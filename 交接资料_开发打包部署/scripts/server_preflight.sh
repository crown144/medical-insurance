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

for command in docker tar gzip sha256sum curl df jq; do
  require_cmd "$command"
done

docker_run version >/dev/null
compose_run version >/dev/null

TARGET_NO="$(release_no "$TARGET_VERSION")"
for file in \
  "$PACKAGE_DIR/yibao_backend_${TARGET_VERSION}.tar" \
  "$PACKAGE_DIR/260723yb-backend-deploy-${TARGET_NO}.tar.gz" \
  "$PACKAGE_DIR/260723yb-frontend-static-${TARGET_NO}.tar.gz" \
  "$PACKAGE_DIR/SHA256SUMS"; do
  require_file "$file"
done

if [[ -n "${SERVER_BACKEND_ENV_FILE:-}" ]]; then
  require_file "$SERVER_BACKEND_ENV_FILE"
fi
if [[ -n "${SERVER_FRONTEND_ENV_FILE:-}" ]]; then
  require_file "$SERVER_FRONTEND_ENV_FILE"
fi

log "Docker 与 Compose 可用"
log "安装盘空间："
df -h "$(dirname "$INSTALL_ROOT")" 2>/dev/null || df -h /

if docker_run image inspect hub.geekery.cn/nginx:alpine >/dev/null 2>&1; then
  log "Nginx 基础镜像已存在"
else
  log "警告：Nginx 基础镜像不存在；需离线导入或设置 ALLOW_NGINX_PULL=1"
fi

if bash -c 'exec 3<>/dev/tcp/127.0.0.1/6379' >/dev/null 2>&1; then
  log "Redis 127.0.0.1:6379 可连接"
else
  log "警告：Redis 127.0.0.1:6379 当前不可连接，请核对 REDIS_URL"
fi

for port in 8018 8044; do
  if bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" >/dev/null 2>&1; then
    log "端口 $port 已被服务监听；若为旧版医保容器，这是正常现象"
  else
    log "端口 $port 当前空闲"
  fi
done

log "执行包校验"
"$SCRIPT_DIR/04_verify_release.sh" "$TARGET_VERSION" "${PROJECT_ROOT:-$(default_project_root)}" "$PACKAGE_DIR"
log "服务器部署前检查完成"
