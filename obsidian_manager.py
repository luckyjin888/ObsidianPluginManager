#!/usr/bin/env python3
# ObsidianPluginManager 0.6.0
# GPL-3.0-only
"""Cross-platform, consent-first Obsidian plugin inventory and heuristic audit."""
from __future__ import annotations
import json, os, platform, re, shutil, subprocess, sys, ssl, time, urllib.error, urllib.request
from pathlib import Path
from datetime import datetime, timezone

VERSION = "0.6.1"
MIN_CLI = (1, 12, 7)
REGISTRY_URL = "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json"
NETWORK_TIMEOUT = 8

def say(s=""):
    """跨平台安全输出；终端编码不支持中文时回退到 UTF-8 字节流。"""
    message = str(s)
    try:
        print(message)
        return
    except UnicodeEncodeError:
        # Windows CI / 重定向终端有时使用 cp1252 等不支持中文的编码。
        # 优先向底层字节流写 UTF-8，避免中文输出导致程序和测试中断。
        stream = sys.stdout
        payload = (message + "\n").encode("utf-8", errors="backslashreplace")
        try:
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                buffer.write(payload)
                buffer.flush()
                return
        except (OSError, ValueError, AttributeError):
            pass
        # 对没有 buffer 的测试替身或特殊终端，使用当前编码的安全替代字符。
        encoding = getattr(stream, "encoding", None) or "ascii"
        safe_message = message.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
        print(safe_message)
def ask(prompt):
    try: return input(prompt).strip()
    except (EOFError, KeyboardInterrupt): say("\n已取消。"); return ""

def ask_yes_no(prompt):
    """统一二选一：1=是/继续，2=否/跳过；空输入按否处理。"""
    while True:
        answer = ask(prompt + "（1=是 / 2=否）：")
        if answer == "1": return True
        if answer in ("2", ""): return False
        say("请输入 1 或 2。")

def select_numbered(items, exclude_all_ids=()):
    """编号选择；all 会排除指定高风险项，直接输入序号仍可明确选择。"""
    for i, item in enumerate(items, 1):
        say(f'{i}. {item["name"]}（{item["id"]}）')
        say(f'   用途：{item.get("purpose","")}')
        say(f'   风险：{item.get("risk","")}')
    raw = ask("输入 all 选择普通插件（自动排除高风险项），或输入序号选择；直接回车跳过：")
    if not raw: return []
    if raw.lower() in ("all", "全部"):
        excluded = set(exclude_all_ids)
        chosen = [item for item in items if item.get("id") not in excluded]
        omitted = [item for item in items if item.get("id") in excluded]
        if omitted:
            say("输入 all 已自动排除高风险插件：" + "、".join(item["name"] for item in omitted))
        return chosen
    try:
        indexes = list(dict.fromkeys(int(x.strip()) for x in raw.split(",") if x.strip()))
    except ValueError:
        say("输入格式不正确，已跳过。"); return []
    if not indexes or any(i < 1 or i > len(items) for i in indexes):
        say(f"序号无效，请输入 1 到 {len(items)} 之间的编号；本次已跳过。"); return []
    return [items[i-1] for i in indexes]

def version_tuple(s):
    nums = re.findall(r"\d+", str(s or ""))
    return tuple((list(map(int, nums[:3])) + [0,0,0])[:3])

def read_json(path):
    try:
        with path.open("r", encoding="utf-8") as f: return json.load(f)
    except Exception: return None

def platform_name():
    return {"Darwin":"macOS", "Windows":"Windows", "Linux":"Linux"}.get(platform.system(), platform.system())

def windows_drive_roots():
    """Return mounted Windows drive roots without recursively scanning disks."""
    if platform.system() != "Windows":
        return []
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [Path(f"{chr(65 + i)}:\\") for i in range(26) if mask & (1 << i)]
    except Exception:
        # Fallback for restricted environments: probe drive roots only.
        return [Path(f"{chr(65 + i)}:\\") for i in range(26)
                if Path(f"{chr(65 + i)}:\\").is_dir()]



def windows_registered_obsidian_paths():
    """Read installer and App Paths registry entries; never write to registry."""
    if platform.system() != "Windows":
        return []
    found = []
    try:
        import winreg
        uninstall_keys = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        for hive, base in uninstall_keys:
            try:
                with winreg.OpenKey(hive, base) as root:
                    for index in range(winreg.QueryInfoKey(root)[0]):
                        try:
                            with winreg.OpenKey(root, winreg.EnumKey(root, index)) as item:
                                values = {}
                                for name in ("DisplayName", "InstallLocation", "DisplayIcon"):
                                    try:
                                        values[name] = winreg.QueryValueEx(item, name)[0]
                                    except OSError:
                                        pass
                            if "obsidian" not in str(values.get("DisplayName", "")).lower():
                                continue
                            location = str(values.get("InstallLocation", "")).strip().strip('"')
                            if location:
                                found.append(Path(os.path.expandvars(location)))
                            icon = str(values.get("DisplayIcon", "")).strip().strip('"')
                            if icon.lower().endswith("obsidian.exe"):
                                found.append(Path(os.path.expandvars(icon)).parent)
                        except OSError:
                            continue
            except OSError:
                continue
        app_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths\Obsidian.exe"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths\Obsidian.exe"),
        ]
        for hive, key in app_paths:
            try:
                with winreg.OpenKey(hive, key) as item:
                    exe = winreg.QueryValueEx(item, None)[0]
                    found.append(Path(os.path.expandvars(str(exe).strip('"'))).parent)
            except OSError:
                continue
    except Exception:
        pass
    return found


def windows_running_obsidian_paths():
    """Read the executable path of a running Obsidian process using PowerShell."""
    if platform.system() != "Windows":
        return []
    command = [
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
        "$p = Get-Process -Name Obsidian -ErrorAction SilentlyContinue; "
        "if ($p) { $p | ForEach-Object { $_.Path } }"
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=5, check=False)
        if result.returncode == 0:
            return [Path(line.strip()).parent for line in result.stdout.splitlines()
                    if line.strip().lower().endswith("obsidian.exe")]
    except Exception:
        pass
    return []


