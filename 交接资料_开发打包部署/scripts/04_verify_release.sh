#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

TARGET_VERSION="${1:-${TARGET_VERSION:-}}"
PROJECT_ROOT="${2:-${PROJECT_ROOT:-$(default_project_root)}}"
PACKAGE_DIR="${3:-${PACKAGE_DIR:-$PROJECT_ROOT/部署包/$TARGET_VERSION}}"
[[ -n "$TARGET_VERSION" ]] || die "用法：$0 TARGET_VERSION [PROJECT_ROOT] [PACKAGE_DIR]"
validate_version "$TARGET_VERSION"

for command in tar gzip sha256sum jq awk; do
  require_cmd "$command"
done

TARGET_NO="$(release_no "$TARGET_VERSION")"
IMAGE="$PACKAGE_DIR/yibao_backend_${TARGET_VERSION}.tar"
BACKEND_ARCHIVE="$PACKAGE_DIR/260723yb-backend-deploy-${TARGET_NO}.tar.gz"
FRONTEND_ARCHIVE="$PACKAGE_DIR/260723yb-frontend-static-${TARGET_NO}.tar.gz"
CHECKSUMS="$PACKAGE_DIR/SHA256SUMS"

require_file "$IMAGE"
require_file "$BACKEND_ARCHIVE"
require_file "$FRONTEND_ARCHIVE"
require_file "$CHECKSUMS"

log "验证 SHA256"
(cd "$PACKAGE_DIR" && sha256sum -c SHA256SUMS)

log "验证 gzip 和 tar 结构"
gzip -t "$BACKEND_ARCHIVE"
gzip -t "$FRONTEND_ARCHIVE"
tar -tf "$IMAGE" >/dev/null

REPOSITORIES_JSON="$(tar -xOf "$IMAGE" repositories)"
jq -e --arg version "$TARGET_VERSION" '.yibao_backend[$version] != null' <<<"$REPOSITORIES_JSON" >/dev/null \
  || die "后端镜像标签不是 yibao_backend:$TARGET_VERSION"

COMPOSE_CONTENT="$(tar -xOzf "$BACKEND_ARCHIVE" backend/docker-compose.yml)"
IMAGE_COUNT="$(grep -c "image: yibao_backend:$TARGET_VERSION" <<<"$COMPOSE_CONTENT" || true)"
[[ "$IMAGE_COUNT" -eq 2 ]] || die "后端部署包中 backend/celery 镜像标签数量异常：$IMAGE_COUNT"

FRONT_LIST="$(mktemp "/tmp/yibao-${TARGET_NO}-front-list.XXXXXX")"
trap 'rm -f -- "$FRONT_LIST"' EXIT
tar -tzf "$FRONTEND_ARCHIVE" > "$FRONT_LIST"
grep -Fx 'frontend/dist/index.html' "$FRONT_LIST" >/dev/null || die "前端包缺少 frontend/dist/index.html"
grep -Fx 'frontend/docker-compose.yml' "$FRONT_LIST" >/dev/null || die "前端包缺少 frontend/docker-compose.yml"
grep -Fx 'frontend/nginx/default.conf' "$FRONT_LIST" >/dev/null || die "前端包缺少 Nginx 配置"

log "三包校验全部通过"
ls -lh "$IMAGE" "$BACKEND_ARCHIVE" "$FRONTEND_ARCHIVE" "$CHECKSUMS"
