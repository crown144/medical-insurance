#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

PROJECT_ROOT="${1:-${PROJECT_ROOT:-$(default_project_root)}}"
FRONTEND_ROOT="$PROJECT_ROOT/frontend/vue-vben-admin"
BUILD_DIST="$FRONTEND_ROOT/apps/web-ele/dist"
DEPLOY_DIST="$PROJECT_ROOT/frontend/dist"

require_cmd pnpm
require_cmd rsync
require_dir "$FRONTEND_ROOT"

if [[ "${SKIP_TYPECHECK:-0}" != "1" ]]; then
  log "执行 web-ele 类型检查"
  (cd "$FRONTEND_ROOT" && pnpm -F @vben/web-ele run typecheck)
fi

log "执行 web-ele 生产构建"
(cd "$FRONTEND_ROOT" && pnpm -F @vben/web-ele run build)

require_file "$BUILD_DIST/index.html"
mkdir -p -- "$DEPLOY_DIST"
[[ "$DEPLOY_DIST" == "$PROJECT_ROOT/frontend/dist" ]] || die "部署目录校验失败：$DEPLOY_DIST"

log "同步构建产物到 Nginx 挂载目录：$DEPLOY_DIST"
rsync -a --delete "$BUILD_DIST/" "$DEPLOY_DIST/"
require_file "$DEPLOY_DIST/index.html"

log "前端构建与同步完成"
