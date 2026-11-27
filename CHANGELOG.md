# Changelog

## [Unreleased]

### Added
- 将 PDF++（`pdf-plus`）加入社区插件安装/启用目录与 GitHub Releases 更新订阅；记录其 MIT 上游仓库、Obsidian 最低版本要求及私有 API/实验性 PDF 编辑风险。

### Changed
- 版本更新至 0.6.6。
- 版本更新至 0.6.5。

### Added
- 新增 QuickAdd 代码块快捷键安装流程：通过官方 package-import 新增三个无脚本 Capture choices，使用 Obsidian CLI 检查默认与自定义快捷键冲突，备份原配置；完全退出 Obsidian 后才写入 `hotkeys.json`，完成后重新启动，不覆盖已有 QuickAdd choices。
- 新增可选的纯 Markdown 模板库，覆盖日常笔记、会议、研究文献、交易复盘与 AI Agent 任务/知识来源。
- 新增模板目录、上游来源/许可证记录及依赖与安全边界说明；只引用上游项目，不复制其模板正文或资源。

### Added
- 新增独立的 GitHub Releases Atom Feed 更新检查器，支持 ETag / Last-Modified 条件请求、本地缓存和新版本通知；仅检查与通知，不自动安装或更新插件。
- 首次运行建立订阅基线；缓存保存在当前用户缓存目录，不读取 Vault；遇到 GitHub 403/429 时停止后续请求，避免持续请求。

### Changed
- 版本更新至 0.6.3。

### Fixed
- 启用插件后轮询等待 `community-plugins.json` 落盘，避免 CLI 已成功但文件尚未写入时误报失败并中断后续批量安装。
- HTTPS 读取官方目录/仓库状态时，对 `IncompleteRead` 与超时等瞬时网络错误自动重试，并将联网超时从 8 秒提高到 30 秒。
- 版本更新至 0.6.2。
- 修复 CLI 在 Obsidian 尚未启动时提前检查导致的连接失败：先启动/聚焦应用，再等待 CLI 就绪。
- 默认读取 Obsidian 当前活动 Vault（新启动时恢复上次使用的 Vault）；支持通过 `switch` 打开官方仓库选择器，无法确认时不随机选择。
- 移植 PR #3 的安装目录与 CLI 来源验证、插件扫描预算、异常 manifest/启用列表处理及 Vault 初始化失败回滚。
- 版本更新至 0.6.1。

### Changed
- 版本更新至 0.6.0。
- 将 Obsidian Git 与 6 个推荐插件整合为统一的 7 项社区插件管理清单。
- 安装与启用合并为一次批次授权：未安装插件安装后自动启用，已安装未启用插件只启用，已启用插件跳过。
- 安装后核验 manifest，启用后核验 community-plugins.json；状态不一致或操作无法验证时安全停止。
- 输入 all 自动排除高风险 Templater；用户仍可通过单独选择明确将其纳入批次。

### Security
- 每个批次只展示一次完整双版本说明并征求一次明确授权；拒绝或取消时不执行该批次操作。
- 不自动卸载、更新插件，不使用 sudo/管理员权限，不修改笔记正文。
- CLI 命令失败或状态无法验证时停止后续批量操作，不报告虚假成功。



### Changed
- CLI 未启用时，同时在终端显示示意图并打开原始中文 SVG 图片；终端优先尝试使用用户已安装的 `chafa` 渲染，失败或未安装时回退到内置 ASCII 示意图。
- 保留原始中文 SVG，不新增必需依赖，不自动安装终端图像工具。
- 版本更新至 0.5.9。

### Added
- 程序启动时自动执行无修改的 `obsidian help` 可用性检查；若 CLI 未启用，立即显示中文文字教程并自动打开中文设置位置示意图。
- CLI 启动检查失败或超时时，在询问 Vault 路径、初始化目录、扫描插件及联网核验之前安全停止。
- 当 Obsidian CLI 明确返回“Command line interface is not enabled”时，识别具体原因并提供“设置 → 通用 → 高级 → 命令行界面”的中英文引导。
- 新增可选打开的 CLI 设置位置示意图；图片缺失时保留完整文字指引。
- CLI 未启用时立即停止当前批量安装/启用流程，避免继续操作或误判安装成功。
- 新增 CLI 错误识别单元测试。

