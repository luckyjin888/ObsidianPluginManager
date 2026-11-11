#!/usr/bin/env python3
# ObsidianPluginManager 0.5.5
# GPL-3.0-only
"""Cross-platform, consent-first Obsidian plugin inventory and heuristic audit."""
from __future__ import annotations
import json, os, platform, re, shutil, subprocess, sys, ssl, urllib.error, urllib.request
from pathlib import Path
from datetime import datetime, timezone

VERSION = "0.5.5"
MIN_CLI = (1, 12, 7)
REGISTRY_URL = "https://raw.githubusercontent.com/obsidianmd/obsidian-releases/master/community-plugins.json"
NETWORK_TIMEOUT = 8

def say(s=""): print(s)
def ask(prompt):
    try: return input(prompt).strip()
    except (EOFError, KeyboardInterrupt): say("\n已取消。"); return ""

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
    """Accept an install folder or Obsidian.exe path only if the GUI executable exists."""
    try:
        candidate = Path(path).expanduser()
        if candidate.is_file() and candidate.name.lower() == "obsidian.exe":
            return candidate.parent
        if candidate.is_dir() and (candidate / "Obsidian.exe").is_file():
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
    else:
        for name in ("obsidian", "Obsidian"):
            found = shutil.which(name)
            if found:
                p = Path(found).resolve()
                candidates.extend([p.parent, p.parent.parent])
        candidates += [Path("/usr/share/obsidian"), Path("/opt/Obsidian"), Path.home()/".local/share/Obsidian"]
    for p in candidates:
        if p.exists(): return p
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
    return [app/"obsidian", app/"obsidian-cli", app/"resources/app.asar.unpacked/obsidian"]

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
    return ask("\n你是否明确同意执行以上 CLI 注册？请输入 YES 同意，其它输入均取消：") == "YES"

def register_cli(app, source):
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
            current = current.reason
        else:
            current = current.__cause__ or current.__context__
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
    repo = re.sub(r"\\.git$","",repo)
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

def scan_source(plugin_dir):
    findings = []
    files = list(plugin_dir.rglob("*.js"))
    if len(files) > 500: files = files[:500]
    for file in files:
        try:
            if file.stat().st_size > 2_000_000: continue
            source = file.read_text(encoding="utf-8", errors="replace")
        except Exception: continue
        for category, patterns in PATTERNS.items():
            hits = [p for p in patterns if re.search(p, source, re.I)]
            if hits: findings.append((category, file.name, hits))
    return findings

def ensure_vault_plugin_dirs(vault):
    """Create missing Obsidian config/plugin directories only after separate consent."""
    vault = Path(vault)
    if not vault.is_dir():
        say(f"Vault 路径不存在或不是文件夹：{vault}")
        return False

    config_dir = vault / ".obsidian"
    plugin_dir = config_dir / "plugins"

    if not config_dir.exists():
        say("\n检测到该文件夹尚未初始化为 Obsidian Vault。")
        say(f"准备创建配置目录：{config_dir}")
        say("\n【标准专业版】")
        say("目的：在用户明确指定的 Vault 根目录下创建 Obsidian 配置目录 .obsidian。")
        say("权限：仅使用当前用户对该 Vault 的普通文件夹写入权限，不申请管理员权限。")
        say("影响：只创建目录，不创建或覆盖配置文件，不修改笔记正文、插件或系统设置。")
        say("风险：这会在所选文件夹中留下 Obsidian 配置目录；如果选错 Vault，请取消。")
        say("\n【10岁儿童比喻版】")
        say("这本笔记本还没有 Obsidian 的管理柜。我们想在你指定的书房里放一个空柜子。")
        say("只放空柜子，不搬动笔记，也不拿走任何东西；如果地方选错了，就先不要放。")
        if ask("确认创建 .obsidian 配置目录？请输入 YES；其它输入均取消：") != "YES":
            say("未获明确同意；没有创建 .obsidian，也不会继续插件相关操作。")
            return False
        try:
            config_dir.mkdir()
            say(f"已创建配置目录：{config_dir}")
        except FileExistsError:
            if not config_dir.is_dir():
                say("创建失败：目标路径已存在，但不是文件夹。")
                return False
        except OSError as exc:
            say(f"创建 .obsidian 失败：{exc}")
            return False
    elif not config_dir.is_dir():
        say(f"配置路径存在但不是文件夹：{config_dir}")
        return False

    if not plugin_dir.exists():
        say(f"\n尚未找到社区插件目录：{plugin_dir}")
        say("\n【标准专业版】")
        say("目的：在当前 Vault 的 .obsidian 配置目录内创建 plugins 文件夹。")
        say("权限：仅使用当前用户对该 Vault 的普通文件夹写入权限，不申请管理员权限。")
        say("影响：只创建空目录；不会下载、安装、启用或执行任何插件。")
        say("风险：目录会出现在该 Vault 中；不创建任何插件文件，也不改变现有设置。")
        say("\n【10岁儿童比喻版】")
        say("管理柜已经有了，但里面还没有放插件的抽屉。我们想加一个空抽屉。")
        say("空抽屉不会自己装进工具，也不会让任何插件开始工作；要不要放，由你决定。")
        if ask("确认创建 .obsidian\\plugins 目录？请输入 YES；其它输入均取消：") != "YES":
            say("未获明确同意；未创建 plugins 目录，已跳过所有插件相关操作。")
            return False
        try:
            plugin_dir.mkdir()
            say(f"已创建插件目录：{plugin_dir}")
        except FileExistsError:
            if not plugin_dir.is_dir():
                say("创建失败：目标路径已存在，但不是文件夹。")
                return False
        except OSError as exc:
            say(f"创建 plugins 目录失败：{exc}")
            return False
    elif not plugin_dir.is_dir():
        say(f"插件路径存在但不是文件夹：{plugin_dir}")
        return False

    return True


