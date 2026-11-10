# ObsidianPluginManager

一个以安全、透明、用户确认优先为原则的 Obsidian 插件盘点与初步审查工具。

**版本：** 0.4.1  
**核心：** Python 3  
**启动入口：** macOS/Linux 使用 Bash；Windows 使用 PowerShell  
**许可证：** GNU GPL-3.0-only

> 0.4.1 修正启动说明：macOS/Linux 用户无需给脚本添加可执行权限，使用 Bash 显式启动即可。0.4.0 是跨平台首轮实现；macOS、Windows、Linux 的路径识别和 CLI 入口逻辑尚未在所有真实系统组合上完成验证。请把它视为早期测试版，不要将“支持入口”理解为所有发行版/安装方式均已兼容。

## 功能

- 运行时识别 macOS、Windows、Linux。
- 由用户输入 Vault 路径，不硬编码个人路径。
- 读取插件 manifest，统计插件目录总数。
- 读取 `.obsidian/community-plugins.json`，统计启用、禁用、未知数量。
- 可选联网核对 Obsidian 官方社区插件目录。
- 可选读取插件 manifest 声明的 GitHub 仓库状态（最近推送时间、是否归档）。
- 对插件 JavaScript 做关键词静态初筛：网络通信、本地文件访问、系统命令/进程、动态代码执行、凭据/环境访问。
- 输出发现的线索与无法确认项；不把“没有命中规则”说成“安全”。
- CLI 未注册时，可尝试创建当前用户级命令入口；执行前展示双版本说明并要求输入完整的 `YES`。

## 环境要求

- Python 3.10 或更高版本。
- 网络核验需要联网；离线时仍可进行本地目录和静态初筛。
- Obsidian CLI 功能仍需先在 Obsidian 设置 → 常规 → 命令行界面中启用。脚本不能代替 GUI 开关。

## 运行

### macOS / Linux（推荐）

**不需要执行 `chmod +x`。** 在终端进入项目目录后运行：

```bash
bash ./obsidian_manager.sh
```

也可以直接指定脚本完整路径：

```bash
bash "/你的项目目录/obsidian_manager.sh"
```

或者直接运行 Python 核心：

```bash
python3 ./obsidian_manager.py
```

不要把 `./obsidian_manager.sh` 当作默认启动命令：如果下载工具包时没有保留 Unix 可执行位，直接执行会出现 `Permission denied`。通过 `bash` 启动不依赖该可执行位，也不需要修改文件权限。

### Windows PowerShell

```powershell
powershell -ExecutionPolicy Bypass -File .\obsidian_manager.ps1
```

如果 PowerShell 执行策略阻止脚本运行，不要为了运行本工具而关闭或绕过系统策略；可直接运行 Python 核心：

```powershell
py -3 .\obsidian_manager.py
```

## CLI 注册行为

程序先检查 `obsidian` 是否已在 PATH 中。若未找到，会尝试定位可能的 Obsidian CLI 文件，并询问是否进行用户级注册。

- macOS：在 `~/.local/bin/obsidian` 创建指向应用内置 CLI 的符号链接。
- Linux：将检测到的 CLI 文件复制到 `~/.local/bin/obsidian`。
- Windows：将 `Obsidian.com` 复制为用户目录下的 `~/.local/bin/obsidian.com`。

不会自动使用 sudo、不会申请管理员权限、不会覆盖已有同名目标，也不会自动修改 PATH。若目录不在 PATH 中，程序只给出人工配置指引。Windows 用户需在“环境变量 → 用户变量 → Path”中自行添加该目录。

**重要：** 仅创建命令入口不代表 CLI 已成功启用。必须先在 Obsidian 设置中打开官方 CLI 开关。不同安装渠道、版本和系统发行版可能有不同布局；无法识别时程序会停止，不会下载或替换二进制文件。

### CLI 注册说明（强制双版本）

**标准专业版：** 注册会在当前用户目录创建一个命令入口；macOS 使用符号链接，Linux/Windows 复制检测到的 CLI 文件。只需当前用户目录写入权限，不调用管理员权限。若目标已存在则停止，不覆盖。此动作不修改 Vault、笔记或插件。若 PATH 未包含目标目录，需用户自行配置；恢复时删除本次创建的入口即可。

**10岁儿童比喻版：** 就像在自己的书桌抽屉里放一个 Obsidian 快捷按钮。只整理自己的抽屉，不进管理员办公室，也不碰你的笔记。如果抽屉里已经有同名按钮，就停下来不覆盖。抽屉不在电脑寻找按钮的路线里时，还要由你自己把它加入路线。

## 全面审查的边界

- 官方社区目录匹配只说明找到相同插件 ID，不代表官方安全认证。
- GitHub 最近推送时间不是维护质量或安全性的保证。
- 静态关键词检查可能误报，也可能漏掉混淆代码、动态加载、依赖包和运行时行为。
- 本工具不执行插件代码、不上传 Vault/笔记正文、不读取笔记内容。
- 网络核验会向 Obsidian 官方 GitHub 社区目录及 manifest 声明的 GitHub API 发起只读请求。
- 插件状态无法从配置文件可靠读取时，会标记为“未知”，不会猜测。

## 测试

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile obsidian_manager.py
bash -n obsidian_manager.sh
```

Windows、macOS、Linux 的真实安装路径测试仍需在对应系统上完成。

## 安全原则

默认只读；所有有副作用操作先说明再征求明确同意；拒绝或取消后停止。所有操作说明必须同时提供标准专业版与10岁儿童比喻版。详见 [SECURITY.md](SECURITY.md)。

## 许可证

GNU General Public License v3.0 only，见 [LICENSE](LICENSE)。
