#!/usr/bin/env python3
"""Reject desktop-only runtime dependencies in the Obsidian plugin source."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mobile-plugin" / "src"
PATTERNS = {
    "Node.js builtin import": re.compile(
        r"""(?:from\s*|import\s*\(|require\s*\()\s*["'](?:node:)?(?:assert|buffer|child_process|crypto|events|fs|http|https|module|net|os|path|process|stream|timers|tls|url|util|worker_threads|zlib)(?:/[^"']*)?["']"""
    ),
    "Electron import": re.compile(r"""(?:from\s*|import\s*\(|require\s*\()\s*["']electron["']"""),
    "CommonJS require": re.compile(r"\brequire\s*\("),
    "Node process global": re.compile(r"\bprocess\s*\.\s*(?:env|platform|versions|cwd|exit|argv)\b"),
    "Node Buffer global": re.compile(r"\bBuffer\s*\.\s*(?:from|alloc|isBuffer|byteLength)\b"),
    "Node path globals": re.compile(r"\b__(?:dirname|filename)\b"),
}

def main() -> int:
    failures: list[str] = []
    for path in sorted(SOURCE.rglob("*.ts")):
        source = path.read_text(encoding="utf-8")
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(source):
                line = source.count("\n", 0, match.start()) + 1
                failures.append(f"{path.relative_to(ROOT)}:{line}: {label}")
    if failures:
        print("Mobile runtime source contains forbidden desktop-only APIs:")
        print("\n".join(failures))
        return 1
    print("Mobile runtime source check passed: no Node.js/Electron-only APIs found.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
