#!/usr/bin/env python3
"""Build a flat, installable ZIP for the Obsidian mobile plugin."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

REQUIRED_FILES = ("manifest.json", "main.js")


def build_package(source: Path, output: Path) -> Path:
    source = source.resolve()
    manifest_path = source / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest.json: {exc}") from exc

    plugin_id = manifest.get("id")
    version = manifest.get("version")
    if not isinstance(plugin_id, str) or not plugin_id:
        raise ValueError("manifest.json must contain a non-empty id")
    if not isinstance(version, str) or not version:
        raise ValueError("manifest.json must contain a non-empty version")

    files = [source / name for name in REQUIRED_FILES]
    styles = source / "styles.css"
    if styles.is_file():
        files.append(styles)

    for path in files:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError(f"required package file is missing or empty: {path.name}")

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.name)

    with ZipFile(output) as archive:
        names = set(archive.namelist())
        expected = {path.name for path in files}
        if names != expected:
            raise ValueError(f"unexpected ZIP contents: {sorted(names)}")

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Built plugin directory")
    parser.add_argument("--output", type=Path, help="Output ZIP path; defaults to <source>/dist/<id>-<version>.zip")
    args = parser.parse_args()

    try:
        source = args.source.resolve()
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        output = args.output or (source / "dist" / f"{manifest['id']}-{manifest['version']}.zip")
        package = build_package(source, output)
    except (OSError, KeyError, json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))

    print(f"Created installable plugin package: {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
