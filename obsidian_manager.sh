#!/usr/bin/env bash
# ObsidianPluginManager v0.4.3 launcher for macOS/Linux
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  printf '需要 Python 3。请从 https://www.python.org/downloads/ 安装。\n'
  exit 1
fi
exec python3 "$SCRIPT_DIR/obsidian_manager.py" "$@"
