# ObsidianPluginManager

一个以安全、透明、用户确认优先为原则的 Obsidian 插件盘点与初步审查工具。

**版本：** 0.6.4  
**核心：** Python 3  
**启动入口：** macOS/Linux 使用 Bash；Windows 使用 PowerShell  
**许可证：** GNU GPL-3.0-only

> 0.4.1 修正启动说明：macOS/Linux 用户无需给脚本添加可执行权限，使用 Bash 显式启动即可。0.4.0 是跨平台首轮实现；macOS、Windows、Linux 的路径识别和 CLI 入口逻辑尚未在所有真实系统组合上完成验证。请把它视为早期测试版，不要将“支持入口”理解为所有发行版/安装方式均已兼容。

## 功能

- 运行时识别 macOS、Windows、Linux。
- 默认启动 Obsidian 并使用应用当前打开的 Vault；新启动时由 Obsidian 恢复上次使用的 Vault。
- 输入 `switch` 可打开 Obsidian 官方仓库选择器；无法确认当前 Vault 时要求用户明确选择，不随机猜测。
- Vault 缺少 `.obsidian` 或 `.obsidian/plugins` 时只创建缺失的空目录；拒绝符号链接，不覆盖已有内容，初始化中途失败时尽力回滚本次创建且仍为空的目录。
- 读取插件 manifest，统计插件目录总数。
- 读取 `.obsidian/community-plugins.json`，统计启用、禁用、未知数量。
- 可选联网核对 Obsidian 官方社区插件目录。
- 可选读取插件 manifest 声明的 GitHub 仓库状态（最近推送时间、是否归档）。
- 对插件 JavaScript 做关键词静态初筛：网络通信、本地文件访问、系统命令/进程、动态代码执行、凭据/环境访问。
- 输出发现的线索与无法确认项；不把“没有命中规则”说成“安全”。
- CLI 未注册时，可尝试创建当前用户级命令入口；执行前展示双版本说明并要求输入完整的 `YES`。
- 程序先启动或聚焦 Obsidian，等待应用就绪后再执行无修改的 `obsidian help` 检查；如果 CLI 未启用，立即显示中文设置示意图并安全停止。
- 将 Obsidian Git 与 7 个推荐社区插件纳入同一张 8 项管理清单。
- 新增优质开源插件推荐库：QuickAdd、Tasks、Excalidraw、Linter、Advanced Tables、Templater、Codeblock Customizer；可按 ID 多选或选择全部。
- 安装前实时核对 Obsidian 官方社区目录、GitHub 源码仓库、SPDX 开源许可证和仓库归档状态；未通过核验的插件跳过。
- 安装与启用合并为一次批次授权：未安装的插件安装后启用，已安装但未启用的只启用，已启用的自动跳过。
- 新增独立的 GitHub Releases REST API 更新检查器：可选使用本机环境变量中的只读 Token，使用 ETag / Last-Modified 条件请求和用户级本地缓存；只通知版本变化，不自动安装或更新插件。

## 插件更新订阅检查

在仓库根目录运行：

```bash
python3 plugin_update_subscription.py
```

首次运行会为八个插件建立本地版本基线，不把当前版本误报为新更新。之后再次运行时，只报告新发布的 Release；服务器返回 HTTP 304 时复用缓存。缓存保存在当前用户的系统缓存目录，不写入 Vault 或仓库。

可选认证：如果公开 API 配额不足，可在启动订阅检查器的本机终端会话中设置 `GITHUB_TOKEN`、`GH_TOKEN` 或 `GITHUB_PAT`。建议使用仅对所需仓库授予 **Contents: Read-only** 的 Fine-grained token。Token 只用于本订阅模块访问 GitHub Releases API，不用于安装器、来源/许可证核验或写入接口；不会写入 Vault、仓库、缓存、日志或插件配置。不要把 Token 粘贴到项目配置文件或提交到 Git。

这是**按需检查的 GitHub Releases API 订阅客户端**，不是常驻后台服务，也不保证实时或不限流。可以按自己的需要手动运行，或由用户自行配置系统计划任务；本工具不会自动创建计划任务。GitHub API 仍可能限流，遇到 403/429 会停止后续请求。更新通知不代表插件已通过安全审查；安装前仍须执行原有来源、仓库和许可证核验，并由用户明确授权。