### Changed
- 版本更新至 0.5.8；CLI 设置示意图在检测到未启用时自动打开，不再要求用户额外确认是否查看。
- Vault 初始化自动补齐缺失的 `.obsidian` 与 `.obsidian/plugins` 空目录；已有内容保持不变，遇到非目录路径或符号链接时安全停止。
- 插件盘点自动执行官方社区目录与 manifest 声明 GitHub 仓库的只读核验；不上传 Vault 或笔记内容，核验失败明确标记为无法确认。
- （旧流程记录）Obsidian Git 曾采用安装、启用分开确认；0.6.0 起已统一为一次批次授权。

### Security
- 自动初始化只创建缺失的基础目录，不覆盖或删除已有内容；拒绝符号链接，避免通过链接写入 Vault 以外的位置。
- 在线核验只发起只读请求，不上传 Vault 或笔记正文；目录匹配和仓库状态不构成安全认证。

### Added
- 建立社区治理制度：开放 Issue/Pull Request 贡献、模块分工、核心审核与主分支保护建议。
- 增加贡献者名单、积分等级及维护者晋升规则；明确积分不自动授予仓库权限。
- 增加 GitHub Issue 与 Pull Request 模板，降低普通用户参与门槛。

## [0.5.5] - 2026-11-11

### Added
- 新增统一的跨平台 HTTPS 证书处理层，联网核验统一使用安全 TLS 上下文。
- 优先使用可选 truststore 的操作系统可信证书库，其次使用 Python 默认证书库，证书验证失败时再尝试可选 certifi CA 证书包。
- 增加证书来源失败诊断、CA 路径信息和 macOS/Windows/Linux/Conda 修复指引。
- 新增 SSL 单元测试，覆盖证书链/主机名验证、可信来源回退、普通网络错误不重试，以及拒绝不安全上下文。

### Security
- 所有 HTTPS 连接强制 CERT_REQUIRED 与主机名验证。
- 禁止关闭 SSL 验证；所有可信证书来源均验证失败时停止联网核验，不继续安装。
- truststore 与 certifi 为可选依赖，不影响离线本地盘点功能。


## [0.5.4] - 2026-11-11

### Added
- 输入有效 Vault 路径后，若缺少 `.obsidian` 配置目录或 `plugins` 子目录，分别向用户说明并要求完整输入 `YES` 后才创建空目录。
- 拒绝创建任一必需目录时，跳过插件盘点、安装与启用流程，避免后续操作绕过用户拒绝。
- 新增 Vault 初始化单元测试，覆盖同意、拒绝、已有目录保护和无效 Vault 路径。


## [0.5.3] - 2026-11-11

### Windows discovery
- 自动识别增加读取正在运行的 Obsidian 进程路径及 Windows 卸载/App Paths 注册表信息（只读）。
- 验证候选目录必须实际包含 `Obsidian.exe`，避免把普通目录误认为应用目录。
- 自动识别失败时，允许用户输入自定义安装目录或 `Obsidian.exe` 完整路径；不扫描整个硬盘。
- 增加自定义路径与手动路径测试。


## [0.5.2] - 2026-11-11

### Windows discovery
- 在所有已挂载 Windows 磁盘上检查有限的常见 Obsidian 安装目录，包括 D:、E: 等非系统盘。
- 使用 Windows 逻辑磁盘列表枚举盘符；不递归扫描整个硬盘。
- 增加非 C 盘安装路径回归测试。


## [0.5.1] - 2026-11-11

### Windows compatibility
- 修正常见 Windows 用户级安装目录识别：增加 `%LOCALAPPDATA%\\Programs\\Obsidian`。
- Windows CLI 只识别 `Obsidian.com`，不再错误地将图形界面 `Obsidian.exe` 作为命令行工具候选。
- Windows CLI 注册时不再对复制文件执行 Unix 权限位设置。
- Obsidian CLI 子进程输出固定按 UTF-8 解码，降低 Windows 中文终端乱码/解码失败风险。
- 支持直接粘贴带外围引号的 Vault 路径；启动时检查 Python 3.10 最低版本。
- 新增 Windows 安装路径和 CLI 候选回归测试；CI 已配置 Windows runner。

