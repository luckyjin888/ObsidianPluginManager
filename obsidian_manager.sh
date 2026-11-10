#!/usr/bin/env bash
#
# Obsidian Manager
# Version: 0.3.0
# Description: Read-only Obsidian environment and community-plugin inventory
# Current platform support: macOS
# License: GPL-3.0-only
#
# Safety principles:
# - Inspection first; no automatic installation, deletion, enabling, or disabling.
# - Never hard-code a user's Vault path.
# - Never request administrator privileges or run sudo.
# - Explain and obtain confirmation before any optional action.
#

set -u

VERSION="0.3.0"
MIN_CLI_VERSION="1.12.7"
OFFICIAL_DOWNLOAD="https://obsidian.md/download"
OFFICIAL_CLI_HELP="https://obsidian.md/help/cli"

print_header() {
    printf '\n========================================\n'
    printf '       Obsidian Manager v%s\n' "$VERSION"
    printf '       Obsidian 安全管理工具\n'
    printf '========================================\n'
}

version_ge() {
    awk -v current="$1" -v required="$2" '
    BEGIN {
        split(current, a, ".");
        split(required, b, ".");
        for (i = 1; i <= 3; i++) {
            x = a[i];
            y = b[i];
            sub(/[^0-9].*$/, "", x);
            sub(/[^0-9].*$/, "", y);
            if (x == "") x = 0;
            if (y == "") y = 0;
            x += 0;
            y += 0;
            if (x > y) exit 0;
            if (x < y) exit 1;
        }
        exit 0;
    }'
}

expand_home_path() {
    case "$1" in
        "~") printf '%s\n' "$HOME" ;;
        "~/"*) printf '%s/%s\n' "$HOME" "${1#\~/}" ;;
        *) printf '%s\n' "$1" ;;
    esac
}

print_header

# 1. Platform check
printf '\n[1/5] 检查操作系统\n'
OS_NAME="$(uname -s 2>/dev/null || true)"
if [[ "$OS_NAME" != "Darwin" ]]; then
    printf '当前版本只支持 macOS；检测到：%s\n' "${OS_NAME:-未知}"
    printf 'Windows/Linux 支持尚未实现，请勿将本版本视为跨平台版本。\n'
    exit 1
fi
printf 'macOS 检查通过。\n'

# 2. Locate Obsidian
printf '\n[2/5] 检查 Obsidian 安装位置\n'
APP_PATH=""
for candidate in "/Applications/Obsidian.app" "$HOME/Applications/Obsidian.app"; do
    if [[ -d "$candidate" ]]; then
        APP_PATH="$candidate"
        break
    fi
done

if [[ -z "$APP_PATH" ]]; then
    printf '未在常见位置找到 Obsidian.app。\n'
    printf '请确认 Obsidian 已安装，或将应用放在 /Applications 或 ~/Applications。\n'
    exit 1
fi
printf '找到 Obsidian：%s\n' "$APP_PATH"

# 3. Check app version and bundled CLI
printf '\n[3/5] 检查 Obsidian 版本及 CLI 文件\n'
VERSION_PLIST="$APP_PATH/Contents/Info.plist"
CLI_BINARY="$APP_PATH/Contents/MacOS/obsidian-cli"

if [[ ! -f "$VERSION_PLIST" ]]; then
    printf '未找到 Info.plist，无法读取应用版本。\n'
    exit 1
fi

APP_VERSION=$(
    /usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$VERSION_PLIST" 2>/dev/null || true
)
if [[ -z "$APP_VERSION" ]]; then
    printf '无法读取 Obsidian 版本。\n'
    exit 1
fi

printf '当前 Obsidian 版本：%s\n' "$APP_VERSION"
printf 'CLI 所需最低安装程序版本：%s+\n' "$MIN_CLI_VERSION"

VERSION_OK=false
if version_ge "$APP_VERSION" "$MIN_CLI_VERSION"; then
    VERSION_OK=true
    printf '版本号检查：通过（此项不等于 CLI 已能正常运行）\n'
else
    printf '版本号检查：未达到要求。\n'
fi

if [[ -x "$CLI_BINARY" ]]; then
    printf '内置 CLI：存在且具有执行权限。\n'
else
    printf '内置 CLI：未找到或不可执行。\n'
fi