def is_obsidian_install(path):
    """Validate a platform-specific Obsidian application layout, not mere path existence."""
    try:
        candidate = Path(path).expanduser()
        system = platform.system()
        if system == "Windows":
            if candidate.is_file() and candidate.name.lower() == "obsidian.exe":
                return candidate.parent
            if candidate.is_dir() and (candidate / "Obsidian.exe").is_file():
                return candidate
            return None
        if system == "Darwin":
            if candidate.suffix != ".app" or not candidate.is_dir():
                return None
            info = candidate / "Contents" / "Info.plist"
            executable = candidate / "Contents" / "MacOS" / "Obsidian"
            if info.is_file() and executable.is_file() and os.access(executable, os.X_OK):
                return candidate
            return None
        if system == "Linux":
            if candidate.is_file():
                if not os.access(candidate, os.X_OK):
                    return None
                candidate = candidate.resolve().parent
            if not candidate.is_dir():
                return None
            resources = candidate / "resources"
            executable = next(
                (p for p in (candidate / "obsidian", candidate / "Obsidian")
                 if p.is_file() and os.access(p, os.X_OK)),
                None,
            )
            if executable and (resources / "app.asar").is_file():
                return candidate
    except (OSError, TypeError, ValueError):
        pass
    return None

def find_obsidian():
    system = platform.system()
    candidates = []
    if system == "Darwin":
        candidates = [Path("/Applications/Obsidian.app"), Path.home()/"Applications/Obsidian.app"]
    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        roots = [
            os.environ.get("ProgramFiles", ""),
            os.environ.get("ProgramFiles(x86)", ""),
            os.environ.get("ProgramW6432", ""),
        ]
        if local_app_data:
            candidates.extend([
                Path(local_app_data)/"Programs"/"Obsidian",
                Path(local_app_data)/"Obsidian",
            ])
        candidates.extend(Path(root)/"Obsidian" for root in roots if root)
        # Registry and running-process discovery cover many custom install paths.
        candidates.extend(windows_running_obsidian_paths())
        candidates.extend(windows_registered_obsidian_paths())
        # Also probe common locations on every mounted drive, without recursive scanning.
        for drive in windows_drive_roots():
            candidates.extend([
                drive/"Program Files"/"Obsidian",
                drive/"Program Files (x86)"/"Obsidian",
                drive/"Obsidian",
                drive/"Apps"/"Obsidian",
                drive/"Applications"/"Obsidian",
            ])
        seen = set()
        for candidate in candidates:
            key = str(candidate).lower()
            if key in seen:
                continue
            seen.add(key)
            match = is_obsidian_install(candidate)
            if match:
                return match
        return None
    elif system == "Linux":
        for name in ("obsidian", "Obsidian"):
            found = shutil.which(name)
            if found:
                executable = Path(found).resolve()
                candidates.extend([executable, executable.parent, executable.parent.parent])
        candidates += [Path("/usr/share/obsidian"), Path("/opt/Obsidian"), Path.home()/".local/share/Obsidian"]
    for candidate in candidates:
        match = is_obsidian_install(candidate)
        if match:
            return match
    return None

def prompt_manual_obsidian_path(app):
    """Offer a manual install path when Windows auto-discovery fails."""
    if platform.system() != "Windows" or app:
        return app
    say("自动定位未成功。你可以输入 Obsidian 安装目录，或 Obsidian.exe 的完整路径。")
    say("此步骤只检查路径和文件是否存在，不会修改应用或系统设置。")
    raw = ask("Obsidian 安装目录（留空跳过）：")
    if not raw:
        return None
    raw = os.path.expandvars(os.path.expanduser(raw.strip().strip('"').strip("'")))
    match = is_obsidian_install(raw)
    if match:
        say(f"已确认 Obsidian 应用位置：{match}")
        return match
    say("该路径中未找到 Obsidian.exe；请检查路径后重试。")
    return None

def app_version(app):
    system = platform.system()
    if system == "Darwin":
        plist = app/"Contents/Info.plist"
        if plist.exists():
            try:
                out = subprocess.check_output(["/usr/libexec/PlistBuddy","-c","Print :CFBundleShortVersionString",str(plist)], text=True, stderr=subprocess.DEVNULL)
                return out.strip()
            except Exception: pass
    if system == "Windows":
        for f in (app/"Obsidian.exe", app/"Obsidian.com"):
            if f.exists():
                # File version is not reliably available in the Python standard library.
                break
    return "未知（无法通过标准库可靠读取）"

def cli_candidates(app):
    system = platform.system()
    if system == "Darwin": return [app/"Contents/MacOS/obsidian-cli"]
    if system == "Windows":
        # Obsidian.com is the CLI shim. Obsidian.exe is the GUI and must never
        # be copied/renamed as a command-line executable.
        return [app/"Obsidian.com"]
    # The top-level "obsidian" binary is commonly the GUI launcher, not a CLI shim.
    return [app/"obsidian-cli", app/"resources/app.asar.unpacked/obsidian"]

def is_valid_cli_source(app, source):
    """Only register an executable located at a platform-specific bundled CLI path."""
    try:
        app_root = Path(app).expanduser().resolve(strict=True)
        source_path = Path(source).expanduser()
        if source_path.is_symlink():
            return False
        candidate = source_path.resolve(strict=True)
        if not candidate.is_relative_to(app_root):
            return False
        allowed = {p.resolve(strict=True) for p in cli_candidates(Path(app))
                   if p.is_file() and not p.is_symlink()}
        if candidate not in allowed or not candidate.is_file():
            return False
        if platform.system() in ("Darwin", "Linux"):
            return os.access(candidate, os.X_OK)
        return platform.system() == "Windows" and candidate.name.lower() == "obsidian.com"
    except (OSError, TypeError, ValueError):
        return False

def explain_cli_registration(target, source, action):
    say("\n【标准专业版】")
    say(f"目的：让当前用户可以在终端输入 obsidian。将{action}：{target}")
    say(f"来源程序：{source}")
    say("权限：仅当前用户目录，不使用 sudo、不申请管理员权限。")
    say("影响：创建或替换一个名为 obsidian 的命令入口；不会修改 Vault、笔记或插件。")
    say("风险：若目标位置已有同名文件，将先停止，不覆盖；CLI 运行时可能启动 Obsidian。")
    say("恢复：删除本次创建的入口即可；不会删除 Obsidian 应用。")
    say("\n【10岁儿童比喻版】")
    say("就像在你自己的书桌抽屉里放一个快捷按钮，让你更容易叫出 Obsidian。")
    say("只动自己的抽屉，不进管理员办公室；如果抽屉里已有同名东西，我们就停下来不碰它。")
    say("这个按钮不会改你的笔记，但按下去时 Obsidian 可能会启动。")
    return ask_yes_no("\n是否同意执行以上 CLI 注册？")