### Documentation
- Windows 启动说明不再推荐 `ExecutionPolicy Bypass`，优先使用 PowerShell 启动器，受策略阻止时可直接运行 Python 核心。


## [0.5.0] - 2026-11-10

### Added
- 新增优质开源 Obsidian 社区插件推荐库：QuickAdd、Tasks、Excalidraw、Linter、Advanced Tables、Templater。
- 支持按插件 ID 多选或选择全部，逐个通过 Obsidian 官方 CLI 安装。
- 安装前核验官方社区目录 ID、仓库来源、GitHub SPDX 开源许可证和归档状态。
- 在推荐文档中列出本次核对的各插件许可证，并强化 Advanced Tables 的实验性/数据丢失风险提示。
- 新插件只安装不自动启用；安装后逐个核验 manifest。

### Safety
- 批量安装前统一展示标准专业版与10岁儿童比喻版说明，并要求完整确认词 INSTALL。
- 未知许可证、仓库不匹配、归档或核验失败时跳过安装。
- 明确标记 Templater 可执行任意 JavaScript 和系统命令的高风险能力。
- `all` 批量安装默认排除 Templater；必须单独输入插件 ID 才会选择。
- 安装不等于启用；不自动启用、更新或卸载插件。

## [0.4.3] - 2026-11-10

### Added
- 增加通过 Obsidian 官方 CLI 安装 Obsidian Git（`obsidian-git`）的可选流程。
- 安装与启用分开确认；安装后核验目标 Vault 的插件 manifest，默认不自动启用。
- 对目标 Vault 使用 CLI 工作目录定位，避免误操作其他活动 Vault。

### Safety
- CLI 安装要求输入 `INSTALL`；启用另行要求输入 `ENABLE`。
- 不使用管理员权限，不自动卸载、更新或启用插件。


## [0.4.2] - 2026-11-10

### Fixed
- 在 Git 仓库中将 macOS/Linux 启动脚本 `obsidian_manager.sh` 记录为可执行文件模式 `100755`，Git 克隆后可直接运行（前提是目标文件系统支持 Unix 执行权限）。
- 保留 GitHub ZIP、浏览器下载等不保留执行位时的 `bash ./obsidian_manager.sh` 备用方式。
- 更新发布与贡献规范，要求持续检查 Git 文件模式，避免后续提交丢失可执行属性。

## [0.4.1] - 2026-11-10

### Fixed
- 修正 macOS/Linux 启动说明：推荐使用 `bash ./obsidian_manager.sh`，不再要求下载者运行 `chmod +x`。
- 明确解释 GitHub ZIP 等下载方式可能不保留 Unix 可执行位，避免直接执行时出现 `Permission denied`。
- 将“下载即运行”定义为无需手动修改文件权限；首次启动仍需通过 Bash、Python 或其他明确启动器调用。

### Documentation
- 在 README、SECURITY、CONTRIBUTING 中加入无需 chmod 的启动规范。
- 明确 Bash 显式启动不会修改文件权限、不会提升权限，也不会改变系统设置。

## [0.4.0] - 2026-11-10

### Added
- 新增 Python 跨平台核心及 Windows PowerShell 启动入口。
- 新增插件总数、启用/禁用/未知状态统计。
- 新增可选的 Obsidian 官方社区插件目录核对。
- 新增可选 GitHub 仓库维护状态查询。
- 新增 JavaScript 静态关键词初筛，覆盖网络、文件、系统命令、动态执行和凭据访问线索。
- 新增用户级 CLI 注册尝试，并强制双版本说明及完整确认词。

### Safety
- CLI 注册不使用管理员权限、不覆盖已有目标、不自动修改 PATH。
- 网络核验只读取官方目录及插件 manifest 声明的 GitHub API。
- 不读取笔记正文、不执行插件代码。
- 报告明确区分发现线索、未命中规则和无法确认。
- macOS、Windows、Linux 首轮支持仍需真实系统矩阵验证，不夸大兼容性。

## [0.3.0] - 2026-11-10
- 新增强制安全规范、贡献指南及 GPL-3.0-only 许可证。
- 增加 CLI 运行检查和 Vault 插件目录清单。
- 明确默认只读及双版本说明规则。

## [0.2.0]
- 初始 Obsidian 环境检查脚本。
