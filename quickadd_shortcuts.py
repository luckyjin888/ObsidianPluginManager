"""Install the bundled QuickAdd code-block choices and safe hotkeys.

QuickAdd's package importer is the supported configuration API. This module
never edits QuickAdd's data.json directly and never overwrites existing choices.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

QUICKADD_ID = "quickadd"
MIN_QUICKADD_VERSION = (2, 30, 0)
PACKAGE_NAME = ".opm-quickadd-code-block-shortcuts.quickadd.json"

CHOICES = (
    {
        "id": "opm-insert-code-block",
        "name": "Insert Code Block",
        "format": "```\n{{CURSOR}}\n```",
        "hotkey": "C",
    },
    {
        "id": "opm-insert-json-block",
        "name": "Insert JSON Block",
        "format": "json\n",
        "hotkey": "J",
        "full_format": "json",
    },
    {
        "id": "opm-insert-python-block",
        "name": "Insert Python Block",
        "format": "python\n",
        "hotkey": "P",
        "full_format": "python",
    },
)


def _capture_format(choice: dict) -> str:
    if choice["id"] == "opm-insert-json-block":
        return "json\n{\n  {{CURSOR}}\n}"
    if choice["id"] == "opm-insert-python-block":
        return "python\n```"
    return choice["format"]


def build_package() -> dict:
    """Return a code-free QuickAdd package using the documented schema v1."""
    choices = []
    for item in CHOICES:
        prefix = "" if item["id"] == "opm-insert-code-block" else ""
        fmt = _capture_format(item)
        if item["id"] == "opm-insert-code-block":
            fmt = "```\n{{CURSOR}}\n```"
        elif item["id"] == "opm-insert-json-block":
            fmt = "```json\n{\n  {{CURSOR}}\n}\n```"
        else:
            fmt = "```python\n{{CURSOR}}\n```"
        choice = {
            "id": item["id"],
            "name": item["name"],
            "type": "Capture",
            "command": True,
            "captureTo": "",
            "captureToActiveFile": True,
            "activeFileWritePosition": "cursor",
            "createFileIfItDoesntExist": {
                "enabled": False,
                "createWithTemplate": False,
                "template": "",
            },
            "format": {"enabled": True, "format": fmt},
            "prepend": False,
            "appendLink": False,
            "copyLinkToClipboard": False,
            "captureToCanvasNodeId": "",
            "insertAfter": {
                "enabled": False,
                "after": "",
                "insertAtEnd": True,
                "considerSubsections": False,
                "createIfNotFound": True,
                "createIfNotFoundLocation": "top",
            },
            "insertBefore": {
                "enabled": False,
                "before": "",
                "createIfNotFound": False,
                "createIfNotFoundLocation": "top",
            },
            "newLineCapture": {"enabled": False, "direction": "below"},
            "task": False,
            "openFile": False,
        }
        choices.append({
            "choice": choice,
            "pathHint": [],
            "parentChoiceId": None,
        })
    return {
        "schemaVersion": 1,
        "quickAddVersion": "2.30.0",
        "createdAt": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "rootChoiceIds": [item["id"] for item in CHOICES],
        "choices": choices,
        "assets": [],
    }


def _version_tuple(value: str) -> tuple[int, int, int]:
    import re
    parts = [int(x) for x in re.findall(r"\d+", str(value or ""))[:3]]
    return tuple((parts + [0, 0, 0])[:3])


def _read_json(path: Path):
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _backup(path: Path) -> Path | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"拒绝备份非普通文件或符号链接：{path}")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = path.with_name(path.name + ".bak-" + stamp)
    suffix = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".bak-{stamp}-{suffix}")
        suffix += 1
    shutil.copy2(path, candidate)
    return candidate


def _atomic_write_json(path: Path, data: dict) -> None:
    if path.is_symlink():
        raise RuntimeError(f"拒绝写入符号链接：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".opm-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def _expected_choice(item: dict) -> dict:
    return next(x["choice"] for x in build_package()["choices"] if x["choice"]["id"] == item["id"])


def _choice_state(data_path: Path) -> str:
    if not data_path.exists():
        return "none"
    data = _read_json(data_path)
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
        raise RuntimeError("QuickAdd data.json 格式异常；为避免损坏现有配置，已停止。")
    existing = {
        entry.get("id"): entry
        for entry in data["choices"]
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
    present = [item for item in CHOICES if item["id"] in existing]
    if not present:
        return "none"
    if len(present) != len(CHOICES):
        raise RuntimeError("QuickAdd 中只存在部分快捷选项；不会覆盖或重复导入，请先人工核对。")
    for item in CHOICES:
        current = existing[item["id"]]
        expected = _expected_choice(item)
        for key in ("name", "type", "command", "captureToActiveFile", "activeFileWritePosition", "format"):
            if current.get(key) != expected.get(key):
                raise RuntimeError(f"已有 QuickAdd 选项 {item['name']} 与管理器预设不同；不会覆盖用户配置。")
    return "complete"


def _binding_matches(binding, key: str) -> bool:
    if not isinstance(binding, dict) or not isinstance(binding.get("modifiers"), list):
        return False
    modifiers = {str(x).lower() for x in binding["modifiers"]}
    return modifiers == {"mod", "shift"} and str(binding.get("key", "")).upper() == key


def _plan_hotkeys(hotkeys: dict) -> tuple[dict, list[str]]:
    if not isinstance(hotkeys, dict):
        raise RuntimeError("hotkeys.json 顶层格式异常；不会修改。")
    planned = json.loads(json.dumps(hotkeys))
    additions = []
    for item in CHOICES:
        command_id = "quickadd:choice:" + item["id"]
        current = planned.get(command_id, [])
        if not isinstance(current, list):
            raise RuntimeError(f"快捷键配置 {command_id} 格式异常；不会修改。")
        if any(_binding_matches(x, item["hotkey"]) for x in current):
            continue
        for other_command, bindings in planned.items():
            if other_command == command_id:
                continue
            if not isinstance(bindings, list):
                raise RuntimeError(f"快捷键配置 {other_command} 格式异常；不会修改。")
            if any(_binding_matches(x, item["hotkey"]) for x in bindings):
                raise RuntimeError(
                    f"快捷键 Mod+Shift+{item['hotkey']} 已被 {other_command} 占用；"
                    "为避免覆盖，三个快捷键均未修改。"
                )
        current.append({"modifiers": ["Mod", "Shift"], "key": item["hotkey"]})
        planned[command_id] = current
        additions.append(f"Mod+Shift+{item['hotkey']} → {item['name']}")
    return planned, additions


def configure_quickadd_shortcuts(vault: Path, cli: str, confirm, say) -> bool:
    """Offer a guarded, idempotent QuickAdd setup. Returns True only if verified."""
    vault = Path(vault)
    config_root = vault / ".obsidian"
    plugin_dir = config_root / "plugins" / QUICKADD_ID
    manifest_path = plugin_dir / "manifest.json"
    enabled_path = config_root / "community-plugins.json"
    manifest = _read_json(manifest_path)
    enabled = _read_json(enabled_path)
    if not isinstance(manifest, dict) or manifest.get("id") != QUICKADD_ID:
        say("\nQuickAdd 尚未安装；请先在插件清单中选择安装 QuickAdd，再运行快捷键配置。")
        return False
    if not isinstance(enabled, list) or QUICKADD_ID not in enabled:
        say("\nQuickAdd 尚未启用；请先启用 QuickAdd，再运行快捷键配置。")
        return False
    if _version_tuple(manifest.get("version", "")) < MIN_QUICKADD_VERSION:
        say("\nQuickAdd 版本低于 2.30.0；请先更新 QuickAdd，再配置快捷键。")
        return False

    data_path = plugin_dir / "data.json"
    state = _choice_state(data_path)
    hotkeys_path = config_root / "hotkeys.json"
    if hotkeys_path.exists():
        hotkeys = _read_json(hotkeys_path)
        if not isinstance(hotkeys, dict):
            say("hotkeys.json 格式异常或无法读取；为避免覆盖，已停止。")
            return False
    else:
        hotkeys = {}
    try:
        planned_hotkeys, additions = _plan_hotkeys(hotkeys)
    except RuntimeError as exc:
        say(str(exc))
        return False

    if state == "complete" and not additions:
        say("\n三个 QuickAdd 选项和快捷键均已配置；无需重复操作。")
        return True

    package_path = vault / ".obsidian" / PACKAGE_NAME
    if package_path.exists() or package_path.is_symlink():
        say(f"临时安装包路径已存在，出于安全考虑不覆盖：{package_path}")
        return False

    say("\n【标准专业版】")
    say(f"目标 Vault：{vault}")
    say("将通过 QuickAdd 官方 package-import 命令新增三个无脚本 Capture 选项，并在 .obsidian/hotkeys.json 中合并三个快捷键。")
    say("快捷键：Mod+Shift+C（普通代码块）、Mod+Shift+J（JSON）、Mod+Shift+P（Python）；Mod 在 macOS 对应 Command。")
    say("不会直接编辑 QuickAdd data.json；choices=import 只允许新增，不覆盖已有选项。")
    say("若存在冲突、部分配置、格式异常或符号链接，将停止而不覆盖。")
    say("修改前备份 QuickAdd data.json 和 hotkeys.json；安装包只在本次操作期间暂存并随后删除。")
    say("\n【10岁儿童比喻版】")
    say("先检查三个按钮是不是已经有了。没有的才添加；你自己改过的按钮不会被替换。")
    say("如果键盘上的按键已经被别的功能占用，我们就停下来，不抢它的按键。")
    say("动手前先复印原来的设置，做完再检查新按钮是否真的出现。")
    if not confirm("\n是否同意在以上 Vault 中新增三个 QuickAdd 选项和快捷键？"):
        say("未获明确授权；没有修改 QuickAdd 或快捷键配置。")
        return False

    backups = []
    try:
        if state == "none":
            backup = _backup(data_path)
            if backup:
                backups.append(backup)
        if additions:
            backup = _backup(hotkeys_path)
            if backup:
                backups.append(backup)

        if state == "none":
            package_path.write_text(json.dumps(build_package(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            try:
                preview = subprocess.run(
                    [str(cli), "quickadd:package-preview", f"path={package_path.relative_to(vault)}"],
                    cwd=str(vault), capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=60, check=False,
                )
                if preview.returncode != 0:
                    raise RuntimeError("QuickAdd package-preview 失败：" + (preview.stderr.strip() or preview.stdout.strip()))
                imported = subprocess.run(
                    [str(cli), "quickadd:package-import", f"path={package_path.relative_to(vault)}", "choices=import"],
                    cwd=str(vault), capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=120, check=False,
                )
                if imported.returncode != 0:
                    raise RuntimeError("QuickAdd package-import 失败：" + (imported.stderr.strip() or imported.stdout.strip()))
            finally:
                try:
                    package_path.unlink()
                except FileNotFoundError:
                    pass

            data = _read_json(data_path)
            if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
                raise RuntimeError("QuickAdd 导入命令返回后，data.json 无法验证。")
            actual = {x.get("id"): x for x in data["choices"] if isinstance(x, dict)}
            for item in CHOICES:
                found = actual.get(item["id"])
                if not isinstance(found, dict) or found.get("type") != "Capture" or found.get("command") is not True:
                    raise RuntimeError(f"导入后未能验证 QuickAdd 选项：{item['name']}")

        if additions:
            _atomic_write_json(hotkeys_path, planned_hotkeys)
            saved = _read_json(hotkeys_path)
            if not isinstance(saved, dict):
                raise RuntimeError("写入后无法读取 hotkeys.json。")
            for item in CHOICES:
                command_id = "quickadd:choice:" + item["id"]
                if not any(_binding_matches(x, item["hotkey"]) for x in saved.get(command_id, [])):
                    raise RuntimeError(f"写入后未能验证快捷键：{item['name']}")

        say("\nQuickAdd 三个 Capture 选项及快捷键已写入并通过文件验证。")
        if backups:
            say("原配置备份：" + "；".join(str(path) for path in backups))
        say("请在 Obsidian 中执行一次“重新加载应用”或重启 Obsidian，使快捷键设置被重新读取。")
        return True
    except Exception as exc:
        say(f"配置未能完整完成：{exc}")
        if backups:
            say("修改前备份仍保留，可用于恢复：" + "；".join(str(path) for path in backups))
        say("请检查 Obsidian 中的 QuickAdd 选项和快捷键；不要盲目重复执行。")
        return False
    finally:
        try:
            package_path.unlink()
        except FileNotFoundError:
            pass