def audit_plugins(vault):
    cfg = vault/".obsidian"
    plugin_root = cfg/"plugins"
    enabled = read_json(cfg/"community-plugins.json")
    enabled_set = set(enabled) if isinstance(enabled,list) else None
    if not plugin_root.is_dir():
        say("没有找到 .obsidian/plugins 目录。"); return
    dirs = sorted([p for p in plugin_root.iterdir() if p.is_dir()], key=lambda p:p.name.lower())
    say(f"\n发现插件目录：{len(dirs)} 个")
    say("启用状态来源：.obsidian/community-plugins.json（缺失或格式异常时标为未知）")
    say("网络核验会向 Obsidian 官方 GitHub 社区插件目录及插件声明的 GitHub 仓库发送只读请求。不会上传 Vault 或笔记内容。")
    do_network = ask("是否进行在线来源与维护状态核验？[y/N] ").lower() == "y"
    registry = None
    if do_network:
        try: registry = fetch_registry(); say(f"已读取官方社区插件目录：{len(registry)} 条记录")
        except Exception as e: say(f"官方目录读取失败：{e}")
    counts = {"启用":0,"禁用":0,"未知":0}
    for p in dirs:
        manifest = read_json(p/"manifest.json") or {}
        pid = str(manifest.get("id") or p.name)
        name = manifest.get("name", p.name)
        if enabled_set is None: state = "未知"
        else: state = "启用" if pid in enabled_set else "禁用"
        counts[state] += 1
        say("\n" + "-"*58)
        say(f"{name}  [{pid}]")
        say(f"版本：{manifest.get('version','未知')} | 作者：{manifest.get('author','未知')} | 状态：{state}")
        say(f"最低 Obsidian 版本：{manifest.get('minAppVersion','未声明')}")
        if not (p/"manifest.json").is_file(): say("来源/完整性：未找到 manifest.json，需人工检查")
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
        findings = scan_source(p)
        if findings:
            say("静态代码线索（不是恶意判定）：")
            for category, filename, hits in findings:
                say(f"  - {category}：{filename}（命中 {', '.join(hits)}）")
        else: say("静态代码线索：未命中本工具的规则（不代表没有风险）")
        risk = "需人工复核" if findings or state=="未知" or not (p/"manifest.json").is_file() else "未发现规则命中（不代表安全）"
        say(f"初步结论：{risk}")
    say("\n" + "="*58)
    say(f"插件统计：总数 {len(dirs)} | 启用 {counts['启用']} | 禁用 {counts['禁用']} | 未知 {counts['未知']}")
    say("重要限制：这是基于 manifest、启用清单和关键词的静态初筛；不能证明插件安全，也不能完整理解混淆、动态加载或运行时行为。")
    say("“官方目录匹配”仅代表目录中存在对应 ID，不代表 Obsidian 或 GitHub 对插件作出安全背书。")


