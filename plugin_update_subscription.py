#!/usr/bin/env python3
# GPL-3.0-only
"""低请求量检查 Obsidian 社区插件的 GitHub Releases API。

GitHub Token 仅用于本订阅模块的只读 Releases API 请求；不会写入缓存、Vault、
仓库文件或日志。工具只检查版本，不会安装/更新插件，也不读取 Vault。
"""
from __future__ import annotations

import json
import os
import tempfile
import time
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
    ("Obsidian Git", "Vinzent03/obsidian-git"),
    ("QuickAdd", "chhoumann/quickadd"),
    ("Tasks", "obsidian-tasks-group/obsidian-tasks"),
    ("Excalidraw", "zsviczian/obsidian-excalidraw-plugin"),
    ("Linter", "platers/obsidian-linter"),
    ("Advanced Tables", "tgrosinger/advanced-tables-obsidian"),
    ("Templater", "SilentVoid13/Templater"),
    ("Codeblock Customizer", "mugiwara85/CodeblockCustomizer"),
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


def github_api_token() -> str | None:
    """只从本机进程环境读取订阅用 Token；绝不持久化或打印。"""
    for name in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT"):
        token = os.environ.get(name, "").strip()
        if token:
            return token
    return None


def github_api_headers() -> dict:
    """仅供 GitHub Releases 订阅 API 使用。"""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = github_api_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_release(payload: bytes) -> dict:
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("GitHub Release 响应超过 1 MiB 安全读取上限。")
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"GitHub Release 响应不是有效 JSON：{exc}") from exc
    if not isinstance(data, dict) or data.get("id") is None:
        raise ValueError("GitHub Release 响应缺少有效 Release ID。")
    return {
        "id": str(data["id"]),
        "title": (data.get("name") or data.get("tag_name") or "").strip(),
        "updated": data.get("published_at") or data.get("created_at") or "",
        "link": data.get("html_url") or "",
    }


def rate_limit_retry_delay(exc: urllib.error.HTTPError) -> int | None:
    """识别真实限流；普通权限 403 不重试。"""
    headers = exc.headers or {}
    body = ""
    try:
        body = exc.read(4096).decode("utf-8", errors="replace").casefold()
    except Exception:
        pass
    retry_after = headers.get("Retry-After")
    remaining = headers.get("X-RateLimit-Remaining")
    limited = (
        exc.code == 429
        or (exc.code == 403 and (
            str(remaining).strip() == "0"
            or "secondary rate limit" in body
            or "api rate limit exceeded" in body
            or "rate limit exceeded" in body
        ))
    )
    if not limited:
        return None
    if retry_after:
        try:
            return max(1, int(float(retry_after)))
        except (TypeError, ValueError):
            pass
    reset_at = headers.get("X-RateLimit-Reset")
    if reset_at:
        try:
            return max(1, int(float(reset_at) - time.time()))
        except (TypeError, ValueError):
            pass
    return 2


def check_one(name: str, repository: str, previous: dict) -> tuple[dict, str]:
    if not isinstance(repository, str) or not __import__("re").fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository
    ):
        raise ValueError("GitHub 仓库名称格式无效。")
    url = f"https://api.github.com/repos/{repository}/releases/latest"
    headers = github_api_headers()
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous.get("last_modified"):
        headers["If-Modified-Since"] = previous["last_modified"]
    request = urllib.request.Request(url, headers=headers)

    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                latest = parse_release(response.read(MAX_FEED_BYTES + 1))
                record = dict(previous)
                record["repository"] = repository
                record["checked"] = True
                record["etag"] = response.headers.get("ETag", previous.get("etag", ""))
                record["last_modified"] = response.headers.get(
                    "Last-Modified", previous.get("last_modified", "")
                )
                old_id = previous.get("latest", {}).get("id") if isinstance(previous.get("latest"), dict) else None
                record["latest"] = latest
                if old_id is None:
                    status = "new" if previous.get("checked") else "baseline"
                elif latest.get("id") != old_id:
                    status = "new"
                else:
                    status = "current"
                return record, status
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                record = dict(previous)
                record["repository"] = repository
                record["checked"] = True
                return record, "not_modified"
            if exc.code == 404:
                record = dict(previous)
                record.update({"repository": repository, "checked": True, "latest": None})
                return record, "empty"
            if exc.code == 401:
                raise RuntimeError("GitHub API Token 认证失败（HTTP 401）；请检查本机环境变量中的 Token。") from exc
            if exc.code in (403, 429):
                delay = rate_limit_retry_delay(exc)
                if delay is None:
                    raise RuntimeError(f"GitHub Releases API 权限被拒绝（HTTP {exc.code}），不是已确认的限流。") from exc
                if attempt >= 3:
                    raise RuntimeError(f"GitHub Releases API 限流（HTTP {exc.code}），已达到重试上限。") from exc
                if delay > 60:
                    raise RuntimeError(f"GitHub Releases API 限流，建议等待约 {delay} 秒后再订阅；已停止自动重试。") from exc
                time.sleep(delay)
                continue
            raise RuntimeError(f"GitHub Releases API 请求失败：HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"网络请求失败：{exc}") from exc
    raise RuntimeError("GitHub Releases API 请求未能完成。")


def run(cache_path: Path | None = None) -> int:
    path = cache_path or cache_file()
    cache = load_cache(path)
    changed = False
    failures = 0
    print("插件更新订阅检查（GitHub Releases API）")
    print("只检查版本发布信息；不会安装、更新插件，也不会读取 Vault。")
    print("订阅认证：" + ("已检测到本机 Token（仅用于本订阅 API）" if github_api_token() else "未检测到 Token，将使用公开 API 配额。"))
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
            if "HTTP 403" in str(exc) or "HTTP 429" in str(exc) or "API 限流" in str(exc):
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
