#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib.sh
source "$SCRIPT_DIR/lib.sh"

BASE_VERSION="${1:-${BASE_VERSION:-}}"
TARGET_VERSION="${2:-${TARGET_VERSION:-}}"
PROJECT_ROOT="${3:-${PROJECT_ROOT:-$(default_project_root)}}"

[[ -n "$BASE_VERSION" && -n "$TARGET_VERSION" ]] || die "用法：$0 BASE_VERSION TARGET_VERSION [PROJECT_ROOT]"
validate_version "$BASE_VERSION"
validate_version "$TARGET_VERSION"
[[ "$BASE_VERSION" != "$TARGET_VERSION" ]] || die "基础版本和目标版本不能相同"

for command in tar rsync jq sha256sum stat awk mktemp install; do
  require_cmd "$command"
done

BASE_NO="$(release_no "$BASE_VERSION")"
TARGET_NO="$(release_no "$TARGET_VERSION")"
RELEASE_ROOT="$PROJECT_ROOT/部署包"
BASE="$RELEASE_ROOT/$BASE_VERSION/yibao_backend_${BASE_VERSION}.tar"
OUT_DIR="$RELEASE_ROOT/$TARGET_VERSION"
OUT="$OUT_DIR/yibao_backend_${TARGET_VERSION}.tar"
APP="$PROJECT_ROOT/backend/app"
DEPLOY_SETTINGS="$PROJECT_ROOT/backend/deploy_settings.py"

require_file "$BASE"
require_dir "$APP"
require_file "$DEPLOY_SETTINGS"
mkdir -p -- "$OUT_DIR"

if [[ -e "$OUT" ]]; then
  [[ "${FORCE:-0}" == "1" ]] || die "目标已存在：$OUT；重打同版本请设置 FORCE=1"
  safe_remove_file "$OUT" "$OUT_DIR"
fi

STAGE="$(mktemp -d "/tmp/yibao-${TARGET_NO}-oci.XXXXXX")"
LROOT="$(mktemp -d "/tmp/yibao-${TARGET_NO}-layer.XXXXXX")"
cleanup() {
  rm -rf -- "$STAGE" "$LROOT"
}
trap cleanup EXIT

log "解开基础镜像：$BASE_VERSION"
tar -C "$STAGE" -xf "$BASE"
mkdir -p "$LROOT/app"

log "复制 backend/app 到新镜像层"
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' "$APP/" "$LROOT/app/"
install -m 0644 "$DEPLOY_SETTINGS" "$LROOT/app/deploy_settings.py"

tar --format=posix --owner=0 --group=0 -C "$LROOT" -cf "$STAGE/new-layer.tar" app
LAYER_HASH="$(sha256sum "$STAGE/new-layer.tar" | awk '{print $1}')"
LAYER_SIZE="$(stat -c '%s' "$STAGE/new-layer.tar")"
LAYER_REF="blobs/sha256/$LAYER_HASH"
LAYER_DIGEST="sha256:$LAYER_HASH"
mv "$STAGE/new-layer.tar" "$STAGE/$LAYER_REF"

OLD_CONFIG_REF="$(jq -r '.[0].Config' "$STAGE/manifest.json")"
OLD_CONFIG="$STAGE/$OLD_CONFIG_REF"
jq \
  --arg created "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg diff_id "$LAYER_DIGEST" \
  --arg version "$TARGET_VERSION" \
  '.created=$created
   | .rootfs.diff_ids += [$diff_id]
   | .history += [{"created":$created,"created_by":("COPY app/ /app/ # " + $version),"comment":"handoff deployment overlay"}]' \
  "$OLD_CONFIG" > "$STAGE/new-config.json"
CONFIG_HASH="$(sha256sum "$STAGE/new-config.json" | awk '{print $1}')"
CONFIG_SIZE="$(stat -c '%s' "$STAGE/new-config.json")"
CONFIG_REF="blobs/sha256/$CONFIG_HASH"
CONFIG_DIGEST="sha256:$CONFIG_HASH"
mv "$STAGE/new-config.json" "$STAGE/$CONFIG_REF"

OLD_MANIFEST_HASH="$(jq -r '.manifests[0].digest' "$STAGE/index.json" | cut -d: -f2)"
OLD_MANIFEST="$STAGE/blobs/sha256/$OLD_MANIFEST_HASH"
jq \
  --arg config_digest "$CONFIG_DIGEST" \
  --argjson config_size "$CONFIG_SIZE" \
  --arg layer_digest "$LAYER_DIGEST" \
  --argjson layer_size "$LAYER_SIZE" \
  '.config.digest=$config_digest
   | .config.size=$config_size
   | .layers += [{"mediaType":"application/vnd.oci.image.layer.v1.tar","digest":$layer_digest,"size":$layer_size}]' \
  "$OLD_MANIFEST" > "$STAGE/new-manifest.json"
MANIFEST_HASH="$(sha256sum "$STAGE/new-manifest.json" | awk '{print $1}')"
MANIFEST_SIZE="$(stat -c '%s' "$STAGE/new-manifest.json")"
MANIFEST_DIGEST="sha256:$MANIFEST_HASH"
mv "$STAGE/new-manifest.json" "$STAGE/blobs/sha256/$MANIFEST_HASH"

jq \
  --arg digest "$MANIFEST_DIGEST" \
  --argjson size "$MANIFEST_SIZE" \
  --arg version "$TARGET_VERSION" \
  '.manifests[0].digest=$digest
   | .manifests[0].size=$size
   | .manifests[0].annotations["org.opencontainers.image.ref.name"]=$version' \
  "$STAGE/index.json" > "$STAGE/index.new.json"
mv "$STAGE/index.new.json" "$STAGE/index.json"

jq \
  --arg config "$CONFIG_REF" \
  --arg tag "yibao_backend:$TARGET_VERSION" \
  --arg layer "$LAYER_REF" \
  --arg layer_digest "$LAYER_DIGEST" \
  --argjson layer_size "$LAYER_SIZE" \
  '.[0] |= (
      .Config=$config
      | .RepoTags=[$tag]
      | .Layers += [$layer]
      | .LayerSources[$layer_digest]={
          "mediaType":"application/vnd.oci.image.layer.v1.tar",
          "size":$layer_size,
          "digest":$layer_digest
        }
    )' \
  "$STAGE/manifest.json" > "$STAGE/manifest.new.json"
mv "$STAGE/manifest.new.json" "$STAGE/manifest.json"

jq -n \
  --arg version "$TARGET_VERSION" \
  --arg layer_digest "$LAYER_DIGEST" \
  '{yibao_backend:{($version):$layer_digest}}' > "$STAGE/repositories"

log "生成后端镜像包：$OUT"
tar -C "$STAGE" -cf "$OUT" blobs index.json manifest.json oci-layout repositories
chmod 0644 "$OUT"

log "增量后端镜像完成；基础=$BASE_VERSION，目标=$TARGET_VERSION，新增层=$LAYER_SIZE bytes"
