#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

CONFIG_FILE="${1:-$SCRIPT_DIR/../release.conf}"
require_file "$CONFIG_FILE"
# 配置文件由项目交接人员维护，只允许在可信本地环境中使用。
# shellcheck disable=SC1090
set -a
source "$CONFIG_FILE"
set +a

: "${PROJECT_ROOT:?release.conf 缺少 PROJECT_ROOT}"
: "${BASE_VERSION:?release.conf 缺少 BASE_VERSION}"
: "${TARGET_VERSION:?release.conf 缺少 TARGET_VERSION}"

validate_version "$BASE_VERSION"
validate_version "$TARGET_VERSION"
require_dir "$PROJECT_ROOT"

log "开始构建发布版：$BASE_VERSION -> $TARGET_VERSION"
"$SCRIPT_DIR/01_build_frontend.sh" "$PROJECT_ROOT"

case "${BACKEND_BUILD_MODE:-incremental}" in
  incremental)
    "$SCRIPT_DIR/02_build_backend_incremental.sh" "$BASE_VERSION" "$TARGET_VERSION" "$PROJECT_ROOT"
    ;;
  full)
    "$SCRIPT_DIR/02_build_backend_full.sh" "$TARGET_VERSION" "$PROJECT_ROOT"
    ;;
  *)
    die "BACKEND_BUILD_MODE 只能是 incremental 或 full"
    ;;
esac

"$SCRIPT_DIR/03_package_release.sh" "$TARGET_VERSION" "$PROJECT_ROOT"
"$SCRIPT_DIR/04_verify_release.sh" "$TARGET_VERSION" "$PROJECT_ROOT"

log "发布版构建成功：$PROJECT_ROOT/部署包/$TARGET_VERSION"