## QuickAdd 代码块快捷模板

项目附带可选的 QuickAdd Capture 模板，可将普通代码块、JSON 代码块和 Python 代码块绑定到 Obsidian 快捷键。模板与安装说明位于 [docs/quickadd-code-block-shortcuts](docs/quickadd-code-block-shortcuts/README.md)，可复用的 Markdown 模板位于 `examples/quickadd-templates/`。

建议 macOS 快捷键为 `⌘ + ⇧ + C`（普通代码块）、`⌘ + ⇧ + J`（JSON）和 `⌘ + ⇧ + P`（Python）。这些只是建议，不会自动写入或覆盖用户的快捷键配置。该功能要求用户已安装并启用 QuickAdd，并由用户手动复制模板、创建 Capture choices 和绑定快捷键。

## 环境要求

- Python 3.10 或更高版本。
- 网络核验需要联网；离线时仍可进行本地目录和静态初筛。
- Obsidian CLI 功能仍需先在 Obsidian 设置 → 常规 → 命令行界面中启用。脚本不能代替 GUI 开关。

## 运行

### macOS / Linux（推荐）

Git 克隆仓库后，启动脚本的可执行属性由 Git 保存，可以尝试直接运行：

```bash
./obsidian_manager.sh
```

如果你通过 GitHub 网页 ZIP、浏览器下载或其他不保留 Unix 权限的渠道获取文件，直接运行可能出现 `Permission denied`。此时使用下面的备用方式即可，无需修改权限：

```bash
bash ./obsidian_manager.sh
```

也可以直接运行 Python 核心：

```bash
python3 ./obsidian_manager.py
```

### Windows 10 / 11（PowerShell）

在仓库文件夹中打开 PowerShell：

```powershell
.\\obsidian_manager.ps1
```

如果系统执行策略阻止启动器，不要为了运行本工具而关闭或绕过系统策略；可直接运行 Python 核心：

```powershell
py -3 .\\obsidian_manager.py
```

也可以使用已安装的 Python：

```powershell
python .\\obsidian_manager.py
```

要求 Python 3.10 或更高版本。程序会尝试通过正在运行的 Obsidian 进程路径、Windows 软件注册表（只读）、常见安装目录，以及所有已挂载磁盘上的有限常见目录定位应用。自定义安装目录若已登记或 Obsidian 正在运行，通常也可自动识别；不会递归扫描整个硬盘。自动识别失败时，可在启动时输入安装目录或 `Obsidian.exe` 完整路径。

## 跨平台 HTTPS 证书处理

联网核验统一使用 Python HTTPS 请求层，适用于 macOS、Windows、Linux，以及常见 Conda/Python 环境：

1. 如果安装了可选的 `truststore`，优先使用操作系统可信证书库。
2. 使用 Python 默认可信证书库作为通用路径。
3. 如果前面的证书来源无法验证服务器证书，再尝试可选的 `certifi` CA 证书包。
4. 只有证书验证错误才会切换到下一个可信证书来源；普通网络错误不会被掩盖，也不会无限重试。

所有路径都强制要求证书链验证（`CERT_REQUIRED`）和主机名验证（`check_hostname=True`）。**本项目不会关闭 TLS 验证，不会接受未知证书，也不会使用不安全的 SSL 上下文。** 所有可信来源都验证失败时，联网核验立即停止，并显示证书来源、Python/OpenSSL CA 路径及修复建议；插件安装不会继续。

基础运行不强制安装额外依赖。希望增强跨平台证书兼容性的用户，可在当前 Python 环境安装可选组件：

macOS / Linux：
```bash
python3 -m pip install -r requirements-ssl.txt
```

Windows PowerShell：
```powershell
py -3 -m pip install -r requirements-ssl.txt
```

Conda 用户也可以优先通过当前环境的 Conda 更新证书组件：
```bash
conda install ca-certificates certifi openssl
```

安装可选组件不会关闭或绕过系统证书验证。若设备使用企业代理或自定义根证书，应由用户/系统管理员将合法根证书正确安装到操作系统可信证书库；不要下载来历不明的证书，也不要关闭验证。

## Vault 目录初始化

