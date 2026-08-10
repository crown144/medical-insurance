#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

TARGET_VERSION="${1:-${TARGET_VERSION:-}}"
PROJECT_ROOT="${2:-${PROJECT_ROOT:-$(default_project_root)}}"
[[ -n "$TARGET_VERSION" ]] || die "用法：$0 TARGET_VERSION [PROJECT_ROOT]"
validate_version "$TARGET_VERSION"

for command in tar rsync sed sha256sum mktemp; do
  require_cmd "$command"
done

TARGET_NO="$(release_no "$TARGET_VERSION")"
OUT_DIR="$PROJECT_ROOT/部署包/$TARGET_VERSION"
IMAGE="$OUT_DIR/yibao_backend_${TARGET_VERSION}.tar"
BACKEND_ARCHIVE="$OUT_DIR/260723yb-backend-deploy-${TARGET_NO}.tar.gz"
FRONTEND_ARCHIVE="$OUT_DIR/260723yb-frontend-static-${TARGET_NO}.tar.gz"
CHECKSUMS="$OUT_DIR/SHA256SUMS"

require_file "$IMAGE"
require_file "$PROJECT_ROOT/backend/docker-compose.yml"
require_file "$PROJECT_ROOT/backend/.env.example"
require_file "$PROJECT_ROOT/frontend/docker-compose.yml"
require_file "$PROJECT_ROOT/frontend/.env.example"
require_file "$PROJECT_ROOT/frontend/dist/index.html"
require_dir "$PROJECT_ROOT/frontend/nginx"

for target in "$BACKEND_ARCHIVE" "$FRONTEND_ARCHIVE" "$CHECKSUMS"; do
  if [[ -e "$target" ]]; then
    [[ "${FORCE:-0}" == "1" ]] || die "目标已存在：$target；重打同版本请设置 FORCE=1"
    safe_remove_file "$target" "$OUT_DIR"
  fi
done

STAGE="$(mktemp -d "/tmp/yibao-${TARGET_NO}-package.XXXXXX")"
cleanup() {
  rm -rf -- "$STAGE"
}
trap cleanup EXIT

mkdir -p "$STAGE/backend" "$STAGE/frontend"
install -m 0644 "$PROJECT_ROOT/backend/docker-compose.yml" "$STAGE/backend/docker-compose.yml"
sed -E -i "s#image: yibao_backend:[^[:space:]]+#image: yibao_backend:$TARGET_VERSION#g" "$STAGE/backend/docker-compose.yml"
install -m 0644 "$PROJECT_ROOT/backend/.env.example" "$STAGE/backend/.env.example"

if [[ "${INCLUDE_BACKEND_ENV:-1}" == "1" ]]; then
  require_file "$PROJECT_ROOT/backend/.env"
  install -m 0600 "$PROJECT_ROOT/backend/.env" "$STAGE/backend/.env"
fi

log "生成后端部署包"
tar -C "$STAGE" -czf "$BACKEND_ARCHIVE" backend

FRONTEND_PACKAGE_MODE="${FRONTEND_PACKAGE_MODE:-full}"
case "$FRONTEND_PACKAGE_MODE" in
  full)
    log "按当前兼容口径打包完整 frontend 目录"
    tar -C "$PROJECT_ROOT" -czf "$FRONTEND_ARCHIVE" frontend
    ;;
  deploy-only)
    log "生成精简前端部署包"
    install -m 0644 "$PROJECT_ROOT/frontend/docker-compose.yml" "$STAGE/frontend/docker-compose.yml"
    install -m 0644 "$PROJECT_ROOT/frontend/.env.example" "$STAGE/frontend/.env.example"
    if [[ "${INCLUDE_FRONTEND_ENV:-1}" == "1" ]]; then
      require_file "$PROJECT_ROOT/frontend/.env"
      install -m 0600 "$PROJECT_ROOT/frontend/.env" "$STAGE/frontend/.env"
    fi
    rsync -a "$PROJECT_ROOT/frontend/nginx/" "$STAGE/frontend/nginx/"
    rsync -a "$PROJECT_ROOT/frontend/dist/" "$STAGE/frontend/dist/"
    tar -C "$STAGE" -czf "$FRONTEND_ARCHIVE" frontend
    ;;
  *)
    die "FRONTEND_PACKAGE_MODE 只能是 full 或 deploy-only"
    ;;
esac

log "生成 SHA256SUMS"
(
  cd "$OUT_DIR"
  sha256sum \
    "$(basename "$IMAGE")" \
    "$(basename "$BACKEND_ARCHIVE")" \
    "$(basename "$FRONTEND_ARCHIVE")" \
    > "$(basename "$CHECKSUMS")"
)

chmod 0644 "$IMAGE" "$BACKEND_ARCHIVE" "$FRONTEND_ARCHIVE" "$CHECKSUMS"
log "三包生成完成：$OUT_DIR"