def explain_plugin_action(vault, action, command):
    say("\n【标准专业版】")
    say(f"目标：在指定 Vault 安装/启用 Obsidian Git（插件 ID：obsidian-git）。")
    say(f"Vault：{vault}")
    say(f"将执行的官方 CLI 命令：{command}")
    say("权限：以当前登录用户权限运行 Obsidian CLI；不使用 sudo 或管理员权限。")
    say("影响：安装会在该 Vault 的 .obsidian/plugins/obsidian-git 写入第三方插件文件；启用会允许 Obsidian 加载并运行该插件代码。")
    say("风险：社区插件是第三方代码；安装来源由 Obsidian 社区插件目录处理。安装本身不等于安全认证。")
    say("恢复：可在 Obsidian 社区插件设置中禁用；卸载需另行确认，不会由本步骤自动执行。")
    say("\n【10岁儿童比喻版】")
    say(f"我们要在你选定的这一本笔记本（{vault}）里{action} Obsidian Git。")
    say("安装就像把一个第三方小工具放进这本笔记本的工具箱；启用就像允许它开始工作、接触这本笔记本。")
    say("只用你自己的普通账户，不找管理员帮忙。这个小工具不是 Obsidian 官方内置的，可能有风险；如果不想用，可以以后在设置里关掉。")
    return ask("\n如果同意以上这一步，请输入 INSTALL 或 ENABLE；其它输入均取消：") == ("INSTALL" if action == "安装" else "ENABLE")

def run_obsidian_cli_plugin(vault, cli, command_name):
    # Official CLI targets the vault from the current working directory.
    # Run inside the selected Vault so another active Vault is not modified.
    command = [cli, command_name, "id=obsidian-git"]
    action = "安装" if command_name == "plugin:install" else "启用"
    if not explain_plugin_action(vault, action, " ".join(command)):
        say("未获明确同意，未执行。")
        return False
    try:
        result = subprocess.run(command, cwd=str(vault), capture_output=True, text=True,
                                encoding="utf-8", errors="replace",
                                timeout=180, check=False)
        if result.stdout.strip(): say(result.stdout.strip())
        if result.stderr.strip(): say("CLI 提示：" + result.stderr.strip())
        if result.returncode != 0:
            say(f"CLI 执行失败，退出码：{result.returncode}。未继续后续步骤。")
            return False
        return True
    except subprocess.TimeoutExpired:
        say("CLI 执行超时；请在 Obsidian 中检查插件状态，不要重复安装。")
    except Exception as e:
        say(f"CLI 调用失败：{e}")
    return False

def offer_obsidian_git(vault):
    cli = shutil.which("obsidian")
    if not cli:
        say("\n未在 PATH 中找到 Obsidian CLI，暂不能通过 CLI 安装插件。")
        say("请先在 Obsidian 设置 → 常规 → 命令行界面启用并注册 CLI，然后重新打开终端。")
        return
    plugin_dir = vault/".obsidian"/"plugins"/"obsidian-git"
    manifest = plugin_dir/"manifest.json"
    if manifest.is_file():
        say("\nObsidian Git 已安装。")
    else:
        say("\n发现可选插件：Obsidian Git（第三方社区插件，ID：obsidian-git）")
        say("官方社区页面：https://community.obsidian.md/plugins/obsidian-git")
        if ask("是否查看并考虑通过 Obsidian 官方 CLI 安装？[y/N] ").lower() != "y":
            say("跳过安装；未修改插件。")
            return
        if not run_obsidian_cli_plugin(vault, cli, "plugin:install"):
            return
        if not manifest.is_file():
            say("CLI 返回成功，但未在所选 Vault 找到插件 manifest.json；请在 Obsidian 中核实，暂不自动启用。")
            return
        say("已检测到 Obsidian Git 安装文件。")
    enabled = read_json(vault/".obsidian"/"community-plugins.json")
    if isinstance(enabled, list) and "obsidian-git" in enabled:
        say("Obsidian Git 当前已启用。")
        return
    say("插件目前未启用。启用会允许 Obsidian 加载并运行第三方插件代码。")
    if ask("是否单独启用 Obsidian Git？[y/N] ").lower() == "y":
        run_obsidian_cli_plugin(vault, cli, "plugin:enable")
    else:
        say("保持未启用状态；未执行启用操作。")


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