def register_cli(app, source):
    if not is_valid_cli_source(app, source):
        say(f"CLI 来源验证失败：{source}；未注册任何命令入口。")
        return False
    bindir = Path.home()/".local"/"bin"
    target = bindir/("obsidian.com" if platform.system() == "Windows" else "obsidian")
    if target.exists() or target.is_symlink():
        say(f"目标已存在，出于安全考虑不覆盖：{target}")
        return False
    action = "创建符号链接" if platform.system() == "Darwin" else "复制 CLI 程序"
    if not explain_cli_registration(target, source, action): say("未获同意，未执行注册。"); return False
    try:
        bindir.mkdir(parents=True, exist_ok=True)
        if platform.system() == "Darwin": target.symlink_to(source)
        else:
            shutil.copy2(source, target)
            if platform.system() != "Windows":
                target.chmod(0o755)
        say(f"注册入口已创建：{target}")
        if str(bindir) not in os.environ.get("PATH","").split(os.pathsep):
            say(f"注意：{bindir} 当前不在 PATH 中。注册文件已创建，但终端可能仍找不到 obsidian。")
            if platform.system() == "Windows":
                say("Windows：请在“环境变量 → 用户变量 → Path”中手动添加上述目录，然后重新打开终端。")
            else:
                say("macOS/Linux：将以下内容加入你正在使用的 shell 配置文件（例如 ~/.zshrc 或 ~/.bashrc）：")
                say('  export PATH="$HOME/.local/bin:$PATH"')
        return True
    except Exception as e:
        say(f"注册失败：{e}")
        say("未尝试提权或绕过系统安全机制。")
        return False

def ssl_context_candidates():
    """Build verified HTTPS contexts using native and portable CA sources.

    No context disables certificate validation. Optional truststore uses the OS
    trust store; Python's default context is retained; certifi is a fallback.
    """
    candidates = []
    errors = []

    try:
        import truststore
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        candidates.append(("操作系统证书库（truststore）", context))
    except ImportError:
        errors.append("truststore 未安装（可选）")
    except Exception as exc:
        errors.append(f"truststore 不可用：{exc}")

    try:
        context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        candidates.append(("Python 默认可信证书库", context))
    except Exception as exc:
        errors.append(f"Python 默认证书库不可用：{exc}")

    try:
        import certifi
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH, cafile=certifi.where()
        )
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        candidates.append(("certifi CA 证书包", context))
    except ImportError:
        errors.append("certifi 未安装（可选）")
    except Exception as exc:
        errors.append(f"certifi 证书包不可用：{exc}")

    if not candidates:
        details = "；".join(errors) or "没有可用证书来源"
        raise RuntimeError("无法建立经过验证的 HTTPS 证书上下文：" + details)
    return candidates


def is_certificate_verification_error(exc):
    """Recognize certificate-validation failures wrapped by urllib."""
    seen = set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        if isinstance(current, ssl.SSLError) and "CERTIFICATE_VERIFY_FAILED" in str(current):
            return True
        if isinstance(current, urllib.error.URLError):
            reason = current.reason
            # URLError.reason may be an exception (e.g. certificate failure)
            # or a plain string (e.g. "timeout"/"network unavailable").
            current = reason if isinstance(reason, BaseException) else None
        elif isinstance(current, BaseException):
            current = current.__cause__ or current.__context__
        else:
            current = None
    return False


def open_verified_https(request):
    """Open HTTPS using verified contexts; retry only certificate-source failures."""
    candidates = ssl_context_candidates()
    failures = []
    for label, context in candidates:
        # Defensive invariant: every attempted context must validate both chain
        # and hostname. Never weaken TLS to make a request succeed.
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise RuntimeError(f"安全检查失败：{label} 未启用完整证书与主机名验证；已停止联网。")
        try:
            return urllib.request.urlopen(
                request, timeout=NETWORK_TIMEOUT, context=context
            )
        except Exception as exc:
            if not is_certificate_verification_error(exc):
                raise
            failures.append(f"{label}：{exc}")

    paths = ssl.get_default_verify_paths()
    path_info = (
        f"OpenSSL 默认 CA 文件={paths.cafile or '未设置'}；"
        f"CA 目录={paths.capath or '未设置'}"
    )
    attempted = "；".join(failures) if failures else "没有成功建立可用证书上下文"
    raise ssl.SSLCertVerificationError(
        "HTTPS 证书验证失败，已尝试所有可用的可信证书来源。"
        + attempted
        + "。"
        + path_info
        + "。未关闭证书验证，已停止本次联网核验。"
        + "建议更新操作系统根证书；Conda 环境可更新 ca-certificates、certifi、openssl；"
        + "也可在当前 Python 环境安装/更新可选组件：python -m pip install -U truststore certifi。"
    )


def fetch_json_https(request):
    with open_verified_https(request) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_registry():
    req = urllib.request.Request(
        REGISTRY_URL,
        headers={"User-Agent": f"ObsidianPluginManager/{VERSION}"}
    )
    data = fetch_json_https(req)
    return {str(x.get("id","")):x for x in data if isinstance(x,dict) and x.get("id")}


def fetch_repo_status(repo):
    repo = re.sub(r"^https?://github.com/","",str(repo or "").strip()).strip("/")
    repo = re.sub(r"\.git$","",repo)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo): return None
    url = "https://api.github.com/repos/"+repo
    req = urllib.request.Request(
        url,
        headers={"User-Agent": f"ObsidianPluginManager/{VERSION}",
                 "Accept":"application/vnd.github+json"}
    )
    return fetch_json_https(req)

PATTERNS = {
 "网络通信": (r"\bfetch\s*\(", r"XMLHttpRequest", r"\bWebSocket\s*\(", r"\bhttps?\.request\s*\(", r"\baxios\b"),
 "本地文件访问": (r"\breadFile\s*\(", r"\bwriteFile\s*\(", r"\bfs\.", r"vault\.adapter", r"getAbstractFileByPath"),
 "系统命令/进程": (r"child_process", r"\bexec\s*\(", r"\bspawn\s*\(", r"shelljs", r"node-pty"),
 "动态代码执行": (r"\beval\s*\(", r"new Function\s*\(", r"WebAssembly"),
 "凭据/环境访问": (r"process\.env", r"keychain", r"credential", r"localStorage", r"sessionStorage")
}

