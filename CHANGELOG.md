# Changelog

本文件记录项目中重要且面向用户的变化。

## [0.3.0] - 2026-11-10

### Added
- 新增强制安全规范 SECURITY.md。
- 新增贡献指南 CONTRIBUTING.md。
- 新增 GPL-3.0-only 许可证。
- 新增可选的 Obsidian CLI 版本运行检查。

### Changed
- Vault 路径继续由用户运行时输入，不再写死个人路径。
- CLI 检查区分版本号、内置可执行文件、PATH 注册和实际运行检查。
- 对可能启动 Obsidian 的 CLI 版本查询，先向用户说明并征求确认。
- 插件目录扫描明确提示：目录存在不等于插件已启用或安全。

### Safety
- 不自动安装、卸载、启用、禁用或修改插件。
- 不自动创建系统链接、不修改 PATH、不调用 sudo。
- 当前版本明确限定为 macOS。

## [0.2.0]

- 初始 Obsidian 环境检查脚本。
- 检查 macOS、Obsidian 安装位置、版本和 CLI 文件。
- 由用户输入 Vault 路径。
- 列出社区插件目录。