输入有效的 Vault 根目录后，程序会自动检查 `.obsidian` 和 `.obsidian/plugins`。缺失时自动创建空目录，不再逐项询问；已有目录和文件保持原样。若目标路径已存在但不是文件夹，或是符号链接（包括指向其他位置的目录链接），程序会停止并报告，不会通过链接写入 Vault 以外的位置。初始化只创建目录，不创建或覆盖配置文件、不安装或启用插件、不读取或修改笔记正文。结果同时提供「标准专业版」与「10岁儿童比喻版」说明。

## Obsidian 自动启动与 Vault 选择

程序先启动或聚焦 Obsidian。首次启动时由 Obsidian 自己恢复上次使用的 Vault；脚本不从多个 Vault 中随机挑选。默认回车使用当前活动 Vault；输入 `switch` 会打开 Obsidian 官方 `obsidian://choose-vault` 仓库选择器，用户选好后再继续。若 CLI 无法确认当前 Vault，程序要求手动输入路径并停止猜测。

**标准专业版：** GUI 启动后等待 CLI 就绪，再读取 `obsidian vault info=path`；切换通过 Obsidian 官方 URI 交给用户确认。

**10岁儿童比喻版：** 软件先打开上次的教室；想换教室就自己从教室列表里选。程序不知道是哪间教室时，会问你，不会闭着眼睛乱选。

## CLI 注册行为

程序先检查 `obsidian` 是否已在 PATH 中。若找到，会先启动或聚焦 Obsidian，等待应用就绪后再运行只读的 `obsidian help`，确认 Obsidian 应用内的 CLI 开关真正可用；如果检测到“Command line interface is not enabled”，就直接在终端显示中文设置示意图，并在询问 Vault 路径之前停止。若系统已安装可选的 `chafa`，程序会尝试把仓库内 SVG 转换为终端字符图；没有 `chafa` 或转换失败时，自动使用内置 ASCII 示意图和完整文字路径。程序会同时显示终端示意图并打开原始 SVG 图片查看器；不会自动安装任何工具。其他 CLI 检查错误也会显示原因并安全停止，不会误判为“CLI 未启用”。若 PATH 中未找到命令，程序会尝试定位可能的 Obsidian CLI 文件，并询问是否进行用户级注册。

- macOS：在 `~/.local/bin/obsidian` 创建指向应用内置 CLI 的符号链接。
- Linux：将检测到的 CLI 文件复制到 `~/.local/bin/obsidian`。
- Windows：只将 Obsidian CLI 启动器 `Obsidian.com` 复制为用户目录下的 `~/.local/bin/obsidian.com`；不会把图形界面程序 `Obsidian.exe` 冒充成 CLI。

不会自动使用 sudo、不会申请管理员权限、不会覆盖已有同名目标，也不会自动修改 PATH。若目录不在 PATH 中，程序只给出人工配置指引。Windows 用户需在“环境变量 → 用户变量 → Path”中自行添加该目录。Windows CLI 仅识别 `Obsidian.com`；如果安装目录中没有该文件，程序会停止，不会复制 `Obsidian.exe` 代替。

**重要：** 仅创建命令入口不代表 CLI 已成功启用。必须先在 Obsidian 设置中打开官方 CLI 开关。不同安装渠道、版本和系统发行版可能有不同布局；无法识别时程序会停止，不会下载或替换二进制文件。

### CLI 注册说明（强制双版本）

**标准专业版：** 注册会在当前用户目录创建一个命令入口；macOS 使用符号链接，Linux/Windows 复制检测到的 CLI 文件。只需当前用户目录写入权限，不调用管理员权限。若目标已存在则停止，不覆盖。此动作不修改 Vault、笔记或插件。若 PATH 未包含目标目录，需用户自行配置；恢复时删除本次创建的入口即可。

**10岁儿童比喻版：** 就像在自己的书桌抽屉里放一个 Obsidian 快捷按钮。只整理自己的抽屉，不进管理员办公室，也不碰你的笔记。如果抽屉里已经有同名按钮，就停下来不覆盖。抽屉不在电脑寻找按钮的路线里时，还要由你自己把它加入路线。

## 社区插件统一安装与启用

程序将 Obsidian Git 与 7 个推荐插件放在同一张清单中，共 8 个插件。每次运行先检查所选 Vault 中的安装状态（插件目录内的 `manifest.json`）和启用状态（`.obsidian/community-plugins.json`）。