def offer_recommended_plugins(vault):
    cli = shutil.which("obsidian")
    if not cli:
        say("\n未找到 Obsidian CLI；推荐插件库暂不可安装。请先在 Obsidian 设置中启用并注册 CLI。")
        return
    say("\n" + "="*58)
    say("优质开源社区插件推荐库")
    say("这些是第三方插件，不是 Obsidian 官方内置功能。")
    say("推荐依据：常见使用场景、公开源代码仓库；安装前还会实时核验官方目录、GitHub 许可证及仓库归档状态。")
    say("这不是安全认证；许可证开放不代表代码没有风险。")
    say("-"*58)
    for item in RECOMMENDED_PLUGINS:
        state = "已安装" if (vault/".obsidian"/"plugins"/item["id"]/"manifest.json").is_file() else "未安装"
        say(f'{item["id"]} | {item["name"]} | {state}')
        say(f'  用途：{item["purpose"]}')
        say(f'  风险提示：{item["risk"]}')
        say(f'  源码仓库：https://github.com/{item["repo"]}')
    say("\n输入要安装的插件 ID（多个用英文逗号分隔），输入 all 选择全部，直接回车跳过。")
    selected_text = ask("选择：")
    if not selected_text:
        say("已跳过推荐插件安装。")
        return
    by_id = {x["id"]:x for x in RECOMMENDED_PLUGINS}
    if selected_text.lower() == "all":
        selected = [x for x in RECOMMENDED_PLUGINS if x["id"] != "templater-obsidian"]
        say("安全提示：Templater 具备执行任意 JavaScript/系统命令的能力；输入 all 不会自动选中它。若确实需要，请单独输入 templater-obsidian。")
    else:
        ids = [x.strip() for x in selected_text.split(",") if x.strip()]
        unknown = [x for x in ids if x not in by_id]
        if unknown:
            say("存在不在推荐清单中的 ID，停止本次安装：" + ", ".join(unknown))
            return
        selected = [by_id[x] for x in dict.fromkeys(ids)]
    selected = [x for x in selected if not (vault/".obsidian"/"plugins"/x["id"]/"manifest.json").is_file()]
    if not selected:
        say("所选插件均已安装，无需重复安装。")
        return
    say("\n开始安装前的来源与许可证核验（只读网络请求）：")
    try:
        registry = fetch_registry()
    except Exception as e:
        say(f"无法读取 Obsidian 官方社区插件目录，出于安全考虑停止安装：{e}")
        return
    verified = []
    for item in selected:
        entry = registry.get(item["id"])
        if not entry:
            say(f'跳过 {item["name"]}：官方社区插件目录中没有找到该 ID。')
            continue
        listed_repo = normalize_repo(entry.get("repo", ""))
        expected_repo = normalize_repo(item["repo"])
        if listed_repo != expected_repo:
            say(f'跳过 {item["name"]}：官方目录仓库与内置推荐仓库不一致（{listed_repo or "未提供"}）。')
            continue
        try:
            info = fetch_repo_status(item["repo"])
        except Exception as e:
            say(f'跳过 {item["name"]}：无法读取 GitHub 仓库许可证/状态（{e}）。')
            continue
        license_info = info.get("license") or {}
        spdx = license_info.get("spdx_id") or ""
        if spdx not in OPEN_SOURCE_LICENSES:
            say(f'跳过 {item["name"]}：未能确认属于允许的开源许可证（GitHub SPDX：{spdx or "未知"}）。')
            continue
        if info.get("archived"):
            say(f'跳过 {item["name"]}：GitHub 仓库已归档。')
            continue
        pushed = info.get("pushed_at") or "未知"
        say(f'核验通过：{item["name"]} | SPDX：{spdx} | 最近推送：{pushed} | 仓库未归档')
        verified.append(item)
    if not verified:
        say("没有通过来源、许可证和归档状态核验的插件；未执行安装。")
        return
    say("\n本次准备安装：")
    for item in verified:
        say(f'  - {item["name"]}（{item["id"]}）')
        say(f'    用途：{item["purpose"]}')
        say(f'    风险：{item["risk"]}')
    say("\n【标准专业版】")
    say(f"目标 Vault：{vault}")
    say("将逐个调用 Obsidian 官方 CLI 的 plugin:install 命令，只安装上方通过核验且尚未安装的插件。")
    say("权限：当前登录用户权限；不使用 sudo/管理员权限。")
    say("影响：向该 Vault 的 .obsidian/plugins/<插件ID>/ 写入第三方插件文件；本流程不会启用插件，也不会修改笔记正文。")
    say("风险：社区插件安装不等于安全认证；启用后插件代码可能读取或修改 Vault。Templater 还能执行任意 JavaScript 和系统命令。")
    say("恢复：安装后可在 Obsidian 社区插件设置中禁用；卸载需另行操作并再次确认。建议先备份 Vault。")
    say("\n【10岁儿童比喻版】")
    say("我们要把上面列出的几个第三方小工具，逐个放进你选定的那本笔记本的工具箱。")
    say("这一步只负责放进去，不会替你打开工具；打开以后，它们才可能开始读写笔记。")
    say("有些工具能力很强，尤其 Templater 像一把能启动电脑命令的工具刀，不懂怎么用就先不要选。")
    say("整个过程只用你自己的普通账户，不找管理员；最好先给笔记本做一份备份。")
    if ask("\n确认安装以上全部已核验插件？请输入 INSTALL；其它输入均取消：") != "INSTALL":
        say("未获明确同意，未执行安装。")
        return
    for item in verified:
        command = [cli, "plugin:install", f'id={item["id"]}']
        say(f'\n正在安装：{item["name"]}（{item["id"]}）')
        try:
            result = subprocess.run(command, cwd=str(vault), capture_output=True, text=True,
                                    encoding="utf-8", errors="replace",
                                    timeout=180, check=False)
            if result.stdout.strip(): say(result.stdout.strip())
            if result.stderr.strip(): say("CLI 提示：" + result.stderr.strip())
            if result.returncode != 0:
                say(f'安装失败，退出码 {result.returncode}；停止后续安装。')
                return
            manifest = vault/".obsidian"/"plugins"/item["id"]/"manifest.json"
            if not manifest.is_file():
                say("CLI 返回成功，但没有找到目标 manifest.json；停止后续安装，请在 Obsidian 中检查。")
                return
            say(f'已核验安装文件：{manifest}')
        except subprocess.TimeoutExpired:
            say("安装超时；请先在 Obsidian 中检查状态，不要立即重复运行。")
            return
        except Exception as e:
            say(f"安装失败：{e}")
            return
    say("\n所选插件安装流程完成。所有新安装插件保持未启用状态，请先逐个审阅后再自行启用。")

