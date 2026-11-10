#!/usr/bin/env python3
# ObsidianPluginManager 0.4.1
# GPL-3.0-only
"""Cross-platform, consent-first Obsidian plugin inventory and heuristic audit."""
from __future__ import annotations
import json, os, platform, re, shutil, subprocess, sys, urllib.request
from pathlib import Path
from datetime import datetime, timezone

VERSION = "0.4.1"
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

def find_obsidian():
    system = platform.system()
    candidates = []
    if system == "Darwin":
        candidates = [Path("/Applications/Obsidian.app"), Path.home()/"Applications/Obsidian.app"]
    elif system == "Windows":
        roots = [os.environ.get("LOCALAPPDATA",""), os.environ.get("ProgramFiles",""), os.environ.get("ProgramFiles(x86)","")]
        candidates = [Path(x)/"Obsidian" for x in roots if x]
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
    if system == "Windows": return [app/"Obsidian.com", app/"Obsidian.exe"]
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

def fetch_registry():
    req = urllib.request.Request(REGISTRY_URL, headers={"User-Agent":"ObsidianPluginManager/0.4.0"})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as r:
        data = json.loads(r.read().decode("utf-8"))
    return {str(x.get("id","")):x for x in data if isinstance(x,dict) and x.get("id")}

def fetch_repo_status(repo):
    repo = re.sub(r"^https?://github.com/","",str(repo or "").strip()).strip("/")
    repo = re.sub(r"\.git$","",repo)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo): return None
    url = "https://api.github.com/repos/"+repo
    req = urllib.request.Request(url, headers={"User-Agent":"ObsidianPluginManager/0.4.0","Accept":"application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as r: return json.loads(r.read().decode("utf-8"))

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

def main():
    say("="*58); say(f" ObsidianPluginManager v{VERSION}"); say(f" 平台：{platform_name()}"); say("="*58)
    if platform.system() not in ("Darwin","Windows","Linux"):
        say("暂不支持此操作系统。"); return 2
    app = find_obsidian()
    if app: say(f"发现 Obsidian 位置：{app}")
    else: say("未能自动定位 Obsidian 安装目录；仍可尝试输入 Vault 路径。")
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
    vault = Path(os.path.expandvars(os.path.expanduser(vault_input))).resolve()
    if not vault.is_dir() or not (vault/".obsidian").is_dir():
        say("该路径不存在，或没有 .obsidian 配置目录。"); return 1
    say(f"Vault：{vault}")
    audit_plugins(vault)
    say("\n检查结束。本工具未安装、卸载、启用、禁用或修改任何插件，也未读取笔记正文。")
    return 0

if __name__ == "__main__": raise SystemExit(main())