def scan_source(plugin_dir, *, max_files=500, max_file_size=2_000_000,
                max_total_bytes=50_000_000):
    """Scan JavaScript deterministically within explicit file-count and byte budgets.

    Returns (findings, stats). Files skipped by a limit or filesystem error are
    reported so a partial scan is never presented as a complete clean result.
    """
    findings = []
    stats = {
        "discovered": 0, "scanned": 0, "skipped": 0,
        "errors": [], "bytes_scanned": 0,
        "max_files": max_files, "max_file_size": max_file_size,
        "max_total_bytes": max_total_bytes,
    }
    try:
        files = sorted(plugin_dir.rglob("*.js"), key=lambda p: p.as_posix().casefold())
    except OSError as exc:
        stats["errors"].append(f"无法枚举 JavaScript 文件：{exc}")
        return findings, stats

    stats["discovered"] = len(files)
    for index, file in enumerate(files):
        if index >= max_files:
            stats["skipped"] += len(files) - index
            break
        try:
            if file.is_symlink():
                stats["skipped"] += 1
                stats["errors"].append(f"符号链接文件不纳入扫描：{file}")
                continue
            size = file.stat().st_size
            if size > max_file_size:
                stats["skipped"] += 1
                stats["errors"].append(f"超过单文件大小上限，已跳过：{file}")
                continue
            remaining = max_total_bytes - stats["bytes_scanned"]
            # Read at most one byte beyond the remaining budget, so a file
            # that grows after stat() cannot exceed the configured memory budget.
            with file.open("rb") as handle:
                raw = handle.read(min(max_file_size, remaining) + 1)
            if len(raw) > max_file_size:
                stats["skipped"] += 1
                stats["errors"].append(f"读取期间文件超过单文件大小上限，已跳过：{file}")
                continue
            if len(raw) > remaining:
                stats["skipped"] += len(files) - index
                stats["errors"].append("达到总读取字节上限；剩余文件未扫描。")
                break
            source = raw.decode("utf-8", errors="replace")
            stats["bytes_scanned"] += len(raw)
            stats["scanned"] += 1
        except OSError as exc:
            stats["skipped"] += 1
            stats["errors"].append(f"读取失败，已跳过 {file}：{exc}")
            continue
        for category, patterns in PATTERNS.items():
            hits = [pattern for pattern in patterns if re.search(pattern, source, re.I)]
            if hits:
                findings.append((category, file.name, hits))
    return findings, stats

def ensure_vault_plugin_dirs(vault):
    """创建 Vault 基础目录；失败时尽力回滚本次新建且仍为空的目录。"""
    vault = Path(vault)
    if not vault.is_dir():
        say(f"Vault 路径不存在或不是文件夹：{vault}")
        return False

    config_dir = vault / ".obsidian"
    plugin_dir = config_dir / "plugins"
    targets = (
        (config_dir, ".obsidian 配置目录"),
        (plugin_dir, "plugins 插件目录"),
    )
    created = []
    try:
        for directory, label in targets:
            # 拒绝普通链接和失效链接，避免把写入引导到 Vault 以外。
            if directory.is_symlink():
                raise ValueError(f"{label}不能是符号链接：{directory}")
            if directory.exists():
                if not directory.is_dir():
                    raise ValueError(f"{label}路径存在但不是文件夹：{directory}")
                say(f"已存在，保留不变：{directory}")
                continue
            try:
                directory.mkdir()
                created.append(directory)
                say(f"已自动创建缺失目录：{directory}")
            except FileExistsError:
                # 允许并发创建者先完成同一路径，但必须重新验证对象类型。
                if directory.is_symlink() or not directory.is_dir():
                    raise ValueError(f"目标路径已存在但不是安全的普通文件夹：{directory}")
                say(f"目录已由其他进程创建，保留不变：{directory}")
    except (OSError, ValueError) as exc:
        say(f"初始化失败：{exc}")
        # 仅删除本次创建、且仍为空的目录；任何已有内容都不会被删除。
        for directory in reversed(created):
            try:
                directory.rmdir()
                say(f"已回滚本次创建的空目录：{directory}")
            except OSError:
                say(f"未能回滚（目录可能已有其他内容），请人工检查：{directory}")
        return False

    say("【标准专业版】缺失的 Vault 基础目录已补齐；若中途失败，会尝试移除本次创建且仍为空的目录。已有内容不会删除。")
    say("【10岁儿童比喻版】搭工具柜时如果第二步失败，会尝试拆掉刚搭好且空空的第一层；如果里面已经有东西，就不会拆。")
    say("本步骤只创建空目录，不安装、启用、删除或上传任何插件/笔记。")
    return True

