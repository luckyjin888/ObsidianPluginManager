#!/usr/bin/env python3
# GPL-3.0-only
"""低请求量检查 Obsidian 社区插件的 GitHub Releases Atom Feed。

本工具使用公开 Atom Feed，而不是 GitHub REST API。它是按需检查器，不是
常驻后台服务，也不保证实时或不限流。不会安装/更新插件，也不读取 Vault。
"""
from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

VERSION = "0.1.0"
USER_AGENT = f"ObsidianPluginManager-ReleaseWatcher/{VERSION}"
TIMEOUT = 15
MAX_FEED_BYTES = 1024 * 1024
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# 订阅源来自插件清单中已声明的 GitHub 仓库。
PLUGINS = (
    ("Obsidian Git", "denolehov/obsidian-git"),
    ("QuickAdd", "chhoumann/quickadd"),
    ("Tasks", "obsidian-tasks-group/obsidian-tasks"),
    ("Excalidraw", "zsviczian/obsidian-excalidraw-plugin"),
    ("Linter", "platers/obsidian-linter"),
    ("Advanced Tables", "tgrosinger/advanced-tables-obsidian"),
    ("Templater", "SilentVoid13/Templater"),
)


def cache_file() -> Path:
    """返回当前用户缓存目录；不在 Vault 或仓库中保存订阅状态。"""
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    elif sys_platform_is_macos():
        root = Path.home() / "Library" / "Caches"
    else:
        root = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return root / "ObsidianPluginManager" / "release-subscriptions.json"


def sys_platform_is_macos() -> bool:
    import sys
    return sys.platform == "darwin"


def load_cache(path: Path) -> dict:
    if path.is_symlink():
        raise RuntimeError(f"缓存文件是符号链接，拒绝读取：{path}")
    if not path.exists():
        return {}
    if not path.is_file():
        raise RuntimeError(f"缓存路径不是普通文件：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"缓存文件无法安全读取：{exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("缓存文件格式无效，预期为 JSON 对象。")
    return data


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.is_symlink():
        raise RuntimeError("缓存目录或文件是符号链接，拒绝写入。")
    fd, temporary = tempfile.mkstemp(prefix=".release-subscriptions-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            if os.path.exists(temporary):
                os.unlink(temporary)
        except OSError:
            pass


def parse_feed(payload: bytes) -> dict | None:
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("Feed 超过 1 MiB 安全读取上限。")
    root = ET.fromstring(payload)
    entry = root.find("atom:entry", ATOM_NS)
    if entry is None:
        return None
    def value(tag: str) -> str:
        node = entry.find(f"atom:{tag}", ATOM_NS)
        return (node.text or "").strip() if node is not None else ""
    link_node = entry.find("atom:link[@rel='alternate']", ATOM_NS)
    if link_node is None:
        link_node = entry.find("atom:link", ATOM_NS)
    link = link_node.get("href", "") if link_node is not None else ""
    return {
        "id": value("id"),
        "title": value("title"),
        "updated": value("updated"),
        "link": link,
    }


def check_one(name: str, repository: str, previous: dict) -> tuple[dict, str]:
    url = f"https://github.com/{repository}/releases.atom"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/xml;q=0.9",
    }
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous.get("last_modified"):
        headers["If-Modified-Since"] = previous["last_modified"]
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = response.read(MAX_FEED_BYTES + 1)
            latest = parse_feed(payload)
            record = dict(previous)
            record["repository"] = repository
            record["checked"] = True
            record["etag"] = response.headers.get("ETag", previous.get("etag", ""))
            record["last_modified"] = response.headers.get(
                "Last-Modified", previous.get("last_modified", "")
            )
            if latest:
                old_id = previous.get("latest", {}).get("id") if isinstance(previous.get("latest"), dict) else None
                record["latest"] = latest
                if old_id is None:
                    status = "baseline"
                elif latest.get("id") and latest.get("id") != old_id:
                    status = "new"
                else:
                    status = "current"
            else:
                record["latest"] = None
                status = "empty"
            return record, status
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            record = dict(previous)
            record["repository"] = repository
            record["checked"] = True
            return record, "not_modified"
        if exc.code in (403, 429):
            retry = exc.headers.get("Retry-After", "") if exc.headers else ""
            suffix = f"；Retry-After={retry}" if retry else ""
            raise RuntimeError(f"GitHub Feed 返回 HTTP {exc.code}，请稍后再试{suffix}") from exc
        raise RuntimeError(f"Feed 请求失败：HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"网络请求失败：{exc}") from exc


def run(cache_path: Path | None = None) -> int:
    path = cache_path or cache_file()
    cache = load_cache(path)
    changed = False
    failures = 0
    print("插件更新订阅检查（GitHub Releases Atom Feed）")
    print("只检查版本发布信息；不会安装、更新插件，也不会读取 Vault。")
    for name, repository in PLUGINS:
        previous = cache.get(repository, {})
        if not isinstance(previous, dict):
            previous = {}
        try:
            record, status = check_one(name, repository, previous)
            cache[repository] = record
            changed = True
            latest = record.get("latest") or {}
            title = latest.get("title") or "暂无公开 Release"
            if status == "new":
                print(f"[发现更新] {name}：{title} {latest.get('link', '')}")
            elif status == "baseline":
                print(f"[已建立订阅基线] {name}：{title}")
            elif status == "not_modified":
                print(f"[无变化] {name}：Feed 未修改")
            elif status == "empty":
                print(f"[暂无发布] {name}")
            else:
                print(f"[当前最新] {name}：{title}")
        except (RuntimeError, ValueError, ET.ParseError) as exc:
            failures += 1
            print(f"[无法检查] {name}：{exc}")
            # 403/429 常是共享限流；不要继续轰炸同一主机。
            if "HTTP 403" in str(exc) or "HTTP 429" in str(exc):
                print("检测到限流，已停止后续 Feed 请求。")
                break
    if changed:
        save_cache(path, cache)
        print(f"订阅缓存已更新：{path}")
    if failures:
        print(f"检查完成：有 {failures} 项未能确认。")
        return 1
    print("检查完成。发现新版本也只通知，不会自动安装或更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
