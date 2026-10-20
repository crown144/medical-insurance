#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
version=$(python3 -c 'import json; print(json.load(open("DEPLOY_VERSION.json"))["commit"][:7])')
[[ "$version" =~ ^[0-9a-f]{7}$ ]] || { echo 'Invalid release metadata' >&2; exit 1; }
new_dist="dist-$version"
backup="dist-before-$version"
[[ -f docker-compose.yml && -d dist-1012 && -d "$new_dist" ]] || {
  echo 'Run in the existing front directory after extracting the update package.' >&2
  exit 1
}
[[ ! -e "$backup" ]] || {
  echo "Backup $backup already exists. Stop; do not overwrite it." >&2
  exit 1
}
# Validate config with the existing image and no published ports first.
bash front-sec run --rm --no-deps yibao_front nginx -t
mv dist-1012 "$backup"
mv "$new_dist" dist-1012
bash front-sec up -d --no-deps --force-recreate yibao_front
echo 'Frontend replaced. Refresh browser and check portal login plus response headers.'
echo "Old assets and runtime config retained in $backup."
