#!/usr/bin/env python3
"""Validate the shared plugin catalogue without third-party dependencies."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "shared" / "plugin-catalog.json"
STATUSES = {"verified", "declared_unverified", "incompatible", "unknown"}
PLATFORMS = {"windows", "macos", "ios", "ipados", "android"}
PLUGIN_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def validate_catalog(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["catalogue root must be an object"]
    for key in ("catalog_version", "generated_at", "compatibility_policy", "plugins"):
        if key not in data:
            errors.append(f"missing root field: {key}")
    if set(data) != {"catalog_version", "generated_at", "compatibility_policy", "plugins"}:
        errors.append("catalogue root has unknown fields")
    if not isinstance(data.get("catalog_version"), int) or data.get("catalog_version", 0) < 1:
        errors.append("catalog_version must be a positive integer")
    if not isinstance(data.get("generated_at"), str) or not re.fullmatch(r"\d{4}-\\d{2}-\\d{2}", data.get("generated_at", "")):
        errors.append("generated_at must use YYYY-MM-DD")
    policy = data.get("compatibility_policy")
    if not isinstance(policy, dict) or set(policy) != {"statuses", "manifest_warning"}:
        errors.append("compatibility_policy must contain only statuses and manifest_warning")
    else:
        if set(policy.get("statuses", [])) != STATUSES:
            errors.append("compatibility_policy.statuses must list all supported statuses")
        if not isinstance(policy.get("manifest_warning"), str) or not policy["manifest_warning"].strip():
            errors.append("compatibility_policy.manifest_warning must be non-empty")
    plugins = data.get("plugins")
    if not isinstance(plugins, list):
        errors.append("plugins must be an array")
        return errors
    seen: set[str] = set()
    required = {"id", "name", "upstream_url", "manifest_is_desktop_only", "manifest_checked_at", "platforms", "risk_level", "risk_notes", "license", "catalog_notes"}
    for index, plugin in enumerate(plugins):
        prefix = f"plugins[{index}]"
        if not isinstance(plugin, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if set(plugin) != required:
            errors.append(f"{prefix} fields do not match the catalogue contract")
        pid = plugin.get("id")
        if not isinstance(pid, str) or not PLUGIN_ID.fullmatch(pid):
            errors.append(f"{prefix}.id is invalid")
        elif pid in seen:
            errors.append(f"duplicate plugin id: {pid}")
        else:
            seen.add(pid)
        if not isinstance(plugin.get("name"), str) or not plugin["name"].strip():
            errors.append(f"{prefix}.name must be non-empty")
        if plugin.get("upstream_url") is not None and (not isinstance(plugin["upstream_url"], str) or not plugin["upstream_url"].startswith("https://")):
            errors.append(f"{prefix}.upstream_url must be HTTPS or null")
        desktop = plugin.get("manifest_is_desktop_only")
        if desktop not in (True, False, None):
            errors.append(f"{prefix}.manifest_is_desktop_only must be boolean or null")
        checked = plugin.get("manifest_checked_at")
        if checked is not None and (not isinstance(checked, str) or not re.fullmatch(r"\d{4}-\\d{2}-\\d{2}", checked)):
            errors.append(f"{prefix}.manifest_checked_at must be YYYY-MM-DD or null")
        platforms = plugin.get("platforms")
        if not isinstance(platforms, dict) or set(platforms) != PLATFORMS:
            errors.append(f"{prefix}.platforms must define exactly {sorted(PLATFORMS)}")
        else:
            for platform, record in platforms.items():
                pfx = f"{prefix}.platforms.{platform}"
                if not isinstance(record, dict) or not {"status", "evidence"}.issubset(record):
                    errors.append(f"{pfx} must contain status and evidence")
                    continue
                if record.get("status") not in STATUSES:
                    errors.append(f"{pfx}.status is invalid")
                if not isinstance(record.get("evidence"), str) or not record["evidence"].strip():
                    errors.append(f"{pfx}.evidence must be non-empty")
                if record.get("status") == "verified":
                    if not record.get("verified_on") or not record.get("device") or not record.get("obsidian_version"):
                        errors.append(f"{pfx}: verified status requires verified_on, device, and obsidian_version")
        if plugin.get("risk_level") not in {"low", "medium", "high", "unknown"}:
            errors.append(f"{prefix}.risk_level is invalid")
        if not isinstance(plugin.get("risk_notes"), list) or any(not isinstance(note, str) for note in plugin.get("risk_notes", [])):
            errors.append(f"{prefix}.risk_notes must be an array of strings")
        if plugin.get("license") is not None and not isinstance(plugin.get("license"), str):
            errors.append(f"{prefix}.license must be a string or null")
        if not isinstance(plugin.get("catalog_notes"), str):
            errors.append(f"{prefix}.catalog_notes must be a string")
    return errors


def main() -> int:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Cannot read catalogue: {exc}", file=sys.stderr)
        return 2
    errors = validate_catalog(data)
    if errors:
        print("Plugin catalogue validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Plugin catalogue valid: {len(data['plugins'])} plugins, 5 platforms.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
