#!/usr/bin/env python3
"""Validate the Obsidian community-plugin manifest against key public rules."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "mobile-plugin" / "manifest.json"
PACKAGE_PATH = ROOT / "mobile-plugin" / "package.json"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PLUGIN_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        package = json.loads(PACKAGE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read plugin manifest/package metadata: {exc}")

    required = ("id", "name", "version", "minAppVersion", "description", "author", "isDesktopOnly")
    missing = [key for key in required if key not in manifest]
    if missing:
        fail(f"manifest missing required fields: {', '.join(missing)}")

    plugin_id = manifest["id"]
    if not isinstance(plugin_id, str) or not PLUGIN_ID.fullmatch(plugin_id):
        fail("manifest id must contain only lowercase letters, digits, and single hyphen separators")
    if "obsidian" in plugin_id or plugin_id.endswith("plugin"):
        fail("manifest id must not contain 'obsidian' or end with 'plugin'")

    name = manifest["name"]
    if not isinstance(name, str) or not name.strip():
        fail("manifest name must be a non-empty string")
    if "plugin" in name.lower():
        fail("manifest name must not contain the word 'plugin'")

    for key in ("version", "minAppVersion"):
        if not isinstance(manifest[key], str) or not SEMVER.fullmatch(manifest[key]):
            fail(f"manifest {key} must use x.y.z semantic version format")

    description = manifest["description"]
    if not isinstance(description, str) or len(description) > 250 or not description.endswith("."):
        fail("manifest description must be a string of at most 250 characters ending with a period")

    if not isinstance(manifest["author"], str) or not manifest["author"].strip():
        fail("manifest author must be a non-empty string")
    if not isinstance(manifest["isDesktopOnly"], bool):
        fail("manifest isDesktopOnly must be a boolean")

    if package.get("name") != plugin_id:
        fail("package.json name must match manifest id")

    print(f"Mobile plugin manifest is valid: {plugin_id} ({manifest['version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
