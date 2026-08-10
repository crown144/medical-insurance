#!/usr/bin/env bash

set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令：$1"
}

require_file() {
  [[ -f "$1" ]] || die "文件不存在：$1"
}

require_dir() {
  [[ -d "$1" ]] || die "目录不存在：$1"
}

validate_version() {
  [[ "$1" =~ ^[0-9]{6}-[0-9]+$ ]] || die "版本格式错误：$1；应类似 260723-23"
}

release_no() {
  printf '%s\n' "${1##*-}"
}

script_dir() {
  cd -- "$(dirname -- "${BASH_SOURCE[1]}")" && pwd
}

default_project_root() {
  local current_script_dir
  current_script_dir="$(script_dir)"
  cd -- "$current_script_dir/../.." && pwd
}

safe_remove_file() {
  local target="$1"
  local required_parent="$2"
  [[ -n "$target" && "$target" == "$required_parent"/* ]] || die "拒绝删除非目标目录文件：$target"
  [[ "$target" != "$required_parent" ]] || die "拒绝删除目标目录本身"
  rm -f -- "$target"
}

docker_run() {
  if [[ "${DOCKER_USE_SUDO:-0}" == "1" ]]; then
    sudo docker "$@"
  else
    docker "$@"
  fi
}

compose_run() {
  if [[ "${DOCKER_USE_SUDO:-0}" == "1" ]]; then
    sudo docker compose "$@"
  else
    docker compose "$@"
  fi
}