def main():
    if sys.version_info < (3, 10):
        say("需要 Python 3.10 或更高版本。")
        say(f"当前 Python：{sys.version.split()[0]}")
        return 2
    # Keep Chinese diagnostics readable in Windows PowerShell/Terminal.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try: reconfigure(encoding="utf-8", errors="replace")
            except Exception: pass
    say("="*58); say(f" ObsidianPluginManager v{VERSION}"); say(f" 平台：{platform_name()}"); say("="*58)
    if platform.system() not in ("Darwin","Windows","Linux"):
        say("暂不支持此操作系统。"); return 2
    app = find_obsidian()
    if app:
        say(f"发现 Obsidian 位置：{app}")
    else:
        say("未能自动定位 Obsidian 安装目录。")
        app = prompt_manual_obsidian_path(app)
        if not app:
            say("未提供有效安装目录；仍可继续输入 Vault 路径，但无法自动注册 CLI。")
    ver = app_version(app) if app else "未知"
    say(f"Obsidian 版本：{ver}")
    cli = shutil.which("obsidian")
    if cli: say(f"CLI 已在 PATH 中：{cli}")
    elif app:
        source = next((x for x in cli_candidates(app) if x.is_file()), None)
        if source:
            say(f"发现可能的内置 CLI：{source}")
            say("CLI 命令尚未注册。官方 CLI 功能仍需先在 Obsidian 设置 → 常规 → 命令行界面中启用。")
            if ask("是否查看并尝试进行当前用户级 CLI 注册？[y/N] ").lower() == "y":
                register_cli(app, source)
        else: say("未找到可识别的内置 CLI 文件；不会下载或替换程序。")
    else: say("未定位应用，无法自动注册 CLI。")
    vault_input = ask("\n请输入 Vault 文件夹路径（留空退出）：")
    if not vault_input: return 0
    # Windows Explorer often copies paths with surrounding quotation marks.
    vault_input = vault_input.strip().strip('"').strip("'")
    vault = Path(os.path.expandvars(os.path.expanduser(vault_input))).resolve()
    if not vault.is_dir():
        say("该 Vault 文件夹不存在或不是文件夹。"); return 1
    say(f"Vault：{vault}")
    if not ensure_vault_plugin_dirs(vault):
        say("目录初始化未完成；已跳过插件盘点、安装与启用流程。")
        say("检查结束。本工具未读取笔记正文。")
        return 0
    audit_plugins(vault)
    offer_obsidian_git(vault)
    offer_recommended_plugins(vault)
    say("\n检查结束。除非用户对 Obsidian Git 的安装/启用步骤分别明确授权，否则本工具不会修改插件；本工具未读取笔记正文。")
    return 0

if __name__ == "__main__": raise SystemExit(main())