def audit_plugins(vault):
    cfg = vault/".obsidian"
    plugin_root = cfg/"plugins"
    enabled = read_json(cfg/"community-plugins.json")
    enabled_set = (
        {item for item in enabled if isinstance(item, str) and item}
        if isinstance(enabled, list) else None
    )
    invalid_enabled_entries = (
        [item for item in enabled if not isinstance(item, str) or not item]
        if isinstance(enabled, list) else []
    )
    if not plugin_root.is_dir():
        say("没有找到 .obsidian/plugins 目录。"); return
    dirs = sorted([p for p in plugin_root.iterdir() if p.is_dir()], key=lambda p:p.name.lower())
    say(f"\n发现插件目录：{len(dirs)} 个")
    say("启用状态来源：.obsidian/community-plugins.json（缺失或格式异常时标为未知）")
    if invalid_enabled_entries:
        say(f"启用列表含 {len(invalid_enabled_entries)} 条非字符串/空值；已忽略这些异常项，其余有效 ID 仍可正常盘点。")
    say("网络核验会向 Obsidian 官方 GitHub 社区插件目录及插件声明的 GitHub 仓库发送只读请求。不会上传 Vault 或笔记内容。")
    do_network = True
    say("自动进行在线来源与维护状态只读核验；不会上传 Vault 或笔记内容。")
    registry = None
    if do_network:
        try: registry = fetch_registry(); say(f"已读取官方社区插件目录：{len(registry)} 条记录")
        except Exception as e: say(f"官方目录读取失败：{e}")
    counts = {"启用":0,"禁用":0,"未知":0}
    for p in dirs:
        manifest_path = p / "manifest.json"
        manifest_data = read_json(manifest_path)
        manifest = manifest_data if isinstance(manifest_data, dict) else {}
        pid = str(manifest.get("id") or p.name)
        name = manifest.get("name", p.name)
        if enabled_set is None: state = "未知"
        else: state = "启用" if pid in enabled_set else "禁用"
        counts[state] += 1
        say("\n" + "-"*58)
        say(f"{name}  [{pid}]")
        say(f"版本：{manifest.get('version','未知')} | 作者：{manifest.get('author','未知')} | 状态：{state}")
        say(f"最低 Obsidian 版本：{manifest.get('minAppVersion','未声明')}")
        if not manifest_path.is_file():
            say("插件信息不完整：未找到 manifest.json，无法确认插件名称和版本")
        elif not isinstance(manifest_data, dict):
            say("插件信息异常：manifest.json 不是有效的 JSON 对象，插件元数据无法确认")
        if registry is not None:
            if pid in registry: say("官方目录：找到匹配记录（不等于安全认证）")
            else: say("官方目录：未找到匹配 ID（可能是非官方、已下架或 ID 不一致）")
        repo = manifest.get("fundingUrl") or manifest.get("repo") or ""
        # Repository is taken from plugin manifest only; no arbitrary page is executed.
        if do_network and manifest.get("repo"):
            try:
                info = fetch_repo_status(manifest.get("repo"))
                if info:
                    pushed = info.get("pushed_at") or "未知"
                    say(f"GitHub：{info.get('full_name','')} | 最近推送：{pushed} | 归档：{info.get('archived',False)}")
                else: say("GitHub：manifest 未提供可识别的仓库地址")
            except Exception as e: say(f"GitHub 状态：无法确认（{e}）")
        findings, scan_stats = scan_source(p)
        say(
            f"静态扫描范围：发现 {scan_stats['discovered']} 个 JS 文件，"
            f"已扫描 {scan_stats['scanned']} 个，跳过 {scan_stats['skipped']} 个，"
            f"读取 {scan_stats['bytes_scanned']} 字节。"
        )
        for scan_error in scan_stats["errors"]:
            say(f"扫描限制/异常：{scan_error}")
        if findings:
            say("自动初筛发现的代码能力线索（不是恶意判定，无需用户逐条审代码）：")
            for category, filename, hits in findings:
                say(f"  - {category}：{filename}（命中 {', '.join(hits)}）")
        else: say("静态代码线索：未命中本工具的规则（不代表没有风险）")
        risk = "发现需要留意的风险线索" if findings or state=="未知" or not (p/"manifest.json").is_file() else "初筛未发现规则命中（不代表绝对安全）"
        say(f"初步结论：{risk}")
    say("\n" + "="*58)
    say(f"插件统计：总数 {len(dirs)} | 启用 {counts['启用']} | 禁用 {counts['禁用']} | 未知 {counts['未知']}")
    say("自动初筛仅提供风险提示，不要求普通用户自行审查源代码；它不能证明插件绝对安全，也不能完整理解混淆、动态加载或运行时行为。是否启用由用户根据用途和风险提示决定。")
    say("“官方目录匹配”仅代表目录中存在对应 ID，不代表 Obsidian 或 GitHub 对插件作出安全背书。")

def is_cli_not_enabled(result):
    """Recognize Obsidian's explicit CLI-disabled response without masking other errors."""
    output = "\n".join((
        str(getattr(result, "stdout", "") or ""),
        str(getattr(result, "stderr", "") or ""),
    )).casefold()
    markers = (
        "command line interface is not enabled",
        "command-line interface is not enabled",
        "command line interface isn't enabled",
        "command-line interface isn't enabled",
        "command line interface has not been enabled",
        "please turn it on in settings > general > advanced",
    )
    return any(marker in output for marker in markers)


def obsidian_is_running():
    """Return whether the Obsidian desktop process is already running."""
    system = platform.system()
    try:
        if system == "Darwin":
            result = subprocess.run(
                ["pgrep", "-x", "Obsidian"], capture_output=True, text=True,
                timeout=5, check=False,
            )
            return result.returncode == 0
        if system == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5, check=False,
            )
            return "Obsidian.exe" in result.stdout
        for process_name in ("obsidian", "Obsidian"):
            result = subprocess.run(
                ["pgrep", "-x", process_name], capture_output=True, text=True,
                timeout=5, check=False,
            )
            if result.returncode == 0:
                return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def launch_obsidian(app):
    """Launch or focus Obsidian; the app itself restores its previously used Vault."""
    if not app:
        say("没有定位到 Obsidian 应用，无法自动启动。")
        return False
    if obsidian_is_running():
        say("Obsidian 已经运行；不重复启动，继续使用当前窗口。")
        return True
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", "-a", str(app)])
        elif system == "Windows":
            executable = Path(app) / "Obsidian.exe"
            if not executable.is_file():
                say(f"找不到 Obsidian 启动程序：{executable}")
                return False
            subprocess.Popen([str(executable)], cwd=str(app))
        elif system == "Linux":
            executable = next(
                (p for p in (Path(app) / "obsidian", Path(app) / "Obsidian")
                 if p.is_file() and os.access(p, os.X_OK)),
                None,
            )
            if executable is None:
                say(f"找不到可执行的 Obsidian 程序：{app}")
                return False
            subprocess.Popen([str(executable)], cwd=str(app))
        else:
            say("当前系统不支持自动启动 Obsidian。")
            return False
        say("已请求启动 Obsidian；等待应用和上次使用的 Vault 就绪……")
        return True
    except OSError as exc:
        say(f"启动 Obsidian 失败：{exc}")
        return False


