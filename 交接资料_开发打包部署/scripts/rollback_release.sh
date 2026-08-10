#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

ROLLBACK_VERSION="${1:-}"
INSTALL_ROOT="${2:-/opt/yibao}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-yibao}"
[[ -n "$ROLLBACK_VERSION" ]] || die "用法：$0 ROLLBACK_VERSION [INSTALL_ROOT]"
validate_version "$ROLLBACK_VERSION"

RELEASE_DIR="$INSTALL_ROOT/releases/$ROLLBACK_VERSION"
require_file "$RELEASE_DIR/backend/docker-compose.yml"
require_file "$RELEASE_DIR/frontend/docker-compose.yml"

log "回切应用版本：$ROLLBACK_VERSION"
compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/backend/docker-compose.yml" up -d --no-build
compose_run -p "$COMPOSE_PROJECT_NAME" -f "$RELEASE_DIR/frontend/docker-compose.yml" up -d --no-build

ln -sfn "$RELEASE_DIR" "$INSTALL_ROOT/current.new"
mv -Tf "$INSTALL_ROOT/current.new" "$INSTALL_ROOT/current"

log "应用版本已回切。注意：数据库迁移不会自动回滚，必须按迁移兼容性另行处理。"
