"""Read active Obsidian hotkey assignments through the documented CLI."""
from __future__ import annotations

import json
import platform
import re
import subprocess
from pathlib import Path


def normalise_hotkey(value):
    if isinstance(value, dict):
        modifiers = value.get("modifiers")
        key = value.get("key")
        if not isinstance(modifiers, list) or not isinstance(key, str):
            return None
        mods = {str(item).strip().lower() for item in modifiers}
    elif isinstance(value, str):
        raw = value.strip().replace(" ", "")
        raw = (raw.replace("⌘", "Mod+").replace("⇧", "Shift+")
                  .replace("⌃", "Ctrl+").replace("⌥", "Alt+"))
        parts = [part for part in re.split(r"\+", raw) if part]
        if not parts:
            return None
        key, mods = parts[-1], {part.lower() for part in parts[:-1]}
    else:
        return None

    if platform.system() == "Darwin":
        mods = {"mod" if item in ("meta", "cmd", "command") else item for item in mods}
    else:
        mods = {"mod" if item in ("ctrl", "control") else item for item in mods}
    return "+".join(sorted(mods | {key.lower()}))


def parse_hotkeys_json(payload: str) -> set[tuple[str, str]]:
    """Accept list records or an ID-to-bindings map; reject unknown nonempty shapes."""
    try:
        root = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Obsidian CLI 的 hotkeys JSON 输出无法解析。") from exc

    found: set[tuple[str, str]] = set()

    def add(command_id, value):
        if not isinstance(command_id, str) or not command_id:
            return
        values = value if isinstance(value, list) else [value]
        for entry in values:
            combo = normalise_hotkey(entry)
            if combo:
                found.add((command_id, combo))

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        command_id = next(
            (node.get(key) for key in ("id", "commandId", "command_id", "command")
             if isinstance(node.get(key), str)),
            None,
        )
        bindings = next(
            (node.get(key) for key in ("hotkey", "hotkeys", "keys", "binding")
             if key in node),
            None,
        )
        if command_id and bindings is not None:
            add(command_id, bindings)
            return

        if isinstance(node.get("hotkeys"), (list, dict)):
            walk(node["hotkeys"])
            return

        for command, value in node.items():
            if isinstance(value, (str, list, dict)):
                before = len(found)
                add(command, value)
                if len(found) == before and isinstance(value, (list, dict)):
                    walk(value)

    walk(root)
    if not found and root not in ([], {}):
        raise ValueError("无法识别 Obsidian CLI hotkeys JSON 结构；为避免遗漏冲突，已停止。")
    return found


def read_active_hotkeys(cli: str, vault: Path) -> set[tuple[str, str]]:
    result = subprocess.run(
        [str(cli), "hotkeys", "format=json"],
        cwd=str(vault),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "无法读取 Obsidian 当前快捷键列表：" +
            (result.stderr.strip() or result.stdout.strip())
        )
    return parse_hotkeys_json(result.stdout)