def active_vault_path(cli):
    """Read the path of the Vault currently active in Obsidian; never guess."""
    try:
        result = subprocess.run(
            [str(cli), "vault", "info=path"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        say(f"无法读取 Obsidian 当前仓库：{exc}")
        return None
    if result.returncode != 0:
        if result.stderr.strip():
            say("读取当前仓库失败：" + result.stderr.strip())
        return None
    output = (result.stdout or "").strip()
    candidates = []
    for line in output.splitlines():
        value = line.strip()
        if value.casefold().startswith("path "):
            candidates.append(value[5:].strip().strip('"'))
        elif value.casefold().startswith("path:"):
            candidates.append(value.split(":", 1)[1].strip().strip('"'))
        elif value.startswith(("/", "~")):
            candidates.append(value.strip('"'))
    for value in reversed(candidates):
        path = Path(os.path.expanduser(value))
        if path.is_dir():
            return path.resolve()
    return None


def open_vault_chooser():
    """Open Obsidian's own Vault chooser; the user makes the selection."""
    uri = "obsidian://choose-vault"
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", uri])
        elif system == "Windows":
            os.startfile(uri)
        elif system == "Linux":
            subprocess.Popen(["xdg-open", uri])
        else:
            return False
        say("已打开 Obsidian 仓库选择器。请在 Obsidian 中亲自选择要使用的 Vault。")
        return True
    except (OSError, AttributeError) as exc:
        say(f"无法打开 Obsidian 仓库选择器：{exc}")
        return False


def check_cli_available(cli, wait_timeout=0):
    """Run harmless CLI help; optionally wait for the just-launched app to become ready."""
    say("正在检查 Obsidian 命令行功能（obsidian help）……")
    deadline = time.monotonic() + max(0, wait_timeout)
    while True:
        try:
            result = subprocess.run(
                [str(cli), "help"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=15, check=False,
            )
        except subprocess.TimeoutExpired:
            say("CLI 检查超时。为避免进入无法确认的安装流程，程序已停止；未扫描 Vault、未安装或启用插件。")
            return False
        except OSError as exc:
            say(f"无法启动 Obsidian CLI：{exc}")
            say("程序已停止；未扫描 Vault、未安装或启用插件。请检查 CLI 路径后重新运行。")
            return False
        if is_cli_not_enabled(result):
            explain_cli_not_enabled()
            return False
        if result.returncode == 0:
            say("Obsidian CLI 检查通过，可以继续。")
            return True
        output = "\n".join((result.stdout or "", result.stderr or ""))
        not_ready = "the cli is unable to find obsidian" in output.casefold()
        if not_ready and time.monotonic() < deadline:
            time.sleep(1)
            continue
        if result.stdout.strip():
            say("CLI 输出：" + result.stdout.strip())
        if result.stderr.strip():
            say("CLI 错误：" + result.stderr.strip())
        if not_ready:
            say("等待 Obsidian 启动后仍无法连接 CLI。程序已停止；未扫描 Vault、未安装或启用插件。")
        else:
            say(f"CLI 检查未通过（退出码 {result.returncode}）。程序已停止；未扫描 Vault、未安装或启用插件。")
        return False

def explain_cli_not_enabled():
    """Guide the user to enable the official Obsidian CLI switch; do not change settings."""
    say("\n" + "=" * 58)
    say("【标准专业版】")
    say("原因：Obsidian CLI 命令已被调用，但 Obsidian 应用内的“命令行界面”开关尚未启用。")
    say("处理：打开 Obsidian → Settings（设置）→ General（通用）→ Advanced（高级）→")
    say("开启 Command line interface（命令行界面）。如果 Obsidian 显示注册 CLI 命令的提示，请按应用内说明完成。")
    say("权限与影响：这只是 Obsidian 应用内的功能开关；本工具不会代替你修改设置，不需要 sudo 或管理员权限。")
    say("安全处理：已停止当前插件安装/启用流程，不会继续批量操作。开启后请重新运行检查，并先核对插件文件是否已部分写入。")
    say("\n【10岁儿童比喻版】")
    say("脚本已经找到 Obsidian 的遥控器，但 Obsidian 还没打开“允许遥控”的开关。")
    say("请打开 Obsidian，按“设置 → 通用 → 高级”，找到“命令行界面”并打开。")
    say("我们不会偷偷替你按开关；开关打开前，先暂停安装，避免重复放东西。")
    image_path = Path(__file__).resolve().parent / "docs" / "images" / "enable-obsidian-cli.svg"
    display_cli_setup_diagram(image_path)


def display_cli_setup_diagram(image_path):
    """Show the setup guide in the terminal and open the original SVG image."""
    say("\n【终端设置示意图】")
    chafa = shutil.which("chafa")
    rendered = False
    if chafa and image_path.is_file():
        try:
            result = subprocess.run(
                [chafa, "--size", "72x24", str(image_path)],
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=10, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                say(result.stdout.rstrip())
                say("（chafa 已将项目 SVG 转换为终端字符图；原始 SVG 保持不变。）")
                rendered = True
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not rendered:
        if not image_path.is_file():
            say("原始 SVG 示意图文件不存在，以下显示文字版路径。")
        else:
            say("未检测到可用的 chafa 图像转换工具，使用内置字符示意图。")
            say("如需彩色终端效果，可自行安装 chafa；本程序不会替你安装。")
        say("+--------------------------------------------------------------+")
        say("|                    Obsidian · 设置                           |")
        say("|  左侧菜单                    右侧设置                        |")
        say("|  +------------------+       +-----------------------------+  |")
        say("|  | 编辑器           |       | 高级设置                    |  |")
        say("|  | > 通用           | ----> | 命令行界面                  |  |")
        say("|  |   外观           |       | 允许命令行工具与 Obsidian   |  |")
        say("|  |   快捷键         |       | 进行交互                    |  |")
        say("|  | > 高级           |       |                             |  |")
        say("|  +------------------+       |      [ 请打开这个开关 ]     |  |")
        say("|                             +-----------------------------+  |")
        say("+--------------------------------------------------------------+")
        say("设置路径：通用 → 高级 → 命令行界面")
        say("注意：这是位置示意图，不是特定版本的真实截图；菜单文字可能因版本不同而变化。")
    if image_path.is_file():
        say("正在打开完整中文 SVG 示意图：" + str(image_path))
        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", str(image_path)])
            elif system == "Windows":
                os.startfile(str(image_path))
            else:
                subprocess.Popen(["xdg-open", str(image_path)])
        except (OSError, AttributeError) as exc:
            say(f"无法打开独立图片窗口，请查看终端示意图；图片位置：{image_path}（{exc}）")
    else:
        say("完整 SVG 文件不存在，已保留终端文字说明。预期图片位置：" + str(image_path))


def plugin_action(plugin_id, installed_ids, enabled_ids):
    """Return the required action for one plugin based on its observed state."""
    if plugin_id in enabled_ids:
        return "skip"
    if plugin_id in installed_ids:
        return "enable"
    return "install_and_enable"


def explain_plugin_batch(vault, plan):
    say("\n【标准专业版】")
    say(f"目标 Vault：{vault}")
    say("本次授权将按清单执行必要操作：")
    for item, action in plan:
        operation = {"install_and_enable": "安装后启用", "enable": "仅启用"}[action]
        say(f'  - {item["name"]}（{item["id"]}）：{operation}')
        say(f'    风险：{item.get("risk", "第三方社区插件")}')
    say("权限：以当前登录用户权限运行 Obsidian CLI；不使用 sudo 或管理员权限。")
    say("影响：安装会向该 Vault 的 .obsidian/plugins/ 写入第三方插件文件；启用会允许 Obsidian 加载并运行插件代码。")
    say("安全边界：不修改笔记正文、不卸载或更新插件；每项操作后检查实际文件和启用状态。")
    say("Templater 可执行 JavaScript 和系统命令，属于高风险插件；只有明确单独选择时才会纳入本次授权。")
    say("恢复：可在 Obsidian 社区插件设置中禁用；卸载需另行确认，不会由本流程自动执行。")
    say("\n【10岁儿童比喻版】")
    say("我们先检查每个工具：没有的先放进工具箱，已经放进去但没打开的只打开开关，已经打开的就不再碰。")
    say("上面的清单就是这次要做的全部事情。你只需要同意一次；不同意就什么也不做。")
    say("这些工具来自第三方；打开后可能接触或修改这本笔记本里的内容。Templater 还可以运行电脑命令，所以要特别小心。")
    return ask_yes_no("\n是否同意一次性执行以上全部操作？")


def run_plugin_cli_action(vault, cli, item, command_name):
    command = [str(cli), command_name, f'id={item["id"]}']
    try:
        result = subprocess.run(
            command, cwd=str(vault), capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=180 if command_name == "plugin:install" else 120,
            check=False,
        )
        if result.stdout.strip():
            say(result.stdout.strip())
        if result.stderr.strip():
            say("CLI 提示：" + result.stderr.strip())
        if is_cli_not_enabled(result):
            explain_cli_not_enabled()
            return False
        if result.returncode != 0:
            say(f'CLI 执行失败：{item["name"]}，退出码 {result.returncode}。')
            return False
        return True
    except subprocess.TimeoutExpired:
        say(f'CLI 执行超时：{item["name"]}。请先检查 Vault 状态，不要盲目重复操作。')
    except Exception as exc:
        say(f'CLI 调用失败：{item["name"]}（{exc}）')
    return False


def offer_obsidian_plugins(vault):
    """Manage Obsidian Git and recommended plugins through one consent-first flow."""
    cli = shutil.which("obsidian")
    if not cli:
        say("\n未找到 Obsidian CLI；插件安装/启用暂不可执行。请先在 Obsidian 设置中启用并注册 CLI。")
        return

    plugin_root = vault / ".obsidian" / "plugins"
    enabled_path = vault / ".obsidian" / "community-plugins.json"
    if enabled_path.exists():
        enabled_data = read_json(enabled_path)
        if not isinstance(enabled_data, list) or not all(isinstance(x, str) for x in enabled_data):
            say("启用状态文件 community-plugins.json 格式异常；为避免误操作，已停止插件管理。")
            return
        enabled_ids = set(enabled_data)
    else:
        enabled_ids = set()

    catalog = [{"id": "obsidian-git", "name": "Obsidian Git",
                "purpose": "在 Vault 中使用 Git 进行版本管理、提交与同步",
                "repo": "Vinzent03/obsidian-git",
                "risk": "第三方插件；配置自动提交/同步前应先理解远程仓库和凭据设置"}] + RECOMMENDED_PLUGINS

    installed_ids = {
        item["id"] for item in catalog
        if (plugin_root / item["id"] / "manifest.json").is_file()
    }
    inconsistent = enabled_ids.intersection({item["id"] for item in catalog}) - installed_ids
    if inconsistent:
        say("启用状态文件列出了插件，但对应 manifest.json 不存在：" + ", ".join(sorted(inconsistent)))
        say("状态不一致；为避免重复或错误操作，已停止插件管理。")
        return

    say("\n" + "=" * 58)
    say("Obsidian 社区插件统一管理")
    say("本清单包含 Obsidian Git 和 6 个推荐插件，共 7 个。")
    say("安装与启用采用同一次授权；已安装且启用的插件自动跳过。")
    say("-" * 58)
    for index, item in enumerate(catalog, 1):
        pid = item["id"]
        if pid in enabled_ids:
            state = "已安装且已启用（跳过）"
        elif pid in installed_ids:
            state = "已安装、未启用（只需启用）"
        else:
            state = "未安装（需要安装并启用）"
        say(f'{index}. {item["name"]}（{pid}）— {state}')

    actionable = [item for item in catalog
                  if plugin_action(item["id"], installed_ids, enabled_ids) != "skip"]
    if not actionable:
        say("\n7 个插件均已安装并启用，无需操作。")
        return

    say("\n请选择本次希望安装并启用的插件；已完成的插件不会重复操作。")
    selected = select_numbered(actionable, exclude_all_ids={"templater-obsidian"})
    if not selected:
        say("未选择插件；没有执行安装或启用。")
        return

    say("\n开始进行官方来源、仓库和许可证只读核验：")
    try:
        registry = fetch_registry()
    except Exception as exc:
        say(f"无法读取 Obsidian 官方社区插件目录，出于安全考虑停止本次操作：{exc}")
        return

    verified = []
    for item in selected:
        entry = registry.get(item["id"])
        if not entry:
            say(f'跳过 {item["name"]}：官方社区插件目录中没有找到该 ID。')
            continue
        if normalize_repo(entry.get("repo", "")) != normalize_repo(item["repo"]):
            say(f'跳过 {item["name"]}：官方目录仓库与预设仓库不一致。')
            continue
        try:
            info = fetch_repo_status(item["repo"])
        except Exception as exc:
            say(f'跳过 {item["name"]}：无法读取 GitHub 仓库状态（{exc}）。')
            continue
        spdx = (info.get("license") or {}).get("spdx_id") or ""
        if spdx not in OPEN_SOURCE_LICENSES:
            say(f'跳过 {item["name"]}：未能确认允许的开源许可证（{spdx or "未知"}）。')
            continue
        if info.get("archived"):
            say(f'跳过 {item["name"]}：GitHub 仓库已归档。')
            continue
        say(f'核验通过：{item["name"]} | 许可证：{spdx} | 最近推送：{info.get("pushed_at") or "未知"}')
        verified.append(item)

    if not verified:
        say("没有插件通过来源与许可证核验；未执行任何操作。")
        return

    plan = [(item, plugin_action(item["id"], installed_ids, enabled_ids))
            for item in verified]
    say("\n本次准备执行的操作：")
    for item, action in plan:
        operation = "安装后启用" if action == "install_and_enable" else "仅启用"
        say(f'  - {item["name"]}：{operation}')
    if not explain_plugin_batch(vault, plan):
        say("未获明确授权；没有执行安装或启用。")
        return

    for item, action in plan:
        pid = item["id"]
        say(f'\n正在处理：{item["name"]}')
        if action == "install_and_enable":
            if not run_plugin_cli_action(vault, cli, item, "plugin:install"):
                say(f'已停止后续批量操作；{item["name"]} 安装未能确认完成。')
                return
            manifest = plugin_root / pid / "manifest.json"
            if not manifest.is_file():
                say(f'CLI 返回成功，但未找到 {manifest}；不继续启用或处理后续插件。')
                return
            say(f'安装文件已验证：{item["name"]}')

        if not run_plugin_cli_action(vault, cli, item, "plugin:enable"):
            say(f'已停止后续批量操作；{item["name"]} 尚未确认启用。')
            return

        current_enabled = read_json(enabled_path)
        if not isinstance(current_enabled, list) or pid not in current_enabled:
            say(f'CLI 返回成功，但 community-plugins.json 尚未确认 {item["name"]} 已启用。')
            say("为避免误报，已停止后续操作；请在 Obsidian 中检查插件状态。")
            return
        say(f'安装/启用状态验证通过：{item["name"]}')

    say("\n本次所选插件的安装与启用操作均已完成，并通过状态验证。")


# Curated open-source community plugin catalogue.
# IDs are checked against Obsidian's official community registry before installation.
RECOMMENDED_PLUGINS = [
    {"id":"quickadd", "name":"QuickAdd", "purpose":"快速捕捉内容、创建笔记、模板与自动化工作流",
     "repo":"chhoumann/quickadd", "risk":"可配置自动化与脚本；只启用自己理解的工作流"},
    {"id":"obsidian-tasks-plugin", "name":"Tasks", "purpose":"跨笔记管理待办、截止日期、重复任务和任务查询",
     "repo":"obsidian-tasks-group/obsidian-tasks", "risk":"会读取并处理 Vault 中的任务标记"},
    {"id":"obsidian-excalidraw-plugin", "name":"Excalidraw", "purpose":"在 Obsidian 中绘图、画关系图和白板",
     "repo":"zsviczian/obsidian-excalidraw-plugin", "risk":"会在 Vault 中创建和修改绘图文件"},
    {"id":"obsidian-linter", "name":"Linter", "purpose":"按规则整理 Markdown 格式、标题、空格和属性",
     "repo":"platers/obsidian-linter", "risk":"运行整理规则时可能批量修改笔记；首次使用前先备份"},
    {"id":"table-editor-obsidian", "name":"Advanced Tables", "purpose":"改善 Markdown 表格的编辑、对齐和导航",
     "repo":"tgrosinger/advanced-tables-obsidian", "risk":"官方说明该插件仍属实验性，可能存在导致当前笔记数据丢失的缺陷；先备份再使用"},
    {"id":"templater-obsidian", "name":"Templater", "purpose":"动态模板，可运行 JavaScript 和系统命令",
     "repo":"SilentVoid13/Templater", "risk":"高风险：可执行任意 JavaScript 和系统命令；仅建议高级用户使用"}
]

OPEN_SOURCE_LICENSES = {
    "MIT", "Apache-2.0", "GPL-3.0", "GPL-3.0-only", "GPL-3.0-or-later",
    "AGPL-3.0", "AGPL-3.0-only", "AGPL-3.0-or-later",
    "BSD-2-Clause", "BSD-3-Clause", "MPL-2.0", "ISC"
}

def normalize_repo(repo):
    value = re.sub(r"^https?://github.com/", "", str(repo or "").strip()).strip("/")
    return re.sub(r"\.git$", "", value).lower()

def main():
    if sys.version_info < (3, 10):
        say("需要 Python 3.10 或更高版本。")
        say(f"当前 Python：{sys.version.split()[0]}")
        return 2
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try: reconfigure(encoding="utf-8", errors="replace")
            except Exception: pass
    say("="*58); say(f" ObsidianPluginManager v{VERSION}"); say(f" 平台：{platform_name()}"); say("="*58)
    if platform.system() not in ("Darwin", "Windows", "Linux"):
        say("暂不支持此操作系统。"); return 2

    app = find_obsidian()
    if app:
        say(f"发现 Obsidian 位置：{app}")
    else:
        say("未能自动定位 Obsidian 安装目录。")
        app = prompt_manual_obsidian_path(app)
        if not app:
            say("未提供有效安装目录；无法自动启动 Obsidian。")
            return 1
    ver = app_version(app)
    say(f"Obsidian 版本：{ver}")

    cli = shutil.which("obsidian")
    if cli:
        say(f"CLI 已在 PATH 中：{cli}")
    else:
        source = next((x for x in cli_candidates(app) if x.is_file()), None)
        if source:
            say(f"发现可能的内置 CLI：{source}")
            say("CLI 命令尚未注册。官方 CLI 功能仍需先在 Obsidian 设置 → 常规 → 命令行界面中启用。")
            if ask_yes_no("是否进行当前用户级 CLI 注册？"):
                if register_cli(app, source):
                    cli = shutil.which("obsidian")
        else:
            say("未找到可识别的内置 CLI 文件；不会下载或替换程序。")

    if not launch_obsidian(app):
        say("无法启动 Obsidian；程序已停止，未扫描 Vault、未安装或启用插件。")
        return 1

    if cli and not check_cli_available(cli, wait_timeout=40):
        return 0
    if not cli:
        say("未找到可用的 Obsidian CLI；本次只能进行本地 Vault 盘点，不能通过 CLI 安装或启用插件。")

    say("\n默认使用 Obsidian 当前打开的 Vault（新启动时由 Obsidian 恢复上次使用的 Vault）。")
    vault_choice = ask("回车=使用当前 Vault；输入 switch=打开 Obsidian 仓库选择器；也可输入 Vault 文件夹路径：")
    if vault_choice.strip().casefold() == "switch":
        if not open_vault_chooser():
            return 1
        ask("请在 Obsidian 仓库选择器中选好 Vault，完成后按回车继续：")
        vault = active_vault_path(cli) if cli else None
    elif vault_choice.strip():
        raw_path = vault_choice.strip().strip('"').strip("'")
        vault = Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()
    else:
        vault = active_vault_path(cli) if cli else None

    if vault is None:
        say("无法确认 Obsidian 当前打开的 Vault。为避免随机选择或误操作，请手动输入 Vault 文件夹路径。")
        vault_input = ask("请输入 Vault 文件夹路径（留空退出）：")
        if not vault_input:
            return 0
        vault = Path(os.path.expandvars(os.path.expanduser(
            vault_input.strip().strip('"').strip("'")
        ))).resolve()

    if not vault.is_dir():
        say(f"Vault 路径不存在或不是文件夹：{vault}")
        return 1
    say(f"本次目标 Vault：{vault}")
    if not ensure_vault_plugin_dirs(vault):
        say("目录初始化未完成；已跳过插件盘点、安装与启用流程。")
        say("检查结束。本工具未读取笔记正文。")
        return 0
    audit_plugins(vault)
    if cli:
        offer_obsidian_plugins(vault)
    else:
        say("未执行插件安装或启用：当前没有可用的 Obsidian CLI。")
    say("\n检查结束。本工具只执行用户对本次插件清单一次明确授权的操作；未读取笔记正文。")
    return 0

if __name__ == "__main__": raise SystemExit(main())
