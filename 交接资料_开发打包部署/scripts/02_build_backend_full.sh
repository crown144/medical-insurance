#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

TARGET_VERSION="${1:-${TARGET_VERSION:-}}"
PROJECT_ROOT="${2:-${PROJECT_ROOT:-$(default_project_root)}}"
[[ -n "$TARGET_VERSION" ]] || die "用法：$0 TARGET_VERSION [PROJECT_ROOT]"
validate_version "$TARGET_VERSION"

require_cmd docker
require_file "$PROJECT_ROOT/backend/Dockerfile"
require_file "$PROJECT_ROOT/backend/requirements-yibao.txt"

OUT_DIR="$PROJECT_ROOT/部署包/$TARGET_VERSION"
OUT="$OUT_DIR/yibao_backend_${TARGET_VERSION}.tar"
mkdir -p -- "$OUT_DIR"
if [[ -e "$OUT" ]]; then
  [[ "${FORCE:-0}" == "1" ]] || die "目标已存在：$OUT；重打同版本请设置 FORCE=1"
  safe_remove_file "$OUT" "$OUT_DIR"
fi

log "完整构建后端镜像 yibao_backend:$TARGET_VERSION"
docker_run build \
  --build-arg PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}" \
  --build-arg PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}" \
  -t "yibao_backend:$TARGET_VERSION" \
  -f "$PROJECT_ROOT/backend/Dockerfile" \
  "$PROJECT_ROOT/backend"

log "导出后端镜像：$OUT"
docker_run save -o "$OUT" "yibao_backend:$TARGET_VERSION"
chmod 0644 "$OUT"
log "完整后端镜像构建完成"
