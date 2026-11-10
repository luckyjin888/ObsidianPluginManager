# Changelog

## [0.5.0] - 2026-11-10

### Added
- 新增优质开源 Obsidian 社区插件推荐库：QuickAdd、Tasks、Excalidraw、Linter、Advanced Tables、Templater。
- 支持按插件 ID 多选或选择全部，逐个通过 Obsidian 官方 CLI 安装。
- 安装前核验官方社区目录 ID、仓库来源、GitHub SPDX 开源许可证和归档状态。
- 新插件只安装不自动启用；安装后逐个核验 manifest。

### Safety
- 批量安装前统一展示标准专业版与10岁儿童比喻版说明，并要求完整确认词 INSTALL。
- 未知许可证、仓库不匹配、归档或核验失败时跳过安装。
- 明确标记 Templater 可执行任意 JavaScript 和系统命令的高风险能力。
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