| 插件 | ID | 用途 | 特别风险 |
|---|---|---|---|
| Obsidian Git | `obsidian-git` | Git 版本管理、提交与同步 | 自动提交/同步前应理解远程仓库和凭据设置 |
| QuickAdd | `quickadd` | 快速捕捉、模板与自动化工作流 | 可配置自动化与脚本 |
| Tasks | `obsidian-tasks-plugin` | 待办、截止日期、重复任务 | 读取并处理 Vault 中的任务标记 |
| Excalidraw | `obsidian-excalidraw-plugin` | 绘图、关系图和白板 | 会在 Vault 中创建和修改绘图文件 |
| Linter | `obsidian-linter` | Markdown 格式整理 | 规则可能批量修改笔记，先备份 |
| Advanced Tables | `table-editor-obsidian` | Markdown 表格编辑 | 仍属实验性，可能有数据丢失缺陷，先备份 |
| Templater | `templater-obsidian` | 动态模板 | 高风险：可执行 JavaScript 和系统命令 |
| Codeblock Customizer | `codeblock-customizer` | 增强代码块显示与自定义样式 | 可修改代码块的显示方式；安装前核对来源与许可证 |

### 统一操作规则

1. 未安装、未启用：一次授权后先安装，再启用。
2. 已安装、未启用：一次授权后只启用，不重复安装。
3. 已安装、已启用：自动跳过，不重复操作。
4. 启用状态文件格式异常，或启用列表与插件文件不一致：停止操作，不猜测状态。
5. 安装或启用失败、状态无法验证：停止后续批量操作，并如实报告；不把 CLI 返回成功直接当作最终成功。
6. 每次批次只展示一次完整的双版本说明并询问一次授权。拒绝或回车取消时，不执行该批次任何安装/启用操作。

**标准专业版：** 用户确认前，程序会列出每个插件本次将执行的具体动作、Vault 路径、权限、写入位置和风险。授权后以当前用户权限执行 Obsidian CLI，不使用 sudo 或管理员权限。安装后验证 manifest，启用后验证 `community-plugins.json`。本流程不卸载、不更新插件，也不修改笔记正文。

**10岁儿童比喻版：** 先看看工具箱：没有的工具先放进去，再打开开关；已经放进去但没打开的，只打开开关；已经打开的就不碰。程序先把这次要做的事全部告诉你，你同意一次才开始。中途出错就停下来告诉你，不会假装已经完成。

### 选择插件与高风险保护

- 输入序号或逗号分隔的序号，可以选择部分插件。
- 输入 `all` 会选择普通插件，并自动排除高风险的 Templater。
- 如果确实需要 Templater，必须单独输入它对应的序号；程序仍会在同一次批次授权说明中突出显示它可执行 JavaScript 和系统命令的风险。
- 选择全部时，已安装且已启用的插件仍会显示为“跳过”，不会重复安装或启用。
- 安装前仍会核验 Obsidian 官方社区目录中的插件 ID、仓库来源、GitHub SPDX 开源许可证和仓库归档状态；核验失败的插件会跳过。
- CLI 需要 Obsidian 正在运行，并且已在设置中启用、注册。安装社区插件还需 Obsidian 允许社区插件（Restricted Mode 可能需要由用户在设置中关闭）。程序不会自动更改这些安全设置。
- CLI 在所选 Vault 目录作为工作目录运行，避免误操作其他 Vault。

## 全面审查的边界

- 官方社区目录匹配只说明找到相同插件 ID，不代表官方安全认证。
- GitHub 最近推送时间不是维护质量或安全性的保证。
- 静态关键词检查按稳定路径顺序处理 JavaScript 文件，默认最多扫描 500 个文件、单文件 2 MB、总读取 50 MB；达到上限或读取失败会报告跳过数量。部分扫描不能证明没有风险。
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


## 参与社区建设

欢迎所有人参与本项目：报告问题、测试不同平台、改善文档、翻译或提交代码都很有价值。普通贡献者无需仓库写入权限，可通过 Fork 和 Pull Request 提交修改。项目采用模块分工、核心审核、贡献者名单与积分认可制度。详情请阅读 [贡献指南](CONTRIBUTING.md)、[项目治理](GOVERNANCE.md) 和 [贡献者名单](CONTRIBUTORS.md)。