if [[ "$VERSION_OK" != true || ! -x "$CLI_BINARY" ]]; then
    printf '\nCLI 前置条件未全部满足。\n'
    printf '请先查看 Obsidian 官方安装说明：%s\n' "$OFFICIAL_CLI_HELP"
    printf '官方下载安装页：%s\n' "$OFFICIAL_DOWNLOAD"
    printf '本脚本不会自动下载、安装或替换 Obsidian。\n'
    exit 0
fi

# 4. Check CLI registration and optionally run a harmless version query
printf '\n[4/5] 检查终端 CLI 注册状态\n'
CLI_PATH="$(command -v obsidian 2>/dev/null || true)"

if [[ -z "$CLI_PATH" ]]; then
    printf '终端命令 obsidian：尚未注册或不在当前 PATH 中。\n'
    printf '\n请在 Obsidian 中手动操作：设置 → 常规 → 命令行界面 → 启用并按提示注册。\n'
    printf '官方说明：%s\n' "$OFFICIAL_CLI_HELP"
    printf '注册可能需要系统授权；本脚本不会调用 sudo，也不会自行创建系统链接。\n'
    printf '注册后请重新打开终端，再运行本脚本。\n'
    exit 0
fi

printf '终端命令位置：%s\n' "$CLI_PATH"
printf '注意：仅找到命令还不能证明 CLI 能正常连接 Obsidian。\n'
printf '\n可选运行检查：执行 obsidian version。Obsidian 未运行时，该命令可能会启动 Obsidian。\n'
printf '标准专业版：该命令只查询版本，但可能启动 Obsidian 应用；不会安装、卸载或修改插件。\n'
printf '10岁儿童版：这像是问 Obsidian“你叫什么版本”；如果它还没开门，电脑可能先帮它开门，不会动你的笔记。\n'
read -r -p "是否现在执行这个版本查询？[y/N] " RUN_VERSION_CHECK

case "$RUN_VERSION_CHECK" in
    y|Y)
        if CLI_OUTPUT="$(obsidian version 2>&1)"; then
            printf 'CLI 运行检查：成功\n%s\n' "$CLI_OUTPUT"
        else
            printf 'CLI 运行检查：失败\n%s\n' "$CLI_OUTPUT"
            printf '请检查 Obsidian 是否正常运行及 CLI 注册状态。\n'
        fi
        ;;
    *)
        printf '跳过 CLI 运行检查；不会执行该命令。\n'
        ;;
esac

# 5. Ask for a Vault path and list plugin directories
printf '\n[5/5] 检查 Obsidian Vault\n'
printf '请输入 Vault 文件夹路径（支持 ~/ 开头的路径）。\n'
read -r -p "Vault 路径：" VAULT_INPUT

if [[ -z "$VAULT_INPUT" ]]; then
    printf '未输入路径，结束检查。\n'
    exit 0
fi

VAULT_INPUT="$(expand_home_path "$VAULT_INPUT")"
if [[ ! -d "$VAULT_INPUT" ]]; then
    printf '路径不存在或不是文件夹：%s\n' "$VAULT_INPUT"
    exit 1
fi

VAULT_PATH="$(cd "$VAULT_INPUT" 2>/dev/null && pwd -P)" || {
    printf '无法访问该目录。\n'
    exit 1
}

if [[ ! -d "$VAULT_PATH/.obsidian" ]]; then
    printf '该目录中没有 .obsidian 文件夹，不像是有效的 Vault。\n'
    printf '本脚本不会创建或修改 Vault 配置。\n'
    exit 1
fi

printf 'Vault 检查通过：%s\n' "$VAULT_PATH"
PLUGIN_DIR="$VAULT_PATH/.obsidian/plugins"

printf '\n========================================\n'
printf '       已发现的社区插件目录\n'
printf '========================================\n'

if [[ -d "$PLUGIN_DIR" ]]; then
    find "$PLUGIN_DIR" -mindepth 1 -maxdepth 1 -type d -print \
        | sed 's#.*/##' \
        | LC_ALL=C sort
    printf '\n说明：目录存在只代表插件文件夹存在，不代表插件已启用、可信或安全。\n'
else
    printf '尚未发现社区插件目录。\n'
fi

printf '\n========================================\n'
printf '             检查完成\n'
printf '========================================\n'
printf '本次为只读检查。没有安装、卸载、启用、禁用或修改任何插件。\n'
printf '本脚本不会读取插件源代码、验证插件签名或判断插件是否安全。\n'
